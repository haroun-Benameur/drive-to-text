"""Tests for exception handlers registered by register_exception_handlers."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.errors import AppError, register_exception_handlers

# ---------------------------------------------------------------------------
# Minimal test application
# ---------------------------------------------------------------------------


def _make_app() -> FastAPI:
    test_app = FastAPI()
    register_exception_handlers(test_app)

    class _Body(BaseModel):
        value: int

    @test_app.get("/app-error")
    async def raise_app_error() -> None:
        raise AppError(code="SOME_CODE", message="something went wrong", status_code=409)

    @test_app.post("/validation-error")
    async def raise_validation_error(body: _Body) -> dict:
        return {"value": body.value}

    @test_app.get("/unhandled-error")
    async def raise_unhandled_error() -> None:
        raise RuntimeError("boom")

    return test_app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(_make_app(), raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# AppError
# ---------------------------------------------------------------------------


def test_app_error_status_code(client: TestClient) -> None:
    response = client.get("/app-error")
    assert response.status_code == 409


def test_app_error_envelope(client: TestClient) -> None:
    data = client.get("/app-error").json()
    assert "error" in data
    assert data["error"]["code"] == "SOME_CODE"
    assert data["error"]["message"] == "something went wrong"


# ---------------------------------------------------------------------------
# RequestValidationError
# ---------------------------------------------------------------------------


def test_validation_error_status_code(client: TestClient) -> None:
    response = client.post("/validation-error", json={"value": "not-an-int"})
    assert response.status_code == 422


def test_validation_error_envelope(client: TestClient) -> None:
    data = client.post("/validation-error", json={"value": "not-an-int"}).json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert isinstance(data["error"]["message"], str)
    assert len(data["error"]["message"]) > 0


# ---------------------------------------------------------------------------
# Unhandled Exception
# ---------------------------------------------------------------------------


def test_unhandled_error_status_code(client: TestClient) -> None:
    response = client.get("/unhandled-error")
    assert response.status_code == 500


def test_unhandled_error_envelope(client: TestClient) -> None:
    data = client.get("/unhandled-error").json()
    assert "error" in data
    assert data["error"]["code"] == "INTERNAL_ERROR"
    assert data["error"]["message"] == "Unexpected server error."


def test_unhandled_error_no_stack_trace(client: TestClient) -> None:
    """Response body must not leak implementation details."""
    text = client.get("/unhandled-error").text
    assert "boom" not in text
    assert "Traceback" not in text
