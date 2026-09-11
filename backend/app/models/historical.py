"""Previous science-fair projects, imported from an approved source.

Two constraints shape this table, and both come from honesty rather than
convenience.

**Provenance is a column, not a comment.** Every row records where it came
from (``source``), that source's own id for it (``source_project_id``) and the
page it came from (``source_url``). A field the source did not publish stays
NULL. Nothing here is ever filled in by inference — the AI's reading of a
project lives in ``HistoricalProjectAnalysis``, a separate table, so a student
looking at the screen can always tell what the fair published from what a model
guessed.

**Re-import must be safe.** ``(source, source_project_id)`` is unique, so an
importer can run nightly, weekly or twice by accident and update rows instead of
duplicating them.

On sources: as of this writing the ISEF abstract database is *not* an approved
source. Society for Science's terms forbid robots and forbid reproducing their
materials without written permission, so no importer targets it. The models and
the importer interface exist so that a source which *is* permitted — a written
grant from Society for Science, an openly-licensed dataset, a regional fair's
own export, or a CSV a coach assembles by hand — can be loaded without any of
this being redesigned.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.project import utcnow


class HistoricalProject(Base):
    """One previously-competed project, as its source published it."""

    __tablename__ = "historical_projects"
    __table_args__ = (
        UniqueConstraint("source", "source_project_id", name="uq_historical_source_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # ---- provenance ------------------------------------------------------ #
    # Which catalogue this came from: "manual", "csv", or a named feed. Kept as
    # a string rather than an enum so adding an approved source is data, not a
    # migration.
    source: Mapped[str] = mapped_column(String(60), index=True, default="manual")
    source_project_id: Mapped[str] = mapped_column(String(120), index=True)
    source_url: Mapped[str | None] = mapped_column(Text, default=None)
    # Who confirmed this may be stored, for the manual path. Free text on
    # purpose: "written permission from SSP, 2026-03-04" is more useful than a
    # boolean.
    permission_note: Mapped[str | None] = mapped_column(Text, default=None)

    # ---- what the source published --------------------------------------- #
    title: Mapped[str] = mapped_column(String(400))
    year: Mapped[int | None] = mapped_column(Integer, default=None, index=True)
    # The fair's own category string, verbatim. Never a value we derived.
    category: Mapped[str | None] = mapped_column(String(160), default=None, index=True)
    subcategory: Mapped[str | None] = mapped_column(String(160), default=None)
    project_type: Mapped[str | None] = mapped_column(String(40), default=None)
    team_project: Mapped[bool | None] = mapped_column(Boolean, default=None)
    abstract: Mapped[str | None] = mapped_column(Text, default=None)
    awards: Mapped[str | None] = mapped_column(Text, default=None)
    # Display strings rather than structured people: a historical record is not
    # a directory, and splitting names invites getting them wrong.
    student_display: Mapped[str | None] = mapped_column(String(400), default=None)
    school_display: Mapped[str | None] = mapped_column(String(400), default=None)
    country: Mapped[str | None] = mapped_column(String(120), default=None)
    state: Mapped[str | None] = mapped_column(String(120), default=None)

    # Everything else the source gave us, unmodelled. Keeping it means a
    # re-import can recover a field we later decide to promote to a column.
    raw_metadata: Mapped[dict] = mapped_column(JSON, default=dict)

    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    analysis: Mapped["HistoricalProjectAnalysis | None"] = relationship(
        back_populates="project", cascade="all, delete-orphan", uselist=False
    )

    @property
    def has_abstract(self) -> bool:
        return bool((self.abstract or "").strip())


class HistoricalProjectTag(Base):
    """A derived research-area tag.

    Deliberately a separate table from ``category``. The fair's category is a
    fact; a tag is this app's guess, and the two must never be rendered as the
    same kind of claim. ``origin`` records which it is.
    """

    __tablename__ = "historical_project_tags"
    __table_args__ = (
        UniqueConstraint("historical_project_id", "tag", name="uq_historical_tag"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    historical_project_id: Mapped[int] = mapped_column(
        ForeignKey("historical_projects.id"), index=True
    )
    tag: Mapped[str] = mapped_column(String(80), index=True)
    # "source" — the fair said so. "derived" — we inferred it from the text.
    origin: Mapped[str] = mapped_column(String(20), default="derived")


class HistoricalProjectAnalysis(Base):
    """An AI reading of one historical project.

    Separate table, separate label in the UI, and never merged into the record
    above. ``model`` and ``generated_at`` are stored so an old analysis produced
    by a weaker model can be identified and regenerated rather than trusted.
    """

    __tablename__ = "historical_project_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    historical_project_id: Mapped[int] = mapped_column(
        ForeignKey("historical_projects.id"), index=True, unique=True
    )

    research_question: Mapped[str | None] = mapped_column(Text, default=None)
    why_it_matters: Mapped[str | None] = mapped_column(Text, default=None)
    methodology: Mapped[str | None] = mapped_column(Text, default=None)
    scientific_depth: Mapped[str | None] = mapped_column(Text, default=None)
    novelty: Mapped[str | None] = mapped_column(Text, default=None)
    evidence: Mapped[str | None] = mapped_column(Text, default=None)
    lessons_for_students: Mapped[list] = mapped_column(JSON, default=list)

    model: Mapped[str] = mapped_column(String(60), default="heuristic")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped[HistoricalProject] = relationship(back_populates="analysis")
