from datetime import datetime

from PyQt6.QtCore import QEvent, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from modules.daily_panel.panel import get_daily_summary

_DAYS_PT   = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
_MONTHS_PT = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


class DailyPanelWindow(QDialog):
    """Morning briefing window — frameless, always on top, auto-closes after 30 min."""

    snooze_requested = pyqtSignal()   # emitted when user clicks Snooze

    _WIDTH  = 520
    _HEIGHT = 580

    def __init__(self, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setModal(False)
        self._build_ui()
        self._center()

        self._auto_close = QTimer(self)
        self._auto_close.setSingleShot(True)
        self._auto_close.timeout.connect(self.close)
        self._auto_close.start(30 * 60 * 1_000)

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        frame = QFrame()
        frame.setObjectName("dailyContainer")
        root.addWidget(frame)

        layout = QVBoxLayout(frame)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header = QWidget()
        header.setObjectName("dailyHeader")
        h_row = QHBoxLayout(header)
        h_row.setContentsMargins(20, 16, 20, 16)

        now = datetime.now()
        date_str = (
            f"{_DAYS_PT[now.weekday()]}, "
            f"{now.day} de {_MONTHS_PT[now.month - 1]}"
        )
        greeting = QLabel(f"Bom dia  ·  {date_str}")
        greeting.setObjectName("dailyGreeting")
        h_row.addWidget(greeting)
        layout.addWidget(header)

        sep = QFrame()
        sep.setObjectName("dailySep")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # Scrollable body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("dailyScroll")

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setSpacing(0)
        body_layout.setContentsMargins(0, 0, 0, 0)

        data = get_daily_summary()

        def fmt_order(o: dict) -> str:
            dl = (
                datetime.fromtimestamp(o["deadline"]).strftime("%d/%m  %H:%M")
                if o.get("deadline") else ""
            )
            client = f" — {o['client_name']}" if o.get("client_name") else ""
            return f"· {o['title']}{client}  {dl}"

        def fmt_stale(o: dict) -> str:
            return f"· {o['title']} — {o['status']} há {o['hours_stuck']:.0f}h"

        def fmt_reminder(r: dict) -> str:
            t = datetime.fromtimestamp(r["trigger_at"]).strftime("%H:%M")
            return f"· {r['text']}  ({t})"

        self._add_section(body_layout, "🔴  PRAZOS CRÍTICOS",           data["critical"],  fmt_order)
        self._add_section(body_layout, "🟡  PRAZOS PRÓXIMOS (24–48h)",  data["warning"],   fmt_order)
        self._add_section(body_layout, "📋  PARA ENTREGAR HOJE",        data["due_today"], fmt_order)
        self._add_section(body_layout, "⚠️   PARADOS SEM MOVIMENTAÇÃO", data["stale"],     fmt_stale)
        self._add_section(body_layout, "📌  LEMBRETES DE HOJE",         data["reminders"], fmt_reminder)

        if not any([data["critical"], data["warning"], data["due_today"],
                    data["stale"], data["reminders"]]):
            empty = QLabel("Tudo em ordem! Nenhum alerta para hoje. ✅")
            empty.setObjectName("dailyEmptyMsg")
            empty.setContentsMargins(20, 24, 20, 24)
            body_layout.addWidget(empty)

        body_layout.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll)

        # Footer
        footer = QWidget()
        footer.setObjectName("dailyFooter")
        f_row = QHBoxLayout(footer)
        f_row.setContentsMargins(20, 12, 20, 12)
        f_row.setSpacing(10)
        f_row.addStretch()

        snooze_btn = QPushButton("Snooze 1h")
        snooze_btn.clicked.connect(self._on_snooze)
        f_row.addWidget(snooze_btn)

        close_btn = QPushButton("Fechar")
        close_btn.setObjectName("authPrimaryBtn")
        close_btn.clicked.connect(self.close)
        f_row.addWidget(close_btn)

        layout.addWidget(footer)

    @staticmethod
    def _add_section(parent_layout, title: str, items: list, formatter):
        if not items:
            return

        section = QWidget()
        section.setObjectName("dailySection")
        s_layout = QVBoxLayout(section)
        s_layout.setSpacing(4)
        s_layout.setContentsMargins(20, 12, 20, 12)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("dailySectionTitle")
        s_layout.addWidget(title_lbl)

        for item in items:
            row_lbl = QLabel(formatter(item))
            row_lbl.setObjectName("dailySectionItem")
            row_lbl.setWordWrap(True)
            s_layout.addWidget(row_lbl)

        parent_layout.addWidget(section)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("dailySep")
        parent_layout.addWidget(sep)

    def _on_snooze(self):
        self._auto_close.stop()
        self.snooze_requested.emit()
        self.close()

    def _center(self):
        from PyQt6.QtWidgets import QApplication
        self.setFixedSize(self._WIDTH, self._HEIGHT)
        screen = QApplication.primaryScreen().geometry()
        self.move(
            screen.center().x() - self._WIDTH  // 2,
            screen.center().y() - self._HEIGHT // 2,
        )
