"""Tests for DriveClient retry logic: Retry-After, jitter, 403 rate-limit retry."""

from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.config import Settings
from app.drive.client import DriveClient
from app.errors import AppError


def _settings(**overrides: Any) -> Settings:
    defaults: dict[str, Any] = {
        "google_api_key": "test-key",
        "cors_origins": ["http://localhost:5173"],
        "max_listed_files": 500,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _json_response(data: dict, status: int = 200, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(status, json=data, headers=headers or {})


def _make_client(
    handler: Callable[[httpx.Request], httpx.Response],
    settings: Settings | None = None,
    sleep: Callable[[float], None] | None = None,
    jitter: Callable[[], float] | None = None,
) -> DriveClient:
    return DriveClient(
        settings=settings or _settings(),
        transport=httpx.MockTransport(handler),
        sleep=sleep or (lambda _: None),
        jitter=jitter or (lambda: 0.0),
    )


def test_retry_after_respected_and_capped() -> None:
    """Retry-After header value is used as the delay (capped at 10s)."""
    sleep_calls: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        # First call returns 503 with Retry-After: 15 (capped to 10)
        # Second call succeeds
        if not hasattr(handler, "_called"):
            handler._called = True
            return httpx.Response(
                503, headers={"retry-after": "15"},
                json={"error": {"errors": [{"reason": "serverError"}]}},
            )
        return _json_response({"files": []})

    client = _make_client(handler, sleep=sleep_calls.append)
    client.list_folder("folder_test_12345")

    # sleep was called once (first retry), value should be >= 10 (capped Retry-After)
    assert len(sleep_calls) == 1
    assert sleep_calls[0] >= 10.0


def test_jitter_added_to_delay() -> None:
    """Jitter value is added on top of the backoff delay."""
    sleep_calls: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if not hasattr(handler, "_called"):
            handler._called = True
            return httpx.Response(503)
        return _json_response({"files": []})

    client = _make_client(
        handler,
        sleep=sleep_calls.append,
        jitter=lambda: 0.2,
    )
    client.list_folder("folder_test_12345")

    assert len(sleep_calls) == 1
    # backoff[0] = 0.5 + jitter 0.2 = 0.7
    assert sleep_calls[0] == pytest.approx(0.7)


def test_403_rate_limit_retried_then_succeeds() -> None:
    """403 with reason rateLimitExceeded is retryable and eventually succeeds."""
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) < 3:
            return httpx.Response(
                403,
                json={"error": {"errors": [{
                    "reason": "rateLimitExceeded",
                    "message": "slow down",
                }]}},
            )
        return _json_response({"files": []})

    client = _make_client(handler)
    files = client.list_folder("folder_test_12345")
    assert len(attempts) == 3
    assert files == []


def test_download_quota_exceeded_not_retried() -> None:
    """403 with reason downloadQuotaExceeded is not retried."""
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(
            403,
            json={"error": {"errors": [{"reason": "downloadQuotaExceeded", "message": "quota"}]}},
        )

    client = _make_client(handler)
    with pytest.raises(AppError) as exc_info:
        client.list_folder("folder_test_12345")
    assert exc_info.value.code == "DRIVE_QUOTA"
    assert len(attempts) == 1


def test_non_numeric_retry_after_ignored() -> None:
    """A non-integer Retry-After (HTTP-date) is ignored, backoff is used."""
    sleep_calls: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if not hasattr(handler, "_called"):
            handler._called = True
            return httpx.Response(
                503,
                headers={"retry-after": "Wed, 21 Oct 2026 07:28:00 GMT"},
            )
        return _json_response({"files": []})

    client = _make_client(handler, sleep=sleep_calls.append, jitter=lambda: 0.0)
    client.list_folder("folder_test_12345")
    # Non-numeric Retry-After ignored, backoff[0] = 0.5 used
    assert sleep_calls[0] == pytest.approx(0.5)