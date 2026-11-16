"""Tests for ExtractionRouter (prompt 17)."""

import io

import pytest
from PIL import Image

from app.errors import AppError
from app.extraction.router import ExtractionRouter
from app.models import ExtractionMethod, ExtractionResult

# ---------------------------------------------------------------------------
# Fake extractors
# ---------------------------------------------------------------------------


class FakeExtractor:
    """Records calls and returns a fixed result."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[tuple[bytes, str]] = []

    def extract(self, data: bytes, language: str) -> ExtractionResult:
        self.calls.append((data, language))
        return ExtractionResult(
            text=f"result-from-{self.name}",
            method=ExtractionMethod.PDF_TEXT,
            engine=self.name,
            page_count=1,
            ocr_pages=0,
            warnings=[],
        )


# ---------------------------------------------------------------------------
# Content fixtures
# ---------------------------------------------------------------------------


def _pdf_bytes() -> bytes:
    return b"%PDF-1.4\n" + b"\x00" * 200


def _png_bytes() -> bytes:
    img = Image.new("RGB", (10, 10), "white")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _jpeg_bytes() -> bytes:
    img = Image.new("RGB", (10, 10), "white")
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    return buf.getvalue()


def _unknown_bytes() -> bytes:
    return b"PK\x03\x04" + b"\x00" * 100


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def test_pdf_bytes_go_to_pdf_extractor() -> None:
    pdf_ext = FakeExtractor("pdf")
    img_ext = FakeExtractor("image")
    router = ExtractionRouter(pdf=pdf_ext, image=img_ext)

    result = router.extract(_pdf_bytes(), "eng")

    assert result.engine == "pdf"
    assert len(pdf_ext.calls) == 1
    assert len(img_ext.calls) == 0


def test_png_bytes_go_to_image_extractor() -> None:
    pdf_ext = FakeExtractor("pdf")
    img_ext = FakeExtractor("image")
    router = ExtractionRouter(pdf=pdf_ext, image=img_ext)

    result = router.extract(_png_bytes(), "eng")

    assert result.engine == "image"
    assert len(img_ext.calls) == 1
    assert len(pdf_ext.calls) == 0


def test_jpeg_bytes_go_to_image_extractor() -> None:
    pdf_ext = FakeExtractor("pdf")
    img_ext = FakeExtractor("image")
    router = ExtractionRouter(pdf=pdf_ext, image=img_ext)

    router.extract(_jpeg_bytes(), "eng")
    assert len(img_ext.calls) == 1


def test_unknown_bytes_raise_unsupported_type() -> None:
    router = ExtractionRouter(pdf=FakeExtractor("pdf"), image=FakeExtractor("image"))
    with pytest.raises(AppError) as exc_info:
        router.extract(_unknown_bytes(), "eng")
    assert exc_info.value.code == "UNSUPPORTED_TYPE"
    assert exc_info.value.status_code == 415


def test_invalid_language_raises_before_routing() -> None:
    pdf_ext = FakeExtractor("pdf")
    router = ExtractionRouter(pdf=pdf_ext, image=FakeExtractor("image"))
    with pytest.raises(AppError) as exc_info:
        router.extract(_pdf_bytes(), "klingon")
    assert exc_info.value.code == "INVALID_LANGUAGE"
    # PDF extractor must NOT have been called
    assert len(pdf_ext.calls) == 0


def test_pdf_bytes_in_image_mime_routed_by_content() -> None:
    """Drive says image/jpeg but bytes are PDF → PDF extractor is called."""
    pdf_ext = FakeExtractor("pdf")
    img_ext = FakeExtractor("image")
    router = ExtractionRouter(pdf=pdf_ext, image=img_ext)

    # bytes are PDF regardless of what the Drive MIME type says
    result = router.extract(_pdf_bytes(), "fra")
    assert result.engine == "pdf"
    assert len(pdf_ext.calls) == 1
