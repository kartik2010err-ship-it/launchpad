"""Outreach personalisation, tone and quality scoring (sections 33-43).

The product claim being tested is narrow but important: this tool should make
it *harder* to send a generic email, not easier to send forty. Every test below
is a version of that.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed import run as seed_run
from app.services import outreach_service


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


GOOD_WORK = "your 2024 paper on early bleaching indices in Acropora, especially figure 3"
GOOD_ASK = "whether 5 tanks per condition is defensible for this measurement"


def draft(client, headers, **overrides):
    payload = {
        "template_key": "methodology_feedback",
        "research_topic": "coral bleaching prediction",
        "research_question": "Can autoencoder features predict bleaching before it is visible?",
        "researcher_name": "Dr. Rivera",
        "their_work": GOOD_WORK,
        "specific_request": GOOD_ASK,
        "school": "BASIS Phoenix",
        "grade_level": 11,
    }
    payload.update(overrides)
    return client.post("/outreach/draft", json=payload, headers=headers)


# --------------------------------------------------------------------------- #
# Section 36 — "why this person?"
# --------------------------------------------------------------------------- #


def test_a_generic_reason_is_called_out(client: TestClient) -> None:
    response = client.post(
        "/outreach/personalisation-check",
        json={"their_work": "They study biology"},
        headers=auth(client, "maya@example.edu"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_specific"] is False
    assert "too generic" in body["message"].lower() or "not yet an answer" in body["message"].lower()


def test_a_specific_reason_passes(client: TestClient) -> None:
    body = client.post(
        "/outreach/personalisation-check",
        json={"their_work": GOOD_WORK},
        headers=auth(client, "maya@example.edu"),
    ).json()
    assert body["is_specific"] is True


def test_the_builder_still_refuses_a_generic_draft(client: TestClient) -> None:
    response = draft(client, auth(client, "maya@example.edu"), their_work="they do biology")
    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# Section 41 — tone variants
# --------------------------------------------------------------------------- #


def test_three_tones_produce_three_different_emails(client: TestClient) -> None:
    headers = auth(client, "maya@example.edu")
    bodies = {}
    for tone in ("concise", "standard", "warmer"):
        response = draft(client, headers, tone=tone)
        assert response.status_code == 200, response.text
        bodies[tone] = response.json()["body"]

    assert len({*bodies.values()}) == 3
    assert len(bodies["concise"].split()) < len(bodies["warmer"].split())


def test_an_unknown_tone_falls_back_to_standard(client: TestClient) -> None:
    response = draft(client, auth(client, "maya@example.edu"), tone="shouty")
    assert response.status_code == 200
    assert response.json()["tone"] == "standard"


def test_warmer_is_not_flattery(client: TestClient) -> None:
    """Section 41 explicitly: warmer must not become sycophantic."""

    body = draft(client, auth(client, "maya@example.edu"), tone="warmer").json()["body"].lower()
    for word in ("world-renowned", "brilliant", "genius", "biggest fan", "honoured to even"):
        assert word not in body


# --------------------------------------------------------------------------- #
# Section 33 — how the email opens
# --------------------------------------------------------------------------- #


def test_no_draft_opens_with_i_hope_this_email_finds_you_well(client: TestClient) -> None:
    headers = auth(client, "maya@example.edu")
    for key in ("research_guidance", "methodology_feedback", "lab_experience", "grad_student"):
        body = draft(client, headers, template_key=key).json()["body"].lower()
        assert "hope this email finds you well" not in body
        assert "to whom it may concern" not in body


def test_a_draft_starts_by_saying_who_the_student_is(client: TestClient) -> None:
    body = draft(client, auth(client, "maya@example.edu")).json()["body"]
    first_paragraph = body.split("\n\n")[1]
    assert first_paragraph.startswith("My name is")


def test_drafts_land_in_a_sendable_length(client: TestClient) -> None:
    """Section 33's target is roughly 100-180 words."""

    body = draft(client, auth(client, "maya@example.edu"), tone="standard").json()
    assert body["word_count"] < 230, "long enough to be skimmed and deleted"


