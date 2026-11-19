"""Batch processing runner."""

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter

from app.batches.cache import ResultCache
from app.batches.store import BatchStore
from app.config import Settings
from app.errors import AppError
from app.models import ErrorInfo, FileStatus

logger = logging.getLogger(__name__)


class BatchRunner:
    """Submits file-processing tasks to a fixed thread pool."""

    def __init__(
        self,
        store: BatchStore,
        drive_client_factory: Callable,
        router_factory: Callable,
        settings: Settings,
        cache: ResultCache | None = None,
    ) -> None:
        self._store = store
        self._drive_factory = drive_client_factory
        self._router_factory = router_factory
        self._settings = settings
        self._cache = cache
        self._executor = ThreadPoolExecutor(max_workers=settings.batch_workers)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, batch_id: str, drive_client=None, router=None) -> None:
        """Submit one task per pending item and return immediately."""
        batch = self._store.get(batch_id)
        for item in batch.items:
            self._executor.submit(
                self._process_file,
                batch_id,
                item.file_id,
                drive_client,
                router,
            )

    def shutdown(self) -> None:
        """Shut down the thread pool without waiting for running tasks."""
        self._executor.shutdown(wait=False, cancel_futures=True)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _process_file(
        self,
        batch_id: str,
        file_id: str,
        drive_override=None,
        router_override=None,
    ) -> None:
        """Process one file inside a worker thread.

        No exception may escape this method.
        """
        t0 = perf_counter()
        drive = drive_override if drive_override is not None else self._drive_factory()
        router = router_override if router_override is not None else self._router_factory()
        try:
            self._store.update_item(batch_id, file_id, status=FileStatus.PROCESSING)

            # --- metadata ---
            meta = drive.get_metadata(file_id)
            self._store.update_item(
                batch_id,
                file_id,
                filename=meta.name,
                mime_type=meta.mime_type,
                size_bytes=meta.size_bytes,
            )

            # --- size guard ---
            max_bytes = self._settings.max_file_size_bytes
            if meta.size_bytes is not None and meta.size_bytes > max_bytes:
                raise AppError(
                    "FILE_TOO_LARGE",
                    f"File size {meta.size_bytes} bytes exceeds the"
                    f" {max_bytes}-byte limit.",
                    413,
                )

            # --- cache check ---
            language = self._store.get(batch_id).language
            md5 = getattr(meta, "md5_checksum", None)
            if self._cache is not None and md5 is not None:
                cached = self._cache.get(
                    file_id, md5, language,
                    self._settings, "ocr_engine",
                )
                if cached is not None:
                    duration_ms = int((perf_counter() - t0) * 1000)
                    warnings = list(cached.warnings)
                    if "CACHE_HIT" not in warnings:
                        warnings.append("CACHE_HIT")
                    self._store.update_item(
                        batch_id,
                        file_id,
                        status=FileStatus.DONE,
                        extraction_method=cached.method,
                        engine=cached.engine,
                        page_count=cached.page_count,
                        ocr_pages=cached.ocr_pages,
                        ocr_confidence=cached.ocr_confidence,
                        text=cached.text,
                        warnings=warnings,
                        duration_ms=duration_ms,
                    )
                    return

            # --- download ---
            data = drive.download(file_id, max_bytes)

            # --- extract ---
            result = router.extract(data, language)

            # --- cache store ---
            if self._cache is not None and md5 is not None:
                self._cache.put(
                    file_id, md5, language,
                    self._settings, "ocr_engine", result,
                )

            duration_ms = int((perf_counter() - t0) * 1000)
            self._store.update_item(
                batch_id,
                file_id,
                status=FileStatus.DONE,
                extraction_method=result.method,
                engine=result.engine,
                page_count=result.page_count,
                ocr_pages=result.ocr_pages,
                ocr_confidence=result.ocr_confidence,
                text=result.text,
                warnings=result.warnings,
                duration_ms=duration_ms,
            )

        except AppError as exc:
            duration_ms = int((perf_counter() - t0) * 1000)
            self._store.update_item(
                batch_id,
                file_id,
                status=FileStatus.FAILED,
                error=ErrorInfo(code=exc.code, message=exc.message),
                duration_ms=duration_ms,
            )
        except Exception:
            duration_ms = int((perf_counter() - t0) * 1000)
            logger.exception(
                "Unexpected error processing file %s in batch %s", file_id, batch_id
            )
            self._store.update_item(
                batch_id,
                file_id,
                status=FileStatus.FAILED,
                error=ErrorInfo(
                    code="INTERNAL_ERROR",
                    message="Unexpected error while processing this file.",
                ),
                duration_ms=duration_ms,
            )