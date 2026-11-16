"""Shared Pydantic models."""

from typing import Literal

from pydantic import BaseModel


class DriveFile(BaseModel):
    """A PDF or image file returned by the Drive listing API."""

    id: str
    name: str
    mime_type: str
    kind: Literal["pdf", "image"]
    size_bytes: int | None


class DriveFileMeta(BaseModel):
    """Metadata for a single Drive file (from GET /files/{id})."""

    id: str
    name: str
    mime_type: str
    size_bytes: int | None
