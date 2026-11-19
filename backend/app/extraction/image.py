"""Image OCR extractor."""

import warnings
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import Settings
from app.errors import AppError
from app.extraction.base import OcrEngine
from app.extraction.ocr_policy import (
    append_low_confidence_warning,
    recognize_with_retry,
)
from app.models import ExtractionMethod, ExtractionResult


class ImageExtractor:
    """Extract text from image bytes via OCR."""

    def __init__(self, ocr: OcrEngine, settings: Settings) -> None:
        self._ocr = ocr
        self._settings = settings
        self._max_pixels = settings.max_image_pixels

    def extract(self, data: bytes, language: str) -> ExtractionResult:
        """Return OCR text extracted from image *data*.

        Strategy:
        1. Open lazily (header only) — no pixel data decoded yet.
        2. Check width × height against the limit BEFORE loading pixels.
        3. Load inside a warnings context that turns DecompressionBombWarning
           into an error so the check catches both Pillow's built-in threshold
           AND any subsequent PIL operations that re-evaluate the limit.
        4. Map every image-decode exception to a typed AppError.
        """
        # ── 1. Lazy open (reads header, not pixels) ───────────────────────────
        try:
            # NOTE: do NOT set Image.MAX_IMAGE_PIXELS globally; leave it at the
            # Pillow default so the warning mechanism remains active for other
            # callers that may not go through this path.
            image = Image.open(BytesIO(data))
        except UnidentifiedImageError as exc:
            raise AppError(
                "CORRUPTED_FILE", "The image could not be identified.", 422
            ) from exc
        except (OSError, SyntaxError, ValueError) as exc:
            raise AppError(
                "CORRUPTED_FILE", "The image file is corrupted or unreadable.", 422
            ) from exc

        # ── 2. Pixel-count guard BEFORE any decode ────────────────────────────
        w, h = image.size
        if w * h > self._max_pixels:
            raise AppError(
                "FILE_TOO_LARGE",
                f"Image dimensions {w}×{h} = {w * h:,} pixels exceed"
                f" the {self._max_pixels:,}-pixel limit.",
                413,
            )

        # ── 3. Load pixels, treating DecompressionBombWarning as an error ─────
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                image.load()
        except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise AppError(
                "FILE_TOO_LARGE",
                "Image exceeds the maximum allowed pixel count.",
                413,
            ) from exc
        except UnidentifiedImageError as exc:
            raise AppError(
                "CORRUPTED_FILE", "The image could not be identified.", 422
            ) from exc
        except (OSError, SyntaxError, ValueError) as exc:
            raise AppError(
                "CORRUPTED_FILE", "The image file is corrupted or unreadable.", 422
            ) from exc

        # ── 4. Post-load transforms ───────────────────────────────────────────
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")

        output = recognize_with_retry(self._ocr, image, language, self._settings)
        result_warnings: list[str] = []
        if not output.text.strip():
            result_warnings.append("NO_TEXT_FOUND")
        append_low_confidence_warning(
            result_warnings,
            output.confidence,
            self._settings.ocr_min_confidence,
        )

        return ExtractionResult(
            text=output.text,
            method=ExtractionMethod.OCR,
            engine=f"tesseract {self._ocr.version()}",
            page_count=1,
            ocr_pages=1,
            warnings=result_warnings,
            ocr_confidence=output.confidence,
        )
