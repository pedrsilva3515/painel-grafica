import ctypes
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QEvent, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QWidget,
)

from modules.command_palette.actions.file_search import search_files
from modules.command_palette.actions.app_search import search_apps
from modules.command_palette.actions.calculator import calculate, list_templates
from modules.command_palette.actions.client_search import search_clients, copy_whatsapp
from modules.command_palette.actions.mubisys import open_os
from modules.reminders.manager import add_reminder, parse_reminder
from modules.preview.renderer import ThumbnailWorker

_GWL_EXSTYLE      = -20
_WS_EX_TOOLWINDOW = 0x00000080

SETTINGS_FILE = Path(__file__).parent.parent.parent / "config" / "settings.json"

_ACTIONS = [
    {"id": "kanban", "label": "📋  Kanban de Pedidos",  "desc": "Abrir o quadro de pedidos"},
    {"id": "prazos", "label": "⏰  Monitor de Prazos",  "desc": "Ver prazos e alertas"},
    {"id": "painel", "label": "📅  Painel do Dia",      "desc": "Resumo matinal consolidado"},
    {"id": "config", "label": "⚙️   Configurações",      "desc": "Pastas monitoradas, hotkey, preferências"},
    {"id": "senha",  "label": "🔒  Trocar Senha",       "desc": "Alterar senha de acesso"},
    {"id": "sair",   "label": "🚪  Sair",               "desc": "Encerrar o Painel Gráfica"},
]


def _load_settings() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _fmt_size(size_bytes: int) -> str:
    if size_bytes >= 1_048_576:
        return f"{size_bytes / 1_048_576:.1f} MB"
    if size_bytes >= 1_024:
        return f"{size_bytes // 1_024} KB"
    return f"{size_bytes} B"


