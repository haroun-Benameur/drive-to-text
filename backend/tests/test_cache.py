"""Tests for ResultCache (step 5)."""

import threading

from app.batches.cache import ResultCache
from app.config import Settings
from app.models import ExtractionMethod, ExtractionResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FID_A = "fileAAAAAAAAAAAAAAA1"
_FID_B = "fileBBBBBBBBBBBBBBB2"
_MD5_A = "abc123"
_MD5_B = "def456"
_LANG = "eng"


def _settings() -> Settings:
    return Settings(
        cors_origins=["http://localhost:5173"],
        max_pdf_pages=30,
        min_page_chars=25,
        ocr_render_dpi=200,
        ocr_min_confidence=60.0,
        ocr_retry_preprocess=True,
    )


def _result(text: str = "hello") -> ExtractionResult:
    return ExtractionResult(
        text=text,
        method=ExtractionMethod.PDF_TEXT,
        engine="pypdf 7.1.0",
        page_count=1,
        ocr_pages=0,
        warnings=[],
    )


def _put(cache: ResultCache, fid: str = _FID_A, md5: str = _MD5_A) -> None:
    cache.put(fid, md5, _LANG, _settings(), "tesseract", _result())


def _get(cache: ResultCache, fid: str = _FID_A, md5: str = _MD5_A) -> ExtractionResult | None:
    return cache.get(fid, md5, _LANG, _settings(), "tesseract")


# ---------------------------------------------------------------------------
# Basic hit / miss
# ---------------------------------------------------------------------------


def test_cache_hit_returns_copy() -> None:
    cache = ResultCache(10)
    _put(cache)
    result = _get(cache)
    assert result is not None
    assert result.text == "hello"


def test_cache_miss_returns_none() -> None:
    cache = ResultCache(10)
    assert _get(cache) is None


def test_put_then_get_is_deep_copy() -> None:
    """Modifying the returned copy must not affect the cached entry."""
    cache = ResultCache(10)
    _put(cache)
    r1 = _get(cache)
    assert r1 is not None
    r1.warnings.append("MUTATED")
    r2 = _get(cache)
    assert r2 is not None
    assert "MUTATED" not in r2.warnings


# ---------------------------------------------------------------------------
# LRU eviction
# ---------------------------------------------------------------------------


def test_lru_eviction_order() -> None:
    cache = ResultCache(2)
    cache.put(_FID_A, _MD5_A, _LANG, _settings(), "t", _result("A"))
    cache.put(_FID_B, _MD5_B, _LANG, _settings(), "t", _result("B"))
    # Access A to make B the least-recently-used
    cache.get(_FID_A, _MD5_A, _LANG, _settings(), "t")
    # Add C → B should be evicted
    cache.put("fileCCCC", "md5C", _LANG, _settings(), "t", _result("C"))
    assert cache.get(_FID_A, _MD5_A, _LANG, _settings(), "t") is not None
    assert cache.get(_FID_B, _MD5_B, _LANG, _settings(), "t") is None
    assert cache.get("fileCCCC", "md5C", _LANG, _settings(), "t") is not None


def test_max_entries_one_evicts_on_second_put() -> None:
    cache = ResultCache(1)
    cache.put(_FID_A, _MD5_A, _LANG, _settings(), "t", _result("A"))
    cache.put(_FID_B, _MD5_B, _LANG, _settings(), "t", _result("B"))
    assert cache.get(_FID_A, _MD5_A, _LANG, _settings(), "t") is None
    assert cache.get(_FID_B, _MD5_B, _LANG, _settings(), "t") is not None


# ---------------------------------------------------------------------------
# Disabled when size == 0
# ---------------------------------------------------------------------------


def test_disabled_when_size_zero() -> None:
    cache = ResultCache(0)
    _put(cache)
    assert _get(cache) is None


# ---------------------------------------------------------------------------
# Different language or missing md5 → miss
# ---------------------------------------------------------------------------


def test_different_language_is_miss() -> None:
    cache = ResultCache(10)
    cache.put(_FID_A, _MD5_A, "fra", _settings(), "t", _result())
    assert cache.get(_FID_A, _MD5_A, "eng", _settings(), "t") is None


def test_missing_md5_is_miss() -> None:
    cache = ResultCache(10)
    cache.put(_FID_A, None, _LANG, _settings(), "t", _result())
    assert cache.get(_FID_A, None, _LANG, _settings(), "t") is None


# ---------------------------------------------------------------------------
# Thread-safety smoke test
# ---------------------------------------------------------------------------


def test_thread_safety_smoke() -> None:
    """50 threads concurrently read and write without raising."""
    cache = ResultCache(20)
    errors: list[Exception] = []

    def worker(i: int) -> None:
        try:
            fid = f"file{i:04d}AAAAAAAAAA"
            md5 = f"md5{i:04d}"
            cache.put(fid, md5, _LANG, _settings(), "t", _result(f"text{i}"))
            cache.get(fid, md5, _LANG, _settings(), "t")
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
