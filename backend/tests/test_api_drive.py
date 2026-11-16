"""Tests for POST /api/drive/files."""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_drive_client
from app.errors import AppError
from app.main import create_app
from app.models import DriveFile

_FOLDER_ID = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"
_FOLDER_URL = f"https://drive.google.com/drive/folders/{_FOLDER_ID}"

_PDF = DriveFile(
    id="file001",
    name="report.pdf",
    mime_type="application/pdf",
    kind="pdf",
    size_bytes=1024,
)
_IMG = DriveFile(
    id="file002",
    name="photo.jpg",
    mime_type="image/jpeg",
    kind="image",
    size_bytes=512,
)


class FakeDriveClient:
    """Controllable stand-in for DriveClient."""

    def __init__(self, files: list[DriveFile] | None = None, error: AppError | None = None) -> None:
        self._files = files or []
        self._error = error

    def list_folder(self, folder_id: str) -> list[DriveFile]:
        if self._error:
            raise self._error
        return self._files


@pytest.fixture()
def app_client() -> TestClient:
    """Return a TestClient whose dependency is not yet overridden."""
    return TestClient(create_app(), raise_server_exceptions=False)


def _make_client(fake: FakeDriveClient) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_drive_client] = lambda: fake
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Success
# ---------------------------------------------------------------------------


def test_list_files_success() -> None:
    client = _make_client(FakeDriveClient(files=[_PDF, _IMG]))
    response = client.post("/api/drive/files", json={"folder_url": _FOLDER_URL})

    assert response.status_code == 200
    data = response.json()
    assert data["folder_id"] == _FOLDER_ID
    assert len(data["files"]) == 2
    assert data["files"][0]["id"] == "file001"
    assert data["files"][0]["kind"] == "pdf"
    assert data["files"][1]["id"] == "file002"


def test_list_files_empty_folder_returns_200() -> None:
    client = _make_client(FakeDriveClient(files=[]))
    response = client.post("/api/drive/files", json={"folder_url": _FOLDER_URL})

    assert response.status_code == 200
    assert response.json()["files"] == []


# ---------------------------------------------------------------------------
# Invalid URL — 422 with INVALID_FOLDER_URL envelope
# ---------------------------------------------------------------------------


def test_invalid_url_returns_422_envelope() -> None:
    client = _make_client(FakeDriveClient())
    response = client.post(
        "/api/drive/files", json={"folder_url": "https://evil.com/folder"}
    )

    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "INVALID_FOLDER_URL"
    assert isinstance(data["error"]["message"], str)


def test_missing_body_field_returns_422_envelope() -> None:
    client = _make_client(FakeDriveClient())
    response = client.post("/api/drive/files", json={})

    assert response.status_code == 422
    assert "error" in response.json()


# ---------------------------------------------------------------------------
# Private / not-found folder — 404 propagated
# ---------------------------------------------------------------------------


def test_private_folder_returns_404_envelope() -> None:
    error = AppError("FOLDER_NOT_FOUND_OR_PRIVATE", "Folder not found.", 404)
    client = _make_client(FakeDriveClient(error=error))
    response = client.post("/api/drive/files", json={"folder_url": _FOLDER_URL})

    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "FOLDER_NOT_FOUND_OR_PRIVATE"
