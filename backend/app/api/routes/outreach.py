"""Research Outreach: templates, the email builder, and the outreach tracker.

Every row here belongs to one student. There is no route that lets a workspace
lead read someone's correspondence, and the queries are filtered by
``user_id == caller`` rather than by any role check, so there is no privilege
level that could widen them by accident.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.db.session import get_db
from app.models.enums import OUTREACH_STATUS_LABELS, OutreachStatus
from app.models.outreach import OutreachContact
from app.models.project import Project, User
from app.services import outreach_service, workspace_service

router = APIRouter(prefix="/outreach", tags=["outreach"])


class DraftRequest(BaseModel):
    template_key: str
    researcher_name: str = Field(min_length=2, max_length=160)
    their_work: str = Field(min_length=1)
    specific_request: str = Field(min_length=1)
    research_topic: str = Field(min_length=2)
    research_question: str | None = None
    timeline: str | None = None
    school: str | None = None
    grade_level: int | None = None
    original_subject: str | None = None


class ContactCreate(BaseModel):
    researcher_name: str = Field(min_length=2, max_length=160)
    institution: str | None = None
    email: str | None = None
    their_work: str | None = None
    project_id: int | None = None
    template_key: str | None = None
    subject: str | None = None
    body: str | None = None
    status: OutreachStatus = OutreachStatus.DRAFT
    sent_on: date | None = None
    follow_up_on: date | None = None
    notes: str | None = None


class ContactUpdate(BaseModel):
    researcher_name: str | None = None
    institution: str | None = None
    email: str | None = None
    their_work: str | None = None
    template_key: str | None = None
    subject: str | None = None
    body: str | None = None
    status: OutreachStatus | None = None
    sent_on: date | None = None
    follow_up_on: date | None = None
    follow_up_done: bool | None = None
    notes: str | None = None


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    researcher_name: str
    institution: str | None
    email: str | None
    their_work: str | None
    project_id: int | None
    template_key: str | None
    subject: str | None
    body: str | None
    status: OutreachStatus
    status_label: str = ""
    sent_on: date | None
    follow_up_on: date | None
    follow_up_done: bool
    follow_up_due: bool = False
    notes: str | None


def _out(row: OutreachContact, today: date | None = None) -> dict:
    today = today or date.today()
    return {
        "id": row.id,
        "researcher_name": row.researcher_name,
        "institution": row.institution,
        "email": row.email,
        "their_work": row.their_work,
        "project_id": row.project_id,
        "template_key": row.template_key,
        "subject": row.subject,
        "body": row.body,
        "status": row.status,
        "status_label": OUTREACH_STATUS_LABELS.get(row.status, str(row.status)),
        "sent_on": row.sent_on,
        "follow_up_on": row.follow_up_on,
        "follow_up_done": row.follow_up_done,
        "follow_up_due": (
            row.status == OutreachStatus.SENT
            and not row.follow_up_done
            and row.follow_up_on is not None
            and row.follow_up_on <= today
        ),
        "notes": row.notes,
    }


def _owned_or_404(db: Session, contact_id: int, user: User) -> OutreachContact:
    row = db.get(OutreachContact, contact_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Outreach record not found.")
    return row


@router.get("/templates")
def templates(_: User = Depends(current_user)):
    return {
        "templates": outreach_service.listing(),
        "spam_warning": outreach_service.SPAM_WARNING,
        "etiquette": outreach_service.ETIQUETTE,
    }


@router.post("/draft")
def build_draft(
    payload: DraftRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Generate a draft from the student's own answers.

    Refuses when the message would be generic — see ``outreach_service``.
    """

    try:
        return outreach_service.build_draft(
            template_key=payload.template_key,
            student_name=user.name,
            school=payload.school or user.school or "my school",
            grade_level=payload.grade_level or user.grade_level or "high school",
            research_topic=payload.research_topic,
            research_question=payload.research_question,
            researcher_name=payload.researcher_name,
            their_work=payload.their_work,
            specific_request=payload.specific_request,
            timeline=payload.timeline,
            original_subject=payload.original_subject,
        )
    except outreach_service.DraftError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.get("/contacts", response_model=list[ContactOut])
def list_contacts(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.scalars(
        select(OutreachContact)
        .where(OutreachContact.user_id == user.id)
        .order_by(OutreachContact.created_at.desc())
    )
    return [_out(row) for row in rows]


@router.post("/contacts", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
def create_contact(
    payload: ContactCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if payload.project_id is not None:
        project = db.get(Project, payload.project_id)
        membership = (
            workspace_service.membership_for(db, project.workspace_id, user.id)
            if project
            else None
        )
        if project is None or not workspace_service.can_view_project(db, project, membership):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found.")

    row = OutreachContact(
        user_id=user.id,
        **payload.model_dump(exclude={"status"}),
        status=payload.status,
    )
    if row.sent_on and row.follow_up_on is None:
        row.follow_up_on = outreach_service.suggested_follow_up(row.sent_on)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _out(row)


@router.patch("/contacts/{contact_id}", response_model=ContactOut)
def update_contact(
    contact_id: int,
    payload: ContactUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    row = _owned_or_404(db, contact_id, user)
    fields = payload.model_dump(exclude_unset=True)
    for field, value in fields.items():
        setattr(row, field, value)
    # Marking something sent schedules the single follow-up, unless the student
    # has already chosen a date.
    if fields.get("status") == OutreachStatus.SENT:
        if row.sent_on is None:
            row.sent_on = date.today()
        if row.follow_up_on is None:
            row.follow_up_on = outreach_service.suggested_follow_up(row.sent_on)
    db.commit()
    db.refresh(row)
    return _out(row)


@router.delete("/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    db.delete(_owned_or_404(db, contact_id, user))
    db.commit()


@router.get("/summary")
def summary(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = list(
        db.scalars(select(OutreachContact).where(OutreachContact.user_id == user.id))
    )
    counts = {status_value: 0 for status_value in OutreachStatus}
    for row in rows:
        counts[row.status] = counts.get(row.status, 0) + 1
    due = outreach_service.follow_ups_due(rows)
    return {
        "total": len(rows),
        "by_status": [
            {"status": key, "label": OUTREACH_STATUS_LABELS[key], "count": value}
            for key, value in counts.items()
        ],
        "follow_ups_due": [_out(r) for r in rows if r.id in due],
        "spam_warning": outreach_service.SPAM_WARNING,
    }
