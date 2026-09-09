"""Authorization tests.

The point of the workspace refactor was that authority is relational. These
tests are the proof: the same person is checked in two workspaces where they
hold different roles, and a student from another school is checked against
every project-scoped route to make sure nothing leaks.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.enums import ProjectVisibility, WorkspaceRole
from app.models.project import Project
from app.models.workspace_org import Workspace, WorkspaceMembership
from app.seed import run as seed_run


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


def _db():
    return SessionLocal()


def workspace_id(name: str) -> int:
    with _db() as db:
        return db.query(Workspace).filter(Workspace.name == name).one().id


def project_id(title: str) -> int:
    with _db() as db:
        return db.query(Project).filter(Project.title == title).one().id


CLUB = "Hamilton High Science Fair Club"
ROBOTICS = "Robotics Research Team"
RIVAL = "Westbrook Academy Research"


# --------------------------------------------------------------------------- #
# Roles are per workspace, not per user
# --------------------------------------------------------------------------- #


def test_same_person_holds_different_roles_in_different_workspaces(client):
    headers = auth(client, "jordan@example.edu")
    spaces = {w["name"]: w["my_role"] for w in client.get("/workspaces", headers=headers).json()}
    assert spaces[CLUB] == WorkspaceRole.LEAD
    assert spaces[ROBOTICS] == WorkspaceRole.OWNER


def test_club_owner_is_only_a_member_elsewhere(client):
    headers = auth(client, "mentor@example.edu")
    spaces = {w["name"]: w["my_role"] for w in client.get("/workspaces", headers=headers).json()}
    assert spaces[CLUB] == WorkspaceRole.OWNER
    assert spaces[ROBOTICS] == WorkspaceRole.MEMBER


def test_student_lead_can_oversee_the_whole_club(client):
    headers = auth(client, "jordan@example.edu")
    rows = client.get(f"/workspaces/{workspace_id(CLUB)}/projects", headers=headers).json()
    assert len(rows) >= 14
    assert {"Ava Ramirez", "Priya Nair"} <= {r["owner_name"] for r in rows}


# --------------------------------------------------------------------------- #
# Cross-workspace isolation
# --------------------------------------------------------------------------- #


def test_outsider_cannot_list_a_workspace_they_are_not_in(client):
    headers = auth(client, "riley@example.edu")
    response = client.get(f"/workspaces/{workspace_id(CLUB)}", headers=headers)
    # 404 not 403: membership is not something an outsider gets to probe.
    assert response.status_code == 404


def test_outsider_cannot_read_a_project_in_another_workspace(client):
    headers = auth(client, "riley@example.edu")
    response = client.get(f"/projects/{project_id('Music and studying')}", headers=headers)
    assert response.status_code == 404


def test_outsider_blocked_from_every_project_subroute(client):
    """The research routes inherit authz from get_project. Prove it holds."""

    headers = auth(client, "riley@example.edu")
    pid = project_id("Biochar and nitrate retention under monsoon rainfall")
    for path in [
        f"/projects/{pid}/evaluation",
        f"/projects/{pid}/rubric",
        f"/projects/{pid}/novelty",
        f"/projects/{pid}/timeline",
        f"/projects/{pid}/readiness",
        f"/projects/{pid}/poster/plan",
        f"/projects/{pid}/interview-prep",
        f"/projects/{pid}/notebook",
    ]:
        assert client.get(path, headers=headers).status_code in (403, 404), path


def test_outsiders_projects_are_invisible_to_the_club(client):
    headers = auth(client, "jordan@example.edu")
    titles = {p["title"] for p in client.get("/projects", headers=headers).json()}
    assert "Solar panel dust accumulation" not in titles


def test_project_list_only_contains_openable_projects(client):
    """Anything listed must also be readable — no teaser rows."""

    headers = auth(client, "kevin@example.edu")
    for project in client.get("/projects", headers=headers).json():
        assert client.get(f"/projects/{project['id']}", headers=headers).status_code == 200


# --------------------------------------------------------------------------- #
# Within a workspace: students, mentors, leads
# --------------------------------------------------------------------------- #


def test_student_cannot_read_a_classmates_private_project(client):
    headers = auth(client, "ava@example.edu")
    response = client.get(f"/projects/{project_id('Enzyme activity across pH')}", headers=headers)
    assert response.status_code == 403


def test_assigned_mentor_can_read_their_students_project(client):
    headers = auth(client, "andre@example.edu")
    assert (
        client.get(
            f"/projects/{project_id('Battery efficiency under cold cycling')}", headers=headers
        ).status_code
        == 200
    )


def test_mentor_cannot_read_a_project_they_are_not_assigned(client):
    headers = auth(client, "andre@example.edu")
    response = client.get(f"/projects/{project_id('Music and studying')}", headers=headers)
    assert response.status_code == 403


def test_mentor_sees_only_assigned_projects_in_the_workspace_table(client):
    headers = auth(client, "andre@example.edu")
    rows = client.get(f"/workspaces/{workspace_id(CLUB)}/projects", headers=headers).json()
    assert rows and all(r["mentor_name"] == "Mr. Andre Cole" for r in rows)


def test_lead_cannot_rewrite_a_students_research(client):
    """Oversight is not authorship."""

    headers = auth(client, "jordan@example.edu")
    pid = project_id("Music and studying")
    assert client.get(f"/projects/{pid}", headers=headers).status_code == 200
    response = client.patch(f"/projects/{pid}", json={"title": "Hijacked"}, headers=headers)
    assert response.status_code == 403


def test_student_can_edit_their_own_project(client):
    headers = auth(client, "ava@example.edu")
    pid = project_id("Music and studying")
    assert (
        client.patch(f"/projects/{pid}", json={"topic": "focus"}, headers=headers).status_code
        == 200
    )


def test_workspace_visibility_opens_projects_to_members(client):
    """Robotics is set to workspace-wide visibility, so teammates can read."""

    headers = auth(client, "liam@example.edu")
    response = client.get(f"/projects/{project_id('Drivetrain gear ratio testing')}", headers=headers)
    assert response.status_code == 200

    with _db() as db:
        project = db.query(Project).filter(
            Project.title == "Drivetrain gear ratio testing"
        ).one()
        assert project.visibility == ProjectVisibility.WORKSPACE


# --------------------------------------------------------------------------- #
# Management actions
# --------------------------------------------------------------------------- #


def test_member_cannot_change_roles(client):
    headers = auth(client, "ava@example.edu")
    with _db() as db:
        target = (
            db.query(WorkspaceMembership)
            .join(Workspace)
            .filter(Workspace.name == CLUB)
            .filter(WorkspaceMembership.role == WorkspaceRole.MEMBER)
            .first()
        )
    response = client.patch(
        f"/workspaces/{workspace_id(CLUB)}/members/{target.user_id}",
        json={"role": "owner"},
        headers=headers,
    )
    assert response.status_code == 403


def test_lead_cannot_change_roles_but_owner_can(client):
    club = workspace_id(CLUB)
    with _db() as db:
        kevin = db.query(Project).filter(Project.title == "Sleep duration and reaction time").one()
        target_id = kevin.owner_id

    lead = auth(client, "jordan@example.edu")
    assert (
        client.patch(
            f"/workspaces/{club}/members/{target_id}", json={"role": "mentor"}, headers=lead
        ).status_code
        == 403
    )

    owner = auth(client, "mentor@example.edu")
    response = client.patch(
        f"/workspaces/{club}/members/{target_id}", json={"role": "mentor"}, headers=owner
    )
    assert response.status_code == 200
    assert response.json()["role"] == "mentor"
    # put it back
    client.patch(
        f"/workspaces/{club}/members/{target_id}", json={"role": "member"}, headers=owner
    )


def test_lead_can_assign_a_mentor(client):
    club = workspace_id(CLUB)
    headers = auth(client, "jordan@example.edu")
    pid = project_id("Layered ceramic water filtration")
    with _db() as db:
        andre = (
            db.query(WorkspaceMembership)
            .join(Workspace)
            .filter(Workspace.name == CLUB, WorkspaceMembership.role == WorkspaceRole.MENTOR)
            .first()
        )
    response = client.patch(
        f"/workspaces/{club}/projects/{pid}/mentor",
        json={"mentor_id": andre.user_id},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["mentor_id"] == andre.user_id


def test_cannot_assign_a_plain_member_as_mentor(client):
    club = workspace_id(CLUB)
    headers = auth(client, "mentor@example.edu")
    with _db() as db:
        ava = db.query(Project).filter(Project.title == "Music and studying").one()
    response = client.patch(
        f"/workspaces/{club}/projects/{ava.id}/mentor",
        json={"mentor_id": ava.owner_id},
        headers=headers,
    )
    assert response.status_code == 400


def test_outsider_cannot_assign_mentors(client):
    headers = auth(client, "riley@example.edu")
    response = client.patch(
        f"/workspaces/{workspace_id(CLUB)}/projects/{project_id('Music and studying')}/mentor",
        json={"mentor_id": 1},
        headers=headers,
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Dashboard, attention queue, activity
# --------------------------------------------------------------------------- #


def test_dashboard_summarises_the_club(client):
    headers = auth(client, "jordan@example.edu")
    data = client.get(f"/workspaces/{workspace_id(CLUB)}/dashboard", headers=headers).json()
    stats = data["stats"]
    assert stats["total_projects"] >= 14
    assert stats["average_readiness"] is not None
    assert sum(
        stats[k] for k in ("on_track", "needs_attention", "at_risk", "blocked", "complete")
    ) == stats["total_projects"]
    assert data["attention"], "a club this messy should have an attention queue"


def test_attention_queue_is_oversight_only(client):
    club = workspace_id(CLUB)
    assert (
        client.get(f"/workspaces/{club}/attention", headers=auth(client, "ava@example.edu")).status_code
        == 403
    )
    assert (
        client.get(
            f"/workspaces/{club}/attention", headers=auth(client, "jordan@example.edu")
        ).status_code
        == 200
    )


def test_activity_feed_is_scoped_to_the_workspace(client):
    headers = auth(client, "jordan@example.edu")
    feed = client.get(f"/workspaces/{workspace_id(CLUB)}/activity", headers=headers).json()
    assert feed
    club_projects = {
        p["project_id"]
        for p in client.get(
            f"/workspaces/{workspace_id(CLUB)}/projects", headers=headers
        ).json()
    }
    for entry in feed:
        if entry["project_id"] is not None:
            assert entry["project_id"] in club_projects


def test_blocked_project_is_detected_with_a_reason(client):
    headers = auth(client, "jordan@example.edu")
    rows = client.get(f"/workspaces/{workspace_id(CLUB)}/projects", headers=headers).json()
    sarah = next(r for r in rows if r["owner_name"] == "Sarah Kim")
    assert sarah["status"] in ("blocked", "at_risk")
    assert sarah["blockers"] or sarah["reasons"]


def test_status_filter_narrows_the_table(client):
    headers = auth(client, "jordan@example.edu")
    club = workspace_id(CLUB)
    rows = client.get(
        f"/workspaces/{club}/projects?project_status=on_track", headers=headers
    ).json()
    assert all(r["status"] == "on_track" for r in rows)


# --------------------------------------------------------------------------- #
# Joining
# --------------------------------------------------------------------------- #


def test_join_code_adds_a_member_not_a_lead(client):
    headers = auth(client, "riley@example.edu")
    response = client.post(
        "/workspaces/join", json={"join_code": "HAMILTON-SCIENCE-27"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["my_role"] == WorkspaceRole.MEMBER
    # Joining does not hand over the club roster.
    assert (
        client.get(
            f"/workspaces/{workspace_id(CLUB)}/attention", headers=headers
        ).status_code
        == 403
    )
    # ...and still cannot read a classmate's private project.
    assert (
        client.get(f"/projects/{project_id('Music and studying')}", headers=headers).status_code
        == 403
    )


def test_bad_join_code_is_rejected(client):
    headers = auth(client, "riley@example.edu")
    response = client.post("/workspaces/join", json={"join_code": "NOPE-1234"}, headers=headers)
    assert response.status_code == 404


def test_new_account_gets_a_personal_workspace(client):
    response = client.post(
        "/auth/register",
        json={
            "name": "Solo Student",
            "email": "solo@example.edu",
            "password": "password1",
            "grade_level": 10,
        },
    )
    assert response.status_code in (200, 201)
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    spaces = client.get("/workspaces", headers=headers).json()
    assert any(w["is_personal"] for w in spaces)

    created = client.post(
        "/projects",
        json={
            "title": "Solo project",
            "initial_question": "Does anything happen when nobody is watching?",
            "grade_level": 10,
            "project_type": "scientific",
            "category": "physics",
        },
        headers=headers,
    )
    assert created.status_code == 201
    personal = next(w for w in spaces if w["is_personal"])
    assert created.json()["workspace_id"] == personal["id"]
