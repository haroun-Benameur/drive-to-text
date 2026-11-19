"""Tests for ocr.py: validate_language, TesseractOcr, ImageExtractor."""

import io

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.config import Settings
from app.errors import AppError
from app.extraction.image import ImageExtractor
from app.extraction.ocr import ALLOWED_LANGUAGES, TesseractOcr, validate_language
from app.models import OcrOutput

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _settings(**overrides) -> Settings:
    defaults = {
        "cors_origins": ["http://localhost:5173"],
        "max_image_pixels": 50_000_000,
        "ocr_page_timeout_s": 60,
    }
    defaults.update(overrides)
    return Settings(**defaults)


class FakeOcr:
    """OcrEngine stand-in that never calls Tesseract."""

    def __init__(self, text: str = "FAKE TEXT") -> None:
        self._text = text
        self.calls: list[tuple] = []

    def version(self) -> str:
        return "fake-1.0"

    def available_languages(self) -> list[str]:
        return ["eng", "fra"]

    def recognize(
        self, image, language: str, timeout: float | None = None
    ) -> OcrOutput:
        self.calls.append((language,))
        return OcrOutput(text=self._text, confidence=95.0, engine="tesseract fake-1.0")

    def ocr_image(
        self, image, language: str, timeout: float | None = None
    ) -> str:
        return self.recognize(image, language, timeout).text


# ---------------------------------------------------------------------------
# validate_language
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", list(ALLOWED_LANGUAGES))
def test_validate_language_accepts_allowed(lang: str) -> None:
    assert validate_language(lang) == lang


@pytest.mark.parametrize("lang", ["de", "es", "unknown", "", "eng+fra"])
def test_validate_language_rejects_unknown(lang: str) -> None:
    with pytest.raises(AppError) as exc_info:
        validate_language(lang)
    assert exc_info.value.code == "INVALID_LANGUAGE"
    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# ImageExtractor – unit tests with FakeOcr
# ---------------------------------------------------------------------------


def _make_png(width: int = 10, height: int = 10) -> bytes:
    img = Image.new("RGB", (width, height), color="white")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def test_image_extractor_success() -> None:
    fake = FakeOcr("hello world")
    extractor = ImageExtractor(ocr=fake, settings=_settings())
    result = extractor.extract(_make_png(), "eng")

    assert result.text == "hello world"
    assert result.ocr_pages == 1
    assert result.page_count == 1
    assert len(fake.calls) == 1


def test_image_extractor_no_text_found_warning() -> None:
    fake = FakeOcr("   ")
    extractor = ImageExtractor(ocr=fake, settings=_settings())
    result = extractor.extract(_make_png(), "eng")
    assert "NO_TEXT_FOUND" in result.warnings


def test_image_extractor_corrupted_bytes() -> None:
    extractor = ImageExtractor(ocr=FakeOcr(), settings=_settings())
    with pytest.raises(AppError) as exc_info:
        extractor.extract(b"not an image", "eng")
    assert exc_info.value.code == "CORRUPTED_FILE"
    assert exc_info.value.status_code == 422


def test_image_extractor_oversize_pixels() -> None:
    # 100×100 = 10 000 pixels; set limit to 50
    extractor = ImageExtractor(ocr=FakeOcr(), settings=_settings(max_image_pixels=50))
    with pytest.raises(AppError) as exc_info:
        extractor.extract(_make_png(100, 100), "eng")
    assert exc_info.value.code == "FILE_TOO_LARGE"
    assert exc_info.value.status_code == 413


# ---------------------------------------------------------------------------
# Real Tesseract – skipped when unavailable
# ---------------------------------------------------------------------------

try:
    from app.extraction.ocr import TesseractOcr as _T

    _ocr = _T(_settings())
    _ocr.version()
    _TESSERACT_AVAILABLE = True
except Exception:
    _TESSERACT_AVAILABLE = False


@pytest.mark.skipif(not _TESSERACT_AVAILABLE, reason="Tesseract not available")
def test_real_ocr_reads_text() -> None:
    """Generate a white image with 'HELLO WORLD' and confirm OCR reads it."""
    settings = _settings()
    ocr = TesseractOcr(settings)

    img = Image.new("RGB", (400, 100), color="white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default(size=48)
    except TypeError:
        font = ImageFont.load_default()
    draw.text((20, 20), "HELLO WORLD", fill="black", font=font)

    text = ocr.ocr_image(img, "eng")
    assert "HELLO" in text.upper()
