"""Tests for PdfExtractor with OCR fallback (prompt 16)."""

import io

import pytest
from PIL import Image

from app.config import Settings
from app.errors import AppError
from app.extraction.pdf import PdfExtractor, decide_method, looks_like_garbage
from app.models import ExtractionMethod, OcrOutput
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


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Le résumé français contient assez de lettres normales.", False),
        ("هذا نص عربي واضح وليس رموزا تالفة أبدا", False),
        ("\ufffd" * 50, True),
        ("(cid:12)" * 4, True),
        ("\ufffd" * 9, False),
        ("Bonjour", False),
        ("a" * 10 + "\t\n" * 20, False),
        ("\x00" * 12, True),
    ],
)
def test_looks_like_garbage(text: str, expected: bool) -> None:
    assert looks_like_garbage(text) is expected


def test_pdfium_text_used_when_pypdf_fails_or_returns_garbage() -> None:
    """pdfium text replaces a failed or garbage pypdf page, without OCR."""
    from unittest.mock import patch

    sentence = "This page has plenty of selectable text to extract."
    pdf = make_text_pdf([sentence, sentence])
    fake = FakeOcr()
    extractor = PdfExtractor(ocr=fake, settings=_settings(min_page_chars=5))

    with patch("pypdf._page.PageObject.extract_text", side_effect=RuntimeError("boom")):
        raised = extractor.extract(pdf, "eng")

    with patch("pypdf._page.PageObject.extract_text", return_value="\ufffd" * 50):
        garbage = extractor.extract(pdf, "eng")

    for result in (raised, garbage):
        assert "selectable" in result.text
        assert result.warnings.count("PDFIUM_TEXT_FALLBACK") == 1
        assert "pdfium" in result.engine
        assert "tesseract" not in result.engine
    assert fake.call_count == 0


# ---------------------------------------------------------------------------
# FakeOcr
# ---------------------------------------------------------------------------


class FakeOcr:
    def __init__(self, text: str = "OCR TEXT") -> None:
        self._text = text
        self.call_count = 0
        self.timeouts: list[float | None] = []

    def version(self) -> str:
        return "fake-5.0"

    def available_languages(self) -> list[str]:
        return ["eng", "fra"]

    def recognize(
        self, image, language: str, timeout: float | None = None
    ) -> OcrOutput:
        self.call_count += 1
        self.timeouts.append(timeout)
        return OcrOutput(text=self._text, confidence=95.0, engine="tesseract fake-5.0")

    def ocr_image(
        self, image, language: str, timeout: float | None = None
    ) -> str:
        return self.recognize(image, language, timeout).text


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


def _make_image_pdf_pages(page_count: int) -> bytes:
    """Build an image-only PDF with *page_count* raster pages."""
    pages = [Image.new("RGB", (200, 100), color="white") for _ in range(page_count)]
    buf = io.BytesIO()
    pages[0].save(
        buf,
        "PDF",
        resolution=200,
        save_all=True,
        append_images=pages[1:],
    )
    return buf.getvalue()


def test_image_pdf_opens_pdfium_once_and_ocr_each_page() -> None:
    """A 3-page image PDF opens pdfium once and OCRs every page."""
    import pypdfium2

    opened = 0
    real_document = pypdfium2.PdfDocument

    def _counting_document(*args, **kwargs):
        nonlocal opened
        opened += 1
        return real_document(*args, **kwargs)

    fake = FakeOcr("page ocr")
    pdf = _make_image_pdf_pages(3)
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(pypdfium2, "PdfDocument", _counting_document)
        result = PdfExtractor(
            ocr=fake, settings=_settings(min_page_chars=1_000)
        ).extract(pdf, "eng")

    assert opened == 1
    assert fake.call_count == 3
    assert result.ocr_pages == 3


def test_ocr_timeout_is_bounded_by_remaining_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """OCR timeout is the lesser of the page timeout and the time left."""
    budget = 10
    elapsed = 4.0
    t0 = 1_000.0
    times = iter((t0, t0 + elapsed))

    def _clock() -> float:
        try:
            return next(times)
        except StopIteration:
            return t0 + elapsed

    monkeypatch.setattr("app.extraction.pdf.time.monotonic", _clock)
    fake = FakeOcr("bounded")
    PdfExtractor(
        ocr=fake,
        settings=_settings(
            file_time_budget_s=budget,
            ocr_page_timeout_s=60,
            min_page_chars=1_000,
        ),
    ).extract(_make_image_pdf(), "eng")

    remaining = budget - elapsed
    assert fake.timeouts == [min(60, remaining)]
    assert fake.timeouts[0] is not None
    assert fake.timeouts[0] <= remaining


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
