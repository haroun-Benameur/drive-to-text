"""FallbackOcr: try primary engine, fall back to secondary on weak results."""

import logging

from PIL import Image

from app.errors import AppError
from app.models import OcrOutput

logger = logging.getLogger(__name__)

_SKIPPABLE_CODES = {"OCR_ENGINE_UNAVAILABLE", "OCR_LANGUAGE_UNSUPPORTED"}


class FallbackOcr:
    """OcrEngine that tries *primary* and falls back to *secondary*.

    Falls back when the primary result is blank or its confidence is below
    *min_confidence*.  If the secondary raises a skippable error (unavailable
    or unsupported language) the primary result is kept and a
    ``SECONDARY_OCR_SKIPPED`` warning is added.
    """

    def __init__(
        self,
        primary: object,
        secondary: object,
        min_confidence: float,
    ) -> None:
        self._primary = primary
        self._secondary = secondary
        self._min_confidence = min_confidence

    # ------------------------------------------------------------------
    # OcrEngine protocol delegation
    # ------------------------------------------------------------------

    def version(self) -> str:
        return self._primary.version()  # type: ignore[attr-defined]

    def available_languages(self) -> list[str]:
        return self._primary.available_languages()  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Core OCR
    # ------------------------------------------------------------------

    def recognize(
        self,
        image: Image.Image,
        language: str,
        timeout: float | None = None,
    ) -> OcrOutput:
        primary_result: OcrOutput = self._primary.recognize(  # type: ignore[attr-defined]
            image, language, timeout
        )

        if not self._should_try_secondary(primary_result):
            return primary_result

        try:
            secondary_result: OcrOutput = self._secondary.recognize(  # type: ignore[attr-defined]
                image, language, timeout
            )
        except AppError as exc:
            if exc.code in _SKIPPABLE_CODES:
                logger.debug("Secondary OCR skipped: %s", exc.message)
                result = OcrOutput(
                    text=primary_result.text,
                    confidence=primary_result.confidence,
                    engine=primary_result.engine,
                    warnings=list(primary_result.warnings) + ["SECONDARY_OCR_SKIPPED"],
                )
                return result
            raise

        return self._prefer(primary_result, secondary_result)

    def ocr_image(
        self,
        image: Image.Image,
        language: str,
        timeout: float | None = None,
    ) -> str:
        return self.recognize(image, language, timeout).text

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _should_try_secondary(self, result: OcrOutput) -> bool:
        if not result.text.strip():
            return True
        if result.confidence is None:
            return True
        return result.confidence < self._min_confidence

    @staticmethod
    def _prefer(first: OcrOutput, second: OcrOutput) -> OcrOutput:
        # Non-blank always beats blank
        if not first.text.strip() and second.text.strip():
            return OcrOutput(
                text=second.text,
                confidence=second.confidence,
                engine=f"{first.engine} -> {second.engine}",
                warnings=second.warnings,
            )
        if first.text.strip() and not second.text.strip():
            return first
        # Both non-blank → compare confidence
        if first.confidence is not None and second.confidence is not None:
            if second.confidence > first.confidence:
                return OcrOutput(
                    text=second.text,
                    confidence=second.confidence,
                    engine=f"{first.engine} -> {second.engine}",
                    warnings=second.warnings,
                )
            return first
        # Fall back to longer text
        if len(second.text.strip()) > len(first.text.strip()):
            return OcrOutput(
                text=second.text,
                confidence=second.confidence,
                engine=f"{first.engine} -> {second.engine}",
                warnings=second.warnings,
            )
        return first
