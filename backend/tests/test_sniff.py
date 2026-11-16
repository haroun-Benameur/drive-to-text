"""Tests for sniff_content_kind."""

import pytest

from app.extraction.sniff import sniff_content_kind

# PNG magic bytes
_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
# JPEG SOI marker
_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100
# PDF with no leading content
_PDF_CLEAN = b"%PDF-1.4\n" + b"\x00" * 100
# PDF with 10 bytes of leading whitespace (still within search window)
_PDF_LEADING_WS = b"   \n   \n  " + b"%PDF-1.4\n" + b"\x00" * 100
# ZIP / .docx header
_ZIP = b"PK\x03\x04" + b"\x00" * 100
# Completely random / unrecognised bytes
_RANDOM = b"\x00\x01\x02\x03\x04\x05\x06\x07" * 20


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (_PDF_CLEAN, "pdf"),
        (_PDF_LEADING_WS, "pdf"),
        (_PNG, "png"),
        (_JPEG, "jpeg"),
        (b"", None),
        (_RANDOM, None),
        (_ZIP, None),
    ],
)
def test_sniff_content_kind(data: bytes, expected: str | None) -> None:
    assert sniff_content_kind(data) == expected
