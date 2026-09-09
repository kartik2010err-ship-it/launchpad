"""The winning-projects library: ingestion, provenance and educational breakdowns.

This module exists to make one failure impossible: presenting a made-up past
project, award, abstract or judging remark as fact.

How that is enforced:

* Nothing reaches the table except through ``ingest``, which rejects records
  without a source and an external id.
* Every content field carries provenance. The read API returns each field
  wrapped with where it came from, so the UI can render "from the source" and
  "written by Research Coach" differently without guessing.
* Breakdown commentary is generated only from fields the record actually has,
  and every line of it is tagged ``ai_analysis``.
* Judging commentary is echoed only when the source itself published it. There
  is no code path that produces an explanation of why judges chose something.

The application ships with no verified winners loaded. That is deliberate: an
empty catalogue that says so is more useful than a full one that cannot be
checked. Load real data with ``python -m app.services.winners_service <file>``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import SourceConfidence
from app.models.library import WinningProject

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEFAULT_DATA_FILE = DATA_DIR / "winning_projects.json"

EMPTY_CATALOG_NOTICE = (
    "No verified past-project dataset has been loaded into this installation. Research Coach "
    "will not display past winners, awards, abstracts or judging information from memory, "
    "because it has no way to guarantee any of it is real. To populate this library, ingest a "
    "dataset you can cite — an official fair's published project archive, an institutional "
    "database, or your own school's records."
)

ILLUSTRATIVE_NOTICE = (
    "This is a constructed teaching example written by Research Coach to show what a strong "
    "write-up looks like. It is not a real project, not a real student's work, and it did not "
    "win anything. Nothing in it should be cited."
)

NO_JUDGING_NOTICE = (
    "This source did not publish judging commentary, so Research Coach cannot tell you why this "
    "project placed. Any explanation of judges' reasoning would be a guess."
)

COPYING_WARNING = (
    "Use these projects to understand research quality and methodology — not to replicate "
    "another student's work. Copying a question, method or analysis is plagiarism, and judges "
    "at every level ask questions that expose it immediately."
)

# Fields whose provenance is tracked individually.
CONTENT_FIELDS = (
    "abstract",
    "research_question",
    "problem_statement",
    "methodology",
    "variables",
    "data_summary",
    "results_summary",
    "award_title",
    "judging_commentary",
)


class IngestError(ValueError):
    """A record that cannot be traced back to a source is not ingestible."""


# --------------------------------------------------------------------------- #
# Ingestion
# --------------------------------------------------------------------------- #


def _validate(record: dict) -> None:
    for required in ("external_id", "title", "category", "source_key", "source_name"):
        if not str(record.get(required) or "").strip():
            raise IngestError(f"Record is missing required field '{required}': {record!r}")
    if not record.get("is_illustrative") and not str(record.get("source_url") or "").strip():
        raise IngestError(
            f"Record {record['external_id']!r} claims to be a real past project but has no "
            "source_url. Real projects must be checkable."
        )
    if record.get("judging_commentary") and not record.get("judging_commentary_published"):
        raise IngestError(
            f"Record {record['external_id']!r} carries judging commentary without "
            "judging_commentary_published=true. Judge reasoning is only ever echoed from a "
            "source that actually published it."
        )


def _provenance_for(record: dict) -> dict:
    """Mark every present content field, defaulting to the record's own claim."""

    declared = record.get("field_provenance") or {}
    default = (
        SourceConfidence.UNVERIFIED
        if record.get("is_illustrative")
        else SourceConfidence.VERIFIED_SOURCE
    )
    out: dict[str, str] = {}
    for field in CONTENT_FIELDS:
        value = record.get(field)
        if value in (None, "", {}, []):
            out[field] = SourceConfidence.NOT_AVAILABLE
        else:
            out[field] = str(declared.get(field, default))
    return out


