from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout, QWidget,
)

from modules.deadlines.scanner import get_classified_orders

_STATUS_ICON = {"critical": "🔴", "warning": "🟡", "ok": "🟢"}


class DeadlinesWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Monitor de Prazos")
        title.setObjectName("panelTitle")
        header.addWidget(title)
        header.addStretch()

        refresh_btn = QPushButton("↻ Atualizar")
        refresh_btn.clicked.connect(self.refresh)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        legend = QLabel("🔴 < 24h   🟡 24–48h   🟢 OK")
        legend.setObjectName("deadlineLegend")
        layout.addWidget(legend)

        self._list = QListWidget()
        self._list.setObjectName("deadlineList")
        self._list.setSpacing(2)
        layout.addWidget(self._list)

    def refresh(self):
        self._list.clear()
        orders = get_classified_orders()

        if not orders:
            self._list.addItem(QListWidgetItem("Nenhum pedido com prazo definido."))
            return

        for order in orders:
            icon   = _STATUS_ICON[order["deadline_status"]]
            dt_str = datetime.fromtimestamp(order["deadline"]).strftime("%d/%m/%Y  %H:%M")
            client = f" — {order['client_name']}" if order.get("client_name") else ""
            os_str = f"OS {order['os_number']}  " if order.get("os_number") else ""

            line1 = f"{icon}  {order['title']}{client}"
            line2 = f"     {os_str}Prazo: {dt_str}  ·  {order['status']}"

            item = QListWidgetItem(f"{line1}\n{line2}")
            item.setData(Qt.ItemDataRole.UserRole, order)
            self._list.addItem(item)
