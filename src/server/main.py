"""FastAPI app entrypoint for the DealTracker ops console.

Run:
    uvicorn src.server.main:app --reload --port 8000

Static UI is mounted from ui/dist if present (production); in dev use the
Vite dev server at :5173 with its built-in proxy to :8000.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

# Configure root logging once at import time so every dealtracker.* logger
# under uvicorn produces uniform output. Honor LOG_LEVEL if set.
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .db import init_db
from .events import bus
from .routes import router
from .scheduler import shutdown as scheduler_shutdown, start as scheduler_start
from .sessions import session_cookie_secure, session_secret


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
UI_DIST = REPO_ROOT / "ui" / "dist"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    bus.attach_loop(asyncio.get_running_loop())
    scheduler_start()
    try:
        yield
    finally:
        scheduler_shutdown()


app = FastAPI(
    title="DealTracker",
    version="0.0.1",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# Session must be added BEFORE CORS so the cookie is set/read on every
# request, including preflighted cross-origin XHRs from the Vite dev server.
app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret(),
    session_cookie="dealtracker_session",
    same_site="lax",
    https_only=session_cookie_secure(),
    max_age=60 * 60 * 24 * 30,  # 30 days
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


if UI_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=UI_DIST / "assets"), name="ui-assets")

    @app.get("/")
    def serve_index() -> FileResponse:
        return FileResponse(UI_DIST / "index.html")

    @app.get("/{path:path}")
    def serve_spa(path: str) -> FileResponse:
        candidate = UI_DIST / path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(UI_DIST / "index.html")
