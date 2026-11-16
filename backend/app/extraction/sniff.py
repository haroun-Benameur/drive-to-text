"""Content-type detection via magic bytes."""

from typing import Literal

# PNG: 8-byte signature
_PNG_SIG = b"\x89PNG\r\n\x1a\n"
# JPEG: SOI marker
_JPEG_SOI = b"\xff\xd8\xff"
# PDF: marker searched within the first 1 024 bytes (some PDFs have a BOM/comment first)
_PDF_SIG = b"%PDF-"
_PDF_SEARCH_WINDOW = 1024


def sniff_content_kind(data: bytes) -> Literal["pdf", "png", "jpeg"] | None:
    """Return the content kind inferred from magic bytes, or ``None``.

    Checks are performed without any file-system or network access.
    """
    if not data:
        return None

    # PNG — fixed 8-byte header at offset 0
    if data[:8] == _PNG_SIG:
        return "png"

    # JPEG — SOI marker at offset 0
    if data[:3] == _JPEG_SOI:
        return "jpeg"

    # PDF — signature anywhere in the first 1 024 bytes
    if _PDF_SIG in data[:_PDF_SEARCH_WINDOW]:
        return "pdf"

    return None
