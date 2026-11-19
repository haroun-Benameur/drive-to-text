"""Tests for FallbackOcr (step 6) — no real EasyOCR import needed."""

import pytest
from PIL import Image

from app.errors import AppError
from app.extraction.ocr_fallback import FallbackOcr
from app.models import OcrOutput

# ---------------------------------------------------------------------------
# Scripted fake engine
# ---------------------------------------------------------------------------


class _FakeEngine:
    """Scriptable OcrEngine fake that returns pre-set OcrOutput objects."""

    def __init__(self, outputs: list[OcrOutput], name: str = "fake") -> None:
        self._outputs = iter(outputs)
        self._name = name
        self.call_count = 0

    def version(self) -> str:
        return f"{self._name}-1.0"

    def available_languages(self) -> list[str]:
        return ["eng", "fra"]

    def recognize(self, image: object, language: str, timeout: object = None) -> OcrOutput:
        self.call_count += 1
        return next(self._outputs)

    def ocr_image(self, image: object, language: str, timeout: object = None) -> str:
        return self.recognize(image, language, timeout).text


def _img() -> Image.Image:
    return Image.new("RGB", (10, 10))


def _out(text: str = "hello", conf: float | None = 80.0, engine: str = "primary") -> OcrOutput:
    return OcrOutput(text=text, confidence=conf, engine=engine)


# ---------------------------------------------------------------------------
# Primary confident → secondary not called
# ---------------------------------------------------------------------------


def test_primary_confident_secondary_not_called() -> None:
    primary = _FakeEngine([_out("good text", 90.0, "tesseract")])
    secondary = _FakeEngine([_out("other", 95.0, "easyocr")])
    fallback = FallbackOcr(primary, secondary, min_confidence=60.0)

    result = fallback.recognize(_img(), "eng")
    assert result.text == "good text"
    assert secondary.call_count == 0


# ---------------------------------------------------------------------------
# Primary low confidence → secondary wins
# ---------------------------------------------------------------------------


def test_secondary_wins_when_higher_confidence() -> None:
    primary = _FakeEngine([_out("weak", 30.0, "tesseract")])
    secondary = _FakeEngine([_out("strong", 90.0, "easyocr")])
    fallback = FallbackOcr(primary, secondary, min_confidence=60.0)

    result = fallback.recognize(_img(), "eng")
    assert result.text == "strong"
    assert result.confidence == pytest.approx(90.0)
    assert "tesseract" in result.engine
    assert "easyocr" in result.engine


# ---------------------------------------------------------------------------
# Primary blank text → secondary tried
# ---------------------------------------------------------------------------


def test_secondary_tried_when_primary_blank() -> None:
    primary = _FakeEngine([_out("", 90.0, "tesseract")])
    secondary = _FakeEngine([_out("recovered", 85.0, "easyocr")])
    fallback = FallbackOcr(primary, secondary, min_confidence=60.0)

    result = fallback.recognize(_img(), "eng")
    assert result.text == "recovered"


# ---------------------------------------------------------------------------
# Secondary unavailable → keep primary + SECONDARY_OCR_SKIPPED warning
# ---------------------------------------------------------------------------


def test_secondary_unavailable_keeps_primary_with_warning() -> None:
    primary = _FakeEngine([_out("primary text", 20.0, "tesseract")])

    class _UnavailableEngine:
        def recognize(self, image: object, language: str, timeout: object = None) -> OcrOutput:
            raise AppError("OCR_ENGINE_UNAVAILABLE", "not installed", 503)
        def version(self) -> str: return "unavailable"
        def available_languages(self) -> list[str]: return []
        def ocr_image(self, image: object, language: str, timeout: object = None) -> str: return ""

    fallback = FallbackOcr(primary, _UnavailableEngine(), min_confidence=60.0)
    result = fallback.recognize(_img(), "eng")
    assert result.text == "primary text"
    assert "SECONDARY_OCR_SKIPPED" in result.warnings


# ---------------------------------------------------------------------------
# Unsupported language → keep primary + SECONDARY_OCR_SKIPPED warning
# ---------------------------------------------------------------------------


def test_unsupported_language_keeps_primary_with_warning() -> None:
    primary = _FakeEngine([_out("native result", 15.0, "tesseract")])

    class _UnsupportedEngine:
        def recognize(self, image: object, language: str, timeout: object = None) -> OcrOutput:
            raise AppError("OCR_LANGUAGE_UNSUPPORTED", f"not supported: {language}", 422)
        def version(self) -> str: return "fake"
        def available_languages(self) -> list[str]: return []
        def ocr_image(self, image: object, language: str, timeout: object = None) -> str: return ""

    fallback = FallbackOcr(primary, _UnsupportedEngine(), min_confidence=60.0)
    result = fallback.recognize(_img(), "fra+eng+ara")
    assert result.text == "native result"
    assert "SECONDARY_OCR_SKIPPED" in result.warnings


# ---------------------------------------------------------------------------
# version() and available_languages() delegate to primary
# ---------------------------------------------------------------------------


def test_delegation_to_primary() -> None:
    primary = _FakeEngine([], name="tess")
    secondary = _FakeEngine([], name="easy")
    fallback = FallbackOcr(primary, secondary, min_confidence=60.0)
    assert fallback.version() == "tess-1.0"
    assert "eng" in fallback.available_languages()


# ---------------------------------------------------------------------------
# EasyOCR not installed → OCR_ENGINE_UNAVAILABLE from deps
# ---------------------------------------------------------------------------


def test_easyocr_not_installed_raises_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """When easyocr is not importable, EasyOcrEngine.version() raises."""
    import sys

    # Remove easyocr from sys.modules and prevent import
    sys.modules.pop("easyocr", None)
    monkeypatch.setitem(sys.modules, "easyocr", None)  # type: ignore[arg-type]

    from app.extraction.ocr_easyocr import EasyOcrEngine
    engine = EasyOcrEngine()
    with pytest.raises(AppError) as exc_info:
        engine.version()
    assert exc_info.value.code == "OCR_ENGINE_UNAVAILABLE"


# ---------------------------------------------------------------------------
# Health endpoint shape includes ocr_engines
# ---------------------------------------------------------------------------


def test_health_includes_ocr_engines_key() -> None:
    from fastapi.testclient import TestClient

    from app.api.deps import get_ocr_engine
    from app.main import create_app

    app = create_app()
    # Use primary fake with version
    class _FakeOcrForHealth:
        def version(self) -> str: return "5.0"
        def available_languages(self) -> list[str]: return ["eng", "fra", "ara"]
        def ocr_image(self, *a, **kw) -> str: return ""  # noqa: ANN001

    app.dependency_overrides[get_ocr_engine] = lambda: _FakeOcrForHealth()
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "tesseract" in data
    assert "ocr_engines" in data
    assert "tesseract" in data["ocr_engines"]
    assert "easyocr" in data["ocr_engines"]
    assert isinstance(data["ocr_engines"]["easyocr"]["available"], bool)