def ingest(db: Session, records: list[dict], *, replace_source: str | None = None) -> dict:
    """Load records, refusing anything that cannot be traced.

    Idempotent per ``(source_key, external_id)``: re-running an ingest updates
    rows rather than duplicating them.
    """

    if replace_source:
        for row in db.scalars(
            select(WinningProject).where(WinningProject.source_key == replace_source)
        ):
            db.delete(row)
        db.flush()

    added = updated = 0
    for record in records:
        _validate(record)
        existing = db.scalars(
            select(WinningProject).where(
                WinningProject.source_key == record["source_key"],
                WinningProject.external_id == str(record["external_id"]),
            )
        ).first()
        row = existing or WinningProject(
            source_key=record["source_key"], external_id=str(record["external_id"])
        )
        row.source_name = record["source_name"]
        row.source_url = record.get("source_url")
        row.license_note = record.get("license_note")
        row.is_illustrative = bool(record.get("is_illustrative"))
        row.retrieved_at = datetime.now(timezone.utc)
        row.title = record["title"]
        row.year = record.get("year")
        row.competition_name = record.get("competition_name")
        row.category = record["category"]
        row.project_type = record.get("project_type", "scientific")
        row.division = record.get("division")
        row.is_team = bool(record.get("is_team"))
        row.team_size = record.get("team_size")
        row.award_title = record.get("award_title")
        row.abstract = record.get("abstract")
        row.research_question = record.get("research_question")
        row.problem_statement = record.get("problem_statement")
        row.methodology = record.get("methodology")
        row.variables = record.get("variables") or {}
        row.data_summary = record.get("data_summary")
        row.results_summary = record.get("results_summary")
        row.judging_commentary = record.get("judging_commentary")
        row.field_provenance = _provenance_for(record)
        if existing is None:
            db.add(row)
            added += 1
        else:
            updated += 1
    db.flush()
    return {"added": added, "updated": updated}


def ingest_file(db: Session, path: Path | str | None = None) -> dict:
    path = Path(path or DEFAULT_DATA_FILE)
    if not path.exists():
        return {"added": 0, "updated": 0, "note": f"No dataset at {path}."}
    payload = json.loads(path.read_text())
    records = payload.get("records", []) if isinstance(payload, dict) else payload
    return ingest(db, records)


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #


def _field(row: WinningProject, name: str) -> dict:
    """One content field plus where it came from."""

    value = getattr(row, name, None)
    provenance = (row.field_provenance or {}).get(name) or SourceConfidence.NOT_AVAILABLE
    if value in (None, "", {}, []):
        provenance = SourceConfidence.NOT_AVAILABLE
    return {"value": value or None, "provenance": provenance}


def summary(row: WinningProject) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "year": row.year,
        "competition_name": row.competition_name,
        "category": row.category,
        "project_type": row.project_type,
        "division": row.division,
        "is_team": row.is_team,
        "team_size": row.team_size,
        "award_title": row.award_title,
        "is_illustrative": row.is_illustrative,
        "source_name": row.source_name,
        "source_url": row.source_url,
        "has_breakdown": row.has_breakdown_material,
        "notice": ILLUSTRATIVE_NOTICE if row.is_illustrative else None,
    }


def search(
    db: Session,
    *,
    category: str | None = None,
    year: int | None = None,
    competition: str | None = None,
    project_type: str | None = None,
    team_only: bool | None = None,
    include_illustrative: bool = True,
    query: str | None = None,
) -> list[WinningProject]:
    stmt = select(WinningProject)
    if category:
        stmt = stmt.where(WinningProject.category == category)
    if year is not None:
        stmt = stmt.where(WinningProject.year == year)
    if competition:
        stmt = stmt.where(WinningProject.competition_name == competition)
    if project_type:
        stmt = stmt.where(WinningProject.project_type == project_type)
    if team_only is not None:
        stmt = stmt.where(WinningProject.is_team.is_(team_only))
    if not include_illustrative:
        stmt = stmt.where(WinningProject.is_illustrative.is_(False))
    rows = list(db.scalars(stmt.order_by(WinningProject.year.desc(), WinningProject.title)))
    if query:
        needle = query.lower()
        rows = [
            r
            for r in rows
            if needle in r.title.lower()
            or needle in (r.abstract or "").lower()
            or needle in (r.research_question or "").lower()
        ]
    return rows


def filter_options(db: Session) -> dict:
    rows = list(db.scalars(select(WinningProject)))
    return {
        "years": sorted({r.year for r in rows if r.year}, reverse=True),
        "competitions": sorted({r.competition_name for r in rows if r.competition_name}),
        "categories": sorted({r.category for r in rows if r.category}),
        "project_types": sorted({r.project_type for r in rows if r.project_type}),
        "total": len(rows),
        "verified_total": sum(1 for r in rows if not r.is_illustrative),
        "illustrative_total": sum(1 for r in rows if r.is_illustrative),
    }


