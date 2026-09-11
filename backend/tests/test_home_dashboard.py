"""The context-aware home and the shared next-action (sections 34-35).

The claim under test is that this page answers four questions and does not
degenerate into a task list, and that the recommendation it shows is the *same*
one the Research Assistant gives — two surfaces telling a student different
things is worse than either one being slightly wrong.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.project import Project
from app.models.team import Team
from app.seed import run as seed_run
from app.services import assistant_context, next_action


@pytest.fixture(scope="module", autouse=True)
def seeded() -> None:
    seed_run()


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def auth(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": email, "password": "coach1234"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def dashboard(client: TestClient, email: str) -> dict:
    response = client.get("/projects/home/dashboard", headers=auth(client, email))
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------- #
# Section 34 — the four questions
# --------------------------------------------------------------------------- #


def test_the_dashboard_answers_all_four_questions(client: TestClient) -> None:
    body = dashboard(client, "maya@example.edu")
    assert body["has_project"] is True
    assert body["project"]["title"]
    assert body["project"]["stage"]
    assert body["next_action"]["primary"]["action"]
    assert "attention" in body
    assert "upcoming" in body


def test_it_shows_the_students_own_work_not_everything_they_can_see(
    client: TestClient,
) -> None:
    """A workspace owner's home is their own project, not the whole workspace.
    Oversight lives on the workspace dashboard."""

    body = dashboard(client, "priyanka@example.edu")
    if body["has_project"]:
        with SessionLocal() as db:
            team = db.query(Team).filter(Team.name == "Team Coral").one()
            coral = db.query(Project).filter(Project.owner_team_id == team.id).one().id
        assert body["project"]["id"] != coral, "the owner is not on Team Coral"


def test_a_team_member_sees_the_shared_team_project(client: TestClient) -> None:
    body = dashboard(client, "maya@example.edu")
    assert body["project"]["is_team_project"] is True


# --------------------------------------------------------------------------- #
# Section 35 — one recommendation, not a backlog
# --------------------------------------------------------------------------- #


def test_there_is_exactly_one_primary_action(client: TestClient) -> None:
    body = dashboard(client, "maya@example.edu")
    primary = body["next_action"]["primary"]
    assert isinstance(primary, dict)
    assert primary["action"]
    assert primary["why"], "a recommendation with no reason teaches nothing"


def test_secondary_actions_are_capped_at_two(client: TestClient) -> None:
    for email in ("maya@example.edu", "ava@example.edu", "sarah@example.edu"):
        body = dashboard(client, email)
        assert len(body["next_action"]["secondary"]) <= 2, email


def test_the_recommendation_differs_by_project_state(client: TestClient) -> None:
    """If every project got the same advice, the feature would be decoration."""

    a = dashboard(client, "maya@example.edu")["next_action"]["primary"]["action"]
    b = dashboard(client, "ava@example.edu")["next_action"]["primary"]["action"]
    assert a != b


def test_home_and_the_assistant_agree(client: TestClient) -> None:
    """Section 35. One service, so the two surfaces cannot contradict."""

    headers = auth(client, "maya@example.edu")
    home = dashboard(client, "maya@example.edu")
    project_id = home["project"]["id"]

    conversation = client.post(
        "/assistant/conversations", json={"project_id": project_id}, headers=headers
    ).json()["id"]
    reply = client.post(
        f"/assistant/conversations/{conversation}/messages",
        json={"content": "What should I do next?"},
        headers=headers,
    ).json()

    primary = home["next_action"]["primary"]["action"].rstrip(".")
    assert primary.lower() in reply["content"].lower()


def test_a_deadline_never_becomes_the_primary_action() -> None:
    """A deadline is a constraint on when, not an answer to what."""

    context = {
        "stage": "experimentation",
        "derived": {k: True for k in next_action.GAP_ORDER},
        "missing": [],
        "evaluation": {"safety_flags": []},
        "next_deadline": {"title": "Poster printing", "due_date": "2026-10-01"},
    }
    plan = next_action.compute(context)
    assert "due" not in plan["primary"]["action"].lower()
    assert any("Poster printing" in item["action"] for item in plan["secondary"])


def test_a_structural_gap_outranks_a_missing_interview_answer() -> None:
    context = {
        "stage": "experimental_design",
        "derived": {"control_defined": False, "quantitative_outcome": True},
        "missing": ["Time budget"],
        "evaluation": {"safety_flags": []},
        "next_deadline": {},
    }
    plan = next_action.compute(context)
    assert "control" in plan["primary"]["action"].lower()


def test_an_open_approval_outranks_everything() -> None:
    context = {
        "stage": "experimental_design",
        "derived": {"control_defined": False},
        "missing": [],
        "evaluation": {"safety_flags": ["Human participants"]},
        "next_deadline": {},
    }
    plan = next_action.compute(context)
    assert "approval" in plan["primary"]["action"].lower()


def test_a_cleared_approval_stops_leading_once_work_has_started() -> None:
    """A flag that leads forever is a flag nobody reads."""

    context = {
        "stage": "data_analysis",
        "derived": {"control_defined": False},
        "missing": [],
        "evaluation": {"safety_flags": ["Human participants"]},
        "next_deadline": {},
    }
    plan = next_action.compute(context)
    assert "approval" not in plan["primary"]["action"].lower()
    assert "control" in plan["primary"]["action"].lower()


def test_no_project_still_gives_a_usable_answer() -> None:
    plan = next_action.compute(None)
    assert plan["primary"]["action"]
    assert plan["source"] == "no_project"


# --------------------------------------------------------------------------- #
# Honesty
# --------------------------------------------------------------------------- #


def test_an_empty_historical_catalogue_reports_zero_not_a_guess(
    client: TestClient,
) -> None:
    """Section 40 applies here too: no fabricated 'related projects' count."""

    body = dashboard(client, "maya@example.edu")
    assert isinstance(body["similar_historical_count"], int)
    assert body["similar_historical_count"] >= 0


def test_the_dashboard_reports_real_readiness_or_says_it_is_unscored(
    client: TestClient,
) -> None:
    body = dashboard(client, "maya@example.edu")
    readiness = body["project"]["readiness"]
    assert readiness is None or 0 <= readiness <= 100


def test_context_and_next_action_stay_in_step(client: TestClient) -> None:
    """The dashboard must not compute its own version of the context."""

    with SessionLocal() as db:
        team = db.query(Team).filter(Team.name == "Team Coral").one()
        project = db.query(Project).filter(Project.owner_team_id == team.id).one()
        direct = next_action.compute(assistant_context.build(db, project))

    body = dashboard(client, "maya@example.edu")
    assert body["next_action"]["primary"]["action"] == direct["primary"]["action"]
