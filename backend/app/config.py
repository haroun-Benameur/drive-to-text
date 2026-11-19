"""Application configuration loaded from environment variables."""

import functools

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All runtime configuration, resolved from environment / .env file."""

    model_config = {"env_file": ".env", "extra": "ignore"}

    # Google Drive
    google_api_key: str | None = None

    # CORS â€“ stored as a list; parsed from a comma-separated string
    cors_origins: list[str] = ["http://localhost:5173"]

    # Tesseract
    tesseract_cmd: str | None = None
    tessdata_prefix: str | None = None
    default_ocr_language: str = "fra+eng"

    # File / batch limits
    max_file_size_mb: int = 25
    max_files_per_batch: int = 50
    max_listed_files: int = 500
    max_pdf_pages: int = 30
    max_image_pixels: int = 50_000_000

    # Timing
    file_time_budget_s: int = 120
    ocr_page_timeout_s: int = 60

    # OCR quality
    min_page_chars: int = 25
    ocr_render_dpi: int = 200

    # Concurrency / retention
    batch_workers: int = 2
    batch_ttl_minutes: int = 60
    max_active_batches: int = 4

    # Logging
    log_level: str = "INFO"

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v: object) -> list[str]:
        """Accept either a comma-separated string or a list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v  # type: ignore[return-value]

    @field_validator("google_api_key", "tesseract_cmd", "tessdata_prefix", mode="before")
    @classmethod
    def _empty_string_to_none(cls, v: object) -> object:
        """Treat blank strings (e.g. from docker-compose) as None."""
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    # ------------------------------------------------------------------
    # Computed property
    # ------------------------------------------------------------------

    @property
    def max_file_size_bytes(self) -> int:
        """Return :attr:`max_file_size_mb` converted to bytes."""
        return self.max_file_size_mb * 1024 * 1024


@functools.lru_cache
def get_settings() -> Settings:
    """Return the cached :class:`Settings` singleton (use with FastAPI Depends)."""
    return Settings()
