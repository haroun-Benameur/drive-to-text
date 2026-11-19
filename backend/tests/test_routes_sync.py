"""Assert that all /api route handlers are synchronous (plain def, not async def).

FastAPI runs plain-def handlers in its default thread-pool executor, which
prevents blocking I/O (httpx, Tesseract subprocess) from stalling the event
loop and blocking concurrent batch-status polling.
"""

import inspect

from app.main import create_app


def test_no_api_route_handler_is_coroutine() -> None:
    """Every endpoint registered under /api must be a plain function, not a coroutine."""
    app = create_app()
    coroutine_routes: list[str] = []

    for route in app.routes:
        # Only check APIRoute objects (skip Mount, WebSocket, etc.)
        path: str = getattr(route, "path", "")
        endpoint = getattr(route, "endpoint", None)
        if endpoint is None:
            continue
        if not path.startswith("/api"):
            continue
        if inspect.iscoroutinefunction(endpoint):
            methods = getattr(route, "methods", {"?"})
            coroutine_routes.append(f"{methods} {path}")

    assert not coroutine_routes, (
        "The following /api handlers are async def and will block the event loop:\n"
        + "\n".join(f"  {r}" for r in coroutine_routes)
        + "\nConvert them to plain def so FastAPI runs them in the thread pool."
    )
