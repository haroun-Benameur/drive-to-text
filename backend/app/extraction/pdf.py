"""PDF text extraction using pypdf."""

from io import BytesIO

import pypdf
from pypdf import PdfReader
from pypdf.errors import DependencyError, PdfReadError

from app.config import Settings
from app.errors import AppError
from app.models import ExtractionMethod, ExtractionResult

_ENGINE = f"pypdf {pypdf.__version__}"


class PdfExtractor:
    """Extract selectable text from PDF bytes using pypdf."""

    def __init__(self, settings: Settings) -> None:
        self._max_pages = settings.max_pdf_pages

    def extract(self, data: bytes, language: str) -> ExtractionResult:  # noqa: ARG002
        """Return text extracted from *data*.

        ``language`` is accepted for interface compatibility but is not used
        by this extractor (pypdf does not perform OCR).
        """
        try:
            reader = PdfReader(BytesIO(data))
        except (PdfReadError, Exception) as exc:
            raise AppError(
                "CORRUPTED_FILE", "The PDF could not be read.", 422
            ) from exc

        if reader.is_encrypted:
            try:
                result = reader.decrypt("")
                # decrypt() returns a DecryptionError enum; 0 means failure
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
        for i in range(pages_to_read):
            try:
                text = reader.pages[i].extract_text() or ""
            except Exception:
                text = ""
            page_texts.append(text)

        full_text = "\n\n".join(page_texts)

        alnum_count = sum(1 for ch in full_text if ch.isalnum())
        if alnum_count == 0:
            warnings.append("NO_TEXT_FOUND")

        return ExtractionResult(
            text=full_text,
            method=ExtractionMethod.PDF_TEXT,
            engine=_ENGINE,
            page_count=total_pages,
            ocr_pages=0,
            warnings=warnings,
        )
