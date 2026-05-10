from PyQt6.QtCore import QObject, pyqtSignal, Qt
from PyQt6.QtGui import QIcon, QColor, QPixmap, QPainter, QFont
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon


_STATUS_COLORS = {
    "ok":       "#a6e3a1",   # green
    "warning":  "#f9e2af",   # yellow
    "critical": "#f38ba8",   # red
}


def _make_tray_icon(status: str = "ok") -> QIcon:
    color = _STATUS_COLORS.get(status, _STATUS_COLORS["ok"])
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Filled circle
    painter.setBrush(QColor(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(2, 2, 28, 28)

    # "G" letter
    font = QFont("Segoe UI", 13, QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(QColor("#1e1e2e"))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "G")

    painter.end()
    return QIcon(pixmap)


class TrayManager(QObject):
    """
    Manages the Windows system-tray icon and its context menu.

    Signals are emitted for each menu action so that main.py can wire them
    to the appropriate module without this class knowing about the UI.
    """

    open_palette_requested    = pyqtSignal()
    open_kanban_requested     = pyqtSignal()
    open_deadlines_requested  = pyqtSignal()
    open_daily_panel_requested = pyqtSignal()
    open_settings_requested   = pyqtSignal()
    change_password_requested = pyqtSignal()
    toggle_startup_requested  = pyqtSignal()
    quit_requested            = pyqtSignal()

    def __init__(self, app: QApplication, parent=None):
        super().__init__(parent)
        self._app = app
        self._status = "ok"

        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(_make_tray_icon("ok"))
        self._tray.setToolTip("Painel Gráfica")
        self._tray.activated.connect(self._on_activated)

        self._build_menu()
        self._tray.show()

    # ── Menu ──────────────────────────────────────────────────────────────────

    def _build_menu(self):
        menu = QMenu()

        header = menu.addAction("Painel Gráfica")
        header.setEnabled(False)
        menu.addSeparator()

        menu.addAction(
            "Abrir Command Palette\t Ctrl+Space",
            self.open_palette_requested,
        )
        menu.addAction("Kanban de Pedidos",   self.open_kanban_requested)
        menu.addAction("Monitor de Prazos",   self.open_deadlines_requested)
        menu.addAction("Painel do Dia",       self.open_daily_panel_requested)

        menu.addSeparator()
        menu.addAction("Configurações",       self.open_settings_requested)
        menu.addAction("Trocar Senha",        self.change_password_requested)
        menu.addAction("Iniciar com Windows", self.toggle_startup_requested)

        menu.addSeparator()
        menu.addAction("Sair",                self.quit_requested)

        self._tray.setContextMenu(menu)

    # ── Slots ──────────────────────────────────────────────────────────────────

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.open_palette_requested.emit()

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_status(self, status: str) -> None:
        """
        Update the tray icon colour to reflect the current alert level.
        status: "ok" | "warning" | "critical"
        """
        if status == self._status:
            return
        self._status = status
        self._tray.setIcon(_make_tray_icon(status))
        self._tray.setToolTip(
            {
                "ok":       "Painel Gráfica — Tudo em ordem",
                "warning":  "Painel Gráfica — Atenção: prazos próximos",
                "critical": "Painel Gráfica — CRÍTICO: prazos vencidos",
            }.get(status, "Painel Gráfica")
        )

    def show_notification(
        self,
        title: str,
        message: str,
        critical: bool = False,
        duration_ms: int = 5000,
    ) -> None:
        icon = (
            QSystemTrayIcon.MessageIcon.Critical
            if critical
            else QSystemTrayIcon.MessageIcon.Information
        )
        self._tray.showMessage(title, message, icon, duration_ms)

    def hide(self) -> None:
        self._tray.hide()
