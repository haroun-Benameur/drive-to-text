"""FastAPI dependency providers."""

import functools
from typing import TYPE_CHECKING

from fastapi import Request

from app.config import get_settings
from app.drive.client import DriveClient
from app.extraction.ocr import TesseractOcr
from app.extraction.router import ExtractionRouter, build_default_router

if TYPE_CHECKING:
    from app.batches.runner import BatchRunner
    from app.batches.store import BatchStore


@functools.lru_cache(maxsize=1)
def get_drive_client() -> DriveClient:
    """Return the cached :class:`DriveClient` (use with FastAPI Depends)."""
    return DriveClient(settings=get_settings())


@functools.lru_cache(maxsize=1)
def get_ocr_engine() -> TesseractOcr:
    """Return the cached :class:`TesseractOcr` (use with FastAPI Depends)."""
    return TesseractOcr(settings=get_settings())


@functools.lru_cache(maxsize=1)
def get_router() -> ExtractionRouter:
    """Return the cached :class:`ExtractionRouter` (use with FastAPI Depends)."""
    return build_default_router(get_settings(), get_ocr_engine())


def get_store(request: Request) -> "BatchStore":
    """Return the :class:`BatchStore` from app state."""
    return request.app.state.store


def get_runner(request: Request) -> "BatchRunner":
    """Return the :class:`BatchRunner` from app state."""
    return request.app.state.runner
