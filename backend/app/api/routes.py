"""Top-level API router.

All route handlers are plain ``def`` (not ``async def``) so FastAPI dispatches
them to its default thread-pool executor.  This prevents the synchronous httpx
network calls and subprocess-based Tesseract invocations from blocking the
event loop and stalling concurrent batch-status polling.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.deps import get_drive_client, get_ocr_engine, get_runner, get_store
from app.api.deps import get_router as get_extraction_router
from app.batches.runner import BatchRunner
from app.batches.store import BatchStore
from app.config import Settings, get_settings
from app.drive.client import DriveClient
from app.drive.url import extract_folder_id, is_valid_drive_id
from app.errors import AppError
from app.extraction.base import OcrEngine
from app.extraction.ocr import validate_language
from app.models import (
    Batch,
    BatchCreateRequest,
    DriveFilesRequest,
    DriveFilesResponse,
)

router = APIRouter(prefix="/api")

_REQUIRED_LANGUAGES = {"fra", "eng", "ara"}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@router.get("/health")
def health(ocr: OcrEngine = Depends(get_ocr_engine)) -> JSONResponse:
    """Return service liveness and Tesseract status."""
    tesseract: dict = {
        "available": False,
        "version": None,
        "languages": [],
        "missing_languages": sorted(_REQUIRED_LANGUAGES),
    }
    try:
        ver = ocr.version()
        langs = ocr.available_languages()
        missing = sorted(_REQUIRED_LANGUAGES - set(langs))
        tesseract = {
            "available": True,
            "version": ver,
            "languages": langs,
            "missing_languages": missing,
        }
    except AppError:
        pass

    return JSONResponse({
        "status": "ok",
        "version": "0.1.0",
        "tesseract": tesseract,
    })


# ---------------------------------------------------------------------------
# Drive
# ---------------------------------------------------------------------------


@router.post("/drive/files", response_model=DriveFilesResponse)
def list_drive_files(
    body: DriveFilesRequest,
    client: DriveClient = Depends(get_drive_client),
) -> DriveFilesResponse:
    """List PDF and image files in a Google Drive folder."""
    folder_id = extract_folder_id(body.folder_url)
    files = client.list_folder(folder_id)
    return DriveFilesResponse(folder_id=folder_id, files=files)


# ---------------------------------------------------------------------------
# Batches
# ---------------------------------------------------------------------------


@router.post("/batches", status_code=202, response_model=Batch)
def create_batch(
    body: BatchCreateRequest,
    settings: Settings = Depends(get_settings),
    store: BatchStore = Depends(get_store),
    runner: BatchRunner = Depends(get_runner),
    drive_client=Depends(get_drive_client),
    extraction_router=Depends(get_extraction_router),
) -> Batch:
    """Create a new extraction batch and start processing."""
    if not body.file_ids:
        raise AppError("VALIDATION_ERROR", "At least one file ID is required.", 422)
    if len(body.file_ids) > settings.max_files_per_batch:
        raise AppError(
            "TOO_MANY_FILES",
            f"Batch exceeds the {settings.max_files_per_batch}-file limit.",
            422,
        )
    for fid in body.file_ids:
        if not is_valid_drive_id(fid):
            raise AppError("INVALID_FILE_ID", f"'{fid}' is not a valid Drive file ID.", 422)

    language = body.language or settings.default_ocr_language
    validate_language(language)

    batch = store.create(body.file_ids, language)
    runner.start(batch.id, drive_client=drive_client, router=extraction_router)
    return batch


@router.get("/batches/{batch_id}", response_model=Batch)
def get_batch(
    batch_id: str,
    store: BatchStore = Depends(get_store),
) -> Batch:
    """Return the current state of a batch."""
    return store.get(batch_id)


@router.get("/batches/{batch_id}/export")
def export_batch(
    batch_id: str,
    store: BatchStore = Depends(get_store),
) -> JSONResponse:
    """Download the full extraction results as a JSON attachment."""
    batch = store.get(batch_id)
    exported_at = datetime.now(tz=UTC).isoformat()

    payload = {
        "schema_version": "1.0",
        "exported_at": exported_at,
        "batch_id": batch.id,
        "language": batch.language,
        "status": batch.status,
        "counts": batch.counts.model_dump(),
        "items": [item.model_dump() for item in batch.items],
    }

    return JSONResponse(
        content=payload,
        headers={
            "Content-Disposition": f'attachment; filename="extraction-{batch.id}.json"'
        },
    )
