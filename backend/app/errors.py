"""Application error classes and exception handlers."""

import logging
import re

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)



def safe_text(value: str, limit: int = 40) -> str:
    """Strip control characters, collapse whitespace, truncate with ellipsis.

    Use whenever user-supplied input is echoed back in an error message so
    that newlines, control characters and long strings cannot be injected.
    """
    cleaned = re.sub(r"[\x00-\x1f\x7f]", " ", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > limit:
        return cleaned[:limit] + "\u2026"
    return cleaned



class AppError(Exception):
    """Domain error raised throughout the application."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all exception handlers to *app*."""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        first = exc.errors()[0]
        field = ".".join(str(loc) for loc in first.get("loc", []))
        msg = first.get("msg", "Invalid input")
        message = f"{field}: {msg}" if field else msg
        return JSONResponse(
            status_code=422,
            content=_error_body("VALIDATION_ERROR", message),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url)
        return JSONResponse(
            status_code=500,
            content=_error_body("INTERNAL_ERROR", "Unexpected server error."),
        )
