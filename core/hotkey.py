import json
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, pyqtSignal

SETTINGS_FILE = Path(__file__).parent.parent / "config" / "settings.json"


def _default_hotkey() -> str:
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return data.get("hotkey", "ctrl+space")
    except Exception:
        return "ctrl+space"


class _HotkeyWorker(QThread):
    triggered = pyqtSignal()

    def __init__(self, hotkey: str, parent=None):
        super().__init__(parent)
        self._hotkey = hotkey
        self._active = False

    def run(self):
        import keyboard  # late import — optional dependency

        self._active = True
        keyboard.add_hotkey(self._hotkey, self.triggered.emit)
        # Block this thread so keyboard keeps listening
        keyboard.wait()

    def stop(self):
        if self._active:
            try:
                import keyboard
                keyboard.remove_hotkey(self._hotkey)
                keyboard.unhook_all()
            except Exception:
                pass
        self.quit()
        self.wait()


class HotkeyManager(QObject):
    """
    Registers a global hotkey using the `keyboard` library running in a
    dedicated QThread so the Qt event loop is never blocked.
    """

    triggered = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hotkey = _default_hotkey()
        self._worker: _HotkeyWorker | None = None

    def start(self) -> None:
        self._worker = _HotkeyWorker(self._hotkey, self)
        self._worker.triggered.connect(self.triggered)
        self._worker.start()

    def stop(self) -> None:
        if self._worker:
            self._worker.stop()
            self._worker = None

    @property
    def hotkey(self) -> str:
        return self._hotkey
