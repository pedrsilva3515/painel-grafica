"""
Painel Gráfica — entry point.

Boot sequence:
  1. QApplication.
  2. Stylesheet.
  3. SQLite init.
  4. Authentication.
  5. System-tray icon.
  6. Main window (hidden).
  7. Command Palette (hidden).
  8. Settings dialog (hidden, shown on demand).
  9. Deadline monitor (30-min QTimer).
 10. File indexer (background, 15-min refresh).
 11. CDR watcher (QFileSystemWatcher).
 12. Daily panel scheduler (fires at configured time).
 13. Global hotkey.
 14. Event loop.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox

from core.auth import SetPasswordDialog, run_auth
from core.tray import TrayManager
from core.startup import toggle_startup
from core.notifications import is_enabled as _notif_on
from data.db import init_db

SETTINGS_FILE = ROOT / "config" / "settings.json"


def _load_settings() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_stylesheet(app: QApplication) -> None:
    qss = ROOT / "ui" / "styles" / "theme.qss"
    if qss.exists():
        app.setStyleSheet(qss.read_text(encoding="utf-8"))


# ── File indexer ──────────────────────────────────────────────────────────────

_indexer_timer:  QTimer | None = None
_indexer_worker = None


def _run_indexer(tray: TrayManager) -> None:
    global _indexer_worker
    folders = _load_settings().get("monitored_folders", [])
    if not folders:
        return
    from modules.command_palette.actions.file_search import FileIndexWorker
    _indexer_worker = FileIndexWorker(folders)
    _indexer_worker.finished.connect(
        lambda n: tray.show_notification("Índice atualizado", f"{n} arquivos indexados.")
        if n > 0 and _notif_on("indice_atualizado") else None
    )
    _indexer_worker.start()


def _start_indexer(tray: TrayManager) -> None:
    global _indexer_timer
    _run_indexer(tray)
    _indexer_timer = QTimer()
    _indexer_timer.timeout.connect(lambda: _run_indexer(tray))
    _indexer_timer.start(15 * 60 * 1_000)


# ── Hotkey ────────────────────────────────────────────────────────────────────

def _setup_hotkey(tray: TrayManager):
    try:
        from core.hotkey import HotkeyManager
        hk = HotkeyManager()
        hk.triggered.connect(tray.open_palette_requested)
        hk.start()
        return hk
    except ImportError:
        tray.show_notification(
            "Painel Gráfica",
            "Biblioteca 'keyboard' não instalada — hotkey global desativado.",
        )
        return None


# ── Handlers ──────────────────────────────────────────────────────────────────

def _on_change_password(tray: TrayManager) -> None:
    dlg = SetPasswordDialog()
    if dlg.exec() == SetPasswordDialog.DialogCode.Accepted:
        tray.show_notification("Painel Gráfica", "Senha alterada com sucesso.")


def _on_toggle_startup(tray: TrayManager) -> None:
    enabled = toggle_startup()
    tray.show_notification(
        "Painel Gráfica",
        f"Início com Windows {'ativado' if enabled else 'desativado'}.",
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Painel Gráfica")
    app.setOrganizationName("PainelGrafica")
    app.setQuitOnLastWindowClosed(False)

    _load_stylesheet(app)

    try:
        init_db()
    except Exception as exc:
        QMessageBox.critical(None, "Erro ao inicializar banco", str(exc))
        sys.exit(1)

    if not run_auth():
        sys.exit(0)

    # ── Tray ──────────────────────────────────────────────────────────────────
    tray = TrayManager(app)
    tray.quit_requested.connect(app.quit)
    tray.change_password_requested.connect(lambda: _on_change_password(tray))
    tray.toggle_startup_requested.connect(lambda: _on_toggle_startup(tray))

    # ── Main window ───────────────────────────────────────────────────────────
    from ui.main_window import MainWindow
    main_win = MainWindow()

    tray.open_kanban_requested.connect(main_win.show_kanban_tab)
    tray.open_deadlines_requested.connect(main_win.show_deadlines_tab)

    # ── Settings dialog ───────────────────────────────────────────────────────
    from ui.settings_dialog import SettingsDialog
    settings_dlg = SettingsDialog()

    def _on_settings_saved():
        # Reload stylesheet (theme might not change but keeps it consistent)
        _load_stylesheet(app)
        # Restart file indexer with possibly new folders
        _run_indexer(tray)
        # Update CDR watcher
        cdr_watcher.set_folder(_load_settings().get("cdr_watch_folder", ""))
        if _notif_on("configuracoes_salvas"):
            tray.show_notification("Configurações salvas", "As alterações foram aplicadas.")

    settings_dlg.saved.connect(_on_settings_saved)

    def _open_settings():
        # Re-create to pick up latest saved values
        nonlocal settings_dlg
        settings_dlg = SettingsDialog()
        settings_dlg.saved.connect(_on_settings_saved)
        settings_dlg.show()
        settings_dlg.raise_()
        settings_dlg.activateWindow()

    tray.open_settings_requested.connect(_open_settings)

    # ── Command palette ───────────────────────────────────────────────────────
    from modules.command_palette.palette import CommandPalette
    palette = CommandPalette()

    def _toggle_palette():
        if palette.isVisible():
            palette.close_palette()
        else:
            palette.show_palette()

    tray.open_palette_requested.connect(_toggle_palette)

    # Palette actions → same handlers as tray
    def _on_palette_action(action_id: str):
        dispatch = {
            "kanban":  main_win.show_kanban_tab,
            "prazos":  main_win.show_deadlines_tab,
            "painel":  _open_daily_panel,
            "config":  _open_settings,
            "senha":   lambda: _on_change_password(tray),
            "sair":    app.quit,
        }
        fn = dispatch.get(action_id)
        if fn:
            fn()

    palette.action_triggered.connect(_on_palette_action)

    # ── Deadline monitor ──────────────────────────────────────────────────────
    from modules.deadlines.monitor import DeadlineMonitor
    deadline_monitor = DeadlineMonitor()
    deadline_monitor.status_changed.connect(tray.set_status)
    deadline_monitor.alert_triggered.connect(
        lambda title, msg, crit=False: tray.show_notification(title, msg, crit)
        if _notif_on("prazos_criticos") else None
    )
    deadline_monitor.scan()

    # ── Daily panel ───────────────────────────────────────────────────────────
    from modules.daily_panel.scheduler import DailyPanelScheduler
    from ui.daily_panel_widget import DailyPanelWindow

    daily_scheduler = DailyPanelScheduler()
    _snooze_timer   = QTimer()
    _snooze_timer.setSingleShot(True)

    def _open_daily_panel():
        dlg = DailyPanelWindow()
        dlg.snooze_requested.connect(lambda: _snooze_timer.start(60 * 60 * 1_000))
        _snooze_timer.timeout.connect(_open_daily_panel)
        dlg.show()

    daily_scheduler.trigger.connect(_open_daily_panel)
    tray.open_daily_panel_requested.connect(_open_daily_panel)

    # ── CDR watcher ───────────────────────────────────────────────────────────
    from modules.kanban.cdr_watcher import CdrWatcher
    cdr_watcher = CdrWatcher()

    cdr_folder = _load_settings().get("cdr_watch_folder", "")
    if cdr_folder:
        cdr_watcher.set_folder(cdr_folder)

    def _on_cdr_order_created(title: str, order_id: int):
        if _notif_on("cdr_nova_os"):
            tray.show_notification(
                "Nova O.S. criada automaticamente",
                f'"{title}" adicionada no Kanban.',
            )
        # Refresh kanban if it's open
        if main_win.isVisible():
            main_win.centralWidget().widget(0).refresh()

    cdr_watcher.order_created.connect(_on_cdr_order_created)

    def _on_cdr_order_renamed(old_title: str, new_title: str, _order_id: int):
        if _notif_on("cdr_os_renomeada"):
            tray.show_notification(
                "O.S. renomeada automaticamente",
                f'"{old_title}" → "{new_title}" atualizado no Kanban.',
            )
        if main_win.isVisible():
            main_win.centralWidget().widget(0).refresh()

    cdr_watcher.order_renamed.connect(_on_cdr_order_renamed)

    # ── Reminder manager ──────────────────────────────────────────────────────
    from modules.reminders.manager import ReminderManager
    reminder_manager = ReminderManager()
    reminder_manager.reminder_triggered.connect(
        lambda title, msg: tray.show_notification(title, msg)
        if _notif_on("lembretes") else None
    )

    # ── File indexer ──────────────────────────────────────────────────────────
    _start_indexer(tray)

    # ── Hotkey ────────────────────────────────────────────────────────────────
    hotkey_manager = _setup_hotkey(tray)
    if hotkey_manager:
        app.aboutToQuit.connect(hotkey_manager.stop)

    if _notif_on("app_pronto"):
        tray.show_notification(
            "Painel Gráfica",
            "Pronto. Use Ctrl+Space para o Command Palette.",
        )

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
