from collections import OrderedDict

from PyQt6.QtGui import QPixmap


class ThumbnailCache:
    """LRU in-memory cache for rendered QPixmap thumbnails."""

    def __init__(self, max_size: int = 50):
        self._store: OrderedDict[str, QPixmap] = OrderedDict()
        self._max = max_size

    def get(self, path: str) -> QPixmap | None:
        if path in self._store:
            self._store.move_to_end(path)
            return self._store[path]
        return None

    def put(self, path: str, pixmap: QPixmap) -> None:
        if path in self._store:
            self._store.move_to_end(path)
        else:
            self._store[path] = pixmap
            if len(self._store) > self._max:
                self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()


# Singleton shared across the whole app
thumbnail_cache = ThumbnailCache()
