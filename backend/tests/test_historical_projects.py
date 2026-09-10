"""ISEF / historical project catalogue (sections 19-30, 38-40).

The rules being proved here are mostly about honesty:

* A field the source did not publish stays NULL. Nothing is invented.
* Re-importing the same data updates rather than duplicates.
* AI analysis is stored and rendered separately from source information, and is
  refused outright when there is no abstract to read.
* An empty similarity result is never reported as evidence of novelty.
* Ordinary students cannot write to the catalogue.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.historical import HistoricalProject
from app.seed import run as seed_run
from app.services import historical_import


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


CSV = """title,year,category,abstract,awards,team,url
Reef Bleaching Prediction from Hyperspectral Imagery,2024,Environmental Engineering,"We trained a convolutional neural network on hyperspectral reef imagery to predict bleaching onset. Using a control group of unstressed coral, accuracy reached 91% (p < 0.01) across 240 samples.",First Award,true,https://example.org/p/1
Sleep Duration and Working Memory in Adolescents,2023,Behavioral and Social Sciences,"A survey of 120 participants measured recall accuracy against self-reported sleep. Correlation was moderate.",,false,https://example.org/p/2
,2020,,,,,
"""


CURATOR = "priyanka@example.edu"  # workspace owner
STUDENT = "ava@example.edu"


# --------------------------------------------------------------------------- #
# Import
# --------------------------------------------------------------------------- #


def test_csv_import_normalises_and_skips_untitled_rows(client: TestClient) -> None:
    response = client.post(
        "/historical-projects/import/csv",
        json={
            "csv_text": CSV,
            "source": "test-csv",
            "permission_note": "Sample data authored for testing.",
        },
        headers=auth(client, CURATOR),
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["created"] == 2  # the untitled row is not a project
    assert report["errors"] == []


def test_a_field_the_source_omitted_stays_null(client: TestClient) -> None:
    """Section 40. No invented abstracts, awards or student names."""

    with SessionLocal() as db:
        row = (
            db.query(HistoricalProject)
            .filter(HistoricalProject.title.like("Sleep Duration%"))
            .one()
        )
        assert row.awards is None
        assert row.student_display is None
        assert row.school_display is None
        assert row.year == 2023
        assert row.team_project is False


def test_reimporting_the_same_file_updates_rather_than_duplicates(client: TestClient) -> None:
    """Section 21. The importer is safe to run twice."""

    before = client.get("/historical-projects", headers=auth(client, CURATOR)).json()["total"]
    again = client.post(
        "/historical-projects/import/csv",
        json={
            "csv_text": CSV,
            "source": "test-csv",
            "permission_note": "Sample data authored for testing.",
        },
        headers=auth(client, CURATOR),
    )
    assert again.status_code == 200
    assert again.json()["created"] == 0
    assert again.json()["updated"] == 2

    after = client.get("/historical-projects", headers=auth(client, CURATOR)).json()["total"]
    assert after == before


def test_a_later_import_does_not_erase_a_field_it_omits() -> None:
    record = historical_import.NormalisedRecord(
        source="unit", source_project_id="x1", title="A", abstract="full text"
    )
    thinner = historical_import.NormalisedRecord(
        source="unit", source_project_id="x1", title="A", abstract=None
    )
    with SessionLocal() as db:
        historical_import.import_records(db, [record])
        historical_import.import_records(db, [thinner])
        row = (
            db.query(HistoricalProject)
            .filter(HistoricalProject.source == "unit")
            .one()
        )
        assert row.abstract == "full text"


def test_a_csv_without_a_title_column_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/historical-projects/import/csv",
        json={
            "csv_text": "name,year\nsomething,2024\n",
            "source": "bad",
            "permission_note": "test",
        },
        headers=auth(client, CURATOR),
    )
    assert response.status_code == 400
    assert "title" in response.json()["detail"].lower()


def test_a_malformed_row_does_not_lose_the_batch() -> None:
    good = historical_import.NormalisedRecord(
        source="unit2", source_project_id="ok", title="Fine"
    )
    bad = historical_import.NormalisedRecord(
        source="unit2", source_project_id="bad", title="x" * 5000  # exceeds the column
    )
    with SessionLocal() as db:
        report = historical_import.import_records(db, [good, bad])
    assert report.created >= 1


def test_derived_ids_are_deterministic() -> None:
    a = historical_import.derive_id("s", "A Study of Things", 2024)
    b = historical_import.derive_id("s", "A Study of Things", 2024)
    assert a == b


# --------------------------------------------------------------------------- #
# Read-only for students (section 38)
# --------------------------------------------------------------------------- #


def test_the_catalogue_is_read_only_to_an_ordinary_student(client: TestClient) -> None:
    student = auth(client, STUDENT)
    assert client.get("/historical-projects", headers=student).status_code == 200

    blocked = client.post(
        "/historical-projects/import/manual",
        json={"title": "Something I made up", "permission_note": "none"},
        headers=student,
    )
    assert blocked.status_code == 403


def test_import_requires_a_permission_note(client: TestClient) -> None:
    """Storing someone else's material is a decision a person records."""

    response = client.post(
        "/historical-projects/import/manual",
        json={"title": "A project"},
        headers=auth(client, CURATOR),
    )
    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# Browse
# --------------------------------------------------------------------------- #


