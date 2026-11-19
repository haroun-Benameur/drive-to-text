"""Decide whether a weak OCR result should be retried once."""

from PIL import Image

from app.config import Settings
from app.extraction.base import OcrEngine
from app.extraction.preprocess import preprocess_for_ocr
from app.models import OcrOutput


def recognize_with_retry(
    ocr: OcrEngine,
    image: Image.Image,
    language: str,
    settings: Settings,
    timeout: float | None = None,
) -> OcrOutput:
    """Recognize *image*, retrying once on a preprocessed copy when needed."""
    first = ocr.recognize(image, language, timeout)
    if not _should_retry(first, settings):
        return first
    second = ocr.recognize(
        preprocess_for_ocr(image, settings.max_image_pixels),
        language,
        timeout,
    )
    return _prefer(first, second)


def mean_confidence(values: list[float | None]) -> float | None:
    """Return the mean of known confidences, rounded to one decimal."""
    known = [value for value in values if value is not None]
    if not known:
        return None
    return round(sum(known) / len(known), 1)


def append_low_confidence_warning(
    warnings: list[str], confidence: float | None, minimum: float
) -> None:
    """Append LOW_OCR_CONFIDENCE when *confidence* is below *minimum*."""
    if (
        confidence is not None
        and confidence < minimum
        and "LOW_OCR_CONFIDENCE" not in warnings
    ):
        warnings.append("LOW_OCR_CONFIDENCE")


def _should_retry(result: OcrOutput, settings: Settings) -> bool:
    if not settings.ocr_retry_preprocess:
        return False
    if not result.text.strip():
        return True
    if result.confidence is None:
        return True
    return result.confidence < settings.ocr_min_confidence


def _prefer(first: OcrOutput, second: OcrOutput) -> OcrOutput:
    if first.confidence is not None and second.confidence is not None:
        if second.confidence > first.confidence:
            return second
        return first
    if len(second.text.strip()) > len(first.text.strip()):
        return second
    return first
