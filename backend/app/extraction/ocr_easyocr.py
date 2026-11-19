"""EasyOCR engine implementation (optional dependency)."""

import logging
import os
import threading

from PIL import Image

from app.errors import AppError
from app.models import OcrOutput

logger = logging.getLogger(__name__)

# EasyOCR language codes keyed by our language identifiers.
_LANG_MAP: dict[str, list[str]] = {
    "fra":         ["fr"],
    "eng":         ["en"],
    "ara":         ["ar", "en"],
    "fra+eng":     ["fr", "en"],
    # fra+eng+ara is not supported — EasyOCR supports at most 2 languages in
    # practice, and mixing Arabic with Latin scripts is not officially supported.
    "fra+eng+ara": None,
}

_READER_LOCK = threading.Lock()
_readers: dict[tuple[str, ...], object] = {}


def _get_reader(languages: list[str]) -> object:
    """Return a cached easyocr.Reader for *languages*, creating if needed."""
    import easyocr  # lazy import — not installed by default

    key = tuple(sorted(languages))
    with _READER_LOCK:
        if key not in _readers:
            model_dir = os.environ.get("EASYOCR_MODEL_DIR") or None
            _readers[key] = easyocr.Reader(list(key), gpu=False, model_storage_directory=model_dir)
        return _readers[key]


class EasyOcrEngine:
    """OcrEngine backed by EasyOCR (optional; not installed by default)."""

    def version(self) -> str:
        try:
            import easyocr
            return str(getattr(easyocr, "__version__", "unknown"))
        except ImportError as exc:
            raise AppError(
                "OCR_ENGINE_UNAVAILABLE",
                "EasyOCR is not installed. Install requirements-optional.txt.",
                503,
            ) from exc

    def available_languages(self) -> list[str]:
        return list(_LANG_MAP.keys())

    def recognize(
        self,
        image: Image.Image,
        language: str,
        timeout: float | None = None,
    ) -> OcrOutput:
        """Run EasyOCR on *image* and return an :class:`~app.models.OcrOutput`."""
        try:
            import easyocr  # noqa: F401
        except ImportError as exc:
            raise AppError(
                "OCR_ENGINE_UNAVAILABLE",
                "EasyOCR is not installed. Install requirements-optional.txt.",
                503,
            ) from exc

        lang_codes = _LANG_MAP.get(language)
        if lang_codes is None:
            raise AppError(
                "OCR_LANGUAGE_UNSUPPORTED",
                f"Language '{language}' is not supported by EasyOCR.",
                422,
            )

        reader = _get_reader(lang_codes)
        results = reader.readtext(image, detail=1)  # type: ignore[attr-defined]

        texts: list[str] = []
        confidences: list[float] = []
        for _bbox, text, conf in results:
            if text.strip():
                texts.append(text)
                confidences.append(conf * 100)

        combined_text = "\n".join(texts)
        confidence: float | None = (
            round(sum(confidences) / len(confidences), 1)
            if confidences else None
        )

        return OcrOutput(
            text=combined_text,
            confidence=confidence,
            engine=f"easyocr {self.version()}",
        )

    def ocr_image(
        self,
        image: Image.Image,
        language: str,
        timeout: float | None = None,
    ) -> str:
        return self.recognize(image, language, timeout).text
