"""PDF text extraction using pypdf, with pdfium+Tesseract OCR fallback."""

import logging
import threading
import time
from io import BytesIO
from typing import TYPE_CHECKING

import pypdf
from pypdf import PdfReader
from pypdf.errors import DependencyError, PdfReadError

from app.config import Settings
from app.errors import AppError
from app.models import ExtractionMethod, ExtractionResult

if TYPE_CHECKING:
    from app.extraction.base import OcrEngine

logger = logging.getLogger(__name__)

_ENGINE_PYPDF = f"pypdf {pypdf.__version__}"

# Single lock guards all pypdfium2 calls (not thread-safe on its own).
_PDFIUM_LOCK = threading.Lock()


def decide_method(total_pages: int, ocr_pages: int) -> ExtractionMethod:
    """Return the appropriate ExtractionMethod given page counts."""
    if ocr_pages == 0:
        return ExtractionMethod.PDF_TEXT
    if ocr_pages == total_pages:
        return ExtractionMethod.OCR
    return ExtractionMethod.PDF_TEXT_OCR


class PdfExtractor:
    """Extract text from PDF bytes, falling back to OCR for image-only pages."""

    def __init__(self, ocr: "OcrEngine", settings: Settings) -> None:
        self._ocr = ocr
        self._max_pages = settings.max_pdf_pages
        self._min_chars = settings.min_page_chars
        self._dpi = settings.ocr_render_dpi
        self._max_pixels = settings.max_image_pixels
        self._time_budget = settings.file_time_budget_s

    def extract(self, data: bytes, language: str) -> ExtractionResult:
        """Return text extracted from *data*, with per-page OCR fallback."""
        try:
            reader = PdfReader(BytesIO(data))
        except (PdfReadError, Exception) as exc:
            raise AppError(
                "CORRUPTED_FILE", "The PDF could not be read.", 422
            ) from exc

        if reader.is_encrypted:
            try:
                result = reader.decrypt("")
                if result == 0:
                    raise AppError(
                        "PDF_ENCRYPTED",
                        "The PDF is password-protected.",
                        422,
                    )
            except DependencyError as exc:
                raise AppError(
                    "PDF_ENCRYPTED",
                    "The PDF is password-protected.",
                    422,
                ) from exc
            except AppError:
                raise
            except Exception as exc:
                raise AppError(
                    "PDF_ENCRYPTED",
                    "The PDF is password-protected.",
                    422,
                ) from exc

        total_pages = len(reader.pages)
        pages_to_read = min(total_pages, self._max_pages)
        warnings: list[str] = []

        if total_pages > self._max_pages:
            warnings.append("TRUNCATED")

        page_texts: list[str] = []
        ocr_pages = 0
        pdfium_doc = None
        t_start = time.monotonic()

        try:
            for i in range(pages_to_read):
                # Time-budget check between pages
                if time.monotonic() - t_start > self._time_budget:
                    if "TRUNCATED" not in warnings:
                        warnings.append("TRUNCATED")
                    break

                # Try pypdf native text extraction
                try:
                    text = reader.pages[i].extract_text() or ""
                except Exception:
                    text = ""

                alnum = sum(1 for ch in text if ch.isalnum())
                if alnum < self._min_chars:
                    # Fall back to OCR for this page
                    ocr_text = self._ocr_page(
                        data, i, language, warnings
                    )
                    if ocr_text is not None:
                        text = ocr_text
                        ocr_pages += 1

                page_texts.append(text)
        finally:
            if pdfium_doc is not None:
                with _PDFIUM_LOCK:
                    pdfium_doc.close()

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

    def _ocr_page(
        self,
        pdf_data: bytes,
        page_index: int,
        language: str,
        warnings: list[str],
    ) -> str | None:
        """Render page *page_index* with pdfium and OCR it.

        Returns the OCR text, or ``None`` if the page was skipped.
        Appends to *warnings* in-place.
        """
        import pypdfium2

        scale = self._dpi / 72.0

        with _PDFIUM_LOCK:
            doc = pypdfium2.PdfDocument(BytesIO(pdf_data))
            try:
                page = doc[page_index]
                try:
                    w_pt, h_pt = page.get_size()
                    pixel_count = int(w_pt * scale) * int(h_pt * scale)
                    if pixel_count > self._max_pixels:
                        warnings.append("PAGE_TOO_LARGE")
                        return None

                    bitmap = page.render(scale=scale)
                    pil_image = bitmap.to_pil()
                finally:
                    page.close()
            finally:
                doc.close()

        return self._ocr.ocr_image(pil_image, language)
