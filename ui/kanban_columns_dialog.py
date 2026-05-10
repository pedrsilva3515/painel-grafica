"""
Gerenciador de colunas do Kanban.

CRUD completo:
  - Adicionar coluna
  - Renomear (duplo clique ou botão)
  - Reordenar (▲ / ▼)
  - Excluir (com aviso se houver pedidos na coluna)

Salva em config/settings.json → kanban.columns.
Ao excluir coluna com pedidos, pergunta para qual coluna movê-los.
"""

import json
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QHBoxLayout,
    QInputDialog, QLabel, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from data.db import get_connection

SETTINGS_FILE = Path(__file__).parent.parent / "config" / "settings.json"


def _load_settings() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_columns(columns: list[str]) -> None:
    data = _load_settings()
    data.setdefault("kanban", {})["columns"] = columns
    SETTINGS_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _orders_in_column(column: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM orders WHERE status = ?", (column,)
        ).fetchone()
    return row["n"] if row else 0


def _move_orders(from_col: str, to_col: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE orders SET status = ? WHERE status = ?", (to_col, from_col)
        )


class KanbanColumnsDialog(QDialog):
    """
    Modal para gerenciar colunas do kanban.
    Após aceitar, o chamador deve chamar KanbanWidget.refresh().
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gerenciar Colunas do Kanban")
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setMinimumHeight(460)

        data = _load_settings()
        self._columns: list[str] = list(
            data.get("kanban", {}).get("columns", [])
        )
        self._build_ui()
        self._refresh_list()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(18, 18, 18, 18)

        info = QLabel(
            "Arraste, reordene com ▲▼ ou edite as colunas abaixo.\n"
            "Duplo clique em uma coluna para renomeá-la."
        )
        info.setObjectName("settingsInfo")
        info.setWordWrap(True)
        root.addWidget(info)

        # Lista + botões de ordem
        body = QHBoxLayout()

        self._list = QListWidget()
        self._list.setObjectName("settingsFolderList")
        self._list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._list.itemDoubleClicked.connect(self._on_rename)
        body.addWidget(self._list, 1)

        order_btns = QVBoxLayout()
        order_btns.setSpacing(4)
        order_btns.setAlignment(Qt.AlignmentFlag.AlignTop)

        up_btn = QPushButton("▲")
        up_btn.setFixedWidth(36)
        up_btn.setToolTip("Mover para cima")
        up_btn.clicked.connect(self._on_move_up)
        order_btns.addWidget(up_btn)

        down_btn = QPushButton("▼")
        down_btn.setFixedWidth(36)
        down_btn.setToolTip("Mover para baixo")
        down_btn.clicked.connect(self._on_move_down)
        order_btns.addWidget(down_btn)

        body.addLayout(order_btns)
        root.addLayout(body)

        # Botões de ação
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        add_btn = QPushButton("+ Adicionar")
        add_btn.setObjectName("primaryBtn")
        add_btn.clicked.connect(self._on_add)
        action_row.addWidget(add_btn)

        rename_btn = QPushButton("✎ Renomear")
        rename_btn.clicked.connect(self._on_rename)
        action_row.addWidget(rename_btn)

        del_btn = QPushButton("✕ Excluir")
        del_btn.clicked.connect(self._on_delete)
        action_row.addWidget(del_btn)

        action_row.addStretch()
        root.addLayout(action_row)

        # Nota sobre ações futuras
        note = QLabel("💡 Em breve: ações automáticas por coluna (notificações, integrações).")
        note.setObjectName("settingsInfo")
        note.setWordWrap(True)
        root.addWidget(note)

        # Salvar / Cancelar
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Save).setText("Salvar")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        btns.accepted.connect(self._on_save)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    # ── List helpers ──────────────────────────────────────────────────────────

    def _refresh_list(self):
        self._list.clear()
        for col in self._columns:
            n = _orders_in_column(col)
            label = col if n == 0 else f"{col}  ({n} pedido{'s' if n > 1 else ''})"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, col)  # nome original
            self._list.addItem(item)

    def _current_name(self) -> str | None:
        item = self._list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _sync_from_list(self):
        """Atualiza self._columns a partir da ordem atual da QListWidget (drag-drop)."""
        self._columns = [
            self._list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._list.count())
        ]

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_add(self):
        name, ok = QInputDialog.getText(self, "Nova Coluna", "Nome da coluna:")
        name = name.strip()
        if not ok or not name:
            return
        if name in self._columns:
            QMessageBox.warning(self, "Coluna duplicada", f'Já existe uma coluna chamada "{name}".')
            return
        self._columns.append(name)
        self._refresh_list()
        # Seleciona o item recém-adicionado
        self._list.setCurrentRow(self._list.count() - 1)

    def _on_rename(self):
        old = self._current_name()
        if old is None:
            return
        new, ok = QInputDialog.getText(
            self, "Renomear Coluna", "Novo nome:", text=old
        )
        new = new.strip()
        if not ok or not new or new == old:
            return
        if new in self._columns:
            QMessageBox.warning(self, "Coluna duplicada", f'Já existe uma coluna chamada "{new}".')
            return

        # Atualiza pedidos no banco
        _move_orders(old, new)

        row = self._list.currentRow()
        self._columns[row] = new
        self._refresh_list()
        self._list.setCurrentRow(row)

    def _on_delete(self):
        self._sync_from_list()
        old = self._current_name()
        if old is None:
            return
        if len(self._columns) <= 1:
            QMessageBox.warning(self, "Ação inválida", "O kanban precisa de ao menos uma coluna.")
            return

        n = _orders_in_column(old)

        if n > 0:
            # Precisa mover os pedidos antes de excluir
            other_cols = [c for c in self._columns if c != old]
            dlg = _MoveOrdersDialog(old, n, other_cols, self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            _move_orders(old, dlg.destination())
        else:
            reply = QMessageBox.question(
                self, "Excluir coluna",
                f'Excluir a coluna "{old}"?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self._columns.remove(old)
        self._refresh_list()

    def _on_move_up(self):
        self._sync_from_list()
        row = self._list.currentRow()
        if row <= 0:
            return
        self._columns[row - 1], self._columns[row] = (
            self._columns[row], self._columns[row - 1]
        )
        self._refresh_list()
        self._list.setCurrentRow(row - 1)

    def _on_move_down(self):
        self._sync_from_list()
        row = self._list.currentRow()
        if row < 0 or row >= len(self._columns) - 1:
            return
        self._columns[row], self._columns[row + 1] = (
            self._columns[row + 1], self._columns[row]
        )
        self._refresh_list()
        self._list.setCurrentRow(row + 1)

    def _on_save(self):
        self._sync_from_list()
        if not self._columns:
            QMessageBox.warning(self, "Ação inválida", "Adicione ao menos uma coluna.")
            return
        _save_columns(self._columns)
        self.accept()


# ── Dialog auxiliar: mover pedidos antes de excluir coluna ────────────────────

class _MoveOrdersDialog(QDialog):
    def __init__(self, column: str, order_count: int, destinations: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mover Pedidos")
        self.setModal(True)
        self.setFixedWidth(380)
        self._build_ui(column, order_count, destinations)

    def _build_ui(self, column: str, n: int, destinations: list[str]):
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(18, 18, 18, 18)

        msg = QLabel(
            f'A coluna "{column}" possui {n} pedido{"s" if n > 1 else ""}.\n'
            "Selecione para qual coluna movê-los antes de excluir:"
        )
        msg.setWordWrap(True)
        root.addWidget(msg)

        self._combo = QComboBox()
        for d in destinations:
            self._combo.addItem(d)
        root.addWidget(self._combo)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Mover e Excluir")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    def destination(self) -> str:
        return self._combo.currentText()
