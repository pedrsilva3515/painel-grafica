import json
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QPushButton, QSpinBox, QTabWidget, QTimeEdit, QVBoxLayout,
    QWidget, QCheckBox,
)
from PyQt6.QtCore import QTime

SETTINGS_FILE = Path(__file__).parent.parent / "config" / "settings.json"


def _load() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict) -> None:
    SETTINGS_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


class SettingsDialog(QDialog):
    """
    Visual settings editor.
    Signals:
      saved — emitted after the user clicks Salvar; caller should
              restart the indexer and apply any changed settings.
    """

    saved = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurações — Painel Gráfica")
        self.setModal(True)
        self.setMinimumWidth(560)
        self._data = _load()
        self._build_ui()
        self._populate()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        self._tabs = QTabWidget()
        self._tabs.setObjectName("settingsTabs")
        layout.addWidget(self._tabs)

        self._tabs.addTab(self._tab_geral(),   "⚙️  Geral")
        self._tabs.addTab(self._tab_pastas(),  "📁  Pastas Monitoradas")
        self._tabs.addTab(self._tab_kanban(),  "📋  Kanban / CDR")
        self._tabs.addTab(self._tab_preview(), "🖼️  Preview")

        # OK / Cancel
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Save).setText("Salvar")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        btns.accepted.connect(self._on_save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    # ── Tab: Geral ────────────────────────────────────────────────────────────

    def _tab_geral(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(14)
        layout.setContentsMargins(16, 16, 16, 16)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._hotkey_input = QLineEdit()
        self._hotkey_input.setPlaceholderText("ex: ctrl+space")
        form.addRow("Hotkey global:", self._hotkey_input)

        self._session_spin = QSpinBox()
        self._session_spin.setRange(1, 72)
        self._session_spin.setSuffix(" horas")
        form.addRow("Duração da sessão:", self._session_spin)

        layout.addLayout(form)

        # Daily panel group
        grp = QGroupBox("Painel Diário")
        grp.setObjectName("settingsGroup")
        grp_layout = QFormLayout(grp)
        grp_layout.setSpacing(10)
        grp_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._daily_enabled = QCheckBox("Ativar abertura automática")
        grp_layout.addRow("", self._daily_enabled)

        self._daily_time = QTimeEdit()
        self._daily_time.setDisplayFormat("HH:mm")
        grp_layout.addRow("Horário:", self._daily_time)

        self._daily_close_spin = QSpinBox()
        self._daily_close_spin.setRange(5, 120)
        self._daily_close_spin.setSuffix(" min")
        grp_layout.addRow("Fechar automaticamente após:", self._daily_close_spin)

        layout.addWidget(grp)
        layout.addStretch()
        return w

    # ── Tab: Pastas Monitoradas ───────────────────────────────────────────────

    def _tab_pastas(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        info = QLabel(
            "As pastas abaixo são indexadas para busca no Command Palette.\n"
            "Subpastas são incluídas automaticamente."
        )
        info.setObjectName("settingsInfo")
        info.setWordWrap(True)
        layout.addWidget(info)

        self._folder_list = QListWidget()
        self._folder_list.setObjectName("settingsFolderList")
        layout.addWidget(self._folder_list)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Adicionar Pasta")
        add_btn.setObjectName("primaryBtn")
        add_btn.clicked.connect(self._on_add_folder)
        btn_row.addWidget(add_btn)

        rem_btn = QPushButton("— Remover Selecionada")
        rem_btn.clicked.connect(self._on_remove_folder)
        btn_row.addWidget(rem_btn)

        btn_row.addStretch()

        reindex_btn = QPushButton("↻ Reindexar Agora")
        reindex_btn.clicked.connect(self._on_reindex)
        btn_row.addWidget(reindex_btn)

        layout.addLayout(btn_row)
        return w

    # ── Tab: Kanban / CDR ─────────────────────────────────────────────────────

    def _tab_kanban(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(14)
        layout.setContentsMargins(16, 16, 16, 16)

        # Columns management
        grp_cols = QGroupBox("Colunas do Kanban")
        grp_cols.setObjectName("settingsGroup")
        grp_cols_layout = QVBoxLayout(grp_cols)

        cols_info = QLabel("Adicione, renomeie, reordene ou exclua colunas do quadro Kanban.")
        cols_info.setObjectName("settingsInfo")
        cols_info.setWordWrap(True)
        grp_cols_layout.addWidget(cols_info)

        manage_btn = QPushButton("⚙️  Gerenciar Colunas…")
        manage_btn.setObjectName("primaryBtn")
        manage_btn.clicked.connect(self._on_manage_columns)
        grp_cols_layout.addWidget(manage_btn)

        layout.addWidget(grp_cols)

        grp = QGroupBox("Inserção Automática de O.S. via CorelDRAW (.cdr)")
        grp.setObjectName("settingsGroup")
        grp_layout = QVBoxLayout(grp)
        grp_layout.setSpacing(8)

        desc = QLabel(
            "Quando um novo arquivo .cdr for criado nesta pasta, o Painel Gráfica\n"
            "cria automaticamente uma nova O.S. no Kanban com o nome do arquivo\n"
            "e a hora de criação do arquivo."
        )
        desc.setObjectName("settingsInfo")
        desc.setWordWrap(True)
        grp_layout.addWidget(desc)

        row = QHBoxLayout()
        self._cdr_folder_input = QLineEdit()
        self._cdr_folder_input.setPlaceholderText("Nenhuma pasta configurada")
        self._cdr_folder_input.setReadOnly(True)
        row.addWidget(self._cdr_folder_input)

        browse_btn = QPushButton("Escolher…")
        browse_btn.clicked.connect(self._on_browse_cdr)
        row.addWidget(browse_btn)

        clear_btn = QPushButton("Limpar")
        clear_btn.clicked.connect(lambda: self._cdr_folder_input.clear())
        row.addWidget(clear_btn)

        grp_layout.addLayout(row)
        layout.addWidget(grp)

        # Print folders
        grp_print = QGroupBox("Pastas de Impressão")
        grp_print.setObjectName("settingsGroup")
        grp_print_layout = QFormLayout(grp_print)
        grp_print_layout.setSpacing(8)
        grp_print_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._print_folder_inputs: dict[str, QLineEdit] = {}
        for material, obj_name in [
            ("Adesivo", "printFolderAdesivo"),
            ("Lona",    "printFolderLona"),
            ("Papel",   "printFolderPapel"),
        ]:
            field = QLineEdit()
            field.setObjectName(obj_name)
            field.setReadOnly(True)
            field.setPlaceholderText("Nenhuma pasta configurada")
            self._print_folder_inputs[material] = field

            row_w = QWidget()
            row_h = QHBoxLayout(row_w)
            row_h.setContentsMargins(0, 0, 0, 0)
            row_h.addWidget(field)

            browse = QPushButton("Escolher…")
            browse.clicked.connect(
                lambda _checked, m=material: self._on_browse_print_folder(m)
            )
            row_h.addWidget(browse)

            clear = QPushButton("Limpar")
            clear.clicked.connect(
                lambda _checked, m=material: self._print_folder_inputs[m].clear()
            )
            row_h.addWidget(clear)

            grp_print_layout.addRow(f"{material}:", row_w)

        layout.addWidget(grp_print)

        # Alert thresholds (read-only info for now)
        grp2 = QGroupBox("Alertas de Pedido Parado")
        grp2.setObjectName("settingsGroup")
        grp2_layout = QVBoxLayout(grp2)
        info2 = QLabel(
            "Thresholds atuais (configuráveis em settings.json):\n"
            "  • Arte Final → alerta após 4h\n"
            "  • Produção   → alerta após 8h"
        )
        info2.setObjectName("settingsInfo")
        grp2_layout.addWidget(info2)
        layout.addWidget(grp2)

        layout.addStretch()
        return w

    # ── Tab: Preview ──────────────────────────────────────────────────────────

    def _tab_preview(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(14)
        layout.setContentsMargins(16, 16, 16, 16)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._preview_enabled = QCheckBox("Ativar preview de arquivos no Command Palette")
        form.addRow("", self._preview_enabled)

        self._preview_max_mb = QSpinBox()
        self._preview_max_mb.setRange(1, 500)
        self._preview_max_mb.setSuffix(" MB")
        form.addRow("Tamanho máximo para preview:", self._preview_max_mb)

        layout.addLayout(form)

        info = QLabel(
            "Extensões suportadas para preview:\n"
            "  Imagens: PNG, JPG, JPEG, BMP, WEBP\n"
            "  Documentos: PDF (renderiza primeira página via PyMuPDF)"
        )
        info.setObjectName("settingsInfo")
        layout.addWidget(info)
        layout.addStretch()
        return w

    # ── Populate from data ────────────────────────────────────────────────────

    def _populate(self):
        d = self._data

        # Geral
        self._hotkey_input.setText(d.get("hotkey", "ctrl+space"))
        self._session_spin.setValue(d.get("session_hours", 8))

        dp = d.get("daily_panel", {})
        self._daily_enabled.setChecked(dp.get("enabled", True))
        t_str = dp.get("time", "08:00").split(":")
        self._daily_time.setTime(QTime(int(t_str[0]), int(t_str[1])))
        self._daily_close_spin.setValue(dp.get("auto_close_minutes", 30))

        # Pastas
        self._folder_list.clear()
        for folder in d.get("monitored_folders", []):
            self._folder_list.addItem(folder)

        # Kanban / CDR
        self._cdr_folder_input.setText(d.get("cdr_watch_folder", ""))

        # Print folders
        pf = d.get("print_folders", {})
        for material, field in self._print_folder_inputs.items():
            field.setText(pf.get(material, ""))

        # Preview
        pv = d.get("preview", {})
        self._preview_enabled.setChecked(pv.get("enabled", True))
        self._preview_max_mb.setValue(pv.get("max_size_mb", 50))

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_add_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Selecionar pasta monitorada", ""
        )
        if folder:
            existing = [
                self._folder_list.item(i).text()
                for i in range(self._folder_list.count())
            ]
            if folder not in existing:
                self._folder_list.addItem(folder)

    def _on_remove_folder(self):
        row = self._folder_list.currentRow()
        if row >= 0:
            self._folder_list.takeItem(row)

    def _on_manage_columns(self):
        from ui.kanban_columns_dialog import KanbanColumnsDialog
        KanbanColumnsDialog(self).exec()

    def _on_browse_print_folder(self, material: str):
        folder = QFileDialog.getExistingDirectory(
            self, f"Selecionar pasta de impressão — {material}", ""
        )
        if folder:
            self._print_folder_inputs[material].setText(folder)

    def _on_browse_cdr(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Selecionar pasta para vigília de .cdr", ""
        )
        if folder:
            self._cdr_folder_input.setText(folder)

    def _on_reindex(self):
        folders = [
            self._folder_list.item(i).text()
            for i in range(self._folder_list.count())
        ]
        if not folders:
            return
        from modules.command_palette.actions.file_search import FileIndexWorker
        self._reindex_worker = FileIndexWorker(folders)
        self._reindex_worker.finished.connect(
            lambda n: None  # caller will show notification
        )
        self._reindex_worker.start()

    def _on_save(self):
        d = self._data

        d["hotkey"]       = self._hotkey_input.text().strip() or "ctrl+space"
        d["session_hours"] = self._session_spin.value()

        t = self._daily_time.time()
        d.setdefault("daily_panel", {})
        d["daily_panel"]["enabled"]            = self._daily_enabled.isChecked()
        d["daily_panel"]["time"]               = f"{t.hour():02d}:{t.minute():02d}"
        d["daily_panel"]["auto_close_minutes"] = self._daily_close_spin.value()

        d["monitored_folders"] = [
            self._folder_list.item(i).text()
            for i in range(self._folder_list.count())
        ]

        d["cdr_watch_folder"] = self._cdr_folder_input.text().strip()

        d.setdefault("print_folders", {})
        for material, field in self._print_folder_inputs.items():
            d["print_folders"][material] = field.text().strip()

        d.setdefault("preview", {})
        d["preview"]["enabled"]    = self._preview_enabled.isChecked()
        d["preview"]["max_size_mb"] = self._preview_max_mb.value()

        _save(d)
        self.saved.emit()
        self.accept()
