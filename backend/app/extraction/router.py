"""Route raw file bytes to the appropriate extractor."""

from app.errors import AppError
from app.extraction.base import Extractor, OcrEngine
from app.extraction.ocr import validate_language
from app.extraction.sniff import sniff_content_kind
from app.models import ExtractionResult


class ExtractionRouter:
    """Dispatch file bytes to the correct :class:`Extractor` by content type."""

    def __init__(self, pdf: Extractor, image: Extractor) -> None:
        self._pdf = pdf
        self._image = image

    def extract(self, data: bytes, language: str) -> ExtractionResult:
        """Validate *language*, sniff *data*, and delegate to the right extractor."""
        validate_language(language)

        kind = sniff_content_kind(data)
        if kind is None:
            raise AppError(
                "UNSUPPORTED_TYPE",
                "Unsupported or unrecognised file content.",
                415,
            )

        if kind == "pdf":
            return self._pdf.extract(data, language)
        # "png" or "jpeg"
        return self._image.extract(data, language)


def build_default_router(settings, ocr: OcrEngine) -> ExtractionRouter:
    """Construct an :class:`ExtractionRouter` wired to real extractors."""
    from app.extraction.image import ImageExtractor
    from app.extraction.pdf import PdfExtractor

    return ExtractionRouter(
        pdf=PdfExtractor(ocr=ocr, settings=settings),
        image=ImageExtractor(ocr=ocr, settings=settings),
    )
