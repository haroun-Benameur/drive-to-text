"""Tests for extended GET /api/health (Tesseract status)."""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_ocr_engine
from app.errors import AppError
from app.main import create_app


class _FakeOcrAvailable:
    def version(self) -> str:
        return "5.3.0"

    def available_languages(self) -> list[str]:
        return ["eng", "fra", "ara", "osd"]

    def ocr_image(
        self, image, language: str, timeout: float | None = None
    ) -> str:  # pragma: no cover
        return ""


class _FakeOcrUnavailable:
    def version(self) -> str:
        raise AppError("OCR_ENGINE_UNAVAILABLE", "Tesseract not found.", 503)

    def available_languages(self) -> list[str]:  # pragma: no cover
        raise AppError("OCR_ENGINE_UNAVAILABLE", "Tesseract not found.", 503)

    def ocr_image(
        self, image, language: str, timeout: float | None = None
    ) -> str:  # pragma: no cover
        return ""


@pytest.fixture()
def client_available() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_ocr_engine] = lambda: _FakeOcrAvailable()
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def client_unavailable() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_ocr_engine] = lambda: _FakeOcrUnavailable()
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Engine available
# ---------------------------------------------------------------------------


def test_health_200_when_engine_available(client_available: TestClient) -> None:
    assert client_available.get("/api/health").status_code == 200


def test_health_includes_status_and_version(client_available: TestClient) -> None:
    data = client_available.get("/api/health").json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"


def test_health_tesseract_available_true(client_available: TestClient) -> None:
    data = client_available.get("/api/health").json()
    t = data["tesseract"]
    assert t["available"] is True
    assert t["version"] == "5.3.0"
    assert "eng" in t["languages"]


def test_health_missing_languages_subset(client_available: TestClient) -> None:
    # _FakeOcrAvailable has eng, fra, ara → no required languages missing
    data = client_available.get("/api/health").json()
    assert data["tesseract"]["missing_languages"] == []


# ---------------------------------------------------------------------------
# Engine unavailable – must still return HTTP 200
# ---------------------------------------------------------------------------


def test_health_200_when_engine_unavailable(client_unavailable: TestClient) -> None:
    assert client_unavailable.get("/api/health").status_code == 200


def test_health_tesseract_available_false(client_unavailable: TestClient) -> None:
    data = client_unavailable.get("/api/health").json()
    t = data["tesseract"]
    assert t["available"] is False
    assert t["version"] is None


def test_health_missing_languages_all_required_when_unavailable(
    client_unavailable: TestClient,
) -> None:
    data = client_unavailable.get("/api/health").json()
    missing = set(data["tesseract"]["missing_languages"])
    assert missing == {"fra", "eng", "ara"}
