"""Tests for BatchRunner (prompt 19)."""

import time

from app.batches.runner import BatchRunner
from app.batches.store import BatchStore
from app.config import Settings
from app.errors import AppError
from app.models import BatchStatus, ExtractionMethod, ExtractionResult, FileStatus

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

_FILE_A = "fileAAAAAAAAAAAAAAAA"
_FILE_B = "fileBBBBBBBBBBBBBBBB"
_FILE_C = "fileCCCCCCCCCCCCCCCC"


class FakeMeta:
    def __init__(self, file_id: str, size: int = 1000) -> None:
        self.id = file_id
        self.name = f"{file_id}.pdf"
        self.mime_type = "application/pdf"
        self.size_bytes = size


class FakeDriveClient:
    def __init__(self, metas=None, errors=None, data=b"%PDF-1.4 tiny") -> None:
        self._metas = metas or {}
        self._errors = errors or {}
        self._data = data

    def get_metadata(self, file_id: str):
        if file_id in self._errors:
            raise self._errors[file_id]
        return self._metas.get(file_id, FakeMeta(file_id))

    def download(self, file_id: str, max_bytes: int) -> bytes:
        if file_id in self._errors:
            raise self._errors[file_id]
        return self._data


class FakeRouter:
    def __init__(self, results=None, errors=None) -> None:
        self._results = results or {}
        self._errors = errors or {}

    def extract(self, data: bytes, language: str) -> ExtractionResult:
        # errors keyed by data content for simplicity
        for key, exc in self._errors.items():
            if key in data:
                raise exc
        return ExtractionResult(
            text="extracted",
            method=ExtractionMethod.PDF_TEXT,
            engine="fake",
            page_count=1,
            ocr_pages=0,
            warnings=[],
        )


def _settings(**overrides) -> Settings:
    defaults = {
        "cors_origins": ["http://localhost:5173"],
        "batch_workers": 2,
        "max_file_size_mb": 25,
        "file_time_budget_s": 120,
        "default_ocr_language": "eng",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _make_runner(drive=None, router=None, **setting_overrides) -> tuple[BatchStore, BatchRunner]:
    store = BatchStore()
    settings = _settings(**setting_overrides)
    _drive = drive or FakeDriveClient()
    _router = router or FakeRouter()
    runner = BatchRunner(
        store=store,
        drive_client_factory=lambda: _drive,
        router_factory=lambda: _router,
        settings=settings,
    )
    return store, runner


def _wait_terminal(store: BatchStore, batch_id: str, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        b = store.get(batch_id)
        if b.status in (BatchStatus.COMPLETED, BatchStatus.COMPLETED_WITH_ERRORS):
            return
        time.sleep(0.05)
    raise TimeoutError(f"Batch {batch_id} did not reach terminal state within {timeout}s")


# ---------------------------------------------------------------------------
# All files succeed
# ---------------------------------------------------------------------------


def test_all_files_succeed() -> None:
    store, runner = _make_runner()
    batch = store.create([_FILE_A, _FILE_B], "eng")
    runner.start(batch.id)
    _wait_terminal(store, batch.id)

    result = store.get(batch.id)
    assert result.status == BatchStatus.COMPLETED
    assert result.counts.done == 2
    assert result.counts.failed == 0
    for item in result.items:
        assert item.status == FileStatus.DONE
        assert item.text == "extracted"
        assert item.duration_ms is not None
    runner.shutdown()


# ---------------------------------------------------------------------------
# One AppError, one bare Exception, rest succeed
# ---------------------------------------------------------------------------


def test_isolated_failures_do_not_affect_other_files() -> None:
    app_error = AppError("FILE_NOT_FOUND", "gone", 404)
    router = FakeRouter(
        errors={
            b"file_b_data": app_error,
            b"file_c_data": RuntimeError("boom"),
        }
    )

    class SelectiveDrive(FakeDriveClient):
        def download(self, file_id: str, max_bytes: int) -> bytes:
            if file_id == _FILE_B:
                return b"file_b_data"
            if file_id == _FILE_C:
                return b"file_c_data"
            return b"%PDF-1.4 normal"

    store, runner = _make_runner(drive=SelectiveDrive(), router=router)
    batch = store.create([_FILE_A, _FILE_B, _FILE_C], "eng")
    runner.start(batch.id)
    _wait_terminal(store, batch.id)

    result = store.get(batch.id)
    assert result.status == BatchStatus.COMPLETED_WITH_ERRORS
    assert result.counts.done == 1
    assert result.counts.failed == 2

    by_id = {item.file_id: item for item in result.items}
    assert by_id[_FILE_A].status == FileStatus.DONE
    assert by_id[_FILE_B].status == FileStatus.FAILED
    assert by_id[_FILE_B].error.code == "FILE_NOT_FOUND"
    assert by_id[_FILE_C].status == FileStatus.FAILED
    assert by_id[_FILE_C].error.code == "INTERNAL_ERROR"
    runner.shutdown()


# ---------------------------------------------------------------------------
# File too large
# ---------------------------------------------------------------------------


def test_file_too_large_sets_failed_with_file_too_large_code() -> None:
    large_meta = FakeMeta(_FILE_A, size=999_999_999)
    drive = FakeDriveClient(metas={_FILE_A: large_meta})

    store, runner = _make_runner(drive=drive, max_file_size_mb=1)
    batch = store.create([_FILE_A], "eng")
    runner.start(batch.id)
    _wait_terminal(store, batch.id)

    result = store.get(batch.id)
    assert result.counts.failed == 1
    item = result.items[0]
    assert item.status == FileStatus.FAILED
    assert item.error.code == "FILE_TOO_LARGE"
    runner.shutdown()


def test_runner_stores_ocr_confidence() -> None:
    class _ConfidenceRouter:
        def extract(self, data: bytes, language: str) -> ExtractionResult:
            return ExtractionResult(
                text="extracted",
                method=ExtractionMethod.OCR,
                engine="tesseract fake",
                page_count=1,
                ocr_pages=1,
                warnings=["LOW_OCR_CONFIDENCE"],
                ocr_confidence=42.5,
            )

    store, runner = _make_runner(router=_ConfidenceRouter())
    batch = store.create([_FILE_A], "eng")
    runner.start(batch.id)
    _wait_terminal(store, batch.id)

    item = store.get(batch.id).items[0]
    assert item.ocr_confidence == 42.5
    assert item.warnings == ["LOW_OCR_CONFIDENCE"]
    runner.shutdown()
