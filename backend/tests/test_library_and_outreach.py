"""Research Library, Winning Projects and Research Outreach.

The tests that matter most here are the honesty ones: the winners library must
never present unsourced content as fact, must never explain judges' reasoning,
and must refuse to ingest a record that cannot be checked.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.content import guides
from app.db.session import SessionLocal
from app.main import app
from app.models.library import WinningProject
from app.seed import run as seed_run
from app.services import guide_recommender, outreach_service, winners_service


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


# --------------------------------------------------------------------------- #
# Research Library
# --------------------------------------------------------------------------- #


def test_every_category_has_guides(client):
    response = client.get("/library/categories", headers=auth(client, "maya@example.edu"))
    assert response.status_code == 200
    for row in response.json():
        assert row["guide_count"] > 0, f"{row['key']} has no guides"


def test_guides_are_searchable(client):
    headers = auth(client, "maya@example.edu")
    hits = client.get("/library/guides?q=hypothesis", headers=headers).json()
    assert any(g["id"] == "writing-a-hypothesis" for g in hits)

    stats = client.get("/library/guides?category=statistics", headers=headers).json()
    assert stats and all(g["category"] == "statistics" for g in stats)


def test_guide_detail_includes_weak_and_strong_examples(client):
    response = client.get(
        "/library/guides/measurable-variables", headers=auth(client, "maya@example.edu")
    )
    assert response.status_code == 200
    body = response.json()
    assert body["sections"]
    comparison = body["comparisons"][0]
    # A comparison without a "why" would just be something to copy.
    assert comparison["weak"] and comparison["strong"] and len(comparison["why"]) > 40


def test_all_related_and_recommended_guide_ids_resolve():
    """Recommendations are by id, so a dangling id is a broken link."""

    for guide in guides.ALL_GUIDES:
        for related in guide.related:
            assert guides.get(related) is not None, f"{guide.id} -> missing {related}"

    referenced = set()
    for ids in guide_recommender.CRITERION_GUIDES.values():
        referenced.update(ids)
    for ids in guide_recommender.RUBRIC_GUIDES.values():
        referenced.update(ids)
    for ids in guide_recommender.STAGE_GUIDES.values():
        referenced.update(ids)
    for guide_id in referenced:
        assert guides.get(guide_id) is not None, f"recommender points at missing {guide_id}"


def test_recommendations_come_from_the_projects_weak_criteria(client):
    """A weak project should be pointed at the guide for what it is weak at."""

    from app.models.project import Project

    with SessionLocal() as db:
        pid = db.query(Project).filter(Project.title == "Music and studying").one().id

    headers = auth(client, "ava@example.edu")
    client.post(f"/projects/{pid}/evaluate", headers=headers)
    response = client.get(f"/projects/{pid}/recommended-guides", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["evaluated"] is True
    ids = [g["guide_id"] for g in body["guides"]]
    assert ids, "an unfinished project should produce reading recommendations"
    # "Does music affect concentration?" scores badly on question specificity and
    # has no control defined, so those are the guides it must be pointed at.
    assert "idea-to-research-question" in ids
    assert "choosing-a-control-group" in ids
    # Each recommendation names the criterion and score that produced it.
    assert all(g["reason"] and "/100" in g["reason"] for g in body["guides"])

    # Recommendations spread across dimensions rather than piling onto one.
    dimensions_covered = {g["reason"].split(":")[0] for g in body["guides"]}
    assert len(dimensions_covered) >= 3


def test_recommendations_are_stable_ids_not_free_text():
    dimensions = [
        {
            "key": "methodology",
            "label": "Methodology",
            "criteria": {"controls": 20, "sample_size": 25, "reproducibility": 95},
        }
    ]
    out = guide_recommender.for_evaluation(dimensions)
    ids = [g["guide_id"] for g in out]
    assert "choosing-a-control-group" in ids
    assert "sample-size" in ids
    # A criterion that scored well must not generate a recommendation.
    assert "research-notebook" not in ids[:2]


# --------------------------------------------------------------------------- #
# Winning Projects: provenance and honesty
# --------------------------------------------------------------------------- #


def test_no_fabricated_winners_are_shipped(client):
    """The app ships zero real past projects, and says so."""

    response = client.get("/winning-projects", headers=auth(client, "maya@example.edu"))
    assert response.status_code == 200
    body = response.json()
    assert body["filters"]["verified_total"] == 0
    assert body["empty_notice"] is not None
    for project in body["projects"]:
        assert project["is_illustrative"] is True
        assert project["award_title"] is None, "a teaching example must not claim an award"
        assert project["notice"] and "not a real project" in project["notice"]


def test_breakdown_separates_source_facts_from_ai_analysis(client):
    headers = auth(client, "maya@example.edu")
    listing = client.get("/winning-projects", headers=headers).json()
    winner_id = listing["projects"][0]["id"]

    body = client.get(f"/winning-projects/{winner_id}", headers=headers).json()
    assert body["lessons_provenance"] == "ai_analysis"
    assert "not statements from the competition" in body["analysis_notice"]
    for field in body["facts"].values():
        assert field["provenance"] in {
            "verified_source",
            "unverified",
            "ai_analysis",
            "not_available",
        }
    # Fields the record does not carry are marked missing, not filled in.
    assert body["facts"]["award_title"]["provenance"] == "not_available"
    assert body["facts"]["award_title"]["value"] is None


def test_judging_reasoning_is_never_invented(client):
    headers = auth(client, "maya@example.edu")
    listing = client.get("/winning-projects", headers=headers).json()
    for project in listing["projects"]:
        body = client.get(f"/winning-projects/{project['id']}", headers=headers).json()
        judging = body["judging"]
        assert judging["commentary"] is None
        assert judging["provenance"] == "not_available"
        assert "cannot tell you why" in judging["notice"]


def test_ingest_refuses_a_real_project_without_a_source_url():
    with SessionLocal() as db:
        with pytest.raises(winners_service.IngestError, match="source_url"):
            winners_service.ingest(
                db,
                [
                    {
                        "external_id": "x1",
                        "title": "Unverifiable project",
                        "category": "physics",
                        "source_key": "hearsay",
                        "source_name": "Someone said so",
                    }
                ],
            )
        db.rollback()


def test_ingest_refuses_judging_commentary_that_was_not_published():
    with SessionLocal() as db:
        with pytest.raises(winners_service.IngestError, match="judging_commentary_published"):
            winners_service.ingest(
                db,
                [
                    {
                        "external_id": "x2",
                        "title": "A project",
                        "category": "physics",
                        "source_key": "somewhere",
                        "source_name": "A source",
                        "source_url": "https://example.org/x2",
                        "judging_commentary": "The judges loved the methodology.",
                    }
                ],
            )
        db.rollback()


def test_ingest_accepts_a_properly_sourced_record_and_is_idempotent():
    record = {
        "external_id": "ok-1",
        "title": "A properly sourced project",
        "category": "physics",
        "source_key": "test_source",
        "source_name": "Test archive",
        "source_url": "https://example.org/ok-1",
        "abstract": "An abstract that came from the archive.",
        "methodology": "A method that came from the archive.",
    }
    with SessionLocal() as db:
        first = winners_service.ingest(db, [record])
        second = winners_service.ingest(db, [record])
        assert first["added"] == 1
        assert second["updated"] == 1 and second["added"] == 0

        row = (
            db.query(WinningProject)
            .filter(WinningProject.external_id == "ok-1")
            .one()
        )
        assert row.field_provenance["abstract"] == "verified_source"
        assert row.field_provenance["results_summary"] == "not_available"
        db.delete(row)
        db.commit()


def test_similar_projects_carry_the_do_not_copy_warning(client):
    from app.models.project import Project

    with SessionLocal() as db:
        pid = (
            db.query(Project)
            .filter(Project.title == "Coral Bleaching Research Project")
            .one()
            .id
        )
    response = client.get(
        f"/projects/{pid}/similar-winning-projects", headers=auth(client, "maya@example.edu")
    )
    assert response.status_code == 200
    assert "not to replicate another student's work" in response.json()["warning"]


# --------------------------------------------------------------------------- #
# Research Outreach
# --------------------------------------------------------------------------- #


def test_all_six_templates_are_offered(client):
    response = client.get("/outreach/templates", headers=auth(client, "maya@example.edu"))
    assert response.status_code == 200
    body = response.json()
    keys = {t["key"] for t in body["templates"]}
    assert keys == {
        "research_guidance",
        "mentorship",
        "paper_question",
        "equipment_access",
        "short_meeting",
        "follow_up",
    }
    assert body["spam_warning"]
    for template in body["templates"]:
        sections = [s["section"] for s in template["structure"]]
        assert sections == [
            "Introduction",
            "Connection",
            "Project",
            "Specific request",
            "Closing",
        ]


def test_draft_builder_refuses_a_generic_email(client):
    headers = auth(client, "maya@example.edu")
    response = client.post(
        "/outreach/draft",
        json={
            "template_key": "research_guidance",
            "researcher_name": "Dr. Example",
            "their_work": "your work",
            "specific_request": "any advice you have",
            "research_topic": "coral bleaching",
        },
        headers=headers,
    )
    assert response.status_code == 422
    assert "mass email" in response.json()["detail"]


def test_draft_builder_produces_a_structured_email(client):
    response = client.post(
        "/outreach/draft",
        json={
            "template_key": "paper_question",
            "researcher_name": "Dr. Elena Marsh",
            "their_work": "your 2023 paper on thermal stress indices, particularly the finding "
            "that visible bleaching lags measurable stress",
            "specific_request": "I wondered whether that lag also held at the lowest stress level "
            "in Figure 3",
            "research_topic": "early bleaching detection",
            "research_question": "Can autoencoder features predict stress before visible bleaching?",
        },
        headers=auth(client, "maya@example.edu"),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert [s["section"] for s in body["sections"]] == [
        "Subject",
        "Introduction",
        "Connection",
        "Project",
        "Specific request",
        "Closing",
    ]
    assert "Maya Patel" in body["body"]
    assert "Dear Dr. Elena Marsh," in body["body"]
    assert body["word_count"] < 220, "a cold email this long will not be read"
    assert body["spam_warning"]


def test_outreach_records_are_private_to_the_student(client):
    maya = auth(client, "maya@example.edu")
    arjun = auth(client, "arjun@example.edu")

    created = client.post(
        "/outreach/contacts",
        json={"researcher_name": "Dr. Private", "institution": "Somewhere"},
        headers=maya,
    )
    assert created.status_code == 201
    contact_id = created.json()["id"]

    # A teammate on the same shared project still cannot see or touch it.
    assert contact_id not in [c["id"] for c in client.get("/outreach/contacts", headers=arjun).json()]
    assert client.patch(
        f"/outreach/contacts/{contact_id}", json={"notes": "nope"}, headers=arjun
    ).status_code == 404
    assert client.delete(f"/outreach/contacts/{contact_id}", headers=arjun).status_code == 404

    assert client.delete(f"/outreach/contacts/{contact_id}", headers=maya).status_code == 204


def test_marking_sent_schedules_a_single_follow_up(client):
    headers = auth(client, "sarah@example.edu")
    created = client.post(
        "/outreach/contacts", json={"researcher_name": "Dr. Followup"}, headers=headers
    ).json()
    updated = client.patch(
        f"/outreach/contacts/{created['id']}", json={"status": "sent"}, headers=headers
    ).json()
    assert updated["sent_on"] is not None
    assert updated["follow_up_on"] is not None

    from datetime import date

    sent = date.fromisoformat(updated["sent_on"])
    due = date.fromisoformat(updated["follow_up_on"])
    assert (due - sent).days == 10
    client.delete(f"/outreach/contacts/{created['id']}", headers=headers)


def test_outreach_summary_surfaces_due_follow_ups(client):
    response = client.get("/outreach/summary", headers=auth(client, "maya@example.edu"))
    assert response.status_code == 200
    body = response.json()
    # The seed has Maya's message sent 12 days ago with a follow-up date passed.
    assert any(row["researcher_name"] == "Dr. Elena Marsh" for row in body["follow_ups_due"])
    assert {row["status"] for row in body["by_status"]} == {
        "draft",
        "sent",
        "replied",
        "meeting_scheduled",
        "no_response",
        "declined",
    }


def test_follow_up_timing_is_ten_days():
    from datetime import date

    assert outreach_service.suggested_follow_up(date(2026, 3, 1)) == date(2026, 3, 11)
    assert outreach_service.suggested_follow_up(None) is None
