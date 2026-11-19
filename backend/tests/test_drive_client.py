"""Tests for DriveClient using httpx.MockTransport."""

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

_FOLDER_ID = "folder_ABC123XYZ"
_API_BASE = "https://www.googleapis.com/drive/v3"

_PDF_FILE = {
    "id": "file_pdf_001",
    "name": "report.pdf",
    "mimeType": "application/pdf",
    "size": "102400",
}
_IMG_FILE = {
    "id": "file_img_001",
    "name": "photo.jpg",
    "mimeType": "image/jpeg",
    "size": "51200",
}
_IMG_NO_SIZE = {
    "id": "file_img_002",
    "name": "scan.png",
    "mimeType": "image/png",
}


def _settings(**overrides: Any) -> Settings:
    defaults: dict[str, Any] = {
        "google_api_key": "test-key-abc",
        "cors_origins": ["http://localhost:5173"],
        "max_listed_files": 500,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _json_response(data: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=data)


def _make_client(
    handler: Callable[[httpx.Request], httpx.Response],
    settings: Settings | None = None,
    sleep: Callable[[float], None] | None = None,
) -> DriveClient:
    transport = httpx.MockTransport(handler)
    return DriveClient(
        settings=settings or _settings(),
        transport=transport,
        sleep=sleep or (lambda _: None),
        jitter=lambda: 0.0,  # deterministic delays in tests
    )


# ---------------------------------------------------------------------------
# Single-page listing
# ---------------------------------------------------------------------------


def test_list_folder_single_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response({"files": [_PDF_FILE, _IMG_FILE]})

    client = _make_client(handler)
    files = client.list_folder(_FOLDER_ID)

    assert len(files) == 2
    assert files[0].id == "file_pdf_001"
    assert files[0].kind == "pdf"
    assert files[0].size_bytes == 102400
    assert files[1].id == "file_img_001"
    assert files[1].kind == "image"


# ---------------------------------------------------------------------------
# Two pages merged
# ---------------------------------------------------------------------------


def test_list_folder_two_pages_merged() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if "pageToken" not in str(request.url):
            return _json_response(
                {"nextPageToken": "tok123", "files": [_PDF_FILE]}
            )
        return _json_response({"files": [_IMG_FILE]})

    client = _make_client(handler)
    files = client.list_folder(_FOLDER_ID)

    assert len(calls) == 2
    assert len(files) == 2
    assert {f.id for f in files} == {"file_pdf_001", "file_img_001"}


# ---------------------------------------------------------------------------
# size_bytes is None when Drive omits the field
# ---------------------------------------------------------------------------


def test_size_bytes_none_when_absent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response({"files": [_IMG_NO_SIZE]})

    files = _make_client(handler).list_folder(_FOLDER_ID)
    assert files[0].size_bytes is None


# ---------------------------------------------------------------------------
# Query string contains q filter; API key is in header only
# ---------------------------------------------------------------------------


def test_q_filter_in_query_string() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return _json_response({"files": []})

    _make_client(handler).list_folder(_FOLDER_ID)

    req = captured[0]
    q = req.url.params["q"]
    assert _FOLDER_ID in q
    assert "trashed = false" in q
    assert "application/pdf" in q
    assert "image/jpeg" in q


def test_api_key_in_header_not_query_string() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return _json_response({"files": []})

    _make_client(handler).list_folder(_FOLDER_ID)

    req = captured[0]
    assert req.headers.get("x-goog-api-key") == "test-key-abc"
    assert "key" not in req.url.params


# ---------------------------------------------------------------------------
# max_listed_files stops early
# ---------------------------------------------------------------------------


def test_max_listed_files_respected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # Return 3 files per page endlessly with a next token
        return _json_response(
            {
                "nextPageToken": "more",
                "files": [_PDF_FILE, _IMG_FILE, _IMG_NO_SIZE],
            }
        )

    client = _make_client(handler, settings=_settings(max_listed_files=2))
    files = client.list_folder(_FOLDER_ID)
    assert len(files) == 2


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------


def test_404_raises_folder_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response({"error": {"code": 404, "message": "not found"}}, 404)

    with pytest.raises(AppError) as exc_info:
        _make_client(handler).list_folder(_FOLDER_ID)

    assert exc_info.value.code == "FOLDER_NOT_FOUND_OR_PRIVATE"
    assert exc_info.value.status_code == 404


def test_403_forbidden_raises_folder_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            {"error": {"errors": [{"reason": "forbidden", "message": "no access"}]}},
            403,
        )

    with pytest.raises(AppError) as exc_info:
        _make_client(handler).list_folder(_FOLDER_ID)

    assert exc_info.value.code == "FOLDER_NOT_FOUND_OR_PRIVATE"


def test_403_quota_raises_drive_quota() -> None:
    # dailyLimitExceeded is non-retryable and maps directly to DRIVE_QUOTA
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            {
                "error": {
                    "errors": [
                        {
                            "reason": "dailyLimitExceeded",
                            "message": "daily limit",
                        }
                    ]
                }
            },
            403,
        )

    with pytest.raises(AppError) as exc_info:
        _make_client(handler).list_folder(_FOLDER_ID)

    assert exc_info.value.code == "DRIVE_QUOTA"
    assert exc_info.value.status_code == 429


def test_429_raises_drive_quota() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429)

    with pytest.raises(AppError) as exc_info:
        _make_client(handler).list_folder(_FOLDER_ID)

    assert exc_info.value.code == "DRIVE_QUOTA"


def test_key_invalid_raises_drive_not_configured() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            {
                "error": {
                    "errors": [{"reason": "keyInvalid", "message": "bad key"}]
                }
            },
            400,
        )

    with pytest.raises(AppError) as exc_info:
        _make_client(handler).list_folder(_FOLDER_ID)

    assert exc_info.value.code == "DRIVE_NOT_CONFIGURED"
    assert exc_info.value.status_code == 500


def test_5xx_raises_drive_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    with pytest.raises(AppError) as exc_info:
        _make_client(handler).list_folder(_FOLDER_ID)

    assert exc_info.value.code == "DRIVE_UNAVAILABLE"
    assert exc_info.value.status_code == 502


# ---------------------------------------------------------------------------
# Retry on transient 503, then success
# ---------------------------------------------------------------------------


def test_retry_503_then_success() -> None:
    attempts: list[int] = []
    sleep_calls: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) < 3:
            return httpx.Response(503)
        return _json_response({"files": [_PDF_FILE]})

    client = _make_client(handler, sleep=sleep_calls.append)
    files = client.list_folder(_FOLDER_ID)

    assert len(files) == 1
    assert len(attempts) == 3  # failed twice, succeeded third
    assert sleep_calls == [0.5, 1.0]


def test_retry_exhausted_raises_last_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    with pytest.raises(AppError) as exc_info:
        _make_client(handler).list_folder(_FOLDER_ID)

    # 3 total attempts (initial + 2 retries), raises DRIVE_UNAVAILABLE
    assert exc_info.value.code == "DRIVE_UNAVAILABLE"


# ---------------------------------------------------------------------------
# Missing API key
# ---------------------------------------------------------------------------


def test_missing_api_key_raises_drive_not_configured() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        return _json_response({"files": []})

    client = _make_client(handler, settings=_settings(google_api_key=None))
    with pytest.raises(AppError) as exc_info:
        client.list_folder(_FOLDER_ID)

    assert exc_info.value.code == "DRIVE_NOT_CONFIGURED"
    assert exc_info.value.status_code == 500
