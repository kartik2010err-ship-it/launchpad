"""Application entry point."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
from app.db.migrations import sync_columns
from app.db.session import Base, engine

# Import models so metadata is populated before create_all.
from app.models import project as _project_models  # noqa: F401
from app.models import workspace_org as _workspace_org_models  # noqa: F401
from app.models import workspace as _workspace_models  # noqa: F401
from app.models import team as _team_models  # noqa: F401
from app.models import outreach as _outreach_models  # noqa: F401
from app.models import library as _library_models  # noqa: F401
from app.models import assistant as _assistant_models  # noqa: F401
from app.models import historical as _historical_models  # noqa: F401

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
app.include_router(assistant.router)
app.include_router(historical.router)


@app.on_event("startup")
def on_startup() -> None:
    """Bring the schema up, and seed only a database that has never been used.

    This must never destroy data. A restart of a live server has to leave every
    account, team and project exactly where it was, so the seed path here is
    ``seed_if_empty`` — which no-ops the moment a single user exists — and never
    ``run()``, which drops.

    ``create_all`` adds missing tables but does not alter existing ones, so a new
    *column* still needs a real migration. That remains the next thing this
    project needs.
    """

    Base.metadata.create_all(bind=engine)

    # create_all adds tables but never columns. This closes that gap for the
    # additive case, so shipping a new field does not break a live database.
    added = sync_columns(engine, Base.metadata)
    if added:
        logging.info("Schema migration added %d column(s): %s", len(added), ", ".join(added))

    from app.seed import seed_if_empty

    if seed_if_empty():
        logging.info("Empty database detected on startup — seeded demo data.")
    else:
        logging.info("Existing data found on startup — left untouched.")

@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "ai_provider": settings.ai_provider}
