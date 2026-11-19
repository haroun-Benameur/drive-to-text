"""Thread-safe LRU cache for extraction results keyed by file checksum."""

import copy
import hashlib
import threading
from collections import OrderedDict

from app.config import Settings
from app.models import ExtractionResult


def _settings_fingerprint(settings: Settings, ocr_engine_name: str) -> str:
    """Hash the extraction-relevant settings plus the OCR engine name."""
    parts = [
        str(settings.max_pdf_pages),
        str(settings.min_page_chars),
        str(settings.ocr_render_dpi),
        str(settings.ocr_min_confidence),
        str(settings.ocr_retry_preprocess),
        ocr_engine_name,
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


class ResultCache:
    """Thread-safe LRU cache of :class:`ExtractionResult`.

    Keyed by (file_id, md5_checksum, language, settings_fingerprint).
    Stores deep copies so callers cannot mutate the cached entry.
    """

    def __init__(self, max_entries: int) -> None:
        self._max = max_entries
        self._lock = threading.RLock()
        self._data: OrderedDict[tuple, ExtractionResult] = OrderedDict()

    def get(
        self,
        file_id: str,
        md5_checksum: str | None,
        language: str,
        settings: Settings,
        ocr_engine_name: str,
    ) -> ExtractionResult | None:
        if self._max <= 0 or md5_checksum is None:
            return None
        key = (
            file_id,
            md5_checksum,
            language,
            _settings_fingerprint(settings, ocr_engine_name),
        )
        with self._lock:
            result = self._data.get(key)
            if result is None:
                return None
            # Move to end (most recently used)
            self._data.move_to_end(key)
            return copy.deepcopy(result)

    def put(
        self,
        file_id: str,
        md5_checksum: str | None,
        language: str,
        settings: Settings,
        ocr_engine_name: str,
        result: ExtractionResult,
    ) -> None:
        if self._max <= 0 or md5_checksum is None:
            return
        key = (
            file_id,
            md5_checksum,
            language,
            _settings_fingerprint(settings, ocr_engine_name),
        )
        with self._lock:
            self._data[key] = copy.deepcopy(result)
            self._data.move_to_end(key)
            while len(self._data) > self._max:
                self._data.popitem(last=False)