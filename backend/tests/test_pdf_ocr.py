"""Tests for PdfExtractor with OCR fallback (prompt 16)."""

import io

import pytest
from PIL import Image

from app.config import Settings
from app.errors import AppError
from app.extraction.pdf import PdfExtractor, decide_method
from app.models import ExtractionMethod
from tests.helpers import make_text_pdf

# ---------------------------------------------------------------------------
# decide_method
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("total", "ocr", "expected"),
    [
        (3, 0, ExtractionMethod.PDF_TEXT),
        (3, 3, ExtractionMethod.OCR),
        (3, 1, ExtractionMethod.PDF_TEXT_OCR),
        (1, 0, ExtractionMethod.PDF_TEXT),
        (1, 1, ExtractionMethod.OCR),
    ],
)
def test_decide_method(total: int, ocr: int, expected: ExtractionMethod) -> None:
    assert decide_method(total, ocr) == expected


# ---------------------------------------------------------------------------
# FakeOcr
# ---------------------------------------------------------------------------


class FakeOcr:
    def __init__(self, text: str = "OCR TEXT") -> None:
        self._text = text
        self.call_count = 0

    def version(self) -> str:
        return "fake-5.0"

    def available_languages(self) -> list[str]:
        return ["eng", "fra"]

    def ocr_image(self, image, language: str) -> str:
        self.call_count += 1
        return self._text


def _settings(**overrides) -> Settings:
    defaults = {
        "cors_origins": ["http://localhost:5173"],
        "max_pdf_pages": 30,
        "min_page_chars": 25,
        "ocr_render_dpi": 150,
        "max_image_pixels": 50_000_000,
        "file_time_budget_s": 120,
        "ocr_page_timeout_s": 60,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _extractor(ocr=None, **overrides) -> PdfExtractor:
    return PdfExtractor(ocr=ocr or FakeOcr(), settings=_settings(**overrides))


# ---------------------------------------------------------------------------
# Image-only PDF (no selectable text) → OCR called
# ---------------------------------------------------------------------------


def _make_image_pdf() -> bytes:
    """Build a PDF whose single page is a raster image (no text stream)."""
    img = Image.new("RGB", (200, 100), color="white")
    buf = io.BytesIO()
    img.save(buf, "PDF", resolution=200)
    return buf.getvalue()


def test_image_pdf_uses_ocr_fallback() -> None:
    fake = FakeOcr("extracted by ocr")
    extractor = PdfExtractor(ocr=fake, settings=_settings())
    result = extractor.extract(_make_image_pdf(), "eng")

    assert "extracted by ocr" in result.text
    assert result.method == ExtractionMethod.OCR
    assert result.ocr_pages >= 1
    assert fake.call_count >= 1


# ---------------------------------------------------------------------------
# Native-text PDF → OCR never called
# ---------------------------------------------------------------------------


def test_native_pdf_does_not_call_ocr() -> None:
    fake = FakeOcr()
    pdf = make_text_pdf(["This page has plenty of selectable text to extract."])
    extractor = PdfExtractor(ocr=fake, settings=_settings(min_page_chars=5))
    extractor.extract(pdf, "eng")

    assert fake.call_count == 0


# ---------------------------------------------------------------------------
# Corrupted bytes
# ---------------------------------------------------------------------------


def test_corrupted_raises_corrupted_file() -> None:
    with pytest.raises(AppError) as exc_info:
        _extractor().extract(b"garbage", "eng")
    assert exc_info.value.code == "CORRUPTED_FILE"


# ---------------------------------------------------------------------------
# Real Tesseract – skipped when unavailable
# ---------------------------------------------------------------------------

try:
    from app.extraction.ocr import TesseractOcr as _T

    _real_ocr = _T(_settings())
    _real_ocr.version()
    _TESSERACT_AVAILABLE = True
except Exception:
    _TESSERACT_AVAILABLE = False


@pytest.mark.skipif(not _TESSERACT_AVAILABLE, reason="Tesseract not available")
def test_image_pdf_real_ocr() -> None:
    """Image-only PDF with the real Tesseract engine."""
    from app.extraction.ocr import TesseractOcr

    ocr = TesseractOcr(_settings())
    extractor = PdfExtractor(ocr=ocr, settings=_settings())
    result = extractor.extract(_make_image_pdf(), "eng")
    assert result.ocr_pages >= 1
