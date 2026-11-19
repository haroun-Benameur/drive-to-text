"""Tests for MAX_ACTIVE_BATCHES cap (STEP 4)."""

import threading
import time

from fastapi.testclient import TestClient

from app.api.deps import get_drive_client, get_router
from app.batches.store import BatchStore
from app.config import Settings
from app.main import create_app
from app.models import ExtractionMethod, ExtractionResult

_FILE_A = "fileAAAAAAAAAAAAAAAA"
_FILE_B = "fileBBBBBBBBBBBBBBBB"
_FILE_C = "fileCCCCCCCCCCCCCCCC"
_FILE_D = "fileDDDDDDDDDDDDDDDD"
_FILE_E = "fileEEEEEEEEEEEEEEEE"


# ---------------------------------------------------------------------------
# BatchStore.count_active unit tests
# ---------------------------------------------------------------------------


def test_count_active_zero_on_empty_store() -> None:
    store = BatchStore()
    assert store.count_active() == 0


def test_count_active_counts_non_terminal_batches() -> None:
    store = BatchStore()
    b1 = store.create([_FILE_A], "eng")
    b2 = store.create([_FILE_B], "eng")
    assert store.count_active() == 2

    # Finish b1 completely
    store.update_item(b1.id, _FILE_A, status="processing")
    store.update_item(b1.id, _FILE_A, status="done", text="hi")
    assert store.count_active() == 1  # b2 still queued

    # Fail b2
    from app.models import ErrorInfo
    store.update_item(b2.id, _FILE_B, status="failed", error=ErrorInfo(code="X", message="y"))
    assert store.count_active() == 0


# ---------------------------------------------------------------------------
# API cap test: 429 when cap reached, 202 after one finishes
# ---------------------------------------------------------------------------


class _BlockingRouter:
    """Router that blocks until released, keeping batches in running state."""

    def __init__(self, event: threading.Event) -> None:
        self._event = event

    def extract(self, data: bytes, language: str) -> ExtractionResult:
        self._event.wait()  # block until test releases it
        return ExtractionResult(
            text="done",
            method=ExtractionMethod.PDF_TEXT,
            engine="fake",
            page_count=1,
            ocr_pages=0,
            warnings=[],
        )


class _FakeDrive:
    class _Meta:
        id = _FILE_A
        name = "f.pdf"
        mime_type = "application/pdf"
        size_bytes = 100

    def get_metadata(self, file_id: str) -> "_FakeDrive._Meta":
        return self._Meta()

    def download(self, file_id: str, max_bytes: int) -> bytes:
        return b"%PDF-1.4"

    def list_folder(self, folder_id: str) -> list:
        return []


def _make_client_with_cap(cap: int, block_event: threading.Event) -> TestClient:
    app = create_app()
    router = _BlockingRouter(block_event)
    app.dependency_overrides[get_drive_client] = lambda: _FakeDrive()
    app.dependency_overrides[get_router] = lambda: router
    # Override settings to use a low cap
    from app.config import get_settings
    app.dependency_overrides[get_settings] = lambda: Settings(
        cors_origins=["http://localhost:5173"],
        max_active_batches=cap,
        google_api_key="fake",
        batch_workers=cap + 2,
        default_ocr_language="eng",
    )
    return TestClient(app, raise_server_exceptions=False)


def test_cap_returns_429_when_full() -> None:
    """With cap=2, the third POST must get 429 TOO_MANY_ACTIVE_BATCHES."""
    block = threading.Event()  # never released — keeps batches active

    with _make_client_with_cap(cap=2, block_event=block) as client:
        # First two batches should be accepted
        r1 = client.post("/api/batches", json={"file_ids": [_FILE_A]})
        r2 = client.post("/api/batches", json={"file_ids": [_FILE_B]})
        assert r1.status_code == 202, r1.json()
        assert r2.status_code == 202, r2.json()

        # Give workers a moment to pick up the items and transition to running
        time.sleep(0.5)

        # Third batch must be rejected
        r3 = client.post("/api/batches", json={"file_ids": [_FILE_C]})
        assert r3.status_code == 429, r3.json()
        assert r3.json()["error"]["code"] == "TOO_MANY_ACTIVE_BATCHES"

    block.set()  # unblock background threads so they can exit cleanly
