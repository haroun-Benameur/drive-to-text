"""Tesseract OCR engine wrapper."""

import logging
import os

import pytesseract
from PIL import Image
from pytesseract import TesseractNotFoundError

from app.config import Settings
from app.errors import AppError, safe_text

logger = logging.getLogger(__name__)

# Languages accepted for extraction.
ALLOWED_LANGUAGES: set[str] = {"fra", "eng", "ara", "fra+eng", "fra+eng+ara"}


def validate_language(lang: str) -> str:
    """Return *lang* if it is allowed, otherwise raise INVALID_LANGUAGE (422)."""
    if lang not in ALLOWED_LANGUAGES:
        allowed = ", ".join(sorted(ALLOWED_LANGUAGES))
        raise AppError(
            "INVALID_LANGUAGE",
            f"Language '{safe_text(lang)}' is not supported. Allowed values: {allowed}.",
            422,
        )
    return lang


class TesseractOcr:
    """OcrEngine implementation backed by Tesseract via pytesseract."""

    def __init__(self, settings: Settings) -> None:
        self._timeout = settings.ocr_page_timeout_s

        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

        if settings.tessdata_prefix:
            os.environ["TESSDATA_PREFIX"] = settings.tessdata_prefix

        # Prevent Tesseract from spawning many threads per page.
        os.environ.setdefault("OMP_THREAD_LIMIT", "1")

    def version(self) -> str:
        """Return the Tesseract version string."""
        try:
            return str(pytesseract.get_tesseract_version())
        except TesseractNotFoundError as exc:
            raise AppError(
                "OCR_ENGINE_UNAVAILABLE",
                "Tesseract OCR engine is not available.",
                503,
            ) from exc

    def available_languages(self) -> list[str]:
        """Return the list of installed Tesseract language codes."""
        try:
            return pytesseract.get_languages()
        except TesseractNotFoundError as exc:
            raise AppError(
                "OCR_ENGINE_UNAVAILABLE",
                "Tesseract OCR engine is not available.",
                503,
            ) from exc

    def ocr_image(self, image: Image.Image, language: str) -> str:
        """Return OCR text for *image* using *language*."""
        try:
            return pytesseract.image_to_string(
                image, lang=language, timeout=self._timeout
            )
        except TesseractNotFoundError as exc:
            raise AppError(
                "OCR_ENGINE_UNAVAILABLE",
                "Tesseract OCR engine is not available.",
                503,
            ) from exc
        except RuntimeError as exc:
            # pytesseract raises RuntimeError on timeout
            if "timeout" in str(exc).lower():
                raise AppError(
                    "OCR_TIMEOUT",
                    "OCR timed out processing this page.",
                    422,
                ) from exc
            raise
