"""Tests for Settings and get_settings()."""

import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clear() -> None:
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def test_defaults() -> None:
    # Pass _env_file=None so a local .env does not pollute the defaults test.
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.google_api_key is None
    assert s.cors_origins == ["http://localhost:5173"]
    assert s.tesseract_cmd is None
    assert s.tessdata_prefix is None
    assert s.default_ocr_language == "fra+eng"
    assert s.max_file_size_mb == 25
    assert s.max_files_per_batch == 50
    assert s.max_listed_files == 500
    assert s.max_pdf_pages == 30
    assert s.max_image_pixels == 50_000_000
    assert s.file_time_budget_s == 120
    assert s.ocr_page_timeout_s == 60
    assert s.min_page_chars == 25
    assert s.ocr_render_dpi == 200
    assert s.ocr_min_confidence == 60.0
    assert s.ocr_retry_preprocess is True
    assert s.ocr_engine == "tesseract"
    assert s.batch_workers == 2
    assert s.batch_ttl_minutes == 60
    assert s.max_active_batches == 4
    assert s.result_cache_size == 64
    assert s.log_level == "INFO"


# ---------------------------------------------------------------------------
# Computed property
# ---------------------------------------------------------------------------


def test_ocr_min_confidence_rejects_out_of_range() -> None:
    with pytest.raises(ValidationError):
        Settings(ocr_min_confidence=101)
    with pytest.raises(ValidationError):
        Settings(ocr_min_confidence=-0.1)


def test_ocr_min_confidence_accepts_bounds() -> None:
    assert Settings(ocr_min_confidence=0).ocr_min_confidence == 0
    assert Settings(ocr_min_confidence=100).ocr_min_confidence == 100


def test_max_file_size_bytes() -> None:
    s = Settings(max_file_size_mb=10)
    assert s.max_file_size_bytes == 10 * 1024 * 1024


# ---------------------------------------------------------------------------
# CORS parsing
# ---------------------------------------------------------------------------


def test_cors_origins_single_string() -> None:
    s = Settings(cors_origins="http://localhost:3000")  # type: ignore[arg-type]
    assert s.cors_origins == ["http://localhost:3000"]


def test_cors_origins_comma_separated() -> None:
    s = Settings(cors_origins="http://localhost:3000,https://example.com")  # type: ignore[arg-type]
    assert s.cors_origins == ["http://localhost:3000", "https://example.com"]


def test_cors_origins_strips_whitespace() -> None:
    s = Settings(cors_origins="http://a.com , http://b.com")  # type: ignore[arg-type]
    assert s.cors_origins == ["http://a.com", "http://b.com"]


def test_cors_origins_as_list() -> None:
    s = Settings(cors_origins=["http://a.com", "http://b.com"])
    assert s.cors_origins == ["http://a.com", "http://b.com"]


# ---------------------------------------------------------------------------
# Empty string -> None
# ---------------------------------------------------------------------------


def test_google_api_key_empty_string_becomes_none() -> None:
    s = Settings(google_api_key="")  # type: ignore[arg-type]
    assert s.google_api_key is None


def test_tesseract_cmd_empty_string_becomes_none() -> None:
    s = Settings(tesseract_cmd="")  # type: ignore[arg-type]
    assert s.tesseract_cmd is None


def test_tessdata_prefix_empty_string_becomes_none() -> None:
    s = Settings(tessdata_prefix="")  # type: ignore[arg-type]
    assert s.tessdata_prefix is None


def test_blank_whitespace_becomes_none() -> None:
    s = Settings(google_api_key="   ")  # type: ignore[arg-type]
    assert s.google_api_key is None


# ---------------------------------------------------------------------------
# get_settings() â€“ caching and env override
# ---------------------------------------------------------------------------


def test_get_settings_returns_settings_instance() -> None:
    _clear()
    s = get_settings()
    assert isinstance(s, Settings)


def test_get_settings_is_cached() -> None:
    _clear()
    assert get_settings() is get_settings()


def test_get_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear()
    monkeypatch.setenv("MAX_FILE_SIZE_MB", "99")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    try:
        s = get_settings()
        assert s.max_file_size_mb == 99
        assert s.log_level == "DEBUG"
    finally:
        _clear()
