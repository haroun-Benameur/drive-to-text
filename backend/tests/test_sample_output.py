"""Validate samples/sample_output.json structure and absence of secrets."""

import json
import re
from pathlib import Path

import pytest

# Path is relative to this test file: backend/tests/ -> samples/
_SAMPLE_PATH = Path(__file__).parent.parent.parent / "samples" / "sample_output.json"

_ALLOWED_METHODS = {"pdf_text", "ocr", "pdf_text+ocr"}

# Patterns that must never appear in the file (secrets / personal data)
_SECRET_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),          # Google API key
    re.compile(r"[A-Za-z]:\\Users"),                   # Windows absolute path
]

_ITEM_REQUIRED_KEYS = {
    "file_id", "filename", "status", "extraction_method",
    "text", "error", "warnings",
}


@pytest.fixture(scope="module")
def sample() -> dict:
    """Load and return the parsed sample JSON (cached for the module)."""
    assert _SAMPLE_PATH.exists(), (
        f"Sample file not found: {_SAMPLE_PATH}\n"
        "Place samples/sample_output.json before running this test."
    )
    return json.loads(_SAMPLE_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Top-level structure
# ---------------------------------------------------------------------------


def test_schema_version(sample: dict) -> None:
    assert sample["schema_version"] == "1.0"


def test_top_level_keys_present(sample: dict) -> None:
    required = {"batch_id", "language", "status", "counts", "items"}
    missing = required - sample.keys()
    assert not missing, f"Missing top-level keys: {missing}"


def test_items_is_non_empty_list(sample: dict) -> None:
    assert isinstance(sample["items"], list)
    assert len(sample["items"]) >= 1


# ---------------------------------------------------------------------------
# Per-item structure
# ---------------------------------------------------------------------------


def test_every_item_has_required_keys(sample: dict) -> None:
    for i, item in enumerate(sample["items"]):
        missing = _ITEM_REQUIRED_KEYS - item.keys()
        assert not missing, f"Item {i} ({item.get('file_id')!r}) missing keys: {missing}"


# ---------------------------------------------------------------------------
# At least one done and one failed item
# ---------------------------------------------------------------------------


def test_at_least_one_done_item(sample: dict) -> None:
    done = [it for it in sample["items"] if it["status"] == "done"]
    assert len(done) >= 1, "Need at least one done item"


def test_at_least_one_failed_item(sample: dict) -> None:
    failed = [it for it in sample["items"] if it["status"] == "failed"]
    assert len(failed) >= 1, "Need at least one failed item"


# ---------------------------------------------------------------------------
# Failed items carry an error envelope
# ---------------------------------------------------------------------------


def test_failed_items_have_error_code_and_message(sample: dict) -> None:
    for item in sample["items"]:
        if item["status"] == "failed":
            assert item["error"] is not None, (
                f"Failed item {item.get('file_id')!r} has no error object"
            )
            assert isinstance(item["error"].get("code"), str) and item["error"]["code"]
            assert isinstance(item["error"].get("message"), str) and item["error"]["message"]


# ---------------------------------------------------------------------------
# Done items have a valid extraction_method
# ---------------------------------------------------------------------------


def test_done_items_extraction_method_in_enum(sample: dict) -> None:
    for item in sample["items"]:
        if item["status"] == "done":
            assert item["extraction_method"] in _ALLOWED_METHODS, (
                f"Item {item.get('file_id')!r} has unexpected method"
                f" {item['extraction_method']!r}"
            )


# ---------------------------------------------------------------------------
# No secrets anywhere in the raw file content
# ---------------------------------------------------------------------------


def test_no_secrets_in_file() -> None:
    raw = _SAMPLE_PATH.read_text(encoding="utf-8")
    for pattern in _SECRET_PATTERNS:
        match = pattern.search(raw)
        assert match is None, (
            f"Potential secret matched pattern {pattern.pattern!r}"
            f" at position {match.start()}"
        )
