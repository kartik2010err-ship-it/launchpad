"""Application entry point."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
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
from app.db.session import Base, engine

# Import models so metadata is populated before create_all.
from app.models import project as _project_models  # noqa: F401
from app.models import workspace_org as _workspace_org_models  # noqa: F401
from app.models import workspace as _workspace_models  # noqa: F401
from app.models import team as _team_models  # noqa: F401
from app.models import outreach as _outreach_models  # noqa: F401
from app.models import library as _library_models  # noqa: F401

logging.basicConfig(level=logging.INFO)
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "A research mentoring API for science-fair students. Every score it returns is this "
        "application's estimate, not an official competition result."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(planning.router)
app.include_router(workspace.router)
app.include_router(workspaces.router)
app.include_router(teams.router)
app.include_router(library.router)
app.include_router(outreach.router)


@app.on_event("startup")
def on_startup() -> None:
    # Fine for a club deployment. Swap for Alembic migrations before the schema
    # carries data anyone would miss.
    Base.metadata.create_all(bind=engine)
    from app.seed import run
    run()

@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "ai_provider": settings.ai_provider}
