"""Wire contracts for the ISEF / historical project explorer.

The shape here carries the honesty rule: source fields and AI fields never
share an object. ``HistoricalProjectDetail.source_information`` is what the fair
published; ``ai_analysis`` is this app's reading, nullable, and separately
labelled. A client cannot accidentally render one as the other.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SourceInformation(BaseModel):
    """Verbatim from the source. Every field nullable — nothing is invented."""

    model_config = ConfigDict(from_attributes=True)

    title: str
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
    source: str
    source_url: str | None = None
    permission_note: str | None = None


class AIAnalysis(BaseModel):
    """This app's reading. Always rendered under an 'AI analysis' heading."""

    model_config = ConfigDict(from_attributes=True)

    research_question: str | None = None
    why_it_matters: str | None = None
    methodology: str | None = None
    scientific_depth: str | None = None
    novelty: str | None = None
    evidence: str | None = None
    lessons_for_students: list[str] = Field(default_factory=list)
    model: str
    generated_at: datetime


class HistoricalProjectCard(BaseModel):
    """A row in the catalogue listing."""

    id: int
    title: str
    year: int | None = None
    category: str | None = None
    team_project: bool | None = None
    awards: str | None = None
    has_abstract: bool = False
    source: str
    derived_tags: list[str] = Field(default_factory=list)


class HistoricalProjectDetail(BaseModel):
    id: int
    source_information: SourceInformation
    source_categories: list[str] = Field(default_factory=list)
    derived_tags: list[str] = Field(
        default_factory=list,
        description="Research areas this app inferred. Never the fair's own category.",
    )
    ai_analysis: AIAnalysis | None = None
    analysis_unavailable_reason: str | None = None
    copying_notice: str


class FacetValue(BaseModel):
    value: str | int
    count: int


class CatalogueFacets(BaseModel):
    total: int
    awarded: int
    categories: list[FacetValue] = Field(default_factory=list)
    years: list[FacetValue] = Field(default_factory=list)
    sources: list[FacetValue] = Field(default_factory=list)
    derived_tags: list[FacetValue] = Field(default_factory=list)


class HistoricalSearchResult(BaseModel):
    results: list[HistoricalProjectCard] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
    copying_notice: str


class SimilarMatch(BaseModel):
    project: HistoricalProjectCard
    score: float
    reasons: list[str] = Field(default_factory=list)


class SimilarResult(BaseModel):
    matches: list[SimilarMatch] = Field(default_factory=list)
    matched_on: list[str] = Field(default_factory=list)
    empty_notice: str | None = None
    copying_notice: str


class ManualProjectIn(BaseModel):
    """One project entered by hand, by someone who may store it."""

    title: str = Field(min_length=3, max_length=400)
    year: int | None = Field(default=None, ge=1950, le=2100)
    category: str | None = Field(default=None, max_length=160)
    subcategory: str | None = Field(default=None, max_length=160)
    project_type: str | None = Field(default=None, max_length=40)
    team_project: bool | None = None
    abstract: str | None = None
    awards: str | None = None
    student_display: str | None = Field(default=None, max_length=400)
    school_display: str | None = Field(default=None, max_length=400)
    country: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    source_url: str | None = None
    source: str = Field(default="manual", max_length=60)
    source_project_id: str | None = Field(default=None, max_length=120)
    # Required in the API layer: storing someone else's material is a decision a
    # person has to make and record, not something the app assumes.
    permission_note: str = Field(min_length=3, max_length=500)


class CsvImportIn(BaseModel):
    csv_text: str = Field(min_length=10)
    source: str = Field(default="csv", max_length=60)
    permission_note: str = Field(min_length=3, max_length=500)


class ImportReportOut(BaseModel):
    created: int
    updated: int
    skipped: int
    total: int
    errors: list[str] = Field(default_factory=list)
