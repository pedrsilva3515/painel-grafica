import os
import time
from pathlib import Path

from PyQt6.QtCore import QFileSystemWatcher, QObject, QTimer, pyqtSignal

import modules.kanban.board as board


class CdrWatcher(QObject):
    """
    Watches a folder for .cdr file changes using QFileSystemWatcher.

    Detection strategy — uses ctime as file identity key:
      - ctime in both old and new, but filename changed → rename
      - ctime only in new                               → new file
      - ctime only in old                               → deleted (ignored)
    """

    order_created = pyqtSignal(str, int)        # title, order_id
    order_renamed = pyqtSignal(str, str, int)   # old_title, new_title, order_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._watcher       = QFileSystemWatcher(self)
        self._watch_folder: str | None = None
        self._known_files:  dict[float, str] = {}   # ctime → filename

        self._watcher.directoryChanged.connect(self._on_dir_changed)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(2_000)
        self._debounce.timeout.connect(self._process_new_files)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_folder(self, folder: str) -> None:
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
    def _scan(folder: str) -> dict[float, str]:
        """Returns {ctime: filename} for every .cdr file in folder."""
        result: dict[float, str] = {}
        try:
            for fname in os.listdir(folder):
                if not fname.lower().endswith(".cdr"):
                    continue
                fpath = os.path.join(folder, fname)
                try:
                    ctime = os.path.getctime(fpath)
                    result[ctime] = fname
                except OSError:
                    pass
        except OSError:
            pass
        return result

    def _on_dir_changed(self, _path: str):
        self._debounce.start()

    def _process_new_files(self):
        if not self._watch_folder:
            return

        current = self._scan(self._watch_folder)

        for ctime, fname in current.items():
            if ctime in self._known_files:
                old_fname = self._known_files[ctime]
                if old_fname != fname:
                    # Same ctime, different name → rename
                    old_title = Path(old_fname).stem
                    new_title = Path(fname).stem
                    self._handle_rename(old_title, new_title)
            else:
                # ctime not seen before → genuinely new file
                fpath = os.path.join(self._watch_folder, fname)
                try:
                    created_at = os.path.getctime(fpath)
                except OSError:
                    created_at = time.time()

                from modules.kanban.cdr_parser import parse_cdr_filename
                parsed = parse_cdr_filename(Path(fname).stem)
                order_id = board.add_order(
                    title       = parsed["title"],
                    os_number   = parsed["os_number"],
                    client_name = parsed["client_name"],
                    notes       = parsed["notes"],
                    created_at  = created_at,
                )
                self.order_created.emit(parsed["title"], order_id)

        self._known_files = current

    def _handle_rename(self, old_title: str, new_title: str):
        """Find the kanban card by title and update it."""
        from data.db import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM orders WHERE title = ? ORDER BY created_at DESC LIMIT 1",
                (old_title,),
            ).fetchone()

        if row:
            order_id = row["id"]
            board.update_order_title(order_id, new_title)
            self.order_renamed.emit(old_title, new_title, order_id)
        else:
            # No matching card found — treat as a new file to avoid data loss
            order_id = board.add_order(title=new_title)
            self.order_created.emit(new_title, order_id)
