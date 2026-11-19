"""Security / robustness tests for PdfExtractor: oversized pages, time budget, malformed data."""

import time
from io import BytesIO
from unittest.mock import patch

import pytest
from pypdf import PdfWriter

from app.config import Settings
from app.errors import AppError
from app.extraction.pdf import PdfExtractor
from app.models import OcrOutput
from tests.helpers import make_encrypted_pdf, make_text_pdf

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeOcr:
    """OcrEngine stand-in that never calls Tesseract."""

    def __init__(self, text: str = "OCR TEXT") -> None:
        self._text = text
        self.call_count = 0

    def version(self) -> str:
        return "fake-5.0"

    def available_languages(self) -> list[str]:
        return ["eng", "fra"]

    def recognize(
        self, image: object, language: str, timeout: float | None = None
    ) -> OcrOutput:
        self.call_count += 1
        return OcrOutput(text=self._text, confidence=95.0, engine="tesseract fake-5.0")

    def ocr_image(
        self, image: object, language: str, timeout: float | None = None
    ) -> str:
        return self.recognize(image, language, timeout).text


def _settings(**overrides) -> Settings:
    defaults = {
        "cors_origins": ["http://localhost:5173"],
        "max_pdf_pages": 30,
        "min_page_chars": 25,
        "ocr_render_dpi": 200,
        "max_image_pixels": 50_000_000,
        "file_time_budget_s": 120,
        "ocr_page_timeout_s": 60,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _make_blank_pdf(width: float, height: float) -> bytes:
    """Return a single-page blank PDF with the given page dimensions in points."""
    writer = PdfWriter()
    writer.add_blank_page(width=width, height=height)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# (a) Oversized page → PAGE_TOO_LARGE warning, OCR never called
# ---------------------------------------------------------------------------


def test_oversized_page_adds_warning_and_skips_ocr() -> None:
    """A 20 000 × 20 000 pt page rendered at 200 DPI exceeds MAX_IMAGE_PIXELS."""
    # scale = 200/72 ≈ 2.78; rendered px ≈ 55 555 × 55 555 ≈ 3 billion >> 50 M
    # min_page_chars=1 so the blank page (0 alnum chars) triggers the OCR path,
    # which is where the PAGE_TOO_LARGE check happens.
    pdf = _make_blank_pdf(width=20_000, height=20_000)
    fake_ocr = FakeOcr()
    extractor = PdfExtractor(ocr=fake_ocr, settings=_settings(min_page_chars=1))

    result = extractor.extract(pdf, "eng")

    assert "PAGE_TOO_LARGE" in result.warnings, (
        f"Expected PAGE_TOO_LARGE in warnings, got: {result.warnings}"
    )
    assert fake_ocr.call_count == 0, (
        f"OCR engine was called {fake_ocr.call_count} time(s) but should not have been"
    )


# ---------------------------------------------------------------------------
# (b) Time budget exceeded → TRUNCATED warning
# ---------------------------------------------------------------------------


def test_time_budget_exceeded_adds_truncated_warning() -> None:
    """When elapsed time exceeds file_time_budget_s, processing stops with TRUNCATED."""
    # Build a 5-page PDF where each page has no selectable text,
    # so the extractor attempts OCR for each page.
    pdf = make_text_pdf([""] * 5)

    fake_ocr = FakeOcr(text="")

    # Patch time.monotonic to simulate budget exhaustion after the first page.
    call_count = [0]
    t0 = time.monotonic()

    def fast_clock() -> float:
        call_count[0] += 1
        # First call returns t0 (start). Every subsequent call returns t0 + 999
        # so the budget (1 s) is exceeded after the first iteration check.
        return t0 if call_count[0] == 1 else t0 + 999.0

    with patch("app.extraction.pdf.time.monotonic", side_effect=fast_clock):
        result = PdfExtractor(
            ocr=fake_ocr,
            settings=_settings(file_time_budget_s=1, min_page_chars=0),
        ).extract(pdf, "eng")

    assert "TRUNCATED" in result.warnings, (
        f"Expected TRUNCATED in warnings, got: {result.warnings}"
    )
    # Only the first page was processed before the budget ran out.
    assert len(result.text.split("\n\n")) <= 2, (
        "More pages were processed than expected given the time budget"
    )


# ---------------------------------------------------------------------------
# (c) PDF header + random bytes → CORRUPTED_FILE
# ---------------------------------------------------------------------------


def test_malformed_pdf_raises_corrupted_file() -> None:
    """A file with a PDF header but invalid body is rejected with CORRUPTED_FILE."""
    garbage = b"%PDF-1.4\n" + b"\xff\x00\xaa\xbb" * 200
    with pytest.raises(AppError) as exc_info:
        PdfExtractor(ocr=FakeOcr(), settings=_settings()).extract(garbage, "eng")
    assert exc_info.value.code == "CORRUPTED_FILE"
    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# (d) Encrypted PDF → PDF_ENCRYPTED
# ---------------------------------------------------------------------------


def test_encrypted_pdf_raises_pdf_encrypted() -> None:
    """A password-protected PDF is rejected with PDF_ENCRYPTED."""
    pdf = make_encrypted_pdf("secret")
    with pytest.raises(AppError) as exc_info:
        PdfExtractor(ocr=FakeOcr(), settings=_settings()).extract(pdf, "eng")
    assert exc_info.value.code == "PDF_ENCRYPTED"
    assert exc_info.value.status_code == 422