# --------------------------------------------------------------------------- #
# Educational breakdown
# --------------------------------------------------------------------------- #


def _lessons(row: WinningProject) -> list[dict]:
    """General lessons, derived only from fields this record actually has.

    Every item is AI analysis of the verified text, never a claim about the
    project's history or its reception.
    """

    lessons: list[dict] = []
    if row.research_question:
        lessons.append(
            {
                "lesson": "Write your question so a stranger could run it.",
                "detail": "Notice how much of the design is already visible in this project's "
                "question. If yours does not name what changes and what gets measured, that is "
                "the cheapest improvement available to you.",
                "guide_id": "idea-to-research-question",
            }
        )
    if row.methodology:
        lessons.append(
            {
                "lesson": "Method detail is what makes a result believable.",
                "detail": "Read the method here and count how many decisions are stated "
                "explicitly — quantities, timings, replicate counts. Each one you leave out of "
                "your own write-up is a question a judge will ask instead.",
                "guide_id": "designing-a-controlled-experiment",
            }
        )
    if row.results_summary:
        lessons.append(
            {
                "lesson": "Report the number, not the direction.",
                "detail": "The results here are stated as quantities. 'It improved' is an "
                "assertion; a value with a unit and a spread is evidence.",
                "guide_id": "descriptive-statistics",
            }
        )
    if row.variables:
        lessons.append(
            {
                "lesson": "Name your variables before you defend them.",
                "detail": "Being able to point at the independent variable, the dependent "
                "variable and what was held constant is the fastest way to show a judge the "
                "design is sound.",
                "guide_id": "independent-dependent-variables",
            }
        )
    lessons.append(
        {
            "lesson": "Adapt the standard of work, not the project.",
            "detail": "The transferable thing here is the level of rigour and clarity, not the "
            "topic. A copied question is obvious to judges and is treated as plagiarism.",
            "guide_id": "explaining-novelty",
        }
    )
    return lessons[:5]


def breakdown(row: WinningProject) -> dict:
    """Educational breakdown, with source facts and AI commentary kept apart."""

    facts = {name: _field(row, name) for name in CONTENT_FIELDS}
    available = [k for k, v in facts.items() if v["provenance"] != SourceConfidence.NOT_AVAILABLE]
    missing = [k for k, v in facts.items() if v["provenance"] == SourceConfidence.NOT_AVAILABLE]

    return {
        **summary(row),
        "facts": facts,
        "fields_available": available,
        "fields_missing": missing,
        "sufficient_for_breakdown": row.has_breakdown_material,
        "insufficient_notice": (
            None
            if row.has_breakdown_material
            else "The source for this project does not contain enough detail for a breakdown. "
            "Research Coach will not fill the gaps in with invented methodology or results."
        ),
        "judging": {
            "commentary": row.judging_commentary,
            "provenance": (
                SourceConfidence.VERIFIED_SOURCE
                if row.judging_commentary
                else SourceConfidence.NOT_AVAILABLE
            ),
            "notice": None if row.judging_commentary else NO_JUDGING_NOTICE,
        },
        "lessons": _lessons(row) if row.has_breakdown_material else [],
        "lessons_provenance": SourceConfidence.AI_ANALYSIS,
        "analysis_notice": (
            "Lessons below are this application's analysis of the text above. They are not "
            "statements from the competition, the researchers, or the judges."
        ),
        "copying_warning": COPYING_WARNING,
    }


def recommend_for_project(
    db: Session, *, category: str | None, project_type: str | None, limit: int = 4
) -> dict:
    """Examples relevant to a student's own project, for the coach to surface."""

    rows = search(db, category=category)
    if project_type:
        preferred = [r for r in rows if r.project_type == project_type]
        rows = preferred + [r for r in rows if r not in preferred]
    if not rows:
        rows = search(db)
    return {
        "projects": [summary(r) for r in rows[:limit]],
        "warning": COPYING_WARNING,
        "empty_notice": EMPTY_CATALOG_NOTICE if not rows else None,
    }


if __name__ == "__main__":  # pragma: no cover - operational entry point
    import sys

    from app.db.session import SessionLocal

    session = SessionLocal()
    result = ingest_file(session, sys.argv[1] if len(sys.argv) > 1 else None)
    session.commit()
    print(result)
