"""Drive-to-Text API application."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.errors import register_exception_handlers


def create_app() -> FastAPI:
    """Create the Drive-to-Text API application."""
    settings = get_settings()

    logging.basicConfig(level=settings.log_level.upper())

    application = FastAPI(title="Drive-to-Text POC", version="0.1.0")

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    register_exception_handlers(application)
    application.include_router(router)

    return application


app = create_app()
