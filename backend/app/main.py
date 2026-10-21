"""Application entry point.

The same ``app`` runs under uvicorn locally and as a Vercel serverless function
(``api/index.py`` at the repository root). Nothing here assumes a long-lived
process: the database is prepared on the first request a process serves, not
in a startup hook that serverless platforms may never call.
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.routes import (
    assistant,
    historical,
    auth,
    library,
    outreach,
    planning,
    projects,
    teams,
    workspace,
    workspaces,
)
from app.core.config import get_settings
from app.db.bootstrap import ensure_database_ready, prepare_database
from app.db.session import engine

# Import models so metadata is populated before create_all.
from app.models import project as _project_models  # noqa: F401
from app.models import workspace_org as _workspace_org_models  # noqa: F401
from app.models import workspace as _workspace_models  # noqa: F401
from app.models import team as _team_models  # noqa: F401
from app.models import outreach as _outreach_models  # noqa: F401
from app.models import library as _library_models  # noqa: F401
from app.models import assistant as _assistant_models  # noqa: F401
from app.models import historical as _historical_models  # noqa: F401
from app.models import security as _security_models  # noqa: F401

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("research_coach")
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Under uvicorn, prepare eagerly so a broken database shows up in the boot
    # log. On serverless this may never run, and the middleware covers it.
    if not settings.config_problems():
        try:
            await run_in_threadpool(ensure_database_ready)
        except Exception:  # noqa: BLE001 — retried on the first request
            log.exception("Database preparation failed at startup; will retry per request")
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    lifespan=lifespan,
    description=(
        "A research mentoring API for science-fair students. Every score it returns is this "
        "application's estimate, not an official competition result."
    ),
)


app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(planning.router)
app.include_router(workspace.router)
app.include_router(workspaces.router)
app.include_router(teams.router)
app.include_router(library.router)
app.include_router(outreach.router)
app.include_router(assistant.router)
app.include_router(historical.router)


_NO_DATABASE_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


@app.middleware("http")
async def serve(request: Request, call_next):
    """Request id, timing log, configuration guard and lazy database setup."""

    request_id = request.headers.get("x-vercel-id") or uuid.uuid4().hex[:12]
    request.state.request_id = request_id
    started = time.perf_counter()
    path = request.url.path

    problems = settings.config_problems()
    if problems and path != "/health":
        log.error("Refusing request: misconfigured deployment: %s", " ".join(problems))
        return JSONResponse(
            {"detail": "The server is not configured yet. Please try again later."},
            status_code=503,
        )

    if path not in _NO_DATABASE_PATHS:
        try:
            await run_in_threadpool(ensure_database_ready)
        except Exception:  # noqa: BLE001
            log.exception("Database unavailable [%s]", request_id)
            return JSONResponse(
                {"detail": "The database is unavailable right now. Please try again shortly."},
                status_code=503,
                headers={"X-Request-Id": request_id},
            )

    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-Id"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers.setdefault("Cache-Control", "no-store")
    level = logging.WARNING if response.status_code >= 500 or elapsed_ms > 3000 else logging.INFO
    log.log(level, "%s %s -> %d in %.0fms [%s]", request.method, path, response.status_code, elapsed_ms, request_id)
    return response


# Added after ``serve`` so it wraps it: even a 503 from the guard above reaches
# a cross-origin frontend with CORS headers, instead of as an opaque failure.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    """Log the traceback with the request id, and give the user that id
    instead of a bare 500 page they cannot report."""

    request_id = getattr(request.state, "request_id", "-")
    log.exception("Unhandled error on %s %s [%s]", request.method, request.url.path, request_id)
    return JSONResponse(
        {"detail": f"Something went wrong on our side. Reference: {request_id}"},
        status_code=500,
        headers={"X-Request-Id": request_id},
    )


def on_startup() -> None:
    """Prepare the schema as a fresh boot would. Never destroys data.

    Kept as a named entry point for the tests that simulate a restart and
    assert every account, team and project survives it.
    """

    prepare_database(force=True)


@app.get("/health", tags=["meta"])
def health() -> JSONResponse:
    """Liveness plus a real database round trip, for uptime monitors."""

    problems = settings.config_problems()
    database = "ok"
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        log.warning("Health check database failure: %s", exc)
        database = "unavailable"
    healthy = database == "ok" and not problems
    return JSONResponse(
        {
            "status": "ok" if healthy else "degraded",
            "database": database,
            "config_problems": problems,
            "ai_provider": settings.ai_provider,
            "version": settings.version,
        },
        status_code=200 if healthy else 503,
    )
