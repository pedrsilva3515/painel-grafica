import json
import time
from pathlib import Path

import bcrypt
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox,
)

CONFIG_DIR  = Path(__file__).parent.parent / "config"
AUTH_FILE   = CONFIG_DIR / "auth.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"


# ── Low-level helpers ──────────────────────────────────────────────────────────

def _load_settings() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"session_hours": 8}


def _load_auth() -> dict:
    try:
        return json.loads(AUTH_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_auth(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    AUTH_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Public API ─────────────────────────────────────────────────────────────────

def is_first_run() -> bool:
    return not bool(_load_auth().get("hash"))


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


def set_password(password: str) -> None:
    data = _load_auth()
    data["hash"] = hash_password(password)
    data.setdefault("session_start", None)
    _save_auth(data)


def save_session() -> None:
    data = _load_auth()
    data["session_start"] = time.time()
    _save_auth(data)


def clear_session() -> None:
    data = _load_auth()
    data["session_start"] = None
    _save_auth(data)


def is_session_valid() -> bool:
    data = _load_auth()
    session_start = data.get("session_start")
    if not session_start:
        return False
    session_hours = _load_settings().get("session_hours", 8)
    return (time.time() - session_start) < session_hours * 3600


# ── Dialogs ────────────────────────────────────────────────────────────────────

class SetPasswordDialog(QDialog):
    """Shown on first run and when the user wants to change the password."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Painel Gráfica — Definir Senha")
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setModal(True)
        self.setFixedWidth(380)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(28, 28, 28, 28)

        title = QLabel("Criar Senha de Acesso")
        title.setObjectName("authTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Esta senha será solicitada ao iniciar o Painel Gráfica."
        )
        subtitle.setObjectName("authSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        self._pw_input = QLineEdit()
        self._pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw_input.setPlaceholderText("Nova senha")
        self._pw_input.setObjectName("authInput")
        layout.addWidget(self._pw_input)

        self._confirm_input = QLineEdit()
        self._confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm_input.setPlaceholderText("Confirmar senha")
        self._confirm_input.setObjectName("authInput")
        self._confirm_input.returnPressed.connect(self._on_confirm)
        layout.addWidget(self._confirm_input)

        layout.addSpacing(4)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        confirm_btn = QPushButton("Confirmar")
        confirm_btn.setObjectName("authPrimaryBtn")
        confirm_btn.clicked.connect(self._on_confirm)
        btn_row.addWidget(confirm_btn)
        layout.addLayout(btn_row)

    def _on_confirm(self):
        pw = self._pw_input.text()
        confirm = self._confirm_input.text()

        if len(pw) < 4:
            QMessageBox.warning(
                self, "Senha inválida", "A senha deve ter pelo menos 4 caracteres."
            )
            return

        if pw != confirm:
            QMessageBox.warning(self, "Senhas diferentes", "As senhas não coincidem.")
            self._confirm_input.clear()
            self._confirm_input.setFocus()
            return

        set_password(pw)
        self.accept()


class AuthDialog(QDialog):
    """Login screen shown when no valid session exists."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Painel Gráfica")
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setModal(True)
        self.setFixedWidth(380)
        self._attempts = 0
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(28, 28, 28, 28)

        title = QLabel("Painel Gráfica")
        title.setObjectName("authTitle")
        layout.addWidget(title)

        subtitle = QLabel("Digite sua senha para continuar.")
        subtitle.setObjectName("authSubtitle")
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        self._pw_input = QLineEdit()
        self._pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw_input.setPlaceholderText("Senha")
        self._pw_input.setObjectName("authInput")
        self._pw_input.returnPressed.connect(self._on_login)
        layout.addWidget(self._pw_input)

        self._error_label = QLabel("")
        self._error_label.setObjectName("authError")
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        layout.addSpacing(4)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        login_btn = QPushButton("Entrar")
        login_btn.setObjectName("authPrimaryBtn")
        login_btn.clicked.connect(self._on_login)
        btn_row.addWidget(login_btn)
        layout.addLayout(btn_row)

    def _on_login(self):
        pw = self._pw_input.text()
        stored_hash = _load_auth().get("hash", "")

        if verify_password(pw, stored_hash):
            save_session()
            self.accept()
        else:
            self._attempts += 1
            self._pw_input.clear()
            self._error_label.setText(f"Senha incorreta. (tentativa {self._attempts})")
            self._error_label.setVisible(True)
            self._pw_input.setFocus()


# ── Entry point ────────────────────────────────────────────────────────────────

def run_auth() -> bool:
    """
    Execute the full authentication flow.
    Returns True if the user is authenticated, False if they cancelled.
    """
    if is_first_run():
        dlg = SetPasswordDialog()
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return False
        save_session()
        return True

    if is_session_valid():
        return True

    dlg = AuthDialog()
    return dlg.exec() == QDialog.DialogCode.Accepted
