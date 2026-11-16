"""Smoke tests for application startup."""

from fastapi import FastAPI

from app.main import create_app


def test_create_app_returns_fastapi() -> None:
    """create_app() returns a FastAPI instance."""
    application = create_app()
    assert isinstance(application, FastAPI)
