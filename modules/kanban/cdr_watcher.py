import os
import time
from pathlib import Path

from PyQt6.QtCore import QFileSystemWatcher, QObject, QTimer, pyqtSignal

import modules.kanban.board as board


class CdrWatcher(QObject):
    """
    Watches a folder for new .cdr files using QFileSystemWatcher.
    When a new file is detected, automatically creates a Kanban entry:
      · title      = filename without extension
      · created_at = file creation time (os.path.getctime)
    """

    order_created = pyqtSignal(str, int)   # title, order_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._watcher       = QFileSystemWatcher(self)
        self._watch_folder: str | None = None
        self._known_files:  set[str]   = set()

        self._watcher.directoryChanged.connect(self._on_dir_changed)

        # Small debounce so we don't fire while CorelDRAW is still writing
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(2_000)   # 2 s
        self._debounce.timeout.connect(self._process_new_files)
        self._pending_dir: str | None = None

    # ── Public API ────────────────────────────────────────────────────────────

    def set_folder(self, folder: str) -> None:
        """Start (or switch) watching a folder. Empty string disables."""
        if self._watch_folder:
            self._watcher.removePath(self._watch_folder)
            self._known_files.clear()
            self._watch_folder = None

        folder = folder.strip()
        if not folder or not os.path.isdir(folder):
            return

        self._watch_folder = folder
        self._known_files  = self._scan(folder)
        self._watcher.addPath(folder)

    # ── Internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _scan(folder: str) -> set[str]:
        try:
            return {
                f for f in os.listdir(folder)
                if f.lower().endswith(".cdr")
            }
        except OSError:
            return set()

    def _on_dir_changed(self, path: str):
        self._pending_dir = path
        self._debounce.start()

    def _process_new_files(self):
        if not self._watch_folder:
            return

        current   = self._scan(self._watch_folder)
        new_files = current - self._known_files
        self._known_files = current

        for fname in new_files:
            fpath = os.path.join(self._watch_folder, fname)
            title = Path(fname).stem

            try:
                created_at = os.path.getctime(fpath)
            except OSError:
                created_at = time.time()

            order_id = board.add_order(
                title      = title,
                notes      = f"Auto-criado a partir de: {fname}",
                created_at = created_at,
            )
            self.order_created.emit(title, order_id)
