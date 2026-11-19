"""Google Drive REST v3 client."""

import logging
import random
import ssl
import time as time_module
from collections.abc import Callable
from typing import Any, Literal

import httpx
import truststore

from app.config import Settings
from app.drive.url import is_valid_drive_id
from app.errors import AppError, safe_text
from app.models import DriveFile, DriveFileMeta

logger = logging.getLogger(__name__)


def _system_ssl_context() -> ssl.SSLContext:
    """Return an SSL context that trusts the OS / Windows certificate store."""
    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    return ctx

_PDF_MIME = "application/pdf"
_IMAGE_MIMES = {"image/png", "image/jpeg"}

_FILES_Q = (
    "trashed = false and ("
    "mimeType = 'application/pdf' or "
    "mimeType = 'image/png' or "
    "mimeType = 'image/jpeg'"
    ")"
)

_BACKOFF = (0.5, 1.0)
_RETRY_AFTER_CAP = 10.0

# 403 reasons that are retryable (transient rate limits).
_RETRYABLE_403_REASONS = {"rateLimitExceeded", "userRateLimitExceeded"}
# 403 reasons that mean quota exhausted — never retry.
_NON_RETRYABLE_QUOTA_REASONS = {"dailyLimitExceeded", "downloadQuotaExceeded"}


def _kind(mime_type: str) -> Literal["pdf", "image"]:
    if mime_type == _PDF_MIME:
        return "pdf"
    return "image"


def _parse_retry_after(value: str | None) -> float | None:
    """Parse Retry-After as integer seconds. Ignore HTTP-date form."""
    if value is None:
        return None
    try:
        return min(float(value), _RETRY_AFTER_CAP)
    except (ValueError, TypeError):
        return None


def _read_reason(response: httpx.Response) -> str:
    """Extract the structured error reason from a Drive API response."""
    try:
        body: dict[str, Any] = response.json()
        errors = body.get("error", {}).get("errors", [])
        if errors:
            return errors[0].get("reason", "")
    except Exception:
        pass
    return ""


def _map_error(
    response: httpx.Response,
    not_found_code: str = "FOLDER_NOT_FOUND_OR_PRIVATE",
) -> AppError:
    """Translate a Drive API error response into an :class:`AppError`."""
    status = response.status_code
    reason = _read_reason(response)

    if reason == "keyInvalid":
        return AppError("DRIVE_NOT_CONFIGURED", "API key is invalid.", 500)

    if status == 429 or (status == 403 and reason in _NON_RETRYABLE_QUOTA_REASONS):
        return AppError("DRIVE_QUOTA", "Drive API quota exceeded.", 429)

    if status in (403, 404):
        return AppError(
            not_found_code,
            "File or folder not found or not accessible.",
            404,
        )

    if status >= 500:
        return AppError("DRIVE_UNAVAILABLE", "Drive API is unavailable.", 502)

    return AppError(
        "DRIVE_UNAVAILABLE",
        f"Unexpected Drive API response: {status}.",
        502,
    )


def _is_retryable(response: httpx.Response) -> bool:
    """Return True for 429, 5xx, and 403 with transient rate-limit reasons."""
    if response.status_code == 429 or response.status_code >= 500:
        return True
    if response.status_code == 403:
        reason = _read_reason(response)
        return reason in _RETRYABLE_403_REASONS
    return False


