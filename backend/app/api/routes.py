"""Top-level API router."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api")


@router.get("/health")
async def health() -> JSONResponse:
    """Return service liveness status."""
    return JSONResponse({"status": "ok", "version": "0.1.0"})
