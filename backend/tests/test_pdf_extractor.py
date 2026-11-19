"""Tests for PdfExtractor."""

import pytest

from app.config import Settings
from app.errors import AppError
from app.extraction.pdf import PdfExtractor
from app.models import ExtractionMethod
from tests.helpers import make_encrypted_pdf, make_text_pdf


class _FakeOcr:
    """Minimal OCR stand-in that is never actually called by these tests."""

    def version(self) -> str:
        return "fake"

    def available_languages(self) -> list[str]:
        return ["eng"]

    def ocr_image(
        self, image, language: str, timeout: float | None = None
    ) -> str:  # pragma: no cover
        return ""


def _extractor(**overrides) -> PdfExtractor:
    settings = Settings(
        cors_origins=["http://localhost:5173"],
        max_pdf_pages=overrides.pop("max_pdf_pages", 30),
        # Set min_page_chars=0 so OCR fallback is never triggered in these
        # native-text tests (make_text_pdf uses non-embedded fonts that pypdf
        # can still extract, but pdfium+FakeOcr would return empty string).
        min_page_chars=overrides.pop("min_page_chars", 0),
        **overrides,
    )
    return PdfExtractor(ocr=_FakeOcr(), settings=settings)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_single_page_text_extracted() -> None:
    pdf = make_text_pdf(["Hello World"])
    result = _extractor().extract(pdf, "eng")

    assert "Hello" in result.text
    assert result.method == ExtractionMethod.PDF_TEXT
    assert result.engine.startswith("pypdf")
    assert result.page_count == 1
    assert result.ocr_pages == 0
    assert result.warnings == []


def test_multi_page_text_joined_with_double_newline() -> None:
    pdf = make_text_pdf(["Page one", "Page two", "Page three"])
    result = _extractor().extract(pdf, "eng")

    assert result.page_count == 3
    # Pages are separated by "\n\n"
    assert result.text.count("\n\n") >= 2


# ---------------------------------------------------------------------------
# Truncation
# ---------------------------------------------------------------------------


def test_truncation_warning_when_pages_exceed_limit() -> None:
    pdf = make_text_pdf(["p1", "p2", "p3", "p4", "p5"])
    result = _extractor(max_pdf_pages=3).extract(pdf, "eng")

    assert "TRUNCATED" in result.warnings
    assert result.page_count == 5  # total pages in file
    # Only 3 pages were read, so text from p4/p5 should be absent
    assert result.text.count("\n\n") == 2  # 3 pages → 2 separators


def test_no_truncation_when_pages_within_limit() -> None:
    pdf = make_text_pdf(["a", "b"])
    result = _extractor(max_pdf_pages=5).extract(pdf, "eng")
    assert "TRUNCATED" not in result.warnings


# ---------------------------------------------------------------------------
# Empty PDF → NO_TEXT_FOUND
# ---------------------------------------------------------------------------


def test_empty_pdf_no_text_found_warning() -> None:
    pdf = make_text_pdf([""])
    result = _extractor().extract(pdf, "eng")
    assert "NO_TEXT_FOUND" in result.warnings


# ---------------------------------------------------------------------------
# Corrupted bytes
# ---------------------------------------------------------------------------


def test_corrupted_bytes_raises_corrupted_file() -> None:
    with pytest.raises(AppError) as exc_info:
        _extractor().extract(b"not a pdf at all", "eng")

    assert exc_info.value.code == "CORRUPTED_FILE"
    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# Encrypted PDF
# ---------------------------------------------------------------------------


def test_encrypted_pdf_raises_pdf_encrypted() -> None:
    pdf = make_encrypted_pdf("secret")
    with pytest.raises(AppError) as exc_info:
        _extractor().extract(pdf, "eng")

    assert exc_info.value.code == "PDF_ENCRYPTED"
    assert exc_info.value.status_code == 422
