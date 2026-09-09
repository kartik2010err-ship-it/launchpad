"""Past science-fair projects, and the provenance that makes them usable.

The hard rule for this table: **nothing in it may be invented.** A row is only
worth showing a student if they could go and check it. So every record carries a
source, every field carries a provenance marker, and the application ships with
an empty catalogue rather than a plausible-looking one.

Two kinds of row exist, and they are never mixed in the UI:

* ``is_illustrative = False`` — a real past project, ingested from a dataset with
  a citable source. Displayed as fact only for fields the source actually
  contained.
* ``is_illustrative = True`` — a teaching example this application wrote, used to
  demonstrate what a strong write-up looks like. Labelled as constructed, never
  described as a winner, never attributed to a real student.

Judging commentary is the sharpest case. The app can never explain *why* judges
chose something. ``judging_commentary`` is populated only when the source itself
published judge remarks; otherwise it stays null and the UI says so.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.project import utcnow


class WinningProject(Base):
    __tablename__ = "winning_projects"
    __table_args__ = (
        UniqueConstraint("source_key", "external_id", name="uq_winning_project_source_ref"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # ---- provenance, first because it gates everything else --------------- #
    source_key: Mapped[str] = mapped_column(String(60), index=True)
    source_name: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(String(500), default=None)
    external_id: Mapped[str] = mapped_column(String(120))
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    license_note: Mapped[str | None] = mapped_column(Text, default=None)
    # True for constructed teaching examples. Never rendered as a real winner.
    is_illustrative: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Per-field provenance: {"abstract": "verified_source", "novelty": "ai_analysis"}.
    # Anything missing from this map is treated as not_available.
    field_provenance: Mapped[dict] = mapped_column(JSON, default=dict)

    # ---- what the project was --------------------------------------------- #
    title: Mapped[str] = mapped_column(String(300))
    year: Mapped[int | None] = mapped_column(Integer, default=None, index=True)
    competition_name: Mapped[str | None] = mapped_column(String(200), default=None, index=True)
    category: Mapped[str] = mapped_column(String(60), index=True)
    project_type: Mapped[str] = mapped_column(String(30), default="scientific")
    division: Mapped[str | None] = mapped_column(String(60), default=None)
    is_team: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    team_size: Mapped[int | None] = mapped_column(Integer, default=None)

    # Award as the source stated it. Null means the source did not say.
    award_title: Mapped[str | None] = mapped_column(String(200), default=None)

    # ---- content, all nullable because sources are uneven ------------------ #
    abstract: Mapped[str | None] = mapped_column(Text, default=None)
    research_question: Mapped[str | None] = mapped_column(Text, default=None)
    problem_statement: Mapped[str | None] = mapped_column(Text, default=None)
    methodology: Mapped[str | None] = mapped_column(Text, default=None)
    variables: Mapped[dict] = mapped_column(JSON, default=dict)
    data_summary: Mapped[str | None] = mapped_column(Text, default=None)
    results_summary: Mapped[str | None] = mapped_column(Text, default=None)

    # Only ever set when the competition itself published judge remarks.
    judging_commentary: Mapped[str | None] = mapped_column(Text, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    @property
    def has_breakdown_material(self) -> bool:
        """Enough verified content to write an educational breakdown at all."""

        present = [self.abstract, self.research_question, self.methodology, self.results_summary]
        return sum(1 for value in present if value and value.strip()) >= 2
