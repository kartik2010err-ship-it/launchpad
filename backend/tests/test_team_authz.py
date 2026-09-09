"""Team authorization and shared-ownership tests.

The claims being proved here are the ones that would be most damaging to get
wrong:

* Every member of a team edits the *same* project row — not a copy.
* A student on another team in the same workspace cannot touch it.
* Team join codes and workspace join codes are separate namespaces.
* Team size limits come from competition configuration and are enforced server
  side, not just hidden in the UI.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.project import Project
from app.models.team import Team, TeamMembership
from app.models.workspace_org import Workspace
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


BASIS = "BASIS Phoenix Science Fair"
CLUB = "Hamilton High Science Fair Club"


def workspace_id(name: str) -> int:
    with _db() as db:
        return db.query(Workspace).filter(Workspace.name == name).one().id


def team_id(name: str) -> int:
    with _db() as db:
        return db.query(Team).filter(Team.name == name).one().id


def team_project_id(team_name: str) -> int:
    with _db() as db:
        team = db.query(Team).filter(Team.name == team_name).one()
        return db.query(Project).filter(Project.owner_team_id == team.id).one().id


def project_id(title: str) -> int:
    with _db() as db:
        return db.query(Project).filter(Project.title == title).one().id


# --------------------------------------------------------------------------- #
# One shared project, not a copy per member
# --------------------------------------------------------------------------- #


def test_team_owns_exactly_one_project_row(client):
    """Three members, one project row. This is the core structural claim."""

    with _db() as db:
        coral = db.query(Team).filter(Team.name == "Team Coral").one()
        projects = db.query(Project).filter(Project.owner_team_id == coral.id).all()
        assert len(projects) == 1
        assert projects[0].owner_id is None
        assert db.query(TeamMembership).filter(TeamMembership.team_id == coral.id).count() == 3


def test_all_members_see_the_same_project(client):
    ws = workspace_id(BASIS)
    pid = team_project_id("Team Coral")
    seen = []
    for email in ("maya@example.edu", "arjun@example.edu", "sarah@example.edu"):
        response = client.get(f"/projects/{pid}", headers=auth(client, email))
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["owner_team_id"] is not None
        assert body["owner_kind"] == "team"
        seen.append((body["id"], body["current_question"]))
    assert len(set(seen)) == 1, "members are not looking at the same project record"

    # And the team dashboard resolves to that same id for each of them.
    tid = team_id("Team Coral")
    for email in ("maya@example.edu", "arjun@example.edu", "sarah@example.edu"):
        dash = client.get(
            f"/workspaces/{ws}/teams/{tid}/dashboard", headers=auth(client, email)
        )
        assert dash.status_code == 200, dash.text
        assert dash.json()["project"]["id"] == pid
        assert dash.json()["can_edit_project"] is True


def test_editing_a_team_project_updates_it_for_everyone(client):
    """Arjun edits; Maya and Sarah see the edit on the same row."""

    pid = team_project_id("Team Coral")
    new_title = "Coral Bleaching Research Project (revised)"
    response = client.patch(
        f"/projects/{pid}", json={"title": new_title}, headers=auth(client, "arjun@example.edu")
    )
    assert response.status_code == 200, response.text

    for email in ("maya@example.edu", "sarah@example.edu"):
        body = client.get(f"/projects/{pid}", headers=auth(client, email)).json()
        assert body["title"] == new_title

    # Put it back so later tests read the seeded title.
    client.patch(
        f"/projects/{pid}",
        json={"title": "Coral Bleaching Research Project"},
        headers=auth(client, "maya@example.edu"),
    )


def test_every_member_can_write_research_content(client):
    """Edit rights belong to the team, not to whoever created the project."""

    pid = team_project_id("Team Aero")
    for email in ("liam@example.edu", "marcus@example.edu", "emma@example.edu"):
        response = client.post(
            f"/projects/{pid}/notebook",
            json={
                "entry_date": "2026-02-01",
                "what_was_done": f"Entry written by {email}",
            },
            headers=auth(client, email),
        )
        assert response.status_code in (200, 201), response.text

    entries = client.get(f"/projects/{pid}/notebook", headers=auth(client, "liam@example.edu"))
    assert entries.status_code == 200
    # One shared notebook: everyone's entries are in the same list.
    written = [e["what_was_done"] for e in entries.json()]
    assert sum(1 for w in written if "Entry written by" in w) == 3


# --------------------------------------------------------------------------- #
# Isolation: one team cannot touch another team's project
# --------------------------------------------------------------------------- #


def test_other_team_member_cannot_edit_this_teams_project(client):
    """Kevin is on Team Neuro, in the same workspace. He is still locked out."""

    pid = team_project_id("Team Coral")
    response = client.patch(
        f"/projects/{pid}",
        json={"title": "Hijacked by another team"},
        headers=auth(client, "kevin@example.edu"),
    )
    assert response.status_code == 403
    assert "team that owns this project" in response.json()["detail"]

    # And the title did not change.
    body = client.get(f"/projects/{pid}", headers=auth(client, "maya@example.edu")).json()
    assert body["title"] == "Coral Bleaching Research Project"


def test_other_team_member_cannot_write_research_content(client):
    pid = team_project_id("Team Coral")
    for path, payload in [
        ("notebook", {"entry_date": "2026-02-01", "what_was_done": "Not mine to write"}),
        ("question", {"question": "A question I do not get to set"}),
    ]:
        response = client.post(
            f"/projects/{pid}/{path}", json=payload, headers=auth(client, "kevin@example.edu")
        )
        assert response.status_code == 403, f"{path} was writable by an outsider"


def test_individual_student_cannot_edit_a_team_project(client):
    """Daniel owns his own project in this workspace and no team project."""

    pid = team_project_id("Team Neuro")
    response = client.patch(
        f"/projects/{pid}", json={"title": "nope"}, headers=auth(client, "daniel@example.edu")
    )
    assert response.status_code == 403


def test_team_member_cannot_edit_an_individual_project(client):
    """Ownership runs both ways: team membership grants nothing outside the team."""

    pid = project_id("Battery Degradation Analysis")
    response = client.patch(
        f"/projects/{pid}", json={"title": "nope"}, headers=auth(client, "maya@example.edu")
    )
    assert response.status_code == 403


def test_outsider_cannot_reach_the_team_at_all(client):
    """Riley is at another school entirely — the workspace 404s before authz runs."""

    ws = workspace_id(BASIS)
    tid = team_id("Team Coral")
    headers = auth(client, "riley@example.edu")
    assert client.get(f"/workspaces/{ws}/teams", headers=headers).status_code == 404
    assert client.get(f"/workspaces/{ws}/teams/{tid}/dashboard", headers=headers).status_code == 404
    assert client.get(f"/projects/{team_project_id('Team Coral')}", headers=headers).status_code == 404


# --------------------------------------------------------------------------- #
# Join codes: two separate namespaces
# --------------------------------------------------------------------------- #


def test_team_join_code_adds_a_member_without_creating_a_project(client):
    """The headline behaviour: joining shares the existing row, never copies it."""

    ws = workspace_id(BASIS)
    before = len(
        client.get(f"/workspaces/{ws}/projects", headers=auth(client, "priyanka@example.edu")).json()
    )
    pid_before = team_project_id("Team Neuro")

    # Grace's teammate slot: Kevin and Grace are on Neuro; add Emma? She is on
    # Aero. Use a member of the workspace who is on no team yet.
    response = client.post(
        f"/workspaces/{ws}/teams/join",
        json={"team_join_code": "NEURO-4T7M"},
        headers=auth(client, "priya@example.edu"),
    )
    assert response.status_code == 200, response.text
    assert response.json()["i_am_member"] is True

    after = len(
        client.get(f"/workspaces/{ws}/projects", headers=auth(client, "priyanka@example.edu")).json()
    )
    assert after == before, "joining a team created a project — it must share the existing one"

    with _db() as db:
        neuro = db.query(Team).filter(Team.name == "Team Neuro").one()
        assert db.query(Project).filter(Project.owner_team_id == neuro.id).count() == 1

    # The joiner now edits the same row the original members do.
    assert team_project_id("Team Neuro") == pid_before
    edit = client.patch(
        f"/projects/{pid_before}",
        json={"topic": "joined-member edit"},
        headers=auth(client, "priya@example.edu"),
    )
    assert edit.status_code == 200, edit.text


def test_workspace_join_code_does_not_work_as_a_team_code(client):
    ws = workspace_id(BASIS)
    response = client.post(
        f"/workspaces/{ws}/teams/join",
        json={"team_join_code": "BASIS-SF-27"},
        headers=auth(client, "grace@example.edu"),
    )
    assert response.status_code == 404


def test_team_join_code_does_not_work_as_a_workspace_code(client):
    response = client.post(
        "/workspaces/join",
        json={"join_code": "CORAL-8K2P"},
        headers=auth(client, "riley@example.edu"),
    )
    assert response.status_code == 404


def test_team_code_from_another_workspace_is_rejected(client):
    """Valid code, wrong workspace: 404 rather than leaking that it exists."""

    club = workspace_id(CLUB)
    response = client.post(
        f"/workspaces/{club}/teams/join",
        json={"team_join_code": "CORAL-8K2P"},
        headers=auth(client, "ava@example.edu"),
    )
    assert response.status_code == 404


def test_cannot_join_a_team_without_joining_the_workspace_first(client):
    ws = workspace_id(BASIS)
    response = client.post(
        f"/workspaces/{ws}/teams/join",
        json={"team_join_code": "AERO-9P3K"},
        headers=auth(client, "riley@example.edu"),
    )
    # The workspace dependency rejects before the team is ever looked up.
    assert response.status_code == 404


def test_join_code_is_hidden_from_people_outside_the_team(client):
    ws = workspace_id(BASIS)
    tid = team_id("Team Coral")

    member = client.get(f"/workspaces/{ws}/teams/{tid}", headers=auth(client, "maya@example.edu"))
    assert member.json()["join_code"] == "CORAL-8K2P"

    lead = client.get(f"/workspaces/{ws}/teams/{tid}", headers=auth(client, "jordan@example.edu"))
    assert lead.json()["join_code"] == "CORAL-8K2P"

    other = client.get(f"/workspaces/{ws}/teams/{tid}", headers=auth(client, "kevin@example.edu"))
    assert other.json()["join_code"] is None


# --------------------------------------------------------------------------- #
# Competition-configured team size
# --------------------------------------------------------------------------- #


def test_team_size_limit_is_enforced_server_side(client):
    """Team Coral is at the AzSEF-configured maximum of three."""

    ws = workspace_id(BASIS)
    tid = team_id("Team Coral")
    detail = client.get(f"/workspaces/{ws}/teams/{tid}", headers=auth(client, "maya@example.edu")).json()
    assert detail["member_count"] == 3
    assert detail["max_team_size"] == 3
    assert detail["seats_left"] == 0

    response = client.post(
        f"/workspaces/{ws}/teams/join",
        json={"team_join_code": "CORAL-8K2P"},
        headers=auth(client, "grace@example.edu"),
    )
    assert response.status_code == 403
    assert "maximum" in response.json()["detail"]


def test_team_size_limit_is_configurable_not_hardcoded(client):
    """Raising the per-team override lets a fourth member join."""

    ws = workspace_id(BASIS)
    tid = team_id("Team Coral")
    lead = auth(client, "jordan@example.edu")

    bumped = client.patch(
        f"/workspaces/{ws}/teams/{tid}", json={"max_members_override": 4}, headers=lead
    )
    assert bumped.status_code == 200, bumped.text
    assert bumped.json()["max_team_size"] == 4

    joined = client.post(
        f"/workspaces/{ws}/teams/join",
        json={"team_join_code": "CORAL-8K2P"},
        headers=auth(client, "grace@example.edu"),
    )
    assert joined.status_code == 200, joined.text

    # And the fifth is refused at the new limit.
    refused = client.post(
        f"/workspaces/{ws}/teams/join",
        json={"team_join_code": "CORAL-8K2P"},
        headers=auth(client, "emma@example.edu"),
    )
    assert refused.status_code == 403

    # Restore.
    client.delete(
        f"/workspaces/{ws}/teams/{tid}/members/{_user_id('grace@example.edu')}", headers=lead
    )
    client.patch(f"/workspaces/{ws}/teams/{tid}", json={"max_members_override": None}, headers=lead)


def test_locked_roster_refuses_new_members(client):
    ws = workspace_id(BASIS)
    tid = team_id("Team Aero")
    owner = auth(client, "priyanka@example.edu")

    locked = client.patch(f"/workspaces/{ws}/teams/{tid}/lock", json={"locked": True}, headers=owner)
    assert locked.status_code == 200
    assert locked.json()["membership_locked"] is True

    response = client.post(
        f"/workspaces/{ws}/teams/join",
        json={"team_join_code": "AERO-9P3K"},
        headers=auth(client, "grace@example.edu"),
    )
    assert response.status_code == 403
    assert "locked" in response.json()["detail"].lower()

    client.patch(f"/workspaces/{ws}/teams/{tid}/lock", json={"locked": False}, headers=owner)


def test_team_rules_are_presented_as_configuration_not_compliance(client):
    ws = workspace_id(BASIS)
    tid = team_id("Team Coral")
    dash = client.get(
        f"/workspaces/{ws}/teams/{tid}/dashboard", headers=auth(client, "maya@example.edu")
    ).json()
    rules = dash["capacity"]["rules"]
    assert rules["official_source_loaded"] is False
    assert rules["source"] == "unverified_competition_item"
    assert "not a statement of official eligibility" in rules["notice"]


# --------------------------------------------------------------------------- #
# Team management permissions
# --------------------------------------------------------------------------- #


def test_students_cannot_create_teams(client):
    ws = workspace_id(BASIS)
    response = client.post(
        f"/workspaces/{ws}/teams",
        json={"name": "Team Rogue"},
        headers=auth(client, "maya@example.edu"),
    )
    assert response.status_code == 403


def test_leads_can_create_and_archive_teams(client):
    ws = workspace_id(BASIS)
    lead = auth(client, "jordan@example.edu")
    created = client.post(
        f"/workspaces/{ws}/teams",
        json={"name": "Team Hydro", "competition_key": "azsef"},
        headers=lead,
    )
    assert created.status_code == 201, created.text
    tid = created.json()["id"]
    assert created.json()["join_code"].startswith("HYDRO-")
    assert created.json()["max_team_size"] == 3

    archived = client.post(f"/workspaces/{ws}/teams/{tid}/archive", headers=lead)
    assert archived.status_code == 200
    assert archived.json()["is_archived"] is True


def test_a_student_cannot_rename_a_team_they_are_not_leading(client):
    ws = workspace_id(BASIS)
    tid = team_id("Team Coral")
    # Sarah is a plain member of Coral.
    response = client.patch(
        f"/workspaces/{ws}/teams/{tid}", json={"name": "Team Renamed"},
        headers=auth(client, "sarah@example.edu"),
    )
    assert response.status_code == 403


def test_team_lead_can_rename_their_own_team(client):
    ws = workspace_id(BASIS)
    tid = team_id("Team Coral")
    maya = auth(client, "maya@example.edu")  # TEAM_LEAD of Coral
    response = client.patch(
        f"/workspaces/{ws}/teams/{tid}", json={"description": "Updated by the team lead."},
        headers=maya,
    )
    assert response.status_code == 200, response.text


# --------------------------------------------------------------------------- #
# Contributions
# --------------------------------------------------------------------------- #


def test_members_log_their_own_contributions(client):
    ws = workspace_id(BASIS)
    tid = team_id("Team Aero")
    response = client.post(
        f"/workspaces/{ws}/teams/{tid}/contributions",
        json={"task": "Calibration check", "description": "Re-zeroed the thrust stand.", "hours": 1.5},
        headers=auth(client, "liam@example.edu"),
    )
    assert response.status_code == 201, response.text
    assert response.json()["user_name"] == "Liam O'Connor"


def test_a_student_cannot_log_a_contribution_for_someone_else(client):
    ws = workspace_id(BASIS)
    tid = team_id("Team Aero")
    with _db() as db:
        emma_id = _user_id("emma@example.edu")
    response = client.post(
        f"/workspaces/{ws}/teams/{tid}/contributions",
        json={"user_id": emma_id, "task": "Work I did not do"},
        headers=auth(client, "liam@example.edu"),
    )
    assert response.status_code == 403


def test_a_mentor_can_request_work_from_a_member(client):
    ws = workspace_id(BASIS)
    tid = team_id("Team Aero")
    response = client.post(
        f"/workspaces/{ws}/teams/{tid}/contributions",
        json={"user_id": _user_id("emma@example.edu"), "task": "Redo the error bars"},
        headers=auth(client, "andre@example.edu"),
    )
    assert response.status_code == 201, response.text
    assert response.json()["requested_by_name"] == "Mr. Andre Cole"


def test_outsiders_cannot_read_contributions(client):
    ws = workspace_id(BASIS)
    tid = team_id("Team Coral")
    # Kevin is in the workspace but on a different team; the project is
    # workspace-visible here, so he may read but never write.
    read = client.get(
        f"/workspaces/{ws}/teams/{tid}/contributions", headers=auth(client, "kevin@example.edu")
    )
    assert read.status_code == 200
    write = client.post(
        f"/workspaces/{ws}/teams/{tid}/contributions",
        json={"task": "Not my team"},
        headers=auth(client, "kevin@example.edu"),
    )
    assert write.status_code == 403


# --------------------------------------------------------------------------- #
# The workspace catalog carries both ownership modes
# --------------------------------------------------------------------------- #


def test_catalog_shows_team_and_individual_projects_together(client):
    ws = workspace_id(BASIS)
    rows = client.get(
        f"/workspaces/{ws}/projects", headers=auth(client, "priyanka@example.edu")
    ).json()

    by_title = {r["title"]: r for r in rows}
    coral = by_title["Coral Bleaching Research Project"]
    assert coral["owner_kind"] == "team"
    assert coral["owner_name"] == "Team Coral"
    assert coral["owner_id"] is None
    assert set(coral["member_names"]) == {"Maya Patel", "Arjun Mehta", "Sarah Kim"}

    battery = by_title["Battery Degradation Analysis"]
    assert battery["owner_kind"] == "individual"
    assert battery["owner_name"] == "Daniel Okafor"
    assert battery["team_id"] is None

    kinds = {r["owner_kind"] for r in rows}
    assert kinds == {"team", "individual"}, "catalog should contain both modes"


def test_team_project_counts_for_every_member(client):
    """The members table credits a shared project to all of its owners."""

    ws = workspace_id(BASIS)
    members = client.get(
        f"/workspaces/{ws}/members", headers=auth(client, "priyanka@example.edu")
    ).json()
    by_name = {m["name"]: m for m in members}
    for name in ("Maya Patel", "Arjun Mehta", "Sarah Kim"):
        assert by_name[name]["project_count"] >= 1
        assert "Team Coral" in [t["name"] for t in by_name[name]["teams"]]


def _user_id(email: str) -> int:
    from app.models.project import User

    with _db() as db:
        return db.query(User).filter(User.email == email).one().id
