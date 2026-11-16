"""Table-driven tests for extract_folder_id and is_valid_drive_id."""

import pytest

from app.drive.url import DRIVE_ID_RE, extract_folder_id, is_valid_drive_id
from app.errors import AppError

# A well-formed ID used throughout the valid cases.
_ID = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"


# ---------------------------------------------------------------------------
# Valid URLs – must return the folder ID without raising
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        # Basic folder path
        f"https://drive.google.com/drive/folders/{_ID}",
        # With usp=sharing query param
        f"https://drive.google.com/drive/folders/{_ID}?usp=sharing",
        # With resourcekey extra query param
        f"https://drive.google.com/drive/folders/{_ID}?usp=sharing&resourcekey=0-abc",
        # User-scoped path  /drive/u/0/
        f"https://drive.google.com/drive/u/0/folders/{_ID}",
        f"https://drive.google.com/drive/u/1/folders/{_ID}",
        # /open?id= form
        f"https://drive.google.com/open?id={_ID}",
        f"https://drive.google.com/open?id={_ID}&usp=sharing",
        # Leading/trailing whitespace stripped
        f"  https://drive.google.com/drive/folders/{_ID}  ",
        # Hostname case-insensitive
        f"https://Drive.Google.Com/drive/folders/{_ID}",
    ],
)
def test_valid_url_returns_id(url: str) -> None:
    assert extract_folder_id(url) == _ID


# ---------------------------------------------------------------------------
# Invalid URLs – must raise AppError with code INVALID_FOLDER_URL and 422
# ---------------------------------------------------------------------------


def _raises(url: str) -> AppError:
    with pytest.raises(AppError) as exc_info:
        extract_folder_id(url)
    err = exc_info.value
    assert err.code == "INVALID_FOLDER_URL"
    assert err.status_code == 422
    return err


# --- scheme ---


@pytest.mark.parametrize(
    "url",
    [
        f"http://drive.google.com/drive/folders/{_ID}",
        f"ftp://drive.google.com/drive/folders/{_ID}",
        f"//drive.google.com/drive/folders/{_ID}",
    ],
)
def test_wrong_scheme(url: str) -> None:
    _raises(url)


# --- hostname lookalikes ---


@pytest.mark.parametrize(
    "url",
    [
        # Subdomain of attacker
        f"https://drive.google.com.evil.com/drive/folders/{_ID}",
        # Path-based lookalike
        f"https://evil.com/drive.google.com/drive/folders/{_ID}",
        # Different Google product
        f"https://docs.google.com/drive/folders/{_ID}",
        f"https://google.com/drive/folders/{_ID}",
        # Port included (not drive.google.com bare)
        f"https://drive.google.com:8080/drive/folders/{_ID}",
    ],
)
def test_wrong_host(url: str) -> None:
    _raises(url)


# --- file link rejected with descriptive message ---


def test_file_link_rejected() -> None:
    err = _raises(f"https://drive.google.com/file/d/{_ID}/view")
    assert "file" in err.message.lower()
    assert "folder" in err.message.lower()


# --- empty / blank ---


@pytest.mark.parametrize("url", ["", "   "])
def test_empty_url(url: str) -> None:
    _raises(url)


# --- ID too short ---


def test_id_too_short() -> None:
    short_id = "ABC123"  # only 6 chars
    _raises(f"https://drive.google.com/drive/folders/{short_id}")


# --- ID with illegal characters ---


@pytest.mark.parametrize(
    "bad_id",
    [
        "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlb!",   # exclamation mark
        "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlb/",   # slash
        "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlb.",   # dot
        "1BxiMVs0 XRA5nFMdKvBdBZjgmUUqptlb",   # space
    ],
)
def test_id_illegal_chars(bad_id: str) -> None:
    _raises(f"https://drive.google.com/drive/folders/{bad_id}")


# --- unrecognised path ---


def test_unrecognised_path() -> None:
    _raises(f"https://drive.google.com/something/else/{_ID}")


# ---------------------------------------------------------------------------
# is_valid_drive_id helper
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (_ID, True),
        ("short", False),          # too short
        ("a" * 10, True),          # minimum length
        ("a" * 100, True),         # maximum length
        ("a" * 101, False),        # one over maximum
        ("has space here!", False),
        ("valid-id_123ABC", True),
    ],
)
def test_is_valid_drive_id(value: str, expected: bool) -> None:
    assert is_valid_drive_id(value) is expected


# ---------------------------------------------------------------------------
# DRIVE_ID_RE constant exported
# ---------------------------------------------------------------------------


def test_drive_id_re_exported() -> None:
    import re

    assert isinstance(DRIVE_ID_RE, re.Pattern)
