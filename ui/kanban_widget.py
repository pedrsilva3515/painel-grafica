import time
from datetime import datetime

import os

from PyQt6.QtCore import QDateTime, QMimeData, QPoint, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QDrag, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QDateTimeEdit, QDialog, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QScrollArea, QSplitter, QTextEdit,
    QVBoxLayout, QWidget,
)

import modules.kanban.board as board
import modules.kanban.alerts as alerts


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


# ── Clickable thumbnail label ─────────────────────────────────────────────────

class _ClickableLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._filepath = ""
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_filepath(self, path: str):
        self._filepath = path

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._filepath:
            try:
                os.startfile(self._filepath)
            except Exception:
                pass
        super().mousePressEvent(event)


# ── Detail dialog ──────────────────────────────────────────────────────────────

class OrderDetailDialog(QDialog):
    def __init__(self, order: dict, parent=None):
        super().__init__(parent)
        self._order           = order
        self._thumb_worker    = None
        self._current_filepath = ""
        self.setWindowTitle("Novo Pedido" if not order.get("id") else "Editar Pedido")
        self.setModal(True)
        self._build_ui()

        if order.get("id"):
            self.setFixedWidth(900)
            os_num = order.get("os_number", "").strip()
            if os_num:
                self._load_file_list(os_num)
            else:
                self._show_empty_list()
        else:
            self._preview_panel.setVisible(False)
            self.setFixedWidth(460)

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── Left: form ────────────────────────────────────────────────────────
        form_widget = QWidget()
        left = QVBoxLayout(form_widget)
        left.setSpacing(12)
        left.setContentsMargins(22, 22, 22, 22)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._title = QLineEdit(self._order.get("title", ""))
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

        left.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        save = QPushButton("Salvar")
        save.setObjectName("authPrimaryBtn")
        save.clicked.connect(self._on_save)
        btn_row.addWidget(save)
        left.addLayout(btn_row)
        left.addStretch()

        root.addWidget(form_widget, stretch=1)

        # ── Right: preview panel ──────────────────────────────────────────────
        preview_panel = self._preview_panel = QFrame()
        preview_panel.setObjectName("orderPreviewPanel")
        preview_panel.setFixedWidth(380)
        pv = QVBoxLayout(preview_panel)
        pv.setSpacing(8)
        pv.setContentsMargins(12, 12, 12, 12)

        self._thumb_label = _ClickableLabel()
        self._thumb_label.setObjectName("orderPreviewThumb")
        self._thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb_label.setMinimumHeight(260)
        self._thumb_label.setScaledContents(False)
        self._thumb_label.setText("Sem preview")
        pv.addWidget(self._thumb_label)

        self._file_list = QListWidget()
        self._file_list.setObjectName("orderFileList")
        self._file_list.setMinimumHeight(120)
        self._file_list.currentItemChanged.connect(self._on_file_selected)
        pv.addWidget(self._file_list)

        root.addWidget(preview_panel)

    def _show_empty_list(self):
        item = QListWidgetItem("Nenhum arquivo exportado")
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        self._file_list.addItem(item)

    def _load_file_list(self, os_number: str):
        from modules.kanban.print_folder_scanner import find_exported_files
        self._exported_files = find_exported_files(os_number)

        if not self._exported_files:
            self._show_empty_list()
            return

        for f in self._exported_files:
            item = QListWidgetItem(f"{f['filename']}\n{f['material']}  ·  {f['status']}")
            item.setData(Qt.ItemDataRole.UserRole, f["filepath"])
            self._file_list.addItem(item)

        self._file_list.setCurrentRow(0)

    def _on_file_selected(self, current: QListWidgetItem, _previous):
        if current is None:
            return
        filepath = current.data(Qt.ItemDataRole.UserRole)
        if filepath:
            self._load_thumb(filepath)

    def _load_thumb(self, filepath: str):
        self._cancel_worker()
        self._thumb_label.setText("Carregando…")
        self._thumb_label.set_filepath("")
        self._current_filepath = filepath

        from modules.preview.renderer import ThumbnailWorker
        self._thumb_worker = ThumbnailWorker(filepath, self)
        self._thumb_worker.ready.connect(self._on_thumb_ready)
        self._thumb_worker.start()

    def _cancel_worker(self):
        if self._thumb_worker and self._thumb_worker.isRunning():
            self._thumb_worker.ready.disconnect()
            self._thumb_worker.quit()
            self._thumb_worker.wait(500)
        self._thumb_worker = None

    def _on_thumb_ready(self, path: str, pixmap):
        if path != self._current_filepath:
            return
        self._thumb_label.setPixmap(
            pixmap.scaled(
                360, 260,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self._thumb_label.set_filepath(path)

    def closeEvent(self, event):
        self._cancel_worker()
        super().closeEvent(event)

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

    def __init__(self, order: dict, columns: list[str], stale_hours: float | None = None, parent=None):
        super().__init__(parent)
        self._order       = order
        self._columns     = columns
        self._stale_hours = stale_hours
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

        if self._stale_hours is not None:
            stale_lbl = QLabel(f"⚠ {self._stale_hours:.0f}h parado")
            stale_lbl.setObjectName("cardStaleLabel")
            layout.addWidget(stale_lbl)

    # ── Drag ──────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        was_click = self._drag_start is not None  # True → no drag occurred
        self._drag_start = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        if was_click and event.button() == Qt.MouseButton.LeftButton:
            QTimer.singleShot(0, self._on_edit)
            return
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

        px = self.grab().scaled(
            self.width(), self.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        drag.setPixmap(px)
        drag.setHotSpot(event.position().toPoint())

        self._drag_start = None
        drag.exec(Qt.DropAction.MoveAction)

    # ── Context menu ──────────────────────────────────────────────────────────

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
        if not event.mimeData().hasFormat(OrderCard._MIME_TYPE):
            return
        order_id = int(event.mimeData().data(OrderCard._MIME_TYPE).data())

        container = self.widget()
        layout    = container.layout()

        # Collect all OrderCard widgets currently in this column
        cards = [
            layout.itemAt(i).widget()
            for i in range(layout.count())
            if layout.itemAt(i) and isinstance(layout.itemAt(i).widget(), OrderCard)
        ]
        dragged = next((c for c in cards if c._order["id"] == order_id), None)

        if dragged is not None:
            # ── Same-column reorder ───────────────────────────────────────────
            drop_y = (
                event.position().y()
                + self.verticalScrollBar().value()
            )

            others = [c for c in cards if c is not dragged]
            insert_at = len(others)
            for i, card in enumerate(others):
                if drop_y < card.y() + card.height() // 2:
                    insert_at = i
                    break

            new_order = others[:insert_at] + [dragged] + others[insert_at:]

            for card in new_order:
                layout.removeWidget(card)
            for card in new_order:
                layout.addWidget(card)

            board.reorder_cards([c._order["id"] for c in new_order])
        else:
            # ── Cross-column drop ─────────────────────────────────────────────
            self.card_dropped.emit(order_id)

        event.acceptProposedAction()


# ── Column ─────────────────────────────────────────────────────────────────────

class KanbanColumn(QWidget):
    card_moved     = pyqtSignal(int, str)   # order_id, new_status
    card_deleted   = pyqtSignal(int)
    refresh_needed = pyqtSignal()

    def __init__(self, name: str, orders: list[dict], columns: list[str],
                 stale_ids: dict[int, float] | None = None,
                 wip_limit: int | None = None, parent=None):
        super().__init__(parent)
        self._name         = name
        self._columns      = columns
        self._total_orders = len(orders)
        self._stale_ids    = stale_ids or {}
        self._wip_limit    = wip_limit
        self.setObjectName("kanbanColumnWidget")
        self.setAcceptDrops(True)
        self._build_ui(orders)

    def _header_text(self, count: int) -> str:
        if self._wip_limit:
            return f"{self._name}  ({count} / {self._wip_limit})"
        return f"{self._name}  ({count})"

    def _apply_wip_style(self, count: int):
        if not self._wip_limit:
            self._header.setStyleSheet("")
            return
        if count > self._wip_limit:
            self._header.setStyleSheet("color: #D97560; font-weight: bold;")
        elif count == self._wip_limit:
            self._header.setStyleSheet("color: #D18960;")
        else:
            self._header.setStyleSheet("")

    def _build_ui(self, orders: list[dict]):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        self._header = QLabel(self._header_text(len(orders)))
        self._header.setObjectName("kanbanColumnHeader")
        self._header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._apply_wip_style(len(orders))
        layout.addWidget(self._header)

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
        stale_hours = self._stale_ids.get(order["id"])
        card = OrderCard(order, self._columns, stale_hours, self)
        card.move_requested.connect(self.card_moved)
        card.delete_requested.connect(self.card_deleted)
        card.refresh_requested.connect(self.refresh_needed)
        self._cards_layout.addWidget(card)

    def apply_filter(self, text: str):
        text = text.strip().lower()
        visible = 0
        for i in range(self._cards_layout.count()):
            item = self._cards_layout.itemAt(i)
            if not item:
                continue
            card = item.widget()
            if not isinstance(card, OrderCard):
                continue
            order = card._order
            if not text:
                card.setVisible(True)
                visible += 1
            else:
                fields = " ".join(filter(None, [
                    order.get("title", ""),
                    order.get("os_number", ""),
                    order.get("client_name", ""),
                    order.get("notes", ""),
                ])).lower()
                matches = text in fields
                card.setVisible(matches)
                if matches:
                    visible += 1
        count = visible if text else self._total_orders
        self._header.setText(self._header_text(count))
        self._apply_wip_style(count)

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

        self._filter_input = QLineEdit()
        self._filter_input.setObjectName("kanbanFilter")
        self._filter_input.setPlaceholderText("Filtrar pedidos…")
        self._filter_input.setMaximumWidth(220)
        self._filter_input.textChanged.connect(self._on_filter_changed)
        tb.addWidget(self._filter_input)

        add_btn = QPushButton("+ Novo Pedido")
        add_btn.setObjectName("primaryBtn")
        add_btn.clicked.connect(self._on_add)
        tb.addWidget(add_btn)

        cols_btn = QPushButton("⚙️ Colunas")
        cols_btn.setToolTip("Adicionar, renomear e reordenar colunas")
        cols_btn.clicked.connect(self._on_manage_columns)
        tb.addWidget(cols_btn)

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

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh)
        self._restart_timer()

        self.refresh()

    def _restart_timer(self):
        interval_ms = board.get_auto_refresh_minutes() * 60 * 1000
        self._refresh_timer.start(interval_ms)

    def refresh(self):
        columns       = board.get_columns()
        orders_by_col = board.get_orders_by_column()
        wip_limits    = board.get_wip_limits()

        stale_list = alerts.get_stale_orders()
        stale_ids  = {o["id"]: o["hours_stuck"] for o in stale_list}

        saved_sizes = (
            self._splitter.sizes()
            if hasattr(self, "_splitter") and self._splitter.count() == len(columns)
            else []
        )

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("kanbanSplitter")
        splitter.setContentsMargins(12, 12, 12, 12)

        for col in columns:
            col_widget = KanbanColumn(
                col, orders_by_col.get(col, []), columns,
                stale_ids=stale_ids,
                wip_limit=wip_limits.get(col),
            )
            col_widget.setObjectName("kanbanColumn")
            col_widget.setMinimumWidth(180)
            col_widget.card_moved.connect(self._on_card_moved)
            col_widget.card_deleted.connect(lambda _: self.refresh())
            col_widget.refresh_needed.connect(self.refresh)
            splitter.addWidget(col_widget)

        if saved_sizes:
            splitter.setSizes(saved_sizes)

        self._splitter = splitter
        self._board_scroll.setWidget(splitter)

        current_filter = self._filter_input.text() if hasattr(self, "_filter_input") else ""
        if current_filter:
            self._on_filter_changed(current_filter)

    def _on_filter_changed(self, text: str):
        if not hasattr(self, "_splitter"):
            return
        for i in range(self._splitter.count()):
            widget = self._splitter.widget(i)
            if isinstance(widget, KanbanColumn):
                widget.apply_filter(text)

    def _on_card_moved(self, order_id: int, new_status: str):
        wip_limits = board.get_wip_limits()
        if new_status in wip_limits:
            orders_by_col = board.get_orders_by_column()
            current_count = len(orders_by_col.get(new_status, []))
            limit = wip_limits[new_status]
            if current_count >= limit:
                reply = QMessageBox.question(
                    self, "Limite WIP atingido",
                    f"A coluna \"{new_status}\" já tem {current_count} card(s) "
                    f"(limite configurado: {limit}).\nDeseja mover mesmo assim?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.No:
                    self.refresh()
                    return
        board.move_order(order_id, new_status)
        self.refresh()

    def _on_manage_columns(self):
        from ui.kanban_columns_dialog import KanbanColumnsDialog
        dlg = KanbanColumnsDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_add(self):
        dlg = OrderDetailDialog({}, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            board.add_order(**dlg.get_data())
            self.refresh()
