import os
import time
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from data.db import get_connection


def search_files(query: str, limit: int = 50) -> list[dict]:
    """Full-text LIKE search on the file_index table."""
    if not query.strip():
        return []
    pattern = f"%{query.strip()}%"
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT filename, filepath, folder, extension, size, modified_at
            FROM   file_index
            WHERE  filename LIKE ?
            ORDER  BY modified_at DESC
            LIMIT  ?
            """,
            (pattern, limit),
        ).fetchall()
    return [dict(r) for r in rows]


class FileIndexWorker(QThread):
    """
    Walks all monitored folders and upserts file metadata into file_index.
    Runs in a background QThread — never blocks the UI.
    """

    finished = pyqtSignal(int)  # number of files indexed

    def __init__(self, folders: list[str], parent=None):
        super().__init__(parent)
        self._folders = folders

    def run(self):
        count = 0
        with get_connection() as conn:
            for folder in self._folders:
                if not os.path.isdir(folder):
                    continue
                for root, _dirs, files in os.walk(folder):
                    for fname in files:
                        fpath = os.path.join(root, fname)
                        ext = Path(fname).suffix.lower().lstrip(".")
                        try:
                            stat = os.stat(fpath)
                            conn.execute(
                                """
                                INSERT INTO file_index
                                    (filename, filepath, folder, extension, size, modified_at)
                                VALUES (?, ?, ?, ?, ?, ?)
                                ON CONFLICT(filepath) DO UPDATE SET
                                    filename    = excluded.filename,
                                    modified_at = excluded.modified_at,
                                    size        = excluded.size,
                                    indexed_at  = unixepoch()
                                """,
                                (fname, fpath, folder, ext, stat.st_size, stat.st_mtime),
                            )
                            count += 1
                        except OSError:
                            pass
                    conn.commit()
        self.finished.emit(count)
