import zipfile
from pathlib import Path

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap

from modules.preview.cache import thumbnail_cache

THUMB_SIZE = 280  # max px on either axis

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif"}
_PDF_EXTS   = {".pdf"}
_CDR_EXTS   = {".cdr"}


def _scale(pixmap: QPixmap) -> QPixmap:
    return pixmap.scaled(
        THUMB_SIZE,
        THUMB_SIZE,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def _render_pdf(path: str) -> QPixmap | None:
    try:
        import fitz  # PyMuPDF
        doc  = fitz.open(path)
        page = doc[0]
        mat  = fitz.Matrix(2, 2)
        pix  = page.get_pixmap(matrix=mat)
        img  = QImage(
            pix.samples, pix.width, pix.height,
            pix.stride, QImage.Format.Format_RGB888,
        )
        doc.close()
        return _scale(QPixmap.fromImage(img))
    except Exception:
        return None


def _render_cdr(path: str) -> QPixmap | None:
    # ── Tentativa 1: CDR baseado em ZIP (CorelDRAW X6+) ──────────────────────
    try:
        with zipfile.ZipFile(path, "r") as z:
            names = z.namelist()
            for candidate in names:
                low = candidate.lower()
                if "preview" in low or "thumbnail" in low:
                    data = z.read(candidate)
                    px = QPixmap()
                    if px.loadFromData(bytes(data)):
                        return _scale(px)
    except Exception:
        pass

    # ── Tentativa 2: CDR RIFF antigo — procura JPEG embutido no binário ───────
    try:
        # Lê até 4 MB para encontrar o preview JPEG
        max_read = 4 * 1024 * 1024
        with open(path, "rb") as f:
            raw = f.read(max_read)

        soi = b"\xff\xd8\xff"   # JPEG Start of Image
        eoi = b"\xff\xd9"       # JPEG End of Image

        idx = raw.find(soi)
        while idx != -1:
            end = raw.find(eoi, idx + 3)
            if end != -1:
                jpeg_bytes = raw[idx : end + 2]
                px = QPixmap()
                if px.loadFromData(jpeg_bytes, "JPEG"):
                    scaled = _scale(px)
                    if not scaled.isNull():
                        return scaled
            idx = raw.find(soi, idx + 1)
    except Exception:
        pass

    return None


def render_thumbnail(path: str) -> QPixmap | None:
    """Synchronous render — call only from a worker thread."""
    ext = Path(path).suffix.lower()

    if ext in _IMAGE_EXTS:
        px = QPixmap(path)
        return _scale(px) if not px.isNull() else None

    if ext in _PDF_EXTS:
        return _render_pdf(path)

    if ext in _CDR_EXTS:
        return _render_cdr(path)

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
