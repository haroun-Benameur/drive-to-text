"""FastAPI dependency providers."""

import functools

from app.config import Settings, get_settings
from app.drive.client import DriveClient


@functools.lru_cache
def _build_drive_client(settings: Settings) -> DriveClient:
    return DriveClient(settings=settings)


def get_drive_client() -> DriveClient:
    """Return the cached :class:`DriveClient` (use with FastAPI Depends)."""
    return _build_drive_client(get_settings())
