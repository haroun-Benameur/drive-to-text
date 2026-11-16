"""Tests for DriveClient.get_metadata and DriveClient.download."""

from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.config import Settings
from app.drive.client import DriveClient
from app.errors import AppError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_ID = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"
_INVALID_ID = "short"
_MAX_BYTES = 1024 * 1024  # 1 MB


def _settings(**overrides: Any) -> Settings:
    defaults: dict[str, Any] = {
        "google_api_key": "test-key",
        "cors_origins": ["http://localhost:5173"],
        "max_listed_files": 500,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _make_client(
    handler: Callable[[httpx.Request], httpx.Response],
    settings: Settings | None = None,
) -> DriveClient:
    return DriveClient(
        settings=settings or _settings(),
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    )


def _json_response(data: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=data)


# ---------------------------------------------------------------------------
# get_metadata – happy path
# ---------------------------------------------------------------------------


def test_get_metadata_returns_model() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            {
                "id": _VALID_ID,
                "name": "report.pdf",
                "mimeType": "application/pdf",
                "size": "204800",
                "trashed": False,
            }
        )

    meta = _make_client(handler).get_metadata(_VALID_ID)

    assert meta.id == _VALID_ID
    assert meta.name == "report.pdf"
    assert meta.mime_type == "application/pdf"
    assert meta.size_bytes == 204800


def test_get_metadata_size_none_when_absent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            {"id": _VALID_ID, "name": "scan.png", "mimeType": "image/png", "trashed": False}
        )

    meta = _make_client(handler).get_metadata(_VALID_ID)
    assert meta.size_bytes is None


def test_get_metadata_trashed_raises_file_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            {"id": _VALID_ID, "name": "old.pdf", "mimeType": "application/pdf", "trashed": True}
        )

    with pytest.raises(AppError) as exc_info:
        _make_client(handler).get_metadata(_VALID_ID)

    assert exc_info.value.code == "FILE_NOT_FOUND"
    assert exc_info.value.status_code == 404


def test_get_metadata_404_raises_file_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response({"error": {"code": 404}}, 404)

    with pytest.raises(AppError) as exc_info:
        _make_client(handler).get_metadata(_VALID_ID)

    assert exc_info.value.code == "FILE_NOT_FOUND"


def test_get_metadata_invalid_id_raises_invalid_file_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        return _json_response({})

    with pytest.raises(AppError) as exc_info:
        _make_client(handler).get_metadata(_INVALID_ID)

    assert exc_info.value.code == "INVALID_FILE_ID"
    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# download – happy path
# ---------------------------------------------------------------------------


def test_download_returns_bytes() -> None:
    body = b"PDF content here"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    result = _make_client(handler).download(_VALID_ID, _MAX_BYTES)
    assert result == body


def test_download_uses_alt_media_param() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=b"data")

    _make_client(handler).download(_VALID_ID, _MAX_BYTES)

    req = captured[0]
    assert req.url.params.get("alt") == "media"
    assert req.url.params.get("supportsAllDrives") == "true"


# ---------------------------------------------------------------------------
# download – Content-Length too large
# ---------------------------------------------------------------------------


def test_download_content_length_too_large_raises_file_too_large() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"x" * 10,
            headers={"content-length": str(_MAX_BYTES + 1)},
        )

    with pytest.raises(AppError) as exc_info:
        _make_client(handler).download(_VALID_ID, _MAX_BYTES)

    assert exc_info.value.code == "FILE_TOO_LARGE"
    assert exc_info.value.status_code == 413


# ---------------------------------------------------------------------------
# download – streamed body too large (no Content-Length)
# ---------------------------------------------------------------------------


def test_download_streamed_body_too_large_raises_file_too_large() -> None:
    # Body is 1 byte over the limit; no Content-Length header.
    over_limit = b"x" * (_MAX_BYTES + 1)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=over_limit)

    with pytest.raises(AppError) as exc_info:
        _make_client(handler).download(_VALID_ID, _MAX_BYTES)

    assert exc_info.value.code == "FILE_TOO_LARGE"
    assert exc_info.value.status_code == 413


# ---------------------------------------------------------------------------
# download – 404
# ---------------------------------------------------------------------------


def test_download_404_raises_file_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response({"error": {"code": 404}}, 404)

    with pytest.raises(AppError) as exc_info:
        _make_client(handler).download(_VALID_ID, _MAX_BYTES)

    assert exc_info.value.code == "FILE_NOT_FOUND"
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# download – invalid file ID rejected before any network call
# ---------------------------------------------------------------------------


def test_download_invalid_id_raises_invalid_file_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        return httpx.Response(200, content=b"")

    with pytest.raises(AppError) as exc_info:
        _make_client(handler).download(_INVALID_ID, _MAX_BYTES)

    assert exc_info.value.code == "INVALID_FILE_ID"
    assert exc_info.value.status_code == 422
