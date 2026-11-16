"""Tests for GET /api/health and CORS behaviour."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import create_app

_ALLOWED_ORIGIN = "http://localhost:5173"
_DISALLOWED_ORIGIN = "http://evil.example.com"


@pytest.fixture(scope="module")
def client() -> TestClient:
    """TestClient wired to an app that allows *_ALLOWED_ORIGIN*."""
    get_settings.cache_clear()
    test_settings = Settings(cors_origins=[_ALLOWED_ORIGIN])

    def _override() -> Settings:
        return test_settings

    app = create_app()
    app.dependency_overrides[get_settings] = _override
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


def test_health_status_code(client: TestClient) -> None:
    assert client.get("/api/health").status_code == 200


def test_health_payload(client: TestClient) -> None:
    data = client.get("/api/health").json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
    assert "tesseract" in data


# ---------------------------------------------------------------------------
# CORS preflight
# ---------------------------------------------------------------------------


def test_cors_allowed_origin_receives_header(client: TestClient) -> None:
    response = client.options(
        "/api/health",
        headers={
            "Origin": _ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") == _ALLOWED_ORIGIN


def test_cors_disallowed_origin_no_header(client: TestClient) -> None:
    response = client.options(
        "/api/health",
        headers={
            "Origin": _DISALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in response.headers
