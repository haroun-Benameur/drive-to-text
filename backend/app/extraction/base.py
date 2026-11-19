"""Abstract interfaces for extraction and OCR engine components."""

from typing import Protocol, runtime_checkable

from PIL import Image

from app.models import ExtractionResult


@runtime_checkable
class Extractor(Protocol):
    """Extract text from raw file bytes."""

    def extract(self, data: bytes, language: str) -> ExtractionResult:
        """Return an :class:`~app.models.ExtractionResult` for *data*."""
        ...


@runtime_checkable
class OcrEngine(Protocol):
    """Run OCR on a single PIL image."""

    def ocr_image(
        self, image: Image.Image, language: str, timeout: float | None = None
    ) -> str:
        """Return the OCR text for *image*.

        When *timeout* is given it overrides the engine's default page timeout.
        """
        ...

    def version(self) -> str:
        """Return a human-readable version string for the engine."""
        ...

    def available_languages(self) -> list[str]:
        """Return the language codes supported by this engine."""
        ...