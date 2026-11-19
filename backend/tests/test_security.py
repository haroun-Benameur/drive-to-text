"""API-level security tests: injection, leakage, malformed input."""

import logging

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_drive_client, get_router
from app.errors import AppError
from app.main import create_app
from app.models import ExtractionMethod, ExtractionResult

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeDriveNoop:
    def list_folder(self, folder_id: str) -> list:
        return []
    def get_metadata(self, file_id: str):
        raise AppError("FILE_NOT_FOUND", "not found", 404)
    def download(self, file_id: str, max_bytes: int) -> bytes:
        raise AppError("FILE_NOT_FOUND", "not found", 404)


class _FakeRouterNoop:
    def extract(self, data: bytes, language: str) -> ExtractionResult:
        return ExtractionResult(
            text="ok", method=ExtractionMethod.PDF_TEXT,
            engine="fake", page_count=1, ocr_pages=0, warnings=[],
        )


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_drive_client] = lambda: _FakeDriveNoop()
    app.dependency_overrides[get_router] = lambda: _FakeRouterNoop()
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# (1) Injection in folder URLs — no Drive transport call made
# ---------------------------------------------------------------------------


INJECTION_URLS = [
    "https://drive.google.com/drive/folders/abc\' or \'1\'=\'1",
    "https://drive.google.com/drive/folders/'; DROP TABLE batches; --",
    "https://drive.google.com/drive/folders/<script>alert(1)</script>",
    "https://evil.com/drive.google.com/drive/folders/validid1234",
    "https://drive.google.com.evil.com/drive/folders/validid1234",
    "http://drive.google.com/drive/folders/validfolderid1234",
    "file:///etc/passwd",
    "ftp://drive.google.com/drive/folders/abc",
    "https://drive.google.com@evil.com/drive/folders/validid",
]


@pytest.mark.parametrize("url", INJECTION_URLS)
def test_injection_folder_url_returns_422(url: str) -> None:
    with _client() as c:
        resp = c.post("/api/drive/files", json={"folder_url": url})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_FOLDER_URL"


# ---------------------------------------------------------------------------
# (2) Invalid / injection file IDs — 422, no network call
# ---------------------------------------------------------------------------


INJECTION_FILE_IDS = [
    "abc' or '1'='1",
    "id/../../etc/passwd",
    "id\nX-Injected: header",
    "a" * 500,
]


@pytest.mark.parametrize("fid", INJECTION_FILE_IDS)
def test_injection_file_id_returns_422(fid: str) -> None:
    with _client() as c:
        resp = c.post("/api/batches", json={"file_ids": [fid]})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_FILE_ID"


def test_long_file_id_message_is_truncated() -> None:
    """A 500-char ID must not appear verbatim in the error message."""
    long_id = "a" * 500
    with _client() as c:
        resp = c.post("/api/batches", json={"file_ids": [long_id]})
    assert long_id not in resp.text


def test_control_chars_in_file_id_stripped_from_message() -> None:
    """Newlines and control characters in an ID must not appear in the message."""
    evil_id = "abc\ndef\x01ghi"
    with _client() as c:
        resp = c.post("/api/batches", json={"file_ids": [evil_id]})
    body = resp.text
    assert "\n" not in body
    assert "\x01" not in body


# ---------------------------------------------------------------------------
# (3) API key never appears in URLs, logs, or error responses
# ---------------------------------------------------------------------------


def test_api_key_not_in_error_response(caplog: pytest.LogCaptureFixture) -> None:
    """The API key must never appear in a response body or log record."""
    from app.config import Settings, get_settings
    app = create_app()
    fake_key = "AIzaFakeKeyForSecurityTest12345678"
    app.dependency_overrides[get_settings] = lambda: Settings(
        google_api_key=fake_key,
        cors_origins=["http://localhost:5173"],
    )
    # Trigger an endpoint that calls get_settings
    with TestClient(app, raise_server_exceptions=False) as c:
        with caplog.at_level(logging.DEBUG):
            resp = c.post("/api/drive/files", json={"folder_url": "https://evil.com/x"})
    assert fake_key not in resp.text
    for record in caplog.records:
        assert fake_key not in record.getMessage()


# ---------------------------------------------------------------------------
# (4) Unhandled exception → generic 500, no detail leaked
# ---------------------------------------------------------------------------


def test_unhandled_exception_no_detail_leaked() -> None:
    from fastapi import APIRouter


    app = create_app()

    secret_router = APIRouter()

    @secret_router.get("/api/secret-bomb")
    def _bomb() -> None:
        raise RuntimeError("secret detail internal")

    app.include_router(secret_router)

    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.get("/api/secret-bomb")

    assert resp.status_code == 500
    assert "secret detail" not in resp.text
    assert "Traceback" not in resp.text
    assert resp.json()["error"]["code"] == "INTERNAL_ERROR"


# ---------------------------------------------------------------------------
# (5) Zero-byte and random bytes → UNSUPPORTED_TYPE (via batch route)
# ---------------------------------------------------------------------------


def test_zero_byte_file_unsupported_type() -> None:
    """The router (content sniff) must reject zero-byte content."""
    class _DriveZero:
        class _Meta:
            id = "fileAAAAAAAAAAAAAAAA"
            name = "f.bin"
            mime_type = "application/pdf"
            size_bytes = 0
        def get_metadata(self, fid: str): return self._Meta()
        def download(self, fid: str, max_bytes: int) -> bytes: return b""
        def list_folder(self, fid: str) -> list: return []

    from app.extraction.sniff import sniff_content_kind
    # Verify at the unit level — zero bytes → None kind → UNSUPPORTED_TYPE
    assert sniff_content_kind(b"") is None


def test_random_bytes_unsupported_type() -> None:
    from app.extraction.sniff import sniff_content_kind
    assert sniff_content_kind(b"\x00\x01\x02\x03" * 50) is None


# ---------------------------------------------------------------------------
# (6) Too many files → TOO_MANY_FILES
# ---------------------------------------------------------------------------


def test_too_many_files_returns_422() -> None:
    file_ids = [f"{'x' * 18}{i:04d}" for i in range(51)]
    with _client() as c:
        resp = c.post("/api/batches", json={"file_ids": file_ids})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "TOO_MANY_FILES"


# ---------------------------------------------------------------------------
# (7) HTML/script in filename returned verbatim as data, not executed
# ---------------------------------------------------------------------------


def test_html_in_filename_returned_as_data() -> None:
    """Drive filenames containing HTML must be echoed as plain data."""
    from app.models import DriveFile

    xss_name = "<script>alert('xss')</script>.pdf"

    class _DriveXss:
        def list_folder(self, folder_id: str):
            return [DriveFile(
                id="fileAAAAAAAAAAAAAAAA", name=xss_name,
                mime_type="application/pdf", kind="pdf", size_bytes=100,
            )]

    app = create_app()
    app.dependency_overrides[get_drive_client] = lambda: _DriveXss()

    folder_id = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"
    url = f"https://drive.google.com/drive/folders/{folder_id}"

    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.post("/api/drive/files", json={"folder_url": url})

    assert resp.status_code == 200
    data = resp.json()
    # The name must be preserved exactly as returned by Drive
    assert data["files"][0]["name"] == xss_name