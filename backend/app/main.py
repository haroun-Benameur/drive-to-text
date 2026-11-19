"""Drive-to-Text API application."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.batches.runner import BatchRunner
from app.batches.store import BatchStore
from app.config import get_settings
from app.errors import register_exception_handlers


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Create shared state before the first request; clean up on shutdown."""
    settings = get_settings()

    from app.api.deps import get_drive_client, get_router
    from app.batches.cache import ResultCache

    store = BatchStore()
    cache = ResultCache(settings.result_cache_size)
    runner = BatchRunner(
        store=store,
        drive_client_factory=get_drive_client,
        router_factory=get_router,
        settings=settings,
        cache=cache,
    )
    app.state.store = store
    app.state.runner = runner

    yield

    runner.shutdown()


def create_app() -> FastAPI:
    """Create the Drive-to-Text API application."""
    settings = get_settings()

    logging.basicConfig(level=settings.log_level.upper())

    application = FastAPI(
        title="Drive-to-Text POC",
        version="0.1.0",
        lifespan=_lifespan,
    )

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
