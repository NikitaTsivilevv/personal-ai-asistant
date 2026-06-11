from fastapi import FastAPI

from assistant_worker.call.runner import CallRegistry
from assistant_worker.call.server import create_ws_app


def test_create_ws_app_returns_fastapi_app():
    app = create_ws_app(CallRegistry())

    assert isinstance(app, FastAPI)
    assert any(getattr(r, "path", None) == "/health" for r in app.routes)
    assert any(getattr(r, "path", None) == "/ws" for r in app.routes)