# --------------------------------------------------------------------------- #
# Section 37 — quality score
# --------------------------------------------------------------------------- #


def test_a_good_draft_scores_well_and_says_why(client: TestClient) -> None:
    quality = draft(client, auth(client, "maya@example.edu")).json()["quality"]
    assert quality["score"] >= 70
    assert quality["strengths"]
    assert quality["verdict"]


def test_scoring_penalises_a_template_opening(client: TestClient) -> None:
    response = client.post(
        "/outreach/score",
        json={
            "subject": "Research question",
            "body": (
                "Dear Professor,\n\nI hope this email finds you well. I am a student "
                "interested in your research. I would love any advice you have.\n\nThanks"
            ),
            "their_work": "they study biology",
            "specific_request": "advice",
        },
        headers=auth(client, "maya@example.edu"),
    )
    assert response.status_code == 200
    quality = response.json()
    assert quality["score"] < 50
    joined = " ".join(quality["improvements"]).lower()
    assert "hope this email finds you well" in joined


def test_scoring_penalises_flattery(client: TestClient) -> None:
    quality = client.post(
        "/outreach/score",
        json={
            "subject": "A question about your work on reef imaging",
            "body": (
                "Dear Dr Rivera, My name is Maya Patel, a grade 11 student. Your "
                "world-renowned and frankly brilliant research inspired me. " + ("word " * 110)
            ),
            "their_work": GOOD_WORK,
            "specific_request": GOOD_ASK,
        },
        headers=auth(client, "maya@example.edu"),
    ).json()
    assert any("flattery" in item.lower() for item in quality["improvements"])


def test_scoring_rewards_a_small_specific_ask() -> None:
    small = outreach_service.score_draft(
        body="x " * 130,
        subject="A question about your reef imaging work",
        their_work=GOOD_WORK,
        specific_request="whether 15 minutes in the next few weeks would be possible",
    )
    vague = outreach_service.score_draft(
        body="x " * 130,
        subject="A question about your reef imaging work",
        their_work=GOOD_WORK,
        specific_request="advice",
    )
    assert small["score"] > vague["score"]


def test_scoring_flags_an_overlong_email() -> None:
    quality = outreach_service.score_draft(
        body="word " * 400,
        subject="A specific and reasonable subject line",
        their_work=GOOD_WORK,
        specific_request=GOOD_ASK,
    )
    assert any("too long" in item.lower() for item in quality["improvements"])


# --------------------------------------------------------------------------- #
# Section 43 — project prefill
# --------------------------------------------------------------------------- #


def test_prefill_uses_what_the_app_already_knows(client: TestClient) -> None:
    from app.db.session import SessionLocal
    from app.models.project import Project
    from app.models.team import Team

    with SessionLocal() as db:
        team = db.query(Team).filter(Team.name == "Team Coral").one()
        project = db.query(Project).filter(Project.owner_team_id == team.id).one()
        pid, question = project.id, project.current_question

    response = client.get(f"/outreach/prefill/{pid}", headers=auth(client, "maya@example.edu"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["research_question"] == question
    assert body["research_topic"]
    assert body["student_name"] == "Maya Patel"


def test_prefill_refuses_someone_elses_project(client: TestClient) -> None:
    from app.db.session import SessionLocal
    from app.models.project import Project
    from app.models.team import Team

    with SessionLocal() as db:
        team = db.query(Team).filter(Team.name == "Team Coral").one()
        pid = db.query(Project).filter(Project.owner_team_id == team.id).one().id

    response = client.get(f"/outreach/prefill/{pid}", headers=auth(client, "riley@example.edu"))
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Section 38 — anti-spam posture
# --------------------------------------------------------------------------- #


def test_the_app_argues_against_mass_email(client: TestClient) -> None:
    body = client.get("/outreach/templates", headers=auth(client, "maya@example.edu")).json()
    warning = body["spam_warning"].lower()
    assert "one at a time" in warning or "generic" in warning


def test_every_template_names_what_must_be_personalised(client: TestClient) -> None:
    body = client.get("/outreach/templates", headers=auth(client, "maya@example.edu")).json()
    for template in body["templates"]:
        assert template["required_personalisation"], template["key"]
