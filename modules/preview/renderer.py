from pathlib import Path

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap

from modules.preview.cache import thumbnail_cache

THUMB_SIZE = 280  # max px on either axis

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif"}
_PDF_EXTS   = {".pdf"}


def _scale(pixmap: QPixmap) -> QPixmap:
    return pixmap.scaled(
        THUMB_SIZE,
        THUMB_SIZE,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def render_thumbnail(path: str) -> QPixmap | None:
    """Synchronous render — call only from a worker thread."""
    ext = Path(path).suffix.lower()

    if ext in _IMAGE_EXTS:
        px = QPixmap(path)
        return _scale(px) if not px.isNull() else None

    if ext in _PDF_EXTS:
        try:
            import fitz  # PyMuPDF

            doc  = fitz.open(path)
            page = doc[0]
            mat  = fitz.Matrix(2, 2)   # 2× zoom for a sharper thumbnail
            pix  = page.get_pixmap(matrix=mat)
            img  = QImage(
                pix.samples, pix.width, pix.height,
                pix.stride, QImage.Format.Format_RGB888,
            )
            doc.close()
            return _scale(QPixmap.fromImage(img))
        except Exception:
            return None

    return None


class ThumbnailWorker(QThread):
    """
    Renders a thumbnail in a background QThread and emits the result.
    Checks the cache first — only renders if not cached.
    """

    ready = pyqtSignal(str, QPixmap)  # (filepath, pixmap)

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self._path = path

    def run(self):
        cached = thumbnail_cache.get(self._path)
        if cached:
            self.ready.emit(self._path, cached)
            return

        pixmap = render_thumbnail(self._path)
        if pixmap and not pixmap.isNull():
            thumbnail_cache.put(self._path, pixmap)
            self.ready.emit(self._path, pixmap)
