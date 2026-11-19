"""Shared test helpers for building in-memory PDF fixtures."""

from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import NameObject

from app.models import OcrOutput


def make_text_pdf(pages: list[str]) -> bytes:
    """Return a minimal valid PDF containing one text stream per page.

    Uses only the standard Helvetica font so no font embedding is needed.
    The result is readable by pypdf and other compliant PDF readers.
    """
    # Build with pypdf's writer so we get a spec-compliant file without
    # hand-crafting the entire cross-reference table.
    writer = PdfWriter()

    for text in pages:
        # add_blank_page gives us a page object we can annotate.
        page = writer.add_blank_page(width=595, height=842)

        # Craft a minimal content stream that renders the text.
        safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = (
            "BT\n"
            "/F1 12 Tf\n"
            "50 800 Td\n"
            f"({safe}) Tj\n"
            "ET\n"
        ).encode()

        from pypdf.generic import (
            DecodedStreamObject,
            DictionaryObject,
        )

        # Register Helvetica as /F1 in the page's resource dictionary.
        font_dict = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        resources = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {NameObject("/F1"): writer._add_object(font_dict)}
                )
            }
        )
        page[NameObject("/Resources")] = resources

        content_stream = DecodedStreamObject()
        content_stream.set_data(stream)
        content_ref = writer._add_object(content_stream)
        page[NameObject("/Contents")] = content_ref

    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


class FakeOcr:
    """OCR stand-in with a queue of scripted :class:`OcrOutput` values."""

    def __init__(
        self,
        text: str = "OCR TEXT",
        confidence: float | None = 95.0,
        outputs: list[OcrOutput] | None = None,
    ) -> None:
        self._text = text
        self._confidence = confidence
        self._outputs = list(outputs or [])
        self.call_count = 0
        self.timeouts: list[float | None] = []
        self.calls: list[tuple[str]] = []

    def version(self) -> str:
        """Return a fixed fake engine version."""
        return "fake-5.0"

    def available_languages(self) -> list[str]:
        """Return the languages this fake claims to support."""
        return ["eng", "fra"]

    def recognize(
        self, image: object, language: str, timeout: float | None = None
    ) -> OcrOutput:
        """Return the next scripted output, or the default text and confidence."""
        self.call_count += 1
        self.timeouts.append(timeout)
        self.calls.append((language,))
        if self._outputs:
            return self._outputs.pop(0)
        return OcrOutput(
            text=self._text,
            confidence=self._confidence,
            engine="tesseract fake-5.0",
        )

    def ocr_image(
        self, image: object, language: str, timeout: float | None = None
    ) -> str:
        """Return ``recognize(...).text``."""
        return self.recognize(image, language, timeout).text


def make_encrypted_pdf(password: str) -> bytes:
    """Return a minimal PDF encrypted with *password*."""
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.encrypt(password)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()
