"""PDF text extraction using pypdf, with pdfium+Tesseract OCR fallback."""

import logging
import re
import threading
import time
import unicodedata
from io import BytesIO
from typing import TYPE_CHECKING

import pypdf
from PIL import Image
from pypdf import PdfReader
from pypdf.errors import DependencyError

from app.config import Settings
from app.errors import AppError
from app.models import ExtractionMethod, ExtractionResult

if TYPE_CHECKING:
    from app.extraction.base import OcrEngine

logger = logging.getLogger(__name__)

_ENGINE_PYPDF = f"pypdf {pypdf.__version__}"
_CID_RE = re.compile(r"\(cid:\d+\)")

# Single lock guards all pypdfium2 calls (not thread-safe on its own).
_PDFIUM_LOCK = threading.Lock()


def looks_like_garbage(text: str) -> bool:
    """Return True when *text* is mostly replacement, cid, or control characters.

    True only when there are at least 10 non-whitespace characters and more
    than 30% of them are U+FFFD, ``(cid:N)`` sequences, or control/private-use
    characters. Newline and tab are ignored.
    """
    cid_indexes: set[int] = set()
    for match in _CID_RE.finditer(text):
        cid_indexes.update(range(match.start(), match.end()))
    non_whitespace = 0
    bad = 0
    for index, char in enumerate(text):
        if char.isspace():
            continue
        non_whitespace += 1
        if index in cid_indexes or _is_garbage_char(char):
            bad += 1
    if non_whitespace < 10:
        return False
    return bad / non_whitespace > 0.3


def _is_garbage_char(char: str) -> bool:
    """Return True for U+FFFD, controls, and private-use characters."""
    if char in "\n\t":
        return False
    if char == "\ufffd":
        return True
    return unicodedata.category(char) in {"Cc", "Co"}


def decide_method(total_pages: int, ocr_pages: int) -> ExtractionMethod:
    """Return the appropriate ExtractionMethod given page counts."""
    if ocr_pages == 0:
        return ExtractionMethod.PDF_TEXT
    if ocr_pages == total_pages:
        return ExtractionMethod.OCR
    return ExtractionMethod.PDF_TEXT_OCR


# ---------------------------------------------------------------------------
# Encryption helper
# ---------------------------------------------------------------------------


def _handle_encryption(reader: PdfReader) -> None:
    """Raise PDF_ENCRYPTED when *reader* is password-protected."""
    if not reader.is_encrypted:
        return
    try:
        result = reader.decrypt("")
        if result == 0:
            raise AppError("PDF_ENCRYPTED", "The PDF is password-protected.", 422)
    except DependencyError as exc:
        raise AppError(
            "PDF_ENCRYPTED", "The PDF is password-protected.", 422
        ) from exc
    except AppError:
        raise
    except Exception as exc:
        raise AppError(
            "PDF_ENCRYPTED", "The PDF is password-protected.", 422
        ) from exc


# ---------------------------------------------------------------------------
# Lazy pdfium context manager
# ---------------------------------------------------------------------------


class _PdfiumPages:
    """Context manager that opens a pdfium document lazily ONCE.

    All pdfium calls (open, get page, get_size, text, render, close) run under
    the module-level :data:`_PDFIUM_LOCK`.  OCR itself runs OUTSIDE the lock.
    """

    def __init__(self, pdf_data: bytes) -> None:
        self._data = pdf_data
        self._doc = None

    def __enter__(self) -> "_PdfiumPages":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _ensure_open(self) -> None:
        if self._doc is not None:
            return
        import pypdfium2

        with _PDFIUM_LOCK:
            if self._doc is None:
                self._doc = pypdfium2.PdfDocument(BytesIO(self._data))

    def close(self) -> None:
        if self._doc is not None:
            with _PDFIUM_LOCK:
                self._doc.close()
            self._doc = None

    def render_page(
        self, page_index: int, scale: float, max_pixels: int
    ) -> Image.Image | None:
        """Render page *page_index* to a PIL image.

        Returns ``None`` when the rendered pixel count exceeds *max_pixels*.
        """
        self._ensure_open()
        with _PDFIUM_LOCK:
            page = self._doc[page_index]
            try:
                w_pt, h_pt = page.get_size()
                pixel_count = int(w_pt * scale) * int(h_pt * scale)
                if pixel_count > max_pixels:
                    return None
                bitmap = page.render(scale=scale)
                pil_image = bitmap.to_pil()
            finally:
                page.close()
        return pil_image

    def text(self, index: int) -> str:
        """Return the pdfium text for page *index*."""
        self._ensure_open()
        with _PDFIUM_LOCK:
            document = self._doc
            if document is None:
                return ""
            page = document[index]
            textpage = None
            try:
                textpage = page.get_textpage()
                return textpage.get_text_bounded() or ""
            finally:
                if textpage is not None:
                    textpage.close()
                page.close()


