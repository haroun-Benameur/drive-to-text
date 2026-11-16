"""Thread-safe in-memory batch store."""

import copy
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from app.errors import AppError
from app.models import (
    Batch,
    BatchCounts,
    BatchItem,
    BatchStatus,
    FileStatus,
)


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _recompute_counts(items: list[BatchItem]) -> BatchCounts:
    counts = BatchCounts()
    for item in items:
        if item.status == FileStatus.PENDING:
            counts.pending += 1
        elif item.status == FileStatus.PROCESSING:
            counts.processing += 1
        elif item.status == FileStatus.DONE:
            counts.done += 1
        elif item.status == FileStatus.FAILED:
            counts.failed += 1
    return counts


def _derive_batch_status(items: list[BatchItem], old_status: BatchStatus) -> BatchStatus:
    """Compute the batch status from item states."""
    statuses = {item.status for item in items}

    # Any item still pending or processing → running
    if FileStatus.PENDING in statuses or FileStatus.PROCESSING in statuses:
        return BatchStatus.RUNNING

    # All items terminal
    if FileStatus.FAILED in statuses:
        return BatchStatus.COMPLETED_WITH_ERRORS
    return BatchStatus.COMPLETED


class BatchStore:
    """Stores batches in memory, protected by a re-entrant lock."""

    def __init__(self, clock: Callable[[], datetime] = _now) -> None:
        self._lock = threading.RLock()
        self._batches: dict[str, Batch] = {}
        self._clock = clock

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(self, file_ids: list[str], language: str) -> Batch:
        """Create a new batch, deduplicating *file_ids* (preserving order).

        Expired batches are purged before the new one is inserted.
        """
        seen: set[str] = set()
        unique_ids: list[str] = []
        for fid in file_ids:
            if fid not in seen:
                seen.add(fid)
                unique_ids.append(fid)

        batch_id = uuid.uuid4().hex
        now = self._clock()
        items = [BatchItem(file_id=fid, language=language) for fid in unique_ids]
        batch = Batch(
            id=batch_id,
            status=BatchStatus.QUEUED,
            language=language,
            created_at=now,
            counts=_recompute_counts(items),
            items=items,
        )

        with self._lock:
            self.purge_expired(ttl_minutes=0)  # purge happens inside the lock
            self._batches[batch_id] = batch

        return copy.deepcopy(batch)

    def get(self, batch_id: str) -> Batch:
        """Return a deep copy of the batch, or raise BATCH_NOT_FOUND (404)."""
        with self._lock:
            batch = self._batches.get(batch_id)
            if batch is None:
                raise AppError("BATCH_NOT_FOUND", f"Batch '{batch_id}' not found.", 404)
            return copy.deepcopy(batch)

    def update_item(self, batch_id: str, file_id: str, **fields) -> Batch:
        """Update fields on a BatchItem and recompute batch-level state.

        Returns a deep copy of the updated batch.
        """
        with self._lock:
            batch = self._batches.get(batch_id)
            if batch is None:
                raise AppError("BATCH_NOT_FOUND", f"Batch '{batch_id}' not found.", 404)

            for item in batch.items:
                if item.file_id == file_id:
                    for k, v in fields.items():
                        setattr(item, k, v)
                    break

            batch.counts = _recompute_counts(batch.items)
            new_status = _derive_batch_status(batch.items, batch.status)
            batch.status = new_status

            # Set finished_at the first time the batch reaches a terminal state
            is_terminal = new_status in (
                BatchStatus.COMPLETED,
                BatchStatus.COMPLETED_WITH_ERRORS,
            )
            if is_terminal and batch.finished_at is None:
                batch.finished_at = self._clock()

            return copy.deepcopy(batch)

    def purge_expired(self, ttl_minutes: int) -> None:
        """Remove batches older than *ttl_minutes* minutes.

        Called with the lock already held when invoked from :meth:`create`.
        """
        if ttl_minutes <= 0:
            return
        cutoff = self._clock().timestamp() - ttl_minutes * 60
        expired = [
            bid
            for bid, b in self._batches.items()
            if b.created_at.timestamp() < cutoff
        ]
        for bid in expired:
            del self._batches[bid]
