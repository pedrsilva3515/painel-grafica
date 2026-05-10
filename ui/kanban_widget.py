import time
from datetime import datetime

from PyQt6.QtCore import QMimeData, QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QDrag, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QDateTimeEdit, QDialog, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QTextEdit, QVBoxLayout, QWidget,
)
from PyQt6.QtCore import QDateTime

import modules.kanban.board as board


def _deadline_status(deadline: float | None) -> str:
    if deadline is None:
        return "none"
    diff_h = (deadline - time.time()) / 3600
    if diff_h < 0:
        return "critical"
    if diff_h < 24:
        return "critical"
    if diff_h < 48:
        return "warning"
    return "ok"


# ── Detail dialog ──────────────────────────────────────────────────────────────

class OrderDetailDialog(QDialog):
    def __init__(self, order: dict, parent=None):
        super().__init__(parent)
        self._order = order
        self.setWindowTitle("Novo Pedido" if not order.get("id") else "Editar Pedido")
        self.setModal(True)
        self.setFixedWidth(440)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(22, 22, 22, 22)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._title  = QLineEdit(self._order.get("title", ""))
        self._title.setPlaceholderText("Nome do trabalho *")
        form.addRow("Título:", self._title)

        self._os = QLineEdit(self._order.get("os_number", ""))
        self._os.setPlaceholderText("Ex: 1042")
        form.addRow("OS:", self._os)

        self._client = QLineEdit(self._order.get("client_name", ""))
        self._client.setPlaceholderText("Nome do cliente")
        form.addRow("Cliente:", self._client)

        self._value = QLineEdit(
            str(self._order["value"]) if self._order.get("value") else ""
        )
        self._value.setPlaceholderText("0.00")
        form.addRow("Valor (R$):", self._value)

        self._deadline = QDateTimeEdit()
        self._deadline.setCalendarPopup(True)
        self._deadline.setDisplayFormat("dd/MM/yyyy  HH:mm")
        if self._order.get("deadline"):
            dt = datetime.fromtimestamp(self._order["deadline"])
            self._deadline.setDateTime(
                QDateTime(dt.year, dt.month, dt.day, dt.hour, dt.minute)
            )
        else:
            self._deadline.setDateTime(QDateTime.currentDateTime())
        form.addRow("Prazo:", self._deadline)

        self._notes = QTextEdit(self._order.get("notes", ""))
        self._notes.setMaximumHeight(72)
        self._notes.setPlaceholderText("Observações...")
        form.addRow("Notas:", self._notes)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        save = QPushButton("Salvar")
        save.setObjectName("authPrimaryBtn")
        save.clicked.connect(self._on_save)
        btn_row.addWidget(save)
        layout.addLayout(btn_row)

    def _on_save(self):
        if not self._title.text().strip():
            QMessageBox.warning(self, "Campo obrigatório", "O título é obrigatório.")
            return
        self.accept()

    def get_data(self) -> dict:
        try:
            value = float(self._value.text().strip().replace(",", "."))
        except ValueError:
            value = None
        deadline = self._deadline.dateTime().toPyDateTime().timestamp()
        return {
            "title":       self._title.text().strip(),
            "os_number":   self._os.text().strip(),
            "client_name": self._client.text().strip(),
            "value":       value,
            "deadline":    deadline,
            "notes":       self._notes.toPlainText().strip(),
        }


# ── Card ───────────────────────────────────────────────────────────────────────

