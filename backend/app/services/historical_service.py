"""Searching the historical-project catalogue, and relating it to a student's
own work (sections 22-24, 26-29).

Three jobs:

* **Search and facets.** Keyword, category, year, team/individual, awarded.
* **Similarity.** Given a student's project, find historical work in the same
  research area and say *why* each one matched — a list of "related projects"
  with no stated reason teaches nothing.
* **Analysis.** An educational reading of a historical project, kept in its own
  table and labelled as inference everywhere it appears.

The honesty rules from sections 24, 27 and 40 are enforced in code, not left to
prompt wording:

* Analysis is only generated for a record that actually has an abstract. No
  abstract, no reading — rather than a paragraph of confident guesses about a
  title.
* Nothing is ever phrased as "this is why it won". The catalogue holds no judge
  commentary, so the app cannot know.
* An empty similarity result is reported as "nothing matched in this catalogue",
  never as evidence that an idea is novel. This database is a small, permitted
  subset of what has been researched, and absence from it proves nothing.
"""

from __future__ import annotations

import re
from collections import Counter

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.historical import (
    HistoricalProject,
    HistoricalProjectAnalysis,
    HistoricalProjectTag,
)
from app.models.project import Project
from app.services import historical_import, project_service

# Said by nearly every abstract; useless for telling two projects apart.
_STOPWORDS = frozenset(
    """a an and are as at be by for from has have how in into is it its of on or that the
    this to was were what when where which who will with we our study research project
    results method methods using used use effect effects analysis data between could would
    more most than then their there these those it's also may can new than very""".split()
)

EMPTY_RESULT_NOTICE = (
    "Nothing in this catalogue matched. That is not evidence your idea is new — this "
    "database holds only the projects we are permitted to store, which is a small "
    "fraction of what has been researched. Treat it as a starting point, not a novelty check."
)

COPYING_NOTICE = (
    "Use previous projects to understand research quality, methodology and presentation — "
    "not to copy another student's research."
)


def keywords(text: str, limit: int = 12) -> list[str]:
    words = re.findall(r"[a-z][a-z0-9-]{3,}", (text or "").lower())
    counts = Counter(w for w in words if w not in _STOPWORDS)
    return [word for word, _ in counts.most_common(limit)]


# --------------------------------------------------------------------------- #
# Browse
# --------------------------------------------------------------------------- #