class DriveClient:
    """Thin wrapper around the Drive Files REST API."""

    def __init__(
        self,
        settings: Settings,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time_module.sleep,
        jitter: Callable[[], float] | None = None,
    ) -> None:
        self._key = settings.google_api_key
        self._max_listed = settings.max_listed_files
        self._sleep = sleep
        self._jitter = jitter if jitter is not None else (lambda: random.uniform(0, 0.25))

        client_kwargs: dict[str, Any] = {
            "base_url": "https://www.googleapis.com/drive/v3",
            "timeout": httpx.Timeout(30.0, connect=10.0),
            "follow_redirects": False,
        }
        if transport is not None:
            client_kwargs["transport"] = transport
        else:
            client_kwargs["verify"] = _system_ssl_context()

        self._client = httpx.Client(**client_kwargs)

    def _headers(self) -> dict[str, str]:
        if self._key is None:
            raise AppError(
                "DRIVE_NOT_CONFIGURED",
                "Google Drive API key is not configured.",
                500,
            )
        return {"X-Goog-Api-Key": self._key}

    def _get(
        self,
        path: str,
        params: dict[str, Any],
        not_found_code: str = "FOLDER_NOT_FOUND_OR_PRIVATE",
    ) -> httpx.Response:
        """GET *path* with retry on transient errors."""
        headers = self._headers()
        last_error: AppError | None = None
        last_response: httpx.Response | None = None

        for attempt, backoff in enumerate([0.0] + list(_BACKOFF)):
            if backoff:
                # Compute delay: max(backoff, Retry-After) + jitter
                retry_after = _parse_retry_after(
                    last_response.headers.get("retry-after")
                    if last_response is not None else None
                )
                base_delay = max(backoff, retry_after or 0)
                delay = base_delay + self._jitter()
                self._sleep(delay)

            response = self._client.get(path, params=params, headers=headers)
            if response.is_success:
                return response

            err = _map_error(response, not_found_code)
            if not _is_retryable(response):
                raise err
            last_error = err
            last_response = response
            logger.warning(
                "Drive API transient error (attempt %d): %s %s",
                attempt + 1,
                response.status_code,
                response.text[:200],
            )

        raise last_error  # type: ignore[misc]

    def list_folder(self, folder_id: str) -> list[DriveFile]:
        """Return all PDF/image files directly inside *folder_id*."""
        q = f"'{folder_id}' in parents and {_FILES_Q}"
        params: dict[str, Any] = {
            "q": q,
            "fields": "nextPageToken,files(id,name,mimeType,size)",
            "pageSize": 1000,
            "orderBy": "name",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        }

        files: list[DriveFile] = []

        while True:
            response = self._get("/files", params)
            data = response.json()

            for item in data.get("files", []):
                mime = item.get("mimeType", "")
                raw_size = item.get("size")
                files.append(
                    DriveFile(
                        id=item["id"],
                        name=item.get("name", ""),
                        mime_type=mime,
                        kind=_kind(mime),
                        size_bytes=int(raw_size) if raw_size is not None else None,
                    )
                )
                if len(files) >= self._max_listed:
                    return files

            next_token: str | None = data.get("nextPageToken")
            if not next_token:
                break
            params = {**params, "pageToken": next_token}

        return files

    def _validate_file_id(self, file_id: str) -> None:
        """Raise INVALID_FILE_ID if *file_id* does not match the Drive ID format."""
        if not is_valid_drive_id(file_id):
            raise AppError(
                "INVALID_FILE_ID",
                f"'{safe_text(file_id)}' is not a valid Drive file ID.",
                422,
            )

    def get_metadata(self, file_id: str) -> DriveFileMeta:
        """Return metadata for a single Drive file.

        Raises FILE_NOT_FOUND (404) if the file is trashed or absent.
        """
        self._validate_file_id(file_id)
        response = self._get(
            f"/files/{file_id}",
            params={
                "fields": "id,name,mimeType,size,trashed,md5Checksum",
                "supportsAllDrives": "true",
            },
            not_found_code="FILE_NOT_FOUND",
        )
        data = response.json()
        if data.get("trashed"):
            raise AppError("FILE_NOT_FOUND", "File has been trashed.", 404)
        raw_size = data.get("size")
        return DriveFileMeta(
            id=data["id"],
            name=data.get("name", ""),
            mime_type=data.get("mimeType", ""),
            size_bytes=int(raw_size) if raw_size is not None else None,
            md5_checksum=data.get("md5Checksum"),
        )

    def download(self, file_id: str, max_bytes: int) -> bytes:
        """Download the content of a Drive file, enforcing *max_bytes*."""
        self._validate_file_id(file_id)
        headers = self._headers()
        params: dict[str, Any] = {
            "alt": "media",
            "supportsAllDrives": "true",
        }

        with self._client.stream(
            "GET", f"/files/{file_id}", params=params, headers=headers
        ) as response:
            if not response.is_success:
                response.read()
                raise _map_error(response, not_found_code="FILE_NOT_FOUND")

            content_length = response.headers.get("content-length")
            if content_length is not None and int(content_length) > max_bytes:
                raise AppError(
                    "FILE_TOO_LARGE",
                    f"File exceeds the {max_bytes}-byte limit"
                    f" (Content-Length: {content_length}).",
                    413,
                )

            chunks: list[bytes] = []
            received = 0
            for chunk in response.iter_bytes():
                received += len(chunk)
                if received > max_bytes:
                    raise AppError(
                        "FILE_TOO_LARGE",
                        f"File exceeds the {max_bytes}-byte limit.",
                        413,
                    )
                chunks.append(chunk)

        return b"".join(chunks)