class PdfExtractor:
    """Extract text from PDF bytes, falling back to OCR for image-only pages."""

    def __init__(self, ocr: "OcrEngine", settings: Settings) -> None:
        self._ocr = ocr
        self._max_pages = settings.max_pdf_pages
        self._min_chars = settings.min_page_chars
        self._dpi = settings.ocr_render_dpi
        self._max_pixels = settings.max_image_pixels
        self._time_budget = settings.file_time_budget_s
        self._ocr_timeout = settings.ocr_page_timeout_s

    def extract(self, data: bytes, language: str) -> ExtractionResult:
        """Return text extracted from *data*, with per-page OCR fallback."""
        try:
            reader = PdfReader(BytesIO(data))
        except Exception as exc:
            raise AppError(
                "CORRUPTED_FILE", "The PDF could not be read.", 422
            ) from exc

        _handle_encryption(reader)

        total_pages = len(reader.pages)
        pages_to_read = min(total_pages, self._max_pages)
        warnings: list[str] = []

        if total_pages > self._max_pages:
            warnings.append("TRUNCATED")

        page_texts: list[str] = []
        ocr_pages = 0
        used_pdfium_text = False
        t_start = time.monotonic()
        scale = self._dpi / 72.0

        with _PdfiumPages(data) as pdfium:
            for i in range(pages_to_read):
                # ── Remaining time budget ───────────────────────────────────
                elapsed = time.monotonic() - t_start
                remaining = self._time_budget - elapsed
                if remaining <= 0:
                    if "TRUNCATED" not in warnings:
                        warnings.append("TRUNCATED")
                    break

                # ── pypdf native text ───────────────────────────────────────
                pypdf_failed = False
                try:
                    text = reader.pages[i].extract_text() or ""
                except Exception:
                    logger.debug(
                        "pypdf extract_text failed on page %d", i, exc_info=True
                    )
                    text = ""
                    pypdf_failed = True

                if pypdf_failed or looks_like_garbage(text):
                    candidate = pdfium.text(i)
                    if not looks_like_garbage(candidate):
                        text = candidate
                        if not used_pdfium_text:
                            warnings.append("PDFIUM_TEXT_FALLBACK")
                            used_pdfium_text = True

                alnum = sum(1 for ch in text if ch.isalnum())
                if alnum < self._min_chars:
                    # ── OCR fallback via pdfium ──────────────────────────────
                    pil_image = pdfium.render_page(i, scale, self._max_pixels)
                    if pil_image is None:
                        warnings.append("PAGE_TOO_LARGE")
                    else:
                        # OCR runs OUTSIDE the pdfium lock
                        ocr_timeout = min(self._ocr_timeout, remaining)
                        ocr_text = self._ocr.ocr_image(
                            pil_image, language, timeout=ocr_timeout
                        )
                        text = ocr_text
                        ocr_pages += 1

                page_texts.append(text)

        full_text = "\n\n".join(page_texts)
        alnum_total = sum(1 for ch in full_text if ch.isalnum())
        if alnum_total == 0:
            warnings.append("NO_TEXT_FOUND")

        method = decide_method(len(page_texts), ocr_pages)

        if ocr_pages > 0:
            engine = (
                f"pypdf {pypdf.__version__}"
                f" + pdfium"
                f" + tesseract {self._ocr.version()}"
            )
        elif used_pdfium_text:
            engine = f"{_ENGINE_PYPDF} + pdfium"
        else:
            engine = _ENGINE_PYPDF

        return ExtractionResult(
            text=full_text,
            method=method,
            engine=engine,
            page_count=total_pages,
            ocr_pages=ocr_pages,
            warnings=warnings,
        )