"""Shared Pydantic models."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Drive listing
# ---------------------------------------------------------------------------


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


class DriveFilesRequest(BaseModel):
    """Request body for POST /api/drive/files."""

    folder_url: str


class DriveFilesResponse(BaseModel):
    """Response body for POST /api/drive/files."""

    folder_id: str
    files: list[DriveFile]


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


class ExtractionMethod(StrEnum):
    """How text was obtained from the file."""

    PDF_TEXT = "pdf_text"
    OCR = "ocr"
    PDF_TEXT_OCR = "pdf_text+ocr"


class ExtractionResult(BaseModel):
    """Outcome of extracting text from a single file."""

    text: str
    method: ExtractionMethod
    engine: str
    page_count: int | None
    ocr_pages: int
    warnings: list[str]
