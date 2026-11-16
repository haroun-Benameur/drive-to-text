"""Tests for BatchStore (prompt 18)."""

from datetime import UTC, datetime

import pytest

from app.batches.store import BatchStore
from app.errors import AppError
from app.models import BatchStatus, FileStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_IDS = ["fileAAAAAAAAAAA", "fileBBBBBBBBBBB", "fileCCCCCCCCCCC"]


def _store() -> BatchStore:
    return BatchStore()


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


def test_create_returns_batch_with_all_items_pending() -> None:
    store = _store()
    batch = store.create(_IDS[:2], "eng")

    assert len(batch.items) == 2
    assert all(item.status == FileStatus.PENDING for item in batch.items)
    assert batch.status == BatchStatus.QUEUED


def test_create_deduplicates_file_ids_preserving_order() -> None:
    store = _store()
    batch = store.create([_IDS[0], _IDS[1], _IDS[0]], "eng")

    ids = [item.file_id for item in batch.items]
    assert ids == [_IDS[0], _IDS[1]]


def test_create_sets_language_on_items() -> None:
    store = _store()
    batch = store.create([_IDS[0]], "fra")
    assert batch.items[0].language == "fra"


def test_create_initial_counts() -> None:
    store = _store()
    batch = store.create(_IDS, "eng")
    assert batch.counts.pending == 3
    assert batch.counts.processing == 0
    assert batch.counts.done == 0
    assert batch.counts.failed == 0


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


def test_get_returns_deep_copy() -> None:
    store = _store()
    batch = store.create([_IDS[0]], "eng")
    fetched = store.get(batch.id)
    assert fetched.id == batch.id
    # Mutating the returned copy must not affect the store
    fetched.language = "MUTATED"
    assert store.get(batch.id).language == "eng"


def test_get_unknown_id_raises_batch_not_found() -> None:
    store = _store()
    with pytest.raises(AppError) as exc_info:
        store.get("nonexistent_batch_id_xyz")
    assert exc_info.value.code == "BATCH_NOT_FOUND"
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# update_item – status transitions
# ---------------------------------------------------------------------------


def test_update_item_processing_sets_running() -> None:
    store = _store()
    batch = store.create([_IDS[0], _IDS[1]], "eng")
    updated = store.update_item(batch.id, _IDS[0], status=FileStatus.PROCESSING)

    assert updated.status == BatchStatus.RUNNING
    assert updated.counts.processing == 1
    assert updated.counts.pending == 1


def test_update_item_all_done_sets_completed() -> None:
    store = _store()
    batch = store.create([_IDS[0]], "eng")
    store.update_item(batch.id, _IDS[0], status=FileStatus.PROCESSING)
    updated = store.update_item(batch.id, _IDS[0], status=FileStatus.DONE, text="hi")

    assert updated.status == BatchStatus.COMPLETED
    assert updated.counts.done == 1
    assert updated.finished_at is not None


def test_update_item_one_failed_sets_completed_with_errors() -> None:
    store = _store()
    batch = store.create([_IDS[0], _IDS[1]], "eng")
    store.update_item(batch.id, _IDS[0], status=FileStatus.DONE)
    updated = store.update_item(batch.id, _IDS[1], status=FileStatus.FAILED)

    assert updated.status == BatchStatus.COMPLETED_WITH_ERRORS
    assert updated.counts.failed == 1
    assert updated.counts.done == 1
    assert updated.finished_at is not None


def test_finished_at_set_only_once() -> None:
    store = _store()
    batch = store.create([_IDS[0], _IDS[1]], "eng")
    store.update_item(batch.id, _IDS[0], status=FileStatus.DONE)
    first_finish = store.update_item(batch.id, _IDS[1], status=FileStatus.DONE).finished_at
    # update again (no-op status change) — finished_at must not change
    second_finish = store.update_item(batch.id, _IDS[1], status=FileStatus.DONE).finished_at
    assert first_finish == second_finish


# ---------------------------------------------------------------------------
# purge_expired
# ---------------------------------------------------------------------------


def test_purge_expired_removes_old_batches() -> None:
    ticks = [0.0]

    def clock() -> datetime:
        return datetime.fromtimestamp(ticks[0], tz=UTC)

    store = BatchStore(clock=clock)
    batch = store.create([_IDS[0]], "eng")

    # advance clock past TTL (1 minute = 60 s)
    ticks[0] = 61.0
    store.purge_expired(ttl_minutes=1)

    with pytest.raises(AppError):
        store.get(batch.id)


def test_purge_expired_keeps_recent_batches() -> None:
    ticks = [0.0]

    def clock() -> datetime:
        return datetime.fromtimestamp(ticks[0], tz=UTC)

    store = BatchStore(clock=clock)
    batch = store.create([_IDS[0]], "eng")

    # advance only 30 s — not yet expired
    ticks[0] = 30.0
    store.purge_expired(ttl_minutes=1)

    fetched = store.get(batch.id)
    assert fetched.id == batch.id