def search(
    db: Session,
    *,
    query: str | None = None,
    category: str | None = None,
    year: int | None = None,
    team_only: bool | None = None,
    awarded_only: bool = False,
    tag: str | None = None,
    limit: int = 30,
    offset: int = 0,
) -> tuple[list[HistoricalProject], int]:
    stmt = select(HistoricalProject)

    if query:
        like = f"%{query.strip()}%"
        stmt = stmt.where(
            or_(
                HistoricalProject.title.ilike(like),
                HistoricalProject.abstract.ilike(like),
                HistoricalProject.category.ilike(like),
                HistoricalProject.subcategory.ilike(like),
            )
        )
    if category:
        stmt = stmt.where(HistoricalProject.category == category)
    if year:
        stmt = stmt.where(HistoricalProject.year == year)
    if team_only is not None:
        stmt = stmt.where(HistoricalProject.team_project.is_(team_only))
    if awarded_only:
        stmt = stmt.where(
            HistoricalProject.awards.is_not(None), HistoricalProject.awards != ""
        )
    if tag:
        stmt = stmt.join(HistoricalProjectTag).where(HistoricalProjectTag.tag == tag)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(
            HistoricalProject.year.desc().nullslast(), HistoricalProject.title
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def facets(db: Session) -> dict:
    """What the catalogue actually contains — never a hardcoded list."""

    def counted(column):
        return [
            {"value": value, "count": count}
            for value, count in db.execute(
                select(column, func.count())
                .where(column.is_not(None))
                .group_by(column)
                .order_by(func.count().desc())
            ).all()
            if value not in (None, "")
        ]

    tags = [
        {"value": value, "count": count}
        for value, count in db.execute(
            select(HistoricalProjectTag.tag, func.count())
            .where(HistoricalProjectTag.origin == "derived")
            .group_by(HistoricalProjectTag.tag)
            .order_by(func.count().desc())
        ).all()
    ]
    total = db.scalar(select(func.count()).select_from(HistoricalProject)) or 0
    awarded = (
        db.scalar(
            select(func.count())
            .select_from(HistoricalProject)
            .where(HistoricalProject.awards.is_not(None), HistoricalProject.awards != "")
        )
        or 0
    )
    return {
        "total": total,
        "awarded": awarded,
        "categories": counted(HistoricalProject.category),
        "years": counted(HistoricalProject.year),
        "sources": counted(HistoricalProject.source),
        "derived_tags": tags,
    }


def tags_for(db: Session, project_id: int) -> dict[str, list[str]]:
    rows = db.scalars(
        select(HistoricalProjectTag).where(
            HistoricalProjectTag.historical_project_id == project_id
        )
    ).all()
    return {
        "source": sorted(t.tag for t in rows if t.origin == "source"),
        "derived": sorted(t.tag for t in rows if t.origin == "derived"),
    }


# --------------------------------------------------------------------------- #
# Similarity (section 26)
# --------------------------------------------------------------------------- #

# Maps this app's project categories onto the derived research-area tags. A
# rough bridge, and labelled as such wherever its output is shown.
_CATEGORY_TAGS: dict[str, tuple[str, ...]] = {
    "computer_science": ("AI / Machine Learning", "Robotics", "Computational Biology"),
    "biomedical_science": ("Biomedical", "Computational Biology"),
    "environmental_science": ("Environmental", "Plant Science", "Energy"),
    "physics": ("Physics", "Materials", "Energy"),
    "chemistry": ("Chemistry", "Materials"),
    "engineering": ("Robotics", "Materials", "Energy"),
    "behavioral_social_science": ("Behavioral Science",),
    "mathematics": ("AI / Machine Learning",),
}


def similar_to_project(db: Session, project: Project, limit: int = 6) -> dict:
    """Historical projects related to a student's own, with reasons."""

    signals = project_service.signals_for(project)
    text = " ".join(
        filter(None, [project.title, project.current_question, project.topic, signals.any_text()])
    )
    terms = keywords(text, limit=14)
    wanted_tags = set(_CATEGORY_TAGS.get(str(project.category), ()))
    wanted_tags.update(historical_import.derive_tags(text))

    candidates = db.scalars(select(HistoricalProject)).all()
    scored: list[tuple[float, HistoricalProject, list[str]]] = []

    for row in candidates:
        haystack = " ".join(filter(None, [row.title, row.abstract, row.category])).lower()
        reasons: list[str] = []
        score = 0.0

        hits = [term for term in terms if term in haystack]
        if hits:
            score += min(len(hits), 6) * 1.0
            reasons.append("Shares vocabulary with your project: " + ", ".join(hits[:4]))

        row_tags = set(tags_for(db, row.id)["derived"])
        shared = wanted_tags & row_tags
        if shared:
            score += len(shared) * 1.5
            reasons.append("Same research area: " + ", ".join(sorted(shared)))

        if row.team_project is not None and row.team_project == (project.teammates > 0):
            score += 0.3
            reasons.append(
                "Also a team project" if row.team_project else "Also an individual project"
            )

        if score > 0:
            scored.append((score, row, reasons))

    scored.sort(key=lambda item: (-item[0], item[1].title))
    top = scored[:limit]

    return {
        "matches": [
            {"project": row, "score": round(score, 2), "reasons": reasons}
            for score, row, reasons in top
        ],
        "empty_notice": EMPTY_RESULT_NOTICE if not top else None,
        "copying_notice": COPYING_NOTICE,
        "matched_on": sorted(wanted_tags),
    }


# --------------------------------------------------------------------------- #
# AI breakdown (sections 23-24)
# --------------------------------------------------------------------------- #

_METHOD_MARKERS = (
    ("randomis", "randomised assignment"),
    ("randomiz", "randomised assignment"),
    ("control group", "a control group"),
    ("double-blind", "blinding"),
    ("blind", "blinding"),
    ("in vitro", "in-vitro work"),
    ("in vivo", "in-vivo work"),
    ("simulation", "simulation"),
    ("finite element", "finite-element modelling"),
    ("machine learning", "a machine-learning model"),
    ("neural network", "a neural network"),
    ("cross-validation", "cross-validation"),
    ("survey", "a survey instrument"),
    ("spectroscop", "spectroscopy"),
    ("chromatograph", "chromatography"),
    ("microscop", "microscopy"),
    ("assay", "an assay"),
    ("prototype", "a physical prototype"),
)

_EVIDENCE_MARKERS = (
    ("p <", "reported significance testing"),
    ("p<", "reported significance testing"),
    ("p =", "reported significance testing"),
    ("significan", "a claim of statistical significance"),
    ("accuracy", "a reported accuracy figure"),
    ("correlation", "a reported correlation"),
    ("r2", "a reported goodness-of-fit"),
    ("r²", "a reported goodness-of-fit"),
    ("confidence interval", "confidence intervals"),
    ("standard deviation", "reported variability"),
)


def _found(text: str, markers) -> list[str]:
    lowered = text.lower()
    out: list[str] = []
    for needle, label in markers:
        if needle in lowered and label not in out:
            out.append(label)
    return out


def build_analysis(db: Session, row: HistoricalProject) -> HistoricalProjectAnalysis | None:
    """Generate and store an educational reading. Returns None with no abstract.

    Every sentence below is hedged deliberately. The abstract is a compression
    written by a student; treating it as a full account of the method would put
    confident claims in front of another student who cannot check them.
    """

    if not row.has_abstract:
        return None

    abstract = row.abstract or ""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", abstract) if s.strip()]
    opening = " ".join(sentences[:2]) if sentences else abstract[:300]
    closing = " ".join(sentences[-2:]) if len(sentences) > 2 else ""

    methods = _found(abstract, _METHOD_MARKERS)
    evidence = _found(abstract, _EVIDENCE_MARKERS)

    analysis = row.analysis or HistoricalProjectAnalysis(historical_project_id=row.id)
    analysis.research_question = (
        f"From the abstract, the project appears to ask about: {opening}"
        if opening
        else None
    )
    analysis.why_it_matters = (
        "The abstract frames the work in terms of "
        f"{row.category.lower()}." if row.category else
        "The abstract does not state a broader motivation explicitly."
    )
    analysis.methodology = (
        "The abstract mentions " + ", ".join(methods) + "."
        if methods
        else "The abstract does not describe the method in enough detail to characterise it."
    )
    analysis.scientific_depth = (
        "Techniques named in the abstract that suggest depth: " + ", ".join(methods) + "."
        if len(methods) >= 2
        else "Not enough detail in the abstract to judge depth."
    )
    analysis.novelty = (
        "What the abstract presents as new cannot be verified from this record alone. "
        "Potential strengths visible from the available description are listed above; "
        "this catalogue holds no judge commentary, so nothing here explains why any "
        "project placed."
    )
    analysis.evidence = (
        "The abstract reports " + ", ".join(evidence) + "."
        if evidence
        else "The abstract does not report quantitative results."
    )
    analysis.lessons_for_students = _lessons(methods, evidence, closing)
    analysis.model = "heuristic"

    if row.analysis is None:
        db.add(analysis)
    db.flush()
    return analysis


def _lessons(methods: list[str], evidence: list[str], closing: str) -> list[str]:
    out: list[str] = []
    if "a control group" in methods:
        out.append(
            "The abstract names its control explicitly. Yours should too — judges look for it."
        )
    if evidence:
        out.append(
            "Results are stated as numbers, not adjectives. That is the difference between "
            "'improved performance' and a result a judge can evaluate."
        )
    else:
        out.append(
            "This abstract reports no numbers. Notice how much harder that makes it to judge "
            "the work — and write yours differently."
        )
    if len(methods) >= 2:
        out.append(
            "Several techniques are combined rather than one applied in isolation. That "
            "combination is often what makes a project look sophisticated."
        )
    if closing:
        out.append("Note how the closing states a conclusion rather than trailing off.")
    return out[:4]