class OrderCard(QFrame):
    move_requested    = pyqtSignal(int, str)
    delete_requested  = pyqtSignal(int)
    refresh_requested = pyqtSignal()

    _MIME_TYPE = "application/x-kanban-order-id"

    def __init__(self, order: dict, columns: list[str], parent=None):
        super().__init__(parent)
        self._order   = order
        self._columns = columns
        self._drag_start: QPoint | None = None

        self.setObjectName("kanbanCard")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setProperty("deadlineStatus", _deadline_status(order.get("deadline")))
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(10, 8, 10, 8)

        title = QLabel(self._order["title"])
        title.setObjectName("cardTitle")
        title.setWordWrap(True)
        layout.addWidget(title)

        meta_parts = []
        if self._order.get("os_number"):
            meta_parts.append(f"OS {self._order['os_number']}")
        if self._order.get("client_name"):
            meta_parts.append(self._order["client_name"])
        if meta_parts:
            meta = QLabel("  ·  ".join(meta_parts))
            meta.setObjectName("cardMeta")
            layout.addWidget(meta)

        if self._order.get("deadline"):
            dt_str = datetime.fromtimestamp(self._order["deadline"]).strftime("%d/%m  %H:%M")
            status = _deadline_status(self._order["deadline"])
            dl = QLabel(f"⏰ {dt_str}")
            dl.setObjectName(f"cardDeadline_{status}")
            layout.addWidget(dl)

    # ── Drag ──────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_start = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton) or self._drag_start is None:
            return
        dist = (event.position().toPoint() - self._drag_start).manhattanLength()
        if dist < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(self._MIME_TYPE, str(self._order["id"]).encode())
        drag.setMimeData(mime)

        # Snapshot of the card as drag pixmap
        px = self.grab().scaled(
            self.width(), self.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        drag.setPixmap(px)
        drag.setHotSpot(event.position().toPoint())

        self._drag_start = None
        drag.exec(Qt.DropAction.MoveAction)

    # ── Context menu / double-click ────────────────────────────────────────────

    def contextMenuEvent(self, event):
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        move_menu = menu.addMenu("Mover para →")
        for col in self._columns:
            if col != self._order["status"]:
                act = move_menu.addAction(col)
                act.triggered.connect(
                    lambda checked, c=col: self.move_requested.emit(self._order["id"], c)
                )
        menu.addSeparator()
        menu.addAction("Editar").triggered.connect(self._on_edit)
        menu.addAction("Excluir").triggered.connect(self._on_delete)
        menu.exec(event.globalPos())

    def mouseDoubleClickEvent(self, _event):
        self._on_edit()

    def _on_edit(self):
        dlg = OrderDetailDialog(self._order, self.window())
        if dlg.exec() == QDialog.DialogCode.Accepted:
            board.update_order(self._order["id"], **dlg.get_data())
            self.refresh_requested.emit()

    def _on_delete(self):
        reply = QMessageBox.question(
            self, "Excluir pedido",
            f"Excluir \"{self._order['title']}\"?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            board.delete_order(self._order["id"])
            self.delete_requested.emit(self._order["id"])


# ── Drop-aware scroll area ─────────────────────────────────────────────────────

class _DropScroll(QScrollArea):
    """QScrollArea that accepts card drops and forwards the order-id up."""

    card_dropped = pyqtSignal(int)   # order_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(OrderCard._MIME_TYPE):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(OrderCard._MIME_TYPE):
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasFormat(OrderCard._MIME_TYPE):
            order_id = int(event.mimeData().data(OrderCard._MIME_TYPE).data())
            self.card_dropped.emit(order_id)
            event.acceptProposedAction()


# ── Column ─────────────────────────────────────────────────────────────────────

class KanbanColumn(QWidget):
    card_moved     = pyqtSignal(int, str)   # order_id, new_status
    card_deleted   = pyqtSignal(int)
    refresh_needed = pyqtSignal()

    def __init__(self, name: str, orders: list[dict], columns: list[str], parent=None):
        super().__init__(parent)
        self._name    = name
        self._columns = columns
        self.setObjectName("kanbanColumnWidget")
        self.setAcceptDrops(True)
        self._build_ui(orders)

    def _build_ui(self, orders: list[dict]):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel(f"{self._name}  ({len(orders)})")
        header.setObjectName("kanbanColumnHeader")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        scroll = _DropScroll()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setObjectName("kanbanColumnScroll")
        scroll.card_dropped.connect(
            lambda oid: self.card_moved.emit(oid, self._name)
        )

        container = QWidget()
        self._cards_layout = QVBoxLayout(container)
        self._cards_layout.setSpacing(6)
        self._cards_layout.setContentsMargins(8, 8, 8, 8)
        self._cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        for order in orders:
            self._add_card(order)

        scroll.setWidget(container)
        layout.addWidget(scroll)

    def _add_card(self, order: dict):
        card = OrderCard(order, self._columns, self)
        card.move_requested.connect(self.card_moved)
        card.delete_requested.connect(self.card_deleted)
        card.refresh_requested.connect(self.refresh_needed)
        self._cards_layout.addWidget(card)

    # Also accept drops on the column header / margins
    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(OrderCard._MIME_TYPE):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(OrderCard._MIME_TYPE):
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasFormat(OrderCard._MIME_TYPE):
            order_id = int(event.mimeData().data(OrderCard._MIME_TYPE).data())
            self.card_moved.emit(order_id, self._name)
            event.acceptProposedAction()


# ── Board ──────────────────────────────────────────────────────────────────────

class KanbanWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QWidget()
        toolbar.setObjectName("kanbanToolbar")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(14, 10, 14, 10)
        title = QLabel("Kanban de Pedidos")
        title.setObjectName("panelTitle")
        tb.addWidget(title)
        tb.addStretch()

        add_btn = QPushButton("+ Novo Pedido")
        add_btn.setObjectName("primaryBtn")
        add_btn.clicked.connect(self._on_add)
        tb.addWidget(add_btn)

        refresh_btn = QPushButton("↻")
        refresh_btn.setToolTip("Atualizar")
        refresh_btn.clicked.connect(self.refresh)
        tb.addWidget(refresh_btn)

        layout.addWidget(toolbar)

        self._board_scroll = QScrollArea()
        self._board_scroll.setWidgetResizable(True)
        self._board_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._board_scroll.setObjectName("kanbanBoardScroll")
        layout.addWidget(self._board_scroll)

        self.refresh()

    def refresh(self):
        columns       = board.get_columns()
        orders_by_col = board.get_orders_by_column()

        board_widget = QWidget()
        board_widget.setObjectName("kanbanBoard")
        row = QHBoxLayout(board_widget)
        row.setSpacing(8)
        row.setContentsMargins(12, 12, 12, 12)

        for col in columns:
            col_widget = KanbanColumn(col, orders_by_col.get(col, []), columns)
            col_widget.setObjectName("kanbanColumn")
            col_widget.setMinimumWidth(210)
            col_widget.setMaximumWidth(250)
            col_widget.card_moved.connect(self._on_card_moved)
            col_widget.card_deleted.connect(lambda _: self.refresh())
            col_widget.refresh_needed.connect(self.refresh)
            row.addWidget(col_widget)

        row.addStretch()
        self._board_scroll.setWidget(board_widget)

    def _on_card_moved(self, order_id: int, new_status: str):
        board.move_order(order_id, new_status)
        self.refresh()

    def _on_add(self):
        dlg = OrderDetailDialog({}, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            board.add_order(**dlg.get_data())
            self.refresh()
