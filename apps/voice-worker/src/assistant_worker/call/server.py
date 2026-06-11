"""Worker-side FastAPI app accepting Twilio media-stream WebSockets.

Twilio connects to /ws (via the public tunnel/VPS URL) with run_id/task_id in
the stream's custom parameters; the handler looks up the pending call in the
registry and runs the pipeline.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, WebSocket

from .runner import CallRegistry

logger = logging.getLogger(__name__)


def create_ws_app(registry: CallRegistry) -> FastAPI:
    app = FastAPI(title="Voice worker media stream endpoint")

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.websocket("/ws")
    async def media_stream(websocket: WebSocket) -> None:
        from .pipeline import read_stream_start, run_call_pipeline

        await websocket.accept()
        stream_info = await read_stream_start(websocket)
        run_id = stream_info["params"].get("run_id", "")
        context = registry.context(run_id)
        if context is None:
            logger.warning("media stream for unknown run %s; closing", run_id)
            await websocket.close()
            return

        try:
            result = await run_call_pipeline(
                websocket=websocket,
                stream_info=stream_info,
                config=context["config"],
                run_client=context["run_client"],
                redis=context["redis"],
                settings=context["settings"],
                run_id=run_id,
            )
            registry.resolve(run_id, result)
        except Exception as exc:
            logger.exception("pipeline crashed for run %s", run_id)
            registry.fail(run_id, exc)

    return app
