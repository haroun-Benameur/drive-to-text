"""Shared Pydantic models."""

from datetime import datetime
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
    md5_checksum: str | None = None


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


class OcrOutput(BaseModel):
    """Text and confidence from one OCR call."""

    text: str
    confidence: float | None
    engine: str
    warnings: list[str] = []


class ExtractionResult(BaseModel):
    """Outcome of extracting text from a single file."""

    text: str
    method: ExtractionMethod
    engine: str
    page_count: int | None
    ocr_pages: int
    warnings: list[str]
    ocr_confidence: float | None = None


# ---------------------------------------------------------------------------
# Batches
# ---------------------------------------------------------------------------


class FileStatus(StrEnum):
    """Processing state of a single file inside a batch."""

    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class BatchStatus(StrEnum):
    """Overall state of a batch."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"


class ErrorInfo(BaseModel):
    """Serialisable error attached to a failed BatchItem."""

    code: str
    message: str


class BatchItem(BaseModel):
    """State for one file inside a batch."""

    file_id: str
    filename: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    status: FileStatus = FileStatus.PENDING
    extraction_method: ExtractionMethod | None = None
    engine: str | None = None
    language: str
    page_count: int | None = None
    ocr_pages: int | None = None
    ocr_confidence: float | None = None
    text: str | None = None
    warnings: list[str] = []
    error: ErrorInfo | None = None
    duration_ms: int | None = None


class BatchCounts(BaseModel):
    """Aggregate counts of item statuses within a batch."""

    pending: int = 0
    processing: int = 0
    done: int = 0
    failed: int = 0


class Batch(BaseModel):
    """A processing batch containing one or more files."""

    id: str
    status: BatchStatus
    language: str
    created_at: datetime
    finished_at: datetime | None = None
    counts: BatchCounts
    items: list[BatchItem]


# ---------------------------------------------------------------------------
# Batch API
# ---------------------------------------------------------------------------


class BatchCreateRequest(BaseModel):
    """Request body for POST /api/batches."""

    file_ids: list[str]
    language: str | None = None
