"""FastAPI dependency providers."""

import functools
import logging
from typing import TYPE_CHECKING, Any

from fastapi import Request

from app.config import get_settings
from app.drive.client import DriveClient
from app.extraction.router import ExtractionRouter, build_default_router

if TYPE_CHECKING:
    from app.batches.runner import BatchRunner
    from app.batches.store import BatchStore

logger = logging.getLogger(__name__)


def _build_ocr_engine(settings: Any) -> Any:
    """Build the OCR engine according to ``settings.ocr_engine``."""
    from app.extraction.ocr import TesseractOcr

    engine_name = (settings.ocr_engine or "tesseract").lower().strip()

    if engine_name == "tesseract":
        return TesseractOcr(settings=settings)

    if engine_name == "easyocr":
        from app.extraction.ocr_easyocr import EasyOcrEngine
        return EasyOcrEngine()

    if engine_name == "auto":
        primary = TesseractOcr(settings=settings)
        try:
            from app.extraction.ocr_easyocr import EasyOcrEngine
            from app.extraction.ocr_fallback import FallbackOcr
            secondary = EasyOcrEngine()
            return FallbackOcr(primary, secondary, settings.ocr_min_confidence)
        except ImportError:
            logger.debug("easyocr not installed; OCR_ENGINE=auto falls back to tesseract")
            return primary

    # Unknown value — default to Tesseract
    logger.warning("Unknown OCR_ENGINE value %r; using tesseract.", engine_name)
    return TesseractOcr(settings=settings)


@functools.lru_cache(maxsize=1)
def get_drive_client() -> DriveClient:
    """Return the cached :class:`DriveClient` (use with FastAPI Depends)."""
    return DriveClient(settings=get_settings())


@functools.lru_cache(maxsize=1)
def get_ocr_engine() -> Any:
    """Return the cached OCR engine (use with FastAPI Depends)."""
    return _build_ocr_engine(get_settings())


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
