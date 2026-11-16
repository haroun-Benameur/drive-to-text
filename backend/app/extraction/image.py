"""Image OCR extractor."""

from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import Settings
from app.errors import AppError
from app.extraction.base import OcrEngine
from app.models import ExtractionMethod, ExtractionResult


class ImageExtractor:
    """Extract text from image bytes via OCR."""

    def __init__(self, ocr: OcrEngine, settings: Settings) -> None:
        self._ocr = ocr
        self._max_pixels = settings.max_image_pixels

    def extract(self, data: bytes, language: str) -> ExtractionResult:
        """Return OCR text extracted from image *data*."""
        # PIL's own limit can raise DecompressionBombError; override with ours
        # by disabling the built-in guard first (we enforce our own below).
        Image.MAX_IMAGE_PIXELS = None

        try:
            image = Image.open(BytesIO(data))
            image.load()  # force decode so errors surface here
        except UnidentifiedImageError as exc:
            raise AppError(
                "CORRUPTED_FILE", "The image could not be identified.", 422
            ) from exc
        except Image.DecompressionBombError as exc:
            raise AppError(
                "FILE_TOO_LARGE",
                "Image exceeds the maximum allowed pixel count.",
                413,
            ) from exc
        except OSError as exc:
            raise AppError(
                "CORRUPTED_FILE", "The image file is corrupted or unreadable.", 422
            ) from exc

        w, h = image.size
        if w * h > self._max_pixels:
            raise AppError(
                "FILE_TOO_LARGE",
                f"Image dimensions {w}×{h} exceed the {self._max_pixels}-pixel limit.",
                413,
            )

        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")

        text = self._ocr.ocr_image(image, language)
        warnings: list[str] = []
        if not text.strip():
            warnings.append("NO_TEXT_FOUND")

        return ExtractionResult(
            text=text,
            method=ExtractionMethod.OCR,
            engine=f"tesseract {self._ocr.version()}",
            page_count=1,
            ocr_pages=1,
            warnings=warnings,
        )
