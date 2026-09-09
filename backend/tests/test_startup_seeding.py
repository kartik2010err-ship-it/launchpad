"""Startup must never destroy data.

This file exists because it already went wrong once: the startup hook called a
seed function that began with ``drop_all``, so every server restart silently
deleted every real account, workspace and project created since the last boot.

The tests below simulate a restart by invoking the same startup path the running
application uses, and assert that real records are still there afterwards.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.session import Base, SessionLocal, engine
from app.main import app, on_startup
from app.models.project import Project, User
from app.models.workspace import NotebookEntry
from app.models.workspace_org import Workspace, WorkspaceMembership
from app.seed import database_is_empty, run as seed_run, seed_if_empty


@pytest.fixture(scope="module", autouse=True)
def seeded() -> None:
    seed_run()


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def auth(client: TestClient, email: str, password: str = "coach1234") -> dict[str, str]:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _count(model) -> int:
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(model)) or 0


# --------------------------------------------------------------------------- #
# The regression: a restart must not wipe real data
# --------------------------------------------------------------------------- #


def test_restart_does_not_delete_a_real_account(client):
    """The exact failure that lost a real user's account overnight."""

    registration = client.post(
        "/auth/register",
        json={
            "name": "Real Person",
            "email": "real.person@example.edu",
            "password": "a-real-password",
            "role": "student",
            "grade_level": 11,
        },
    )
    assert registration.status_code in (200, 201), registration.text

    with SessionLocal() as db:
        before = db.scalars(
            select(User).where(User.email == "real.person@example.edu")
        ).one()
        user_id, created_at = before.id, before.created_at

    # Restart the server.
    on_startup()

    with SessionLocal() as db:
        after = db.scalars(
            select(User).where(User.email == "real.person@example.edu")
        ).one_or_none()

    assert after is not None, "the account was deleted by a restart"
    assert after.id == user_id, "the account was recreated rather than preserved"
    assert after.created_at == created_at

    # And they can still sign in with the password they chose.
    assert auth(client, "real.person@example.edu", "a-real-password")


def test_restart_preserves_a_users_project_and_its_work(client):
    """A project plus the research written into it has to survive a restart."""

    headers = auth(client, "real.person@example.edu", "a-real-password")

    created = client.post(
        "/projects",
        json={
            "title": "Persistence Research Project",
            "initial_question": "Does this project survive a server restart?",
            "grade_level": 11,
            "project_type": "scientific",
            "category": "physics",
        },
        headers=headers,
    )
    assert created.status_code in (200, 201), created.text
    project_id = created.json()["id"]
    workspace_id = created.json()["workspace_id"]

    entry = client.post(
        f"/projects/{project_id}/notebook",
        json={"entry_date": "2026-03-01", "what_was_done": "Ran the first trial."},
        headers=headers,
    )
    assert entry.status_code in (200, 201), entry.text

    # Restart the server.
    on_startup()

    with SessionLocal() as db:
        assert db.get(Project, project_id) is not None, "the project was deleted by a restart"
        assert db.get(Workspace, workspace_id) is not None, "the workspace was deleted"
        notebook_count = db.scalar(
            select(func.count())
            .select_from(NotebookEntry)
            .where(NotebookEntry.project_id == project_id)
        )
        assert notebook_count == 1, "the notebook entry did not survive the restart"

    # Still readable and editable by its owner afterwards.
    assert client.get(f"/projects/{project_id}", headers=headers).status_code == 200
    edit = client.patch(
        f"/projects/{project_id}", json={"topic": "still editable"}, headers=headers
    )
    assert edit.status_code == 200, edit.text


def test_repeated_restarts_do_not_accumulate_or_remove_rows(client):
    """Startup is idempotent: three restarts change nothing."""

    models = (User, Workspace, WorkspaceMembership, Project)
    before = {model: _count(model) for model in models}

    for _ in range(3):
        on_startup()

    assert {model: _count(model) for model in models} == before


def test_startup_does_not_reseed_when_data_exists():
    assert database_is_empty() is False
    assert seed_if_empty() is False, "a populated database must not be reseeded"


# --------------------------------------------------------------------------- #
# First run still works
# --------------------------------------------------------------------------- #


def test_empty_database_is_seeded_on_first_run():
    """The behaviour we did not want to lose: a fresh install comes up usable."""

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    assert database_is_empty() is True
    assert _count(User) == 0

    assert seed_if_empty() is True, "an empty database should be seeded"
    assert _count(User) > 0
    assert _count(Project) > 0
    assert database_is_empty() is False

    # And a second call is a no-op rather than a duplicate.
    users_after_first = _count(User)
    assert seed_if_empty() is False
    assert _count(User) == users_after_first


def test_seed_run_without_reset_does_not_drop():
    """``run(reset=False)`` is the call seed_if_empty makes; it must not drop.

    Starts from an empty schema holding one pre-existing row, because that is the
    only situation seed_if_empty ever calls it in. (``run`` is not idempotent —
    re-running it over its own demo data collides on unique emails — which is
    exactly why the startup path is gated on the database being empty rather
    than on run() being safe to repeat.)
    """

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        db.add(
            User(
                name="Survivor",
                email="survivor@example.edu",
                hashed_password="x",
                role="student",
            )
        )
        db.commit()

    seed_run(reset=False)

    with SessionLocal() as db:
        survivor = db.scalars(
            select(User).where(User.email == "survivor@example.edu")
        ).one_or_none()
    assert survivor is not None, "run(reset=False) destroyed existing rows"
    # The demo data landed alongside it rather than replacing it.
    assert _count(User) > 1

    # Leave a clean, known dataset behind for any module that runs after this one.
    seed_run(reset=True)
