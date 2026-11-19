"""Tesseract OCR engine wrapper."""

import logging
import os

import pytesseract
from PIL import Image
from pytesseract import TesseractNotFoundError

from app.config import Settings
from app.errors import AppError, safe_text
from app.models import OcrOutput

logger = logging.getLogger(__name__)

# Languages accepted for extraction.
ALLOWED_LANGUAGES: set[str] = {"fra", "eng", "ara", "fra+eng", "fra+eng+ara"}


def parse_tsv_confidence(tsv: str) -> float | None:
    """Return the mean word confidence, or None when *tsv* has no words.

    Only rows with non-empty text and a confidence of at least 0 count.
    When a ``level`` column is present, only word rows (level 5) count.
    The mean is rounded to one decimal place.
    """
    lines = [line for line in tsv.splitlines() if line.strip()]
    if not lines:
        return None
    header = lines[0].split("\t")
    try:
        conf_index = header.index("conf")
        text_index = header.index("text")
    except ValueError:
        return None
    level_index = header.index("level") if "level" in header else None

    values: list[float] = []
    for line in lines[1:]:
        columns = line.split("\t")
        if len(columns) <= max(conf_index, text_index):
            continue
        if level_index is not None and columns[level_index] != "5":
            continue
        if not columns[text_index].strip():
            continue
        try:
            confidence = float(columns[conf_index])
        except ValueError:
            continue
        if confidence >= 0:
            values.append(confidence)
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def _as_text(value: str | bytes) -> str:
    """Decode Tesseract output that may arrive as bytes."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


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

    def recognize(
        self,
        image: Image.Image,
        language: str,
        timeout: float | None = None,
    ) -> OcrOutput:
        """Return text and mean word confidence for *image* in one Tesseract run."""
        effective_timeout = timeout if timeout is not None else self._timeout
        try:
            text, tsv = self._text_and_tsv(image, language, effective_timeout)
        except TesseractNotFoundError as exc:
            raise AppError(
                "OCR_ENGINE_UNAVAILABLE",
                "Tesseract OCR engine is not available.",
                503,
            ) from exc
        except RuntimeError as exc:
            if "timeout" in str(exc).lower():
                raise AppError(
                    "OCR_TIMEOUT",
                    "OCR timed out processing this page.",
                    422,
                ) from exc
            raise
        return OcrOutput(
            text=text,
            confidence=parse_tsv_confidence(tsv),
            engine=f"tesseract {self.version()}",
        )

    def ocr_image(
        self, image: Image.Image, language: str, timeout: float | None = None
    ) -> str:
        """Return OCR text for *image* using *language*."""
        return self.recognize(image, language, timeout).text

    def _text_and_tsv(
        self, image: Image.Image, language: str, timeout: float
    ) -> tuple[str, str]:
        """Run Tesseract once for text and TSV when the helper exists."""
        multi = getattr(pytesseract, "run_and_get_multiple_output", None)
        if callable(multi):
            text, tsv = multi(
                image,
                extensions=["txt", "tsv"],
                lang=language,
                timeout=timeout,
            )
            return _as_text(text), _as_text(tsv)
        text = pytesseract.image_to_string(image, lang=language, timeout=timeout)
        tsv = pytesseract.image_to_data(image, lang=language, timeout=timeout)
        return text, _as_text(tsv)