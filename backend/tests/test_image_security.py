"""Security tests for ImageExtractor: oversized images and corrupt data."""

import io

import pytest
from PIL import Image

from app.config import Settings
from app.errors import AppError
from app.extraction.image import ImageExtractor
from app.models import OcrOutput

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LOW_LIMIT = 100  # 100 pixels total — tiny limit for tests


def _settings(max_pixels: int = _LOW_LIMIT) -> Settings:
    return Settings(
        cors_origins=["http://localhost:5173"],
        max_image_pixels=max_pixels,
        ocr_page_timeout_s=60,
    )


class FakeOcr:
    call_count = 0

    def version(self) -> str:
        return "fake"

    def available_languages(self) -> list[str]:
        return ["eng"]

    def recognize(
        self, image: object, language: str, timeout: float | None = None
    ) -> OcrOutput:
        FakeOcr.call_count += 1
        return OcrOutput(text="text", confidence=95.0, engine="tesseract fake")

    def ocr_image(
        self, image: object, language: str, timeout: float | None = None
    ) -> str:
        return self.recognize(image, language, timeout).text


def _png_bytes(width: int, height: int) -> bytes:
    img = Image.new("RGB", (width, height), color="white")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _truncated_png() -> bytes:
    """Valid PNG header but truncated body."""
    return _png_bytes(10, 10)[:30]


def _garbage_with_png_sig() -> bytes:
    """PNG signature followed by random garbage."""
    return b"\x89PNG\r\n\x1a\n" + b"\x00\xff\xaa" * 50


# ---------------------------------------------------------------------------
# Oversized image is rejected BEFORE load() is called
# ---------------------------------------------------------------------------


def test_oversized_image_raises_file_too_large(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 20×20 image (400 px) is over our 100-px limit → FILE_TOO_LARGE.

    The pixel-count check uses image.size (set during open/header parse).
    Our code must reject the image before calling image.load() explicitly
    (the load that actually decodes the full pixel buffer).
    We verify this by patching the instance's load() after Image.open()
    returns — meaning any explicit load() call in extract() will be caught.
    """
    extractor = ImageExtractor(ocr=FakeOcr(), settings=_settings(max_pixels=100))

    # Intercept Image.open to inject a spy on the returned instance.
    original_open = Image.open
    explicit_load_called = []

    def patched_open(fp, *args, **kwargs):  # type: ignore[no-untyped-def]
        img = original_open(fp, *args, **kwargs)
        # Replace load on this instance so any post-open load() call is tracked.
        original_instance_load = img.load

        def spy_load():  # type: ignore[no-untyped-def]
            explicit_load_called.append(True)
            return original_instance_load()

        img.load = spy_load  # type: ignore[method-assign]
        return img

    monkeypatch.setattr(Image, "open", patched_open)

    with pytest.raises(AppError) as exc_info:
        extractor.extract(_png_bytes(20, 20), "eng")

    assert exc_info.value.code == "FILE_TOO_LARGE"
    assert exc_info.value.status_code == 413
    # Our explicit load() call (after the size check) must NOT have been reached
    assert not explicit_load_called, (
        "image.load() was called after Image.open(), meaning pixels were decoded"
        " despite the image being over the size limit"
    )


# ---------------------------------------------------------------------------
# PIL.Image.MAX_IMAGE_PIXELS is NOT mutated globally
# ---------------------------------------------------------------------------


def test_global_max_image_pixels_unchanged() -> None:
    import PIL.Image as _pil

    original = _pil.MAX_IMAGE_PIXELS
    extractor = ImageExtractor(ocr=FakeOcr(), settings=_settings(max_pixels=10_000_000))
    # Use a small image so it passes the limit and runs to completion.
    try:
        extractor.extract(_png_bytes(5, 5), "eng")
    except AppError:
        pass
    assert _pil.MAX_IMAGE_PIXELS == original, (
        f"Image.MAX_IMAGE_PIXELS was mutated: {_pil.MAX_IMAGE_PIXELS!r} != {original!r}"
    )


# ---------------------------------------------------------------------------
# Corrupt / truncated images → CORRUPTED_FILE (never 500)
# ---------------------------------------------------------------------------


def test_truncated_png_raises_corrupted_file() -> None:
    extractor = ImageExtractor(ocr=FakeOcr(), settings=_settings(max_pixels=10_000_000))
    with pytest.raises(AppError) as exc_info:
        extractor.extract(_truncated_png(), "eng")
    assert exc_info.value.code == "CORRUPTED_FILE"
    assert exc_info.value.status_code == 422


def test_garbage_with_png_sig_raises_corrupted_file() -> None:
    extractor = ImageExtractor(ocr=FakeOcr(), settings=_settings(max_pixels=10_000_000))
    with pytest.raises(AppError) as exc_info:
        extractor.extract(_garbage_with_png_sig(), "eng")
    assert exc_info.value.code == "CORRUPTED_FILE"
    assert exc_info.value.status_code == 422


def test_pure_garbage_bytes_raises_corrupted_file() -> None:
    extractor = ImageExtractor(ocr=FakeOcr(), settings=_settings(max_pixels=10_000_000))
    with pytest.raises(AppError) as exc_info:
        extractor.extract(b"\x00\x01\x02\x03" * 100, "eng")
    assert exc_info.value.code == "CORRUPTED_FILE"
    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# Normal small image still works
# ---------------------------------------------------------------------------


def test_normal_image_succeeds() -> None:
    FakeOcr.call_count = 0
    extractor = ImageExtractor(ocr=FakeOcr(), settings=_settings(max_pixels=10_000_000))
    result = extractor.extract(_png_bytes(5, 5), "eng")
    assert result.ocr_pages == 1
    assert FakeOcr.call_count == 1