class CommandPalette(QWidget):
    closed           = pyqtSignal()
    action_triggered = pyqtSignal(str)

    _W, _H = 800, 460

    def __init__(self, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(150)
        self._debounce.timeout.connect(self._do_search)

        self._focus_timer = QTimer(self)
        self._focus_timer.setInterval(50)
        self._focus_timer.timeout.connect(self._check_focus)

        self._thumb_worker: ThumbnailWorker | None = None
        self._settings: dict = {}

        self._build_ui()
        self._reposition()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        container = QFrame()
        container.setObjectName("paletteContainer")
        root.addWidget(container)

        layout = QVBoxLayout(container)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        sr = QHBoxLayout()
        sr.setContentsMargins(16, 12, 16, 12)
        sr.setSpacing(10)
        lupe = QLabel("🔍")
        lupe.setObjectName("paletteIcon")
        sr.addWidget(lupe)
        self._search = QLineEdit()
        self._search.setObjectName("paletteSearch")
        self._search.setPlaceholderText(
            "Buscar arquivo ou app · @cliente · =cálculo · os:1042 · !lembrete 14h"
        )
        self._search.textChanged.connect(self._debounce.start)
        self._search.installEventFilter(self)
        sr.addWidget(self._search)
        layout.addLayout(sr)

        sep = QFrame()
        sep.setObjectName("paletteSeparator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        body = QHBoxLayout()
        body.setSpacing(0)
        body.setContentsMargins(0, 0, 0, 0)

        self._results = QListWidget()
        self._results.setObjectName("paletteResults")
        self._results.currentItemChanged.connect(self._on_selection_changed)
        self._results.itemActivated.connect(self._on_item_activated)
        body.addWidget(self._results, 3)

        vsep = QFrame()
        vsep.setObjectName("paletteSeparator")
        vsep.setFrameShape(QFrame.Shape.VLine)
        body.addWidget(vsep)

        preview = QFrame()
        preview.setObjectName("palettePreview")
        preview.setFixedWidth(210)
        pl = QVBoxLayout(preview)
        pl.setContentsMargins(12, 12, 12, 12)
        pl.setSpacing(8)
        self._thumb_label = QLabel()
        self._thumb_label.setObjectName("previewThumb")
        self._thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb_label.setMinimumHeight(160)
        pl.addWidget(self._thumb_label)
        self._preview_name = QLabel()
        self._preview_name.setObjectName("previewName")
        self._preview_name.setWordWrap(True)
        pl.addWidget(self._preview_name)
        self._preview_meta = QLabel()
        self._preview_meta.setObjectName("previewMeta")
        self._preview_meta.setWordWrap(True)
        pl.addWidget(self._preview_meta)
        pl.addStretch()
        body.addWidget(preview)

        layout.addLayout(body)

        status = QLabel("↑↓ navegar · Enter confirmar · Ctrl+Enter abrir pasta · Esc fechar")
        status.setObjectName("paletteStatus")
        status.setContentsMargins(16, 5, 16, 7)
        layout.addWidget(status)

    def _reposition(self):
        self.setFixedSize(self._W, self._H)
        scr = QApplication.primaryScreen().geometry()
        self.move(scr.center().x() - self._W // 2,
                  scr.center().y() - self._H // 2 - 60)

    # ── Show / hide ───────────────────────────────────────────────────────────

    def _hide_from_taskbar(self):
        try:
            hwnd  = int(self.winId())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, _GWL_EXSTYLE, style | _WS_EX_TOOLWINDOW)
        except Exception:
            pass

    def _force_foreground(self):
        try:
            hwnd      = int(self.winId())
            u32       = ctypes.windll.user32
            fg_hwnd   = u32.GetForegroundWindow()
            fg_thread = u32.GetWindowThreadProcessId(fg_hwnd, None)
            my_thread = ctypes.windll.kernel32.GetCurrentThreadId()
            if fg_thread and fg_thread != my_thread:
                u32.AttachThreadInput(fg_thread, my_thread, True)
                u32.SetForegroundWindow(hwnd)
                u32.AttachThreadInput(fg_thread, my_thread, False)
            else:
                u32.SetForegroundWindow(hwnd)
        except Exception:
            pass

    def _check_focus(self):
        if not self.isActiveWindow():
            self.close_palette()

    def _start_focus_watch(self):
        if self.isVisible():
            self._focus_timer.start()

    def show_palette(self):
        self._focus_timer.stop()
        self._settings = _load_settings()
        self._search.clear()
        self._results.clear()
        self._clear_preview()
        self._populate_actions("")
        self._reposition()
        self.show()
        self._hide_from_taskbar()
        self._force_foreground()
        self.raise_()
        QTimer.singleShot(50,  lambda: self._search.setFocus() if self.isVisible() else None)
        QTimer.singleShot(250, self._start_focus_watch)

    def close_palette(self):
        self._focus_timer.stop()
        self._debounce.stop()
        if self._thumb_worker and self._thumb_worker.isRunning():
            self._thumb_worker.quit()
            self._thumb_worker.wait()
        self._search.clear()
        self._results.clear()
        self._clear_preview()
        self.hide()
        self.closed.emit()

    # ── Search ────────────────────────────────────────────────────────────────

    def _do_search(self):
        query   = self._search.text().strip()
        q_lower = query.lower()
        self._results.clear()
        self._clear_preview()

        if not query:
            self._populate_actions("")
            return

        # ── Prefixo @ → busca de clientes ────────────────────────────────────
        if query.startswith("@"):
            self._search_clients(query[1:].strip())

        # ── Prefixo = → calculadora ───────────────────────────────────────────
        elif query.startswith("="):
            self._run_calculator(query[1:].strip())

        # ── Prefixo os: → abrir OS no Mubisys ────────────────────────────────
        elif q_lower.startswith("os:"):
            os_num = query[3:].strip()
            item = QListWidgetItem(f"🔗  Abrir OS {os_num} no Mubisys\n    Pressione Enter para abrir no browser")
            item.setData(Qt.ItemDataRole.UserRole, {"_mubisys": os_num})
            self._results.addItem(item)

        # ── Prefixo ! → criar lembrete ────────────────────────────────────────
        elif query.startswith("!"):
            self._preview_reminder(query[1:].strip())

        # ── Busca geral: ações + apps + arquivos ──────────────────────────────
        else:
            self._populate_actions(q_lower)
            self._search_apps(query)
            self._search_files(query)

        if self._results.count():
            self._results.setCurrentRow(0)

    # ── Ações ─────────────────────────────────────────────────────────────────

    def _populate_actions(self, filter_text: str):
        for action in _ACTIONS:
            if filter_text and (
                filter_text not in action["label"].lower()
                and filter_text not in action["desc"].lower()
            ):
                continue
            item = QListWidgetItem(f"{action['label']}\n    {action['desc']}")
            item.setData(Qt.ItemDataRole.UserRole, {"_action": action["id"]})
            self._results.addItem(item)
        if self._results.count():
            self._results.setCurrentRow(0)

    # ── Apps ─────────────────────────────────────────────────────────────────

    def _search_apps(self, query: str):
        for app in search_apps(query):
            folder = f" — {app['folder']}" if app.get("folder") else ""
            item = QListWidgetItem(f"🖥️  {app['name']}\n    Aplicativo{folder}")
            item.setData(Qt.ItemDataRole.UserRole, {"_app": True, "lnk_path": app["lnk_path"], "name": app["name"]})
            self._results.addItem(item)

    # ── Calculadora ───────────────────────────────────────────────────────────

    def _run_calculator(self, expr: str):
        if not expr:
            for t in list_templates():
                item = QListWidgetItem(f"🧮  ={t['prefixo']} …\n    {t['nome']}")
                item.setData(Qt.ItemDataRole.UserRole, {"_stub": True})
                self._results.addItem(item)
            return

        result = calculate(expr)
        if result is None:
            self._results.addItem(QListWidgetItem("⚠️  Prefixo não encontrado. Templates disponíveis em ⚙️ Configurações."))
            return

        copied_note = "  ✓ copiado" if result.get("copied") else ""
        item = QListWidgetItem(f"🧮  {result['result_text']}{copied_note}\n    {result['label']}")
        item.setData(Qt.ItemDataRole.UserRole, {"_calc_result": result["result_text"]})
        self._results.addItem(item)

    # ── Clientes ──────────────────────────────────────────────────────────────

    def _search_clients(self, query: str):
        if not query:
            self._results.addItem(QListWidgetItem("💡  Digite @nome para buscar clientes"))
            return
        clients = search_clients(query)
        if not clients:
            self._results.addItem(QListWidgetItem(f"Nenhum cliente encontrado para '{query}'"))
            return
        for c in clients:
            orders_info = f"{c['order_count']} pedido(s)" if c["order_count"] else "sem pedidos"
            last = f" · Último: {c['last_order_title']} [{c['last_order_status']}]" if c.get("last_order_title") else ""
            whats = f" · 📱 {c['whatsapp']}" if c.get("whatsapp") else ""
            item = QListWidgetItem(f"👤  {c['name']}{whats}\n    {orders_info}{last}")
            item.setData(Qt.ItemDataRole.UserRole, {"_client": True, "client_id": c["id"], "whatsapp": c.get("whatsapp", ""), "name": c["name"]})
            self._results.addItem(item)

    # ── Lembrete ──────────────────────────────────────────────────────────────

    def _preview_reminder(self, raw: str):
        if not raw:
            self._results.addItem(QListWidgetItem("💡  !texto 14h  ·  !texto amanhã 9h  ·  !texto em 30min"))
            return
        parsed = parse_reminder(raw)
        if parsed:
            text, trigger_at = parsed
            dt = datetime.fromtimestamp(trigger_at).strftime("%d/%m %H:%M")
            item = QListWidgetItem(f"📌  {text}\n    Lembrete para {dt} — Enter para salvar")
            item.setData(Qt.ItemDataRole.UserRole, {"_reminder": True, "text": text, "trigger_at": trigger_at})
        else:
            item = QListWidgetItem(f"📌  {raw}\n    ⚠️ Horário não reconhecido — tente '14h', 'amanhã 9h' ou 'em 30min'")
            item.setData(Qt.ItemDataRole.UserRole, {"_stub": True})
        self._results.addItem(item)

    # ── Arquivos ──────────────────────────────────────────────────────────────

    def _search_files(self, query: str):
        results = search_files(query)
        if not results and self._results.count() == 0:
            self._results.addItem(
                QListWidgetItem(
                    "Nenhum resultado encontrado.\n"
                    "Dica: configure as pastas em ⚙️ Configurações."
                )
            )
            return
        for r in results:
            modified = (
                datetime.fromtimestamp(r["modified_at"]).strftime("%d/%m/%Y")
                if r.get("modified_at") else ""
            )
            size_str = _fmt_size(r["size"]) if r.get("size") else ""
            ext  = (r.get("extension") or "").upper()
            line2 = "  ".join(filter(None, [r["folder"], ext, size_str, modified]))
            item = QListWidgetItem(f"{r['filename']}\n{line2}")
            item.setData(Qt.ItemDataRole.UserRole, r)
            self._results.addItem(item)

    # ── Preview ───────────────────────────────────────────────────────────────

    def _on_selection_changed(self, current, _prev):
        self._clear_preview()
        if not current:
            return
        data = current.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict) or not data.get("filepath"):
            return

        self._preview_name.setText(data.get("filename", ""))
        ext      = (data.get("extension") or "").upper()
        size_str = _fmt_size(data["size"]) if data.get("size") else ""
        modified = (
            datetime.fromtimestamp(data["modified_at"]).strftime("%d/%m/%Y")
            if data.get("modified_at") else ""
        )
        self._preview_meta.setText(f"{ext}  ·  {size_str}\n{modified}")

        cfg      = self._settings.get("preview", {})
        allowed  = cfg.get("show_for_extensions", [])
        max_mb   = cfg.get("max_size_mb", 50)
        file_ext = (data.get("extension") or "").lower()
        size_mb  = (data.get("size") or 0) / 1_048_576

        if not cfg.get("enabled", True) or file_ext not in allowed or size_mb > max_mb:
            return

        self._thumb_label.setText("…")
        if self._thumb_worker and self._thumb_worker.isRunning():
            self._thumb_worker.quit()
            self._thumb_worker.wait()
        self._thumb_worker = ThumbnailWorker(data["filepath"], self)
        self._thumb_worker.ready.connect(self._on_thumb_ready)
        self._thumb_worker.start()

    def _on_thumb_ready(self, path: str, pixmap):
        cur = self._results.currentItem()
        if cur:
            d = cur.data(Qt.ItemDataRole.UserRole)
            if isinstance(d, dict) and d.get("filepath") == path:
                self._thumb_label.setPixmap(pixmap)

    def _clear_preview(self):
        self._thumb_label.clear()
        self._preview_name.clear()
        self._preview_meta.clear()

    # ── Activation ────────────────────────────────────────────────────────────

    def _on_item_activated(self, item: QListWidgetItem):
        self._activate(item)

    def _activate(self, item: QListWidgetItem):
        data = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict):
            return

        # Ação interna (kanban, prazos, etc.)
        if "_action" in data:
            self.close_palette()
            self.action_triggered.emit(data["_action"])

        # Abrir arquivo
        elif data.get("filepath"):
            try:
                os.startfile(data["filepath"])
            except Exception:
                pass
            self.close_palette()

        # Abrir aplicativo
        elif data.get("_app"):
            try:
                os.startfile(data["lnk_path"])
            except Exception:
                pass
            self.close_palette()

        # Mubisys
        elif data.get("_mubisys"):
            open_os(data["_mubisys"])
            self.close_palette()

        # Lembrete
        elif data.get("_reminder"):
            add_reminder(data["text"], data["trigger_at"])
            self.close_palette()

        # Cliente — copiar WhatsApp se disponível
        elif data.get("_client"):
            wa = data.get("whatsapp", "")
            if wa:
                QApplication.clipboard().setText(wa)
            self.close_palette()

        # Resultado de cálculo — copiar
        elif data.get("_calc_result"):
            QApplication.clipboard().setText(data["_calc_result"])
            self.close_palette()

    def _open_folder(self, filepath: str):
        try:
            subprocess.Popen(["explorer", str(Path(filepath).parent)])
        except Exception:
            pass
        self.close_palette()

    # ── Events ────────────────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close_palette()
        else:
            super().keyPressEvent(event)

    def eventFilter(self, obj, event):
        if obj is self._search and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Down:
                r = self._results.currentRow()
                self._results.setCurrentRow(min(r + 1, self._results.count() - 1))
                return True
            if key == Qt.Key.Key_Up:
                r = self._results.currentRow()
                self._results.setCurrentRow(max(r - 1, 0))
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                item = self._results.currentItem()
                if item:
                    data = item.data(Qt.ItemDataRole.UserRole)
                    if isinstance(data, dict) and data.get("filepath"):
                        ctrl = event.modifiers() & Qt.KeyboardModifier.ControlModifier
                        if ctrl:
                            self._open_folder(data["filepath"])
                            return True
                    self._activate(item)
                return True
        return super().eventFilter(obj, event)