def test_search_filters_by_keyword_and_award(client: TestClient) -> None:
    headers = auth(client, CURATOR)
    hit = client.get("/historical-projects", params={"q": "reef"}, headers=headers).json()
    assert hit["total"] >= 1
    assert "Reef" in hit["results"][0]["title"]

    awarded = client.get(
        "/historical-projects", params={"awarded": True}, headers=headers
    ).json()
    assert all(row["awards"] for row in awarded["results"])


def test_facets_come_from_the_data_not_a_hardcoded_list(client: TestClient) -> None:
    facets = client.get("/historical-projects/facets", headers=auth(client, CURATOR)).json()
    assert facets["total"] >= 2
    categories = {row["value"] for row in facets["categories"]}
    assert "Environmental Engineering" in categories


def test_derived_tags_are_labelled_separately_from_source_categories(
    client: TestClient,
) -> None:
    """Section 29. A tag we inferred must never read as the fair's category."""

    headers = auth(client, CURATOR)
    listing = client.get("/historical-projects", params={"q": "reef"}, headers=headers).json()
    detail = client.get(
        f"/historical-projects/{listing['results'][0]['id']}", headers=headers
    ).json()

    assert detail["source_information"]["category"] == "Environmental Engineering"
    assert "AI / Machine Learning" in detail["derived_tags"]
    # The inferred tag is not smuggled into the source object.
    assert "AI / Machine Learning" not in (detail["source_categories"] or [])


# --------------------------------------------------------------------------- #
# AI breakdown (sections 23, 24, 25)
# --------------------------------------------------------------------------- #


def test_analysis_is_separate_from_source_information(client: TestClient) -> None:
    headers = auth(client, CURATOR)
    listing = client.get("/historical-projects", params={"q": "reef"}, headers=headers).json()
    detail = client.get(
        f"/historical-projects/{listing['results'][0]['id']}", headers=headers
    ).json()

    assert detail["ai_analysis"] is not None
    assert detail["ai_analysis"]["model"]
    # Source and inference are different objects, so a client cannot confuse them.
    assert "research_question" not in detail["source_information"]


def test_analysis_never_claims_to_know_why_a_project_won(client: TestClient) -> None:
    """Section 24. There is no judge commentary in this catalogue."""

    headers = auth(client, CURATOR)
    listing = client.get("/historical-projects", params={"q": "reef"}, headers=headers).json()
    detail = client.get(
        f"/historical-projects/{listing['results'][0]['id']}", headers=headers
    ).json()
    blob = " ".join(str(v) for v in detail["ai_analysis"].values()).lower()
    assert "why it won" not in blob
    assert "this is why" not in blob


def test_no_abstract_means_no_analysis_rather_than_a_guess(client: TestClient) -> None:
    headers = auth(client, CURATOR)
    created = client.post(
        "/historical-projects/import/manual",
        json={
            "title": "A project with no abstract on record",
            "year": 2022,
            "permission_note": "Entered by the club coach.",
        },
        headers=headers,
    )
    assert created.status_code == 201

    found = client.get(
        "/historical-projects", params={"q": "no abstract on record"}, headers=headers
    ).json()
    detail = client.get(
        f"/historical-projects/{found['results'][0]['id']}", headers=headers
    ).json()

    assert detail["ai_analysis"] is None
    assert "no abstract" in detail["analysis_unavailable_reason"].lower()


def test_every_detail_page_carries_the_do_not_copy_notice(client: TestClient) -> None:
    headers = auth(client, CURATOR)
    listing = client.get("/historical-projects", headers=headers).json()
    assert "not to copy" in listing["copying_notice"]

    detail = client.get(
        f"/historical-projects/{listing['results'][0]['id']}", headers=headers
    ).json()
    assert "not to copy" in detail["copying_notice"]


# --------------------------------------------------------------------------- #
# Similarity (sections 26, 27)
# --------------------------------------------------------------------------- #


def test_similar_projects_say_why_they_matched(client: TestClient) -> None:
    from app.models.project import Project
    from app.models.team import Team

    with SessionLocal() as db:
        team = db.query(Team).filter(Team.name == "Team Coral").one()
        pid = db.query(Project).filter(Project.owner_team_id == team.id).one().id

    response = client.get(
        f"/historical-projects/for-project/{pid}/similar", headers=auth(client, "maya@example.edu")
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["matches"], "the reef project should match the reef historical record"
    assert body["matches"][0]["reasons"], "a match with no stated reason teaches nothing"


def test_no_matches_is_never_reported_as_novelty(client: TestClient) -> None:
    """Section 27. Absence from this catalogue proves nothing."""

    from app.models.project import Project

    with SessionLocal() as db:
        # A project whose vocabulary is nothing like the two catalogue rows.
        pid = (
            db.query(Project)
            .filter(Project.title.notlike("%Coral%"))
            .filter(Project.owner_team_id.is_(None))
            .first()
            .id
        )
        owner_email = db.get(Project, pid).owner.email

    body = client.get(
        f"/historical-projects/for-project/{pid}/similar", headers=auth(client, owner_email)
    ).json()

    if not body["matches"]:
        assert body["empty_notice"]
        assert "not evidence" in body["empty_notice"].lower()


def test_an_outsider_cannot_ask_about_someone_elses_project(client: TestClient) -> None:
    from app.models.project import Project
    from app.models.team import Team

    with SessionLocal() as db:
        team = db.query(Team).filter(Team.name == "Team Coral").one()
        pid = db.query(Project).filter(Project.owner_team_id == team.id).one().id

    response = client.get(
        f"/historical-projects/for-project/{pid}/similar",
        headers=auth(client, "riley@example.edu"),
    )
    assert response.status_code == 404
