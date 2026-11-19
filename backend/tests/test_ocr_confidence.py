"""OCR confidence parsing, retry policy, and propagation."""

import io

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.config import Settings
from app.extraction.image import ImageExtractor
from app.extraction.ocr import TesseractOcr, parse_tsv_confidence
from app.extraction.ocr_policy import recognize_with_retry
from app.extraction.pdf import PdfExtractor
from app.models import OcrOutput
from tests.helpers import FakeOcr

_HEADER = (
    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\t"
    "left\ttop\twidth\theight\tconf\ttext"
)


def _settings(**overrides) -> Settings:
    defaults = {
        "cors_origins": ["http://localhost:5173"],
        "max_image_pixels": 50_000_000,
        "ocr_page_timeout_s": 60,
        "min_page_chars": 1_000,
        "ocr_min_confidence": 60.0,
        "ocr_retry_preprocess": True,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _output(text: str, confidence: float | None) -> OcrOutput:
    return OcrOutput(text=text, confidence=confidence, engine="tesseract fake")


def _png() -> bytes:
    image = Image.new("RGB", (40, 20), color="white")
    buf = io.BytesIO()
    image.save(buf, "PNG")
    return buf.getvalue()


def _image_pdf(page_count: int) -> bytes:
    pages = [Image.new("RGB", (80, 40), color="white") for _ in range(page_count)]
    buf = io.BytesIO()
    pages[0].save(
        buf, "PDF", resolution=72, save_all=True, append_images=pages[1:]
    )
    return buf.getvalue()


@pytest.mark.parametrize(
    ("tsv", "expected"),
    [
        ("", None),
        (_HEADER, None),
        (
            _HEADER + "\n5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t-1\tfoo",
            None,
        ),
        (
            _HEADER
            + "\n5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t90\tHello"
            + "\n5\t1\t1\t1\t1\t2\t20\t0\t10\t10\t70\tWorld"
            + "\n5\t1\t1\t1\t1\t3\t40\t0\t10\t10\t-1\t"
            + "\n4\t1\t1\t1\t1\t0\t0\t0\t50\t10\t10\tignored",
            80.0,
        ),
        (
            _HEADER
            + "\n5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t91\tUn"
            + "\n5\t1\t1\t1\t1\t2\t20\t0\t10\t10\t80\tDeux"
            + "\n5\t1\t1\t1\t1\t3\t40\t0\t10\t10\t63\tTrois",
            78.0,
        ),
    ],
)
def test_parse_tsv_confidence(tsv: str, expected: float | None) -> None:
    assert parse_tsv_confidence(tsv) == expected


def test_retry_keeps_higher_confidence() -> None:
    ocr = FakeOcr(outputs=[_output("low", 40.0), _output("high", 90.0)])
    result = recognize_with_retry(ocr, Image.new("RGB", (10, 10)), "eng", _settings())
    assert result.text == "high"
    assert result.confidence == 90.0
    assert ocr.call_count == 2


def test_retry_keeps_better_of_two_low_scores() -> None:
    ocr = FakeOcr(outputs=[_output("alpha", 40.0), _output("beta", 20.0)])
    result = recognize_with_retry(ocr, Image.new("RGB", (10, 10)), "eng", _settings())
    assert result.text == "alpha"
    assert result.confidence == 40.0
    assert ocr.call_count == 2


def test_retry_disabled_keeps_first_result() -> None:
    ocr = FakeOcr(outputs=[_output("only", 20.0), _output("later", 99.0)])
    result = recognize_with_retry(
        ocr,
        Image.new("RGB", (10, 10)),
        "eng",
        _settings(ocr_retry_preprocess=False),
    )
    assert result.text == "only"
    assert ocr.call_count == 1


def test_missing_confidence_retries_and_prefers_longer_text() -> None:
    ocr = FakeOcr(outputs=[_output("ab", None), _output("longer", None)])
    result = recognize_with_retry(ocr, Image.new("RGB", (10, 10)), "eng", _settings())
    assert result.text == "longer"
    assert result.confidence is None
    assert ocr.call_count == 2


def test_blank_text_retries_and_prefers_longer_text() -> None:
    ocr = FakeOcr(outputs=[_output("   ", None), _output("hello", None)])
    result = recognize_with_retry(ocr, Image.new("RGB", (10, 10)), "eng", _settings())
    assert result.text == "hello"
    assert ocr.call_count == 2


def test_image_extractor_propagates_confidence() -> None:
    extractor = ImageExtractor(
        ocr=FakeOcr(text="hello", confidence=88.0),
        settings=_settings(ocr_retry_preprocess=False),
    )
    result = extractor.extract(_png(), "eng")
    assert result.ocr_confidence == 88.0
    assert "LOW_OCR_CONFIDENCE" not in result.warnings


def test_image_extractor_flags_low_confidence() -> None:
    extractor = ImageExtractor(
        ocr=FakeOcr(text="hello", confidence=42.5),
        settings=_settings(ocr_retry_preprocess=False),
    )
    result = extractor.extract(_png(), "eng")
    assert result.ocr_confidence == 42.5
    assert "LOW_OCR_CONFIDENCE" in result.warnings


def test_pdf_extractor_averages_ocr_page_confidence() -> None:
    ocr = FakeOcr(
        outputs=[_output("page one text", 80.0), _output("page two text", 60.0)]
    )
    result = PdfExtractor(
        ocr=ocr, settings=_settings(ocr_retry_preprocess=False)
    ).extract(_image_pdf(2), "eng")
    assert result.ocr_pages == 2
    assert result.ocr_confidence == 70.0
    assert "LOW_OCR_CONFIDENCE" not in result.warnings


def test_pdf_extractor_flags_low_mean_confidence() -> None:
    ocr = FakeOcr(
        outputs=[_output("page one text", 40.0), _output("page two text", 50.0)]
    )
    result = PdfExtractor(
        ocr=ocr, settings=_settings(ocr_retry_preprocess=False)
    ).extract(_image_pdf(2), "eng")
    assert result.ocr_confidence == 45.0
    assert "LOW_OCR_CONFIDENCE" in result.warnings


try:
    TesseractOcr(_settings()).version()
    _TESSERACT_AVAILABLE = True
except Exception:
    _TESSERACT_AVAILABLE = False


@pytest.mark.skipif(not _TESSERACT_AVAILABLE, reason="Tesseract not available")
def test_real_ocr_reports_confidence_on_generated_image() -> None:
    image = Image.new("RGB", (400, 120), color="white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.load_default(size=48)
    except TypeError:
        font = ImageFont.load_default()
    draw.text((20, 30), "HELLO", fill="black", font=font)

    output = TesseractOcr(_settings()).recognize(image, "eng")
    assert output.engine.startswith("tesseract ")
    assert output.confidence is None or 0 <= output.confidence <= 100
