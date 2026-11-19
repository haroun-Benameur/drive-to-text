"""Light image preprocessing before a second OCR attempt."""

from PIL import Image, ImageOps


def preprocess_for_ocr(image: Image.Image, max_pixels: int) -> Image.Image:
    """Return a grayscale, autocontrasted copy, upscaled when it stays small.

    Images narrower than 1500 pixels are doubled with Lanczos resampling,
    unless the doubled image would exceed *max_pixels*.
    """
    prepared = ImageOps.autocontrast(ImageOps.grayscale(image), cutoff=1)
    width, height = prepared.size
    if width < 1500:
        doubled_width = width * 2
        doubled_height = height * 2
        if doubled_width * doubled_height <= max_pixels:
            prepared = prepared.resize(
                (doubled_width, doubled_height),
                Image.Resampling.LANCZOS,
            )
    return prepared
