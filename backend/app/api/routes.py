"""Top-level API router."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.deps import get_drive_client
from app.drive.client import DriveClient
from app.drive.url import extract_folder_id
from app.models import DriveFilesRequest, DriveFilesResponse

router = APIRouter(prefix="/api")


@router.get("/health")
async def health() -> JSONResponse:
    """Return service liveness status."""
    return JSONResponse({"status": "ok", "version": "0.1.0"})


@router.post("/drive/files", response_model=DriveFilesResponse)
async def list_drive_files(
    body: DriveFilesRequest,
    client: DriveClient = Depends(get_drive_client),
) -> DriveFilesResponse:
    """List PDF and image files in a Google Drive folder."""
    folder_id = extract_folder_id(body.folder_url)
    files = client.list_folder(folder_id)
    return DriveFilesResponse(folder_id=folder_id, files=files)
