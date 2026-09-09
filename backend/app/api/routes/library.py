"""Research Library and Winning Projects.

Both are reference material rather than user data, so these routes are readable
by any signed-in account and are not workspace-scoped. The winners routes are
careful to pass provenance through untouched — the API never flattens "the
source said this" and "we inferred this" into the same shape.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import current_user, get_project
from app.content import guides
from app.db.session import get_db
from app.models.enums import GUIDE_CATEGORY_LABELS, GuideCategory
from app.models.library import WinningProject
from app.models.project import Project, User
from app.services import guide_recommender, project_service, winners_service

router = APIRouter(tags=["library"])


# --------------------------------------------------------------------------- #
# Research Library
# --------------------------------------------------------------------------- #


def _guide_summary(guide: guides.Guide) -> dict:
    return {
        "id": guide.id,
        "title": guide.title,
        "category": guide.category,
        "category_label": GUIDE_CATEGORY_LABELS[guide.category],
        "summary": guide.summary,
        "read_minutes": guide.read_minutes,
        "tags": guide.tags,
        "has_comparisons": bool(guide.comparisons),
    }


@router.get("/library/categories")
def library_categories(_: User = Depends(current_user)):
    return [
        {
            "key": category,
            "label": GUIDE_CATEGORY_LABELS[category],
            "guide_count": len(guides.by_category(category)),
        }
        for category in GuideCategory
    ]


@router.get("/library/guides")
def list_guides(
    _: User = Depends(current_user),
    q: str | None = Query(default=None),
    category: GuideCategory | None = Query(default=None),
    tag: str | None = Query(default=None),
):
    return [_guide_summary(g) for g in guides.search(query=q, category=category, tag=tag)]


@router.get("/library/guides/{guide_id}")
def read_guide(guide_id: str, _: User = Depends(current_user)):
    guide = guides.get(guide_id)
    if guide is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No guide with that id.")
    return {
        **_guide_summary(guide),
        "sections": [asdict(s) for s in guide.sections],
        "comparisons": [asdict(c) for c in guide.comparisons],
        "related": [
            _guide_summary(related)
            for related_id in guide.related
            if (related := guides.get(related_id)) is not None
        ],
    }


@router.get("/projects/{project_id}/recommended-guides")
def recommended_guides(
    project: Project = Depends(get_project),
    db: Session = Depends(get_db),
):
    """Guides tied to this project's weakest scored criteria.

    Resolved from ``(dimension, criterion)`` identifiers, so a reworded weakness
    message never changes which guide a student is pointed at.
    """

    evaluation = project_service.latest_evaluation(db, project.id)
    dimensions = evaluation.dimensions if evaluation else []
    return {
        "guides": guide_recommender.for_evaluation(dimensions, stage=str(project.stage)),
        "stage_guides": guide_recommender.for_stage(str(project.stage)),
        "evaluated": evaluation is not None,
    }


# --------------------------------------------------------------------------- #
# Winning Projects
# --------------------------------------------------------------------------- #


@router.get("/winning-projects")
def list_winning_projects(
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
    q: str | None = Query(default=None),
    category: str | None = Query(default=None),
    year: int | None = Query(default=None),
    competition: str | None = Query(default=None),
    project_type: str | None = Query(default=None),
    team: bool | None = Query(default=None),
    include_illustrative: bool = Query(default=True),
):
    rows = winners_service.search(
        db,
        category=category,
        year=year,
        competition=competition,
        project_type=project_type,
        team_only=team,
        include_illustrative=include_illustrative,
        query=q,
    )
    options = winners_service.filter_options(db)
    return {
        "projects": [winners_service.summary(r) for r in rows],
        "filters": options,
        "empty_notice": (
            winners_service.EMPTY_CATALOG_NOTICE if options["verified_total"] == 0 else None
        ),
        "copying_warning": winners_service.COPYING_WARNING,
    }


@router.get("/winning-projects/{winner_id}")
def read_winning_project(
    winner_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    row = db.get(WinningProject, winner_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found in the library.")
    return winners_service.breakdown(row)


@router.get("/projects/{project_id}/similar-winning-projects")
def similar_winning_projects(
    project: Project = Depends(get_project),
    db: Session = Depends(get_db),
):
    """Examples the coach can point at, with the do-not-copy warning attached."""

    return winners_service.recommend_for_project(
        db, category=str(project.category), project_type=str(project.project_type)
    )
