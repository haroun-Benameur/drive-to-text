"""Drive-to-Text API application."""

from fastapi import FastAPI


def create_app() -> FastAPI:
    """Create the Drive-to-Text API application."""
    return FastAPI(title="Drive-to-Text POC", version="0.1.0")


app = create_app()
