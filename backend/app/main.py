"""Drive-to-Text API application."""

from fastapi import FastAPI

from app.errors import register_exception_handlers


def create_app() -> FastAPI:
    """Create the Drive-to-Text API application."""
    application = FastAPI(title="Drive-to-Text POC", version="0.1.0")
    register_exception_handlers(application)
    return application


app = create_app()
