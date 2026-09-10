"""Importing previous science-fair projects.

The interface is a ``HistoricalSource``: something that yields
``NormalisedRecord`` objects. ``import_records`` takes that stream and upserts
it, keyed on ``(source, source_project_id)``, so running an import twice
updates rather than duplicates.

Two sources ship:

* ``CsvSource`` — a file. This is the path that works today: a coach or student
  assembles rows they are permitted to store, and imports them.
* ``ManualRecord`` — one project typed into a form.

There is no ISEF web source, and adding one is a decision about permission
rather than about code. Society for Science's terms forbid robots and forbid
reproducing their material without written permission, so a scraper against
their abstract database is not something this module will grow. When a
permitted feed exists — a written grant, an openly-licensed dataset, a regional
fair's own export — it implements ``HistoricalSource`` and everything
downstream is already built.

Nothing here invents data. A column the source left blank arrives as ``None``
and is stored as ``None``; there is no default abstract, no inferred award, no
guessed category.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.historical import HistoricalProject, HistoricalProjectTag

log = logging.getLogger(__name__)

# Derived tags. These are this app's guesses and are stored with
# origin="derived" so the UI can never present them as the fair's own category.
DERIVED_TAG_PATTERNS: dict[str, tuple[str, ...]] = {
    "AI / Machine Learning": (
        "machine learning", "neural network", "deep learning", "classifier",
        "convolutional", "transformer", "random forest", "training data", "cnn",
    ),
    "Robotics": ("robot", "actuator", "servo", "autonomous vehicle", "manipulator", "drone"),
    "Biomedical": ("cancer", "tumor", "tumour", "clinical", "patient", "therapeutic", "drug", "disease"),
    "Environmental": ("pollution", "climate", "ecosystem", "watershed", "emissions", "microplastic", "reef"),
    "Energy": ("solar", "photovoltaic", "battery", "fuel cell", "turbine", "energy efficiency"),
    "Materials": ("composite", "polymer", "alloy", "nanoparticle", "tensile", "coating"),
    "Physics": ("quantum", "optics", "particle", "magnetic field", "thermodynamic"),
    "Chemistry": ("catalyst", "synthesis", "titration", "reagent", "chromatograph", "ph "),
    "Behavioral Science": ("participants", "survey", "cognitive", "behaviour", "behavior", "memory task"),
    "Plant Science": ("germination", "seedling", "photosynthesis", "crop", "soil", "leaf"),
    "Computational Biology": ("genome", "sequencing", "protein folding", "bioinformatic", "rna", "dna "),
}


@dataclass
class NormalisedRecord:
    """One project, in the shape the table expects.

    ``source_project_id`` is required because deduplication depends on it. When
    a source has no stable id of its own, ``derive_id`` builds a deterministic
    one — deterministic being the whole point, so the same row imported twice
    lands on the same record.
    """

    source: str
    source_project_id: str
    title: str
    source_url: str | None = None
    year: int | None = None
    category: str | None = None
    subcategory: str | None = None
    project_type: str | None = None
    team_project: bool | None = None
    abstract: str | None = None
    awards: str | None = None
    student_display: str | None = None
    school_display: str | None = None
    country: str | None = None
    state: str | None = None
    permission_note: str | None = None
    raw_metadata: dict = field(default_factory=dict)


class HistoricalSource(Protocol):
    """Anything that can yield records. Implement this for a permitted feed."""

    name: str

    def fetch(self) -> Iterable[NormalisedRecord]:
        """Yield every record this source offers.

        Implementations must raise on transport failure rather than yielding a
        partial set silently — a half-import that looks complete is worse than
        a visible error, because the next run will treat the gap as deletions.
        """


@dataclass
class ImportReport:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.created + self.updated

    def as_dict(self) -> dict:
        return {
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "total": self.total,
            "errors": self.errors,
        }


def derive_id(source: str, title: str, year: int | None) -> str:
    """A stable fallback id for a source with none of its own."""

    slug = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")[:80]
    return f"{source}:{year or 'unknown'}:{slug or 'untitled'}"


def _clean(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_int(value) -> int | None:
    text = _clean(value)
    if text is None:
        return None
    match = re.search(r"\d{4}", text)
    return int(match.group()) if match else None


def _to_bool(value) -> bool | None:
    text = _clean(value)
    if text is None:
        return None
    lowered = text.lower()
    if lowered in {"true", "yes", "y", "1", "team"}:
        return True
    if lowered in {"false", "no", "n", "0", "individual"}:
        return False
    return None


# --------------------------------------------------------------------------- #
# CSV source
# --------------------------------------------------------------------------- #

# Accepted column spellings -> field name. Generous on input, strict on output.
_COLUMN_ALIASES: dict[str, str] = {
    "id": "source_project_id",
    "project_id": "source_project_id",
    "source_project_id": "source_project_id",
    "title": "title",
    "project_title": "title",
    "year": "year",
    "fair_year": "year",
    "category": "category",
    "subcategory": "subcategory",
    "sub_category": "subcategory",
    "project_type": "project_type",
    "team": "team_project",
    "team_project": "team_project",
    "abstract": "abstract",
    "awards": "awards",
    "award": "awards",
    "student": "student_display",
    "students": "student_display",
    "student_display": "student_display",
    "school": "school_display",
    "school_display": "school_display",
    "country": "country",
    "state": "state",
    "url": "source_url",
    "source_url": "source_url",
}


class CsvSource:
    """Records from a CSV a human assembled and is permitted to store."""

    def __init__(self, text: str, source: str = "csv", permission_note: str | None = None) -> None:
        self.name = source
        self._text = text
        self._permission_note = permission_note

    def fetch(self) -> Iterable[NormalisedRecord]:
        reader = csv.DictReader(io.StringIO(self._text))
        if reader.fieldnames is None:
            raise ValueError("That file has no header row, so its columns cannot be identified.")

        mapping = {
            name: _COLUMN_ALIASES[name.strip().lower()]
            for name in reader.fieldnames
            if name and name.strip().lower() in _COLUMN_ALIASES
        }
        if "title" not in mapping.values():
            raise ValueError(
                "A 'title' column is required. Recognised columns: "
                + ", ".join(sorted(set(_COLUMN_ALIASES)))
            )

        for line_number, row in enumerate(reader, start=2):
            fields: dict = {}
            extras: dict = {}
            for column, value in row.items():
                if column is None:
                    continue
                target = mapping.get(column)
                if target is None:
                    cleaned = _clean(value)
                    if cleaned is not None:
                        extras[column.strip()] = cleaned
                    continue
                fields[target] = value

            title = _clean(fields.get("title"))
            if not title:
                # A row with no title is not a project. Skipping beats importing
                # a blank card the student cannot interpret.
                continue

            year = _to_int(fields.get("year"))
            record = NormalisedRecord(
                source=self.name,
                source_project_id=_clean(fields.get("source_project_id"))
                or derive_id(self.name, title, year),
                title=title,
                source_url=_clean(fields.get("source_url")),
                year=year,
                category=_clean(fields.get("category")),
                subcategory=_clean(fields.get("subcategory")),
                project_type=_clean(fields.get("project_type")),
                team_project=_to_bool(fields.get("team_project")),
                abstract=_clean(fields.get("abstract")),
                awards=_clean(fields.get("awards")),
                student_display=_clean(fields.get("student_display")),
                school_display=_clean(fields.get("school_display")),
                country=_clean(fields.get("country")),
                state=_clean(fields.get("state")),
                permission_note=self._permission_note,
                raw_metadata={"csv_line": line_number, **extras},
            )
            yield record


# --------------------------------------------------------------------------- #
# Upsert
# --------------------------------------------------------------------------- #

_WRITABLE = (
    "title", "source_url", "year", "category", "subcategory", "project_type",
    "team_project", "abstract", "awards", "student_display", "school_display",
    "country", "state", "permission_note",
)


def import_records(
    db: Session, records: Iterable[NormalisedRecord], *, retag: bool = True
) -> ImportReport:
    """Upsert a stream of records. Safe to run repeatedly."""

    report = ImportReport()
    for record in records:
        try:
            existing = db.scalars(
                select(HistoricalProject).where(
                    HistoricalProject.source == record.source,
                    HistoricalProject.source_project_id == record.source_project_id,
                )
            ).first()

            if existing is None:
                row = HistoricalProject(
                    source=record.source, source_project_id=record.source_project_id
                )
                db.add(row)
                report.created += 1
            else:
                row = existing
                report.updated += 1

            for attribute in _WRITABLE:
                value = getattr(record, attribute)
                # A later import that simply omits a field must not erase a
                # value an earlier one supplied.
                if value is not None:
                    setattr(row, attribute, value)
            if record.raw_metadata:
                row.raw_metadata = {**(row.raw_metadata or {}), **record.raw_metadata}
            row.updated_at = datetime.now(timezone.utc)

            db.flush()
            if retag:
                apply_derived_tags(db, row)
        except Exception as exc:  # noqa: BLE001 — one bad row must not lose the batch
            report.skipped += 1
            report.errors.append(f"{record.source_project_id}: {exc}")
            log.exception("historical import: could not store %s", record.source_project_id)

    db.commit()
    return report


def derive_tags(text: str) -> list[str]:
    lowered = (text or "").lower()
    return [
        tag
        for tag, needles in DERIVED_TAG_PATTERNS.items()
        if any(needle in lowered for needle in needles)
    ]


def apply_derived_tags(db: Session, row: HistoricalProject) -> list[str]:
    """Recompute this row's derived tags. Source categories are untouched."""

    haystack = " ".join(filter(None, [row.title, row.abstract, row.category, row.subcategory]))
    wanted = set(derive_tags(haystack))

    current = db.scalars(
        select(HistoricalProjectTag).where(
            HistoricalProjectTag.historical_project_id == row.id,
            HistoricalProjectTag.origin == "derived",
        )
    ).all()
    have = {tag.tag for tag in current}

    for tag in current:
        if tag.tag not in wanted:
            db.delete(tag)
    for tag in wanted - have:
        db.add(
            HistoricalProjectTag(
                historical_project_id=row.id, tag=tag, origin="derived"
            )
        )
    db.flush()
    return sorted(wanted)
