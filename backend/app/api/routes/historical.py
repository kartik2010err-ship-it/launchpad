"""ISEF Project Explorer API (sections 22-30).

Reads are open to any signed-in user; the catalogue is reference material.
Writes are not: importing a project means asserting it is permitted to be
stored, so every write requires a ``permission_note`` and is restricted to
workspace oversight. Section 38's "historical catalogue is read-only to
ordinary users" is enforced here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.db.session import get_db
from app.models.enums import WorkspaceRole
from app.models.historical import HistoricalProject
from app.models.project import Project, User
from app.models.workspace_org import Workspace, WorkspaceMembership
from app.schemas.historical import (
    AIAnalysis,
    CatalogueFacets,
    CsvImportIn,
    HistoricalProjectCard,
    HistoricalProjectDetail,
    HistoricalSearchResult,
    ImportReportOut,
    ManualProjectIn,
    SimilarMatch,
    SimilarResult,
    SourceInformation,
)
from app.services import historical_import, historical_service, workspace_service

router = APIRouter(prefix="/historical-projects", tags=["historical projects"])


def _require_curator(db: Session, user: User) -> None:
    """Importing asserts a right to store someone else's material.

    That is a judgement a person makes and signs their name to, so it is limited
    to people who hold oversight in at least one workspace rather than offered
    to every student account.
    """

    # Every account owns a personal workspace, so membership role alone is not
    # a privilege signal — it would make every student a curator. Only a shared
    # workspace counts.
    holds_oversight = db.scalars(
        select(WorkspaceMembership)
        .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
        .where(
            WorkspaceMembership.user_id == user.id,
            WorkspaceMembership.role.in_([WorkspaceRole.OWNER, WorkspaceRole.LEAD]),
            Workspace.is_personal.is_(False),
        )
    ).first()
    if holds_oversight is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only a workspace owner or lead can add projects to the catalogue.",
        )


def _card(db: Session, row: HistoricalProject) -> HistoricalProjectCard:
    return HistoricalProjectCard(
        id=row.id,
        title=row.title,
        year=row.year,
        category=row.category,
        team_project=row.team_project,
        awards=row.awards,
        has_abstract=row.has_abstract,
        source=row.source,
        derived_tags=historical_service.tags_for(db, row.id)["derived"],
    )


# --------------------------------------------------------------------------- #
# Browse
# --------------------------------------------------------------------------- #


@router.get("", response_model=HistoricalSearchResult)
def search_catalogue(
    q: str | None = Query(default=None),
    category: str | None = Query(default=None),
    year: int | None = Query(default=None),
    team: bool | None = Query(default=None),
    awarded: bool = Query(default=False),
    tag: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> HistoricalSearchResult:
    rows, total = historical_service.search(
        db,
        query=q,
        category=category,
        year=year,
        team_only=team,
        awarded_only=awarded,
        tag=tag,
        limit=limit,
        offset=offset,
    )
    return HistoricalSearchResult(
        results=[_card(db, row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
        copying_notice=historical_service.COPYING_NOTICE,
    )


@router.get("/facets", response_model=CatalogueFacets)
def catalogue_facets(
    db: Session = Depends(get_db), user: User = Depends(current_user)
) -> CatalogueFacets:
    return CatalogueFacets(**historical_service.facets(db))


@router.get("/{historical_id}", response_model=HistoricalProjectDetail)
def read_historical_project(
    historical_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> HistoricalProjectDetail:
    row = db.get(HistoricalProject, historical_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That project is not in the catalogue.")

    tags = historical_service.tags_for(db, row.id)
    analysis = row.analysis
    reason = None
    if analysis is None:
        if not row.has_abstract:
            reason = (
                "This record has no abstract, so there is nothing to analyse. Rather than "
                "guess from the title, the app shows you nothing."
            )
        else:
            analysis = historical_service.build_analysis(db, row)
            db.commit()

    return HistoricalProjectDetail(
        id=row.id,
        source_information=SourceInformation.model_validate(row),
        source_categories=tags["source"],
        derived_tags=tags["derived"],
        ai_analysis=AIAnalysis.model_validate(analysis) if analysis else None,
        analysis_unavailable_reason=reason,
        copying_notice=historical_service.COPYING_NOTICE,
    )


# --------------------------------------------------------------------------- #
# Relate to the student's own project (section 26)
# --------------------------------------------------------------------------- #


@router.get("/for-project/{project_id}/similar", response_model=SimilarResult)
def similar_for_project(
    project_id: int,
    limit: int = Query(default=6, ge=1, le=20),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> SimilarResult:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found.")
    membership = workspace_service.membership_for(db, project.workspace_id, user.id)
    if membership is None or not workspace_service.can_view_project(db, project, membership):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found.")

    result = historical_service.similar_to_project(db, project, limit=limit)
    return SimilarResult(
        matches=[
            SimilarMatch(
                project=_card(db, match["project"]),
                score=match["score"],
                reasons=match["reasons"],
            )
            for match in result["matches"]
        ],
        matched_on=result["matched_on"],
        empty_notice=result["empty_notice"],
        copying_notice=result["copying_notice"],
    )


# --------------------------------------------------------------------------- #
# Import (sections 19-21)
# --------------------------------------------------------------------------- #


@router.post("/import/manual", response_model=ImportReportOut, status_code=status.HTTP_201_CREATED)
def import_one(
    payload: ManualProjectIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ImportReportOut:
    _require_curator(db, user)
    record = historical_import.NormalisedRecord(
        source=payload.source,
        source_project_id=payload.source_project_id
        or historical_import.derive_id(payload.source, payload.title, payload.year),
        **payload.model_dump(
            exclude={"source", "source_project_id"},
        ),
    )
    report = historical_import.import_records(db, [record])
    return ImportReportOut(**report.as_dict())


@router.post("/import/csv", response_model=ImportReportOut)
def import_csv(
    payload: CsvImportIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ImportReportOut:
    """Bulk import from a file the caller is permitted to store.

    Re-running the same file updates rather than duplicates, so a corrected
    spreadsheet can simply be imported again.
    """

    _require_curator(db, user)
    source = historical_import.CsvSource(
        payload.csv_text, source=payload.source, permission_note=payload.permission_note
    )
    try:
        records = list(source.fetch())
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    report = historical_import.import_records(db, records)
    return ImportReportOut(**report.as_dict())
