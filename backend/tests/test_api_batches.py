"""Tests for batch API endpoints (prompt 20)."""

import time

from fastapi.testclient import TestClient

from app.errors import AppError
from app.main import create_app
from app.models import ExtractionMethod, ExtractionResult

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

_FILE_A = "fileAAAAAAAAAAAAAAAA"
_FILE_B = "fileBBBBBBBBBBBBBBBB"


class FakeMeta:
    def __init__(self, file_id: str) -> None:
        self.id = file_id
        self.name = f"{file_id}.pdf"
        self.mime_type = "application/pdf"
        self.size_bytes = 1024


class FakeDriveOk:
    def get_metadata(self, file_id: str):
        return FakeMeta(file_id)

    def list_folder(self, folder_id: str):
        return []

    def download(self, file_id: str, max_bytes: int) -> bytes:
        return b"%PDF-1.4 data"


class FakeDriveOneFailure:
    """FILE_B raises an AppError; FILE_A succeeds."""

    def get_metadata(self, file_id: str):
        if file_id == _FILE_B:
            raise AppError("FILE_NOT_FOUND", "not found", 404)
        return FakeMeta(file_id)

    def list_folder(self, folder_id: str):
        return []

    def download(self, file_id: str, max_bytes: int) -> bytes:
        return b"%PDF-1.4 data"


class FakeRouter:
    def extract(self, data: bytes, language: str) -> ExtractionResult:
        return ExtractionResult(
            text="hello",
            method=ExtractionMethod.PDF_TEXT,
            engine="fake",
            page_count=1,
            ocr_pages=0,
            warnings=[],
        )


# ---------------------------------------------------------------------------
# Client factory using lifespan context manager
# ---------------------------------------------------------------------------

from app.api.deps import get_drive_client, get_router  # noqa: E402


def _make_app_client(drive=None, router=None) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_drive_client] = lambda: (drive or FakeDriveOk())
    app.dependency_overrides[get_router] = lambda: (router or FakeRouter())
    return TestClient(app, raise_server_exceptions=False)


def _wait_terminal(client: TestClient, batch_id: str, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = client.get(f"/api/batches/{batch_id}")
        data = resp.json()
        if data["status"] in ("completed", "completed_with_errors"):
            return data
        time.sleep(0.05)
    raise TimeoutError("batch never reached terminal state")


# ---------------------------------------------------------------------------
# Create → poll → completed_with_errors
# ---------------------------------------------------------------------------


def test_create_and_poll_completed_with_errors() -> None:
    with _make_app_client(drive=FakeDriveOneFailure()) as client:
        # POST /api/batches
        resp = client.post("/api/batches", json={"file_ids": [_FILE_A, _FILE_B]})
        assert resp.status_code == 202
        batch_id = resp.json()["id"]

        # Poll until terminal
        final = _wait_terminal(client, batch_id)
        assert final["status"] == "completed_with_errors"
        assert final["counts"]["done"] == 1
        assert final["counts"]["failed"] == 1

        by_id = {item["file_id"]: item for item in final["items"]}
        assert by_id[_FILE_A]["status"] == "done"
        assert by_id[_FILE_B]["status"] == "failed"
        assert by_id[_FILE_B]["error"]["code"] == "FILE_NOT_FOUND"


# ---------------------------------------------------------------------------
# Unknown batch → 404
# ---------------------------------------------------------------------------


def test_get_unknown_batch_returns_404() -> None:
    with _make_app_client() as client:
        resp = client.get("/api/batches/nonexistentbatch123")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "BATCH_NOT_FOUND"


# ---------------------------------------------------------------------------
# Too many files
# ---------------------------------------------------------------------------


def test_too_many_files_returns_422() -> None:
    with _make_app_client() as client:
        # default MAX_FILES_PER_BATCH = 50
        too_many = [f"{'x' * 20}{i:04d}" for i in range(51)]
        resp = client.post("/api/batches", json={"file_ids": too_many})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "TOO_MANY_FILES"


# ---------------------------------------------------------------------------
# Invalid language
# ---------------------------------------------------------------------------


def test_invalid_language_returns_422() -> None:
    with _make_app_client() as client:
        resp = client.post(
            "/api/batches",
            json={"file_ids": [_FILE_A], "language": "klingon"},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "INVALID_LANGUAGE"


# ---------------------------------------------------------------------------
# Export headers and schema
# ---------------------------------------------------------------------------


def test_export_attachment_header_and_schema() -> None:
    with _make_app_client() as client:
        # Create a batch and wait for it to finish
        resp = client.post("/api/batches", json={"file_ids": [_FILE_A]})
        batch_id = resp.json()["id"]
        _wait_terminal(client, batch_id)

        export_resp = client.get(f"/api/batches/{batch_id}/export")
        assert export_resp.status_code == 200

        cd = export_resp.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert f"extraction-{batch_id}.json" in cd

        payload = export_resp.json()
        assert payload["schema_version"] == "1.0"
        assert payload["batch_id"] == batch_id
        assert "exported_at" in payload
        assert "language" in payload
        assert "status" in payload
        assert "counts" in payload
        assert isinstance(payload["items"], list)
        # Every required field present on each item
        item = payload["items"][0]
        for field in ("file_id", "status", "language", "warnings"):
            assert field in item


def test_export_unknown_batch_returns_404() -> None:
    with _make_app_client() as client:
        resp = client.get("/api/batches/doesnotexist123abc/export")
        assert resp.status_code == 404
