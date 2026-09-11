"""Research Assistant tests (sections 11-15, 37, 38).

The claim that matters most here is the privacy one. Everywhere else in this
app a workspace OWNER can see any project, and that is correct — it is
oversight. A conversation with the assistant is not part of the project, it is
a student thinking, and the oversight path must NOT reach it. Several tests
below exist purely to prove that the shortcut was not added by accident.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.content import guides
from app.db.session import SessionLocal
from app.main import app
from app.models.project import Project
from app.models.team import Team
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


def coral_project_id() -> int:
    with SessionLocal() as db:
        team = db.query(Team).filter(Team.name == "Team Coral").one()
        return db.query(Project).filter(Project.owner_team_id == team.id).one().id


def start(client: TestClient, headers: dict, project_id: int | None = None) -> int:
    response = client.post(
        "/assistant/conversations", json={"project_id": project_id}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def say(client: TestClient, headers: dict, conversation_id: int, text: str) -> dict:
    response = client.post(
        f"/assistant/conversations/{conversation_id}/messages",
        json={"content": text},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------- #
# Privacy (section 37, section 38)
# --------------------------------------------------------------------------- #


def test_a_students_conversation_is_private_from_their_own_teammate(client: TestClient) -> None:
    """Maya and Arjun share one project row. They do not share a train of thought."""

    maya = auth(client, "maya@example.edu")
    conversation_id = start(client, maya, coral_project_id())
    say(client, maya, conversation_id, "What should I do next?")

    arjun = auth(client, "arjun@example.edu")
    assert client.get(f"/assistant/conversations/{conversation_id}", headers=arjun).status_code == 404


def test_workspace_owner_oversight_does_not_reach_conversations(client: TestClient) -> None:
    """The load-bearing test. Priyanka owns the BASIS workspace and can open every
    project in it — and still cannot read what a student asked the assistant."""

    maya = auth(client, "maya@example.edu")
    project_id = coral_project_id()
    conversation_id = start(client, maya, project_id)
    say(client, maya, conversation_id, "I don't understand controls.")

    owner = auth(client, "priyanka@example.edu")
    # Oversight over the project itself is intact...
    assert client.get(f"/projects/{project_id}", headers=owner).status_code == 200
    # ...and stops at the conversation.
    assert client.get(f"/assistant/conversations/{conversation_id}", headers=owner).status_code == 404


def test_workspace_lead_cannot_read_conversations_either(client: TestClient) -> None:
    maya = auth(client, "maya@example.edu")
    conversation_id = start(client, maya, coral_project_id())
    lead = auth(client, "jordan@example.edu")
    assert client.get(f"/assistant/conversations/{conversation_id}", headers=lead).status_code == 404


def test_listing_never_returns_another_students_conversations(client: TestClient) -> None:
    maya = auth(client, "maya@example.edu")
    project_id = coral_project_id()
    mine = start(client, maya, project_id)

    arjun = auth(client, "arjun@example.edu")
    theirs = client.get(
        "/assistant/conversations", params={"project_id": project_id}, headers=arjun
    )
    assert theirs.status_code == 200
    assert mine not in [row["id"] for row in theirs.json()]


def test_sharing_opens_a_conversation_to_the_team_but_not_the_workspace(
    client: TestClient,
) -> None:
    maya = auth(client, "maya@example.edu")
    conversation_id = start(client, maya, coral_project_id())
    say(client, maya, conversation_id, "What would a judge ask me about this?")

    shared = client.patch(
        f"/assistant/conversations/{conversation_id}/share",
        json={"shared_with_team": True},
        headers=maya,
    )
    assert shared.status_code == 200
    assert shared.json()["shared_with_team"] is True

    # Teammate on the same team: allowed.
    arjun = auth(client, "arjun@example.edu")
    assert client.get(f"/assistant/conversations/{conversation_id}", headers=arjun).status_code == 200

    # A student on a different team in the same workspace: still not allowed.
    kevin = auth(client, "kevin@example.edu")
    assert client.get(f"/assistant/conversations/{conversation_id}", headers=kevin).status_code == 404

    # And the workspace owner still gets nothing.
    owner = auth(client, "priyanka@example.edu")
    assert client.get(f"/assistant/conversations/{conversation_id}", headers=owner).status_code == 404


def test_a_shared_conversation_is_still_read_only_for_teammates(client: TestClient) -> None:
    maya = auth(client, "maya@example.edu")
    conversation_id = start(client, maya, coral_project_id())
    say(client, maya, conversation_id, "Why do I need a control?")
    client.patch(
        f"/assistant/conversations/{conversation_id}/share",
        json={"shared_with_team": True},
        headers=maya,
    )

    arjun = auth(client, "arjun@example.edu")
    response = client.post(
        f"/assistant/conversations/{conversation_id}/messages",
        json={"content": "adding my own question"},
        headers=arjun,
    )
    assert response.status_code == 403


def test_a_conversation_with_no_project_cannot_be_shared(client: TestClient) -> None:
    maya = auth(client, "maya@example.edu")
    conversation_id = start(client, maya, None)
    response = client.patch(
        f"/assistant/conversations/{conversation_id}/share",
        json={"shared_with_team": True},
        headers=maya,
    )
    assert response.status_code == 400


def test_outsider_cannot_open_a_conversation_on_a_project_they_cannot_see(
    client: TestClient,
) -> None:
    riley = auth(client, "riley@example.edu")  # a different school entirely
    response = client.post(
        "/assistant/conversations", json={"project_id": coral_project_id()}, headers=riley
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Project awareness (section 11)
# --------------------------------------------------------------------------- #


def test_context_endpoint_reports_what_the_assistant_was_given(client: TestClient) -> None:
    maya = auth(client, "maya@example.edu")
    response = client.get(f"/assistant/projects/{coral_project_id()}/context", headers=maya)
    assert response.status_code == 200
    body = response.json()

    assert body["question"]
    assert body["stage"]
    assert body["total_questions"] > 0
    # Known and missing must partition the interview, never overlap.
    assert not set(body["known_fields"]) & set(body["missing_fields"])


def test_the_student_never_has_to_restate_the_project(client: TestClient) -> None:
    """Section 11: opened inside a project, the reply is grounded in that project."""

    maya = auth(client, "maya@example.edu")
    conversation_id = start(client, maya, coral_project_id())
    reply = say(client, maya, conversation_id, "Explain my methodology back to me.")
    # The question on record has to appear — it can only have come from context.
    with SessionLocal() as db:
        question = db.get(Project, coral_project_id()).current_question
    assert question[:40] in reply["content"]


def test_next_step_gives_one_primary_recommendation(client: TestClient) -> None:
    """Section 35: one thing to do, not a task dump."""

    maya = auth(client, "maya@example.edu")
    conversation_id = start(client, maya, coral_project_id())
    reply = say(client, maya, conversation_id, "What should I do next?")
    assert "Do this first" in reply["content"]
    assert reply["content"].count("Do this first") == 1


# --------------------------------------------------------------------------- #
# Teaching, not doing (section 14)
# --------------------------------------------------------------------------- #


def test_it_refuses_to_write_the_students_hypothesis(client: TestClient) -> None:
    maya = auth(client, "maya@example.edu")
    conversation_id = start(client, maya, coral_project_id())
    reply = say(client, maya, conversation_id, "write my hypothesis for me")

    body = reply["content"].lower()
    assert "not going to write it for you" in body
    # It redirects into a question rather than stonewalling.
    assert reply["follow_ups"]


def test_it_refuses_to_write_the_research_question(client: TestClient) -> None:
    maya = auth(client, "maya@example.edu")
    conversation_id = start(client, maya, coral_project_id())
    reply = say(client, maya, conversation_id, "can you write my research question")
    assert "has to be yours" in reply["content"].lower()


# --------------------------------------------------------------------------- #
# Library integration (section 15, 17)
# --------------------------------------------------------------------------- #


def test_a_concept_question_recommends_a_real_guide(client: TestClient) -> None:
    maya = auth(client, "maya@example.edu")
    conversation_id = start(client, maya, coral_project_id())
    reply = say(client, maya, conversation_id, "I don't understand controls.")

    assert reply["guides"], "a controls question should surface a guide"
    ids = [g["guide_id"] for g in reply["guides"]]
    assert "choosing-a-control-group" in ids
    # Every recommendation resolves to a guide that actually exists.
    for guide_id in ids:
        assert guides.get(guide_id) is not None


def test_recommendations_are_ids_not_urls(client: TestClient) -> None:
    """Section 15: no hard-coded links anywhere in a reply."""

    maya = auth(client, "maya@example.edu")
    conversation_id = start(client, maya, coral_project_id())
    for question in ("What graph should I use?", "What statistical test should I use?"):
        reply = say(client, maya, conversation_id, question)
        assert "http://" not in reply["content"]
        assert "https://" not in reply["content"]


def test_statistics_question_routes_to_the_statistics_guides(client: TestClient) -> None:
    maya = auth(client, "maya@example.edu")
    conversation_id = start(client, maya, coral_project_id())
    reply = say(client, maya, conversation_id, "what does statistical significance mean?")
    ids = [g["guide_id"] for g in reply["guides"]]
    assert "statistical-significance" in ids


# --------------------------------------------------------------------------- #
# Transcript integrity
# --------------------------------------------------------------------------- #


def test_the_transcript_keeps_both_sides_in_order(client: TestClient) -> None:
    maya = auth(client, "maya@example.edu")
    conversation_id = start(client, maya, coral_project_id())
    say(client, maya, conversation_id, "Why do I need a control?")
    say(client, maya, conversation_id, "What about confounding variables?")

    detail = client.get(f"/assistant/conversations/{conversation_id}", headers=maya).json()
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant", "user", "assistant"]


def test_first_message_titles_the_conversation(client: TestClient) -> None:
    maya = auth(client, "maya@example.edu")
    conversation_id = start(client, maya, coral_project_id())
    say(client, maya, conversation_id, "Why do I need a control group in my reef study?")
    detail = client.get(f"/assistant/conversations/{conversation_id}", headers=maya).json()
    assert detail["title"] != "New conversation"


def test_suggested_actions_are_offered(client: TestClient) -> None:
    maya = auth(client, "maya@example.edu")
    response = client.get("/assistant/suggested-actions", headers=maya)
    assert response.status_code == 200
    keys = {row["key"] for row in response.json()}
    assert {"next_step", "find_weaknesses", "judge_questions"} <= keys


def test_deleting_a_conversation_removes_its_messages(client: TestClient) -> None:
    maya = auth(client, "maya@example.edu")
    conversation_id = start(client, maya, coral_project_id())
    say(client, maya, conversation_id, "Why do I need a control?")
    assert client.delete(f"/assistant/conversations/{conversation_id}", headers=maya).status_code == 204
    assert client.get(f"/assistant/conversations/{conversation_id}", headers=maya).status_code == 404
