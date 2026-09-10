"""The Research Assistant API (sections 11-15, 37).

Every handler here is thin. Context assembly lives in
``app.services.assistant_context``, the mentor logic in
``app.services.research_assistant_service``, and the model call behind the
provider seam — section 36's rule that no route handler talks to an LLM.

Privacy is enforced by ``_owned`` and ``_readable``. Note what is *absent*:
there is no oversight path. A workspace owner cannot open a student's
conversation from here, by design.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.db.session import get_db
from app.models.assistant import AIConversation
from app.models.project import Project, User
from app.schemas.assistant import (
    ConversationDetail,
    ConversationSummary,
    MessageOut,
    NewConversationIn,
    ProjectContextOut,
    SendMessageIn,
    ShareIn,
    SuggestedAction,
)
from app.services import assistant_context, research_assistant_service, workspace_service

router = APIRouter(prefix="/assistant", tags=["assistant"])


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _viewable_project(db: Session, project_id: int, user: User) -> Project:
    """A project the caller may read. 404 rather than 403 for a stranger."""

    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found.")
    membership = workspace_service.membership_for(db, project.workspace_id, user.id)
    if membership is None or not workspace_service.can_view_project(db, project, membership):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found.")
    return project


def _readable(db: Session, conversation_id: int, user: User) -> AIConversation:
    conversation = db.get(AIConversation, conversation_id)
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found.")
    if not research_assistant_service.can_read(db, conversation, user):
        # 404, not 403: a conversation id should not be probeable.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found.")
    return conversation


def _owned(db: Session, conversation_id: int, user: User) -> AIConversation:
    conversation = _readable(db, conversation_id, user)
    if not research_assistant_service.can_write(conversation, user):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This conversation belongs to another student. You can read it, not add to it.",
        )
    return conversation


def _project_of(db: Session, conversation: AIConversation, user: User) -> Project | None:
    if conversation.project_id is None:
        return None
    return _viewable_project(db, conversation.project_id, user)


# --------------------------------------------------------------------------- #
# Conversations
# --------------------------------------------------------------------------- #


@router.get("/conversations", response_model=list[ConversationSummary])
def list_conversations(
    project_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[ConversationSummary]:
    """The caller's own conversations. Never anyone else's, shared or not."""

    if project_id is not None:
        _viewable_project(db, project_id, user)
    return [
        ConversationSummary(**row)
        for row in research_assistant_service.list_for_user(db, user, project_id)
    ]


@router.post(
    "/conversations", response_model=ConversationDetail, status_code=status.HTTP_201_CREATED
)
def create_conversation(
    payload: NewConversationIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ConversationDetail:
    project = None
    if payload.project_id is not None:
        project = _viewable_project(db, payload.project_id, user)
    conversation = research_assistant_service.create(
        db, user, project_id=payload.project_id, title=payload.title
    )
    return _detail(db, conversation, project)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def read_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ConversationDetail:
    conversation = _readable(db, conversation_id, user)
    return _detail(db, conversation, _project_of(db, conversation, user))


@router.post("/conversations/{conversation_id}/messages", response_model=MessageOut)
def send_message(
    conversation_id: int,
    payload: SendMessageIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> MessageOut:
    conversation = _owned(db, conversation_id, user)
    project = _project_of(db, conversation, user)
    reply = research_assistant_service.send(db, conversation, project, payload.content)
    return MessageOut(
        id=reply.id,
        role=reply.role,
        content=reply.content,
        follow_ups=reply.follow_ups or [],
        provider=reply.provider,
        created_at=reply.created_at,
        guides=research_assistant_service.resolve_guides(reply.guide_ids or []),
    )


@router.patch("/conversations/{conversation_id}/share", response_model=ConversationDetail)
def set_sharing(
    conversation_id: int,
    payload: ShareIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ConversationDetail:
    conversation = _owned(db, conversation_id, user)
    if payload.shared_with_team and conversation.project_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "A conversation with no project attached has no team to share it with.",
        )
    conversation = research_assistant_service.set_shared(db, conversation, payload.shared_with_team)
    return _detail(db, conversation, _project_of(db, conversation, user))


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Response:
    conversation = _owned(db, conversation_id, user)
    research_assistant_service.delete(db, conversation)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- #
# Context preview
# --------------------------------------------------------------------------- #


@router.get("/projects/{project_id}/context", response_model=ProjectContextOut)
def project_context(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ProjectContextOut:
    """What the assistant will be told. Shown to the student before they ask."""

    project = _viewable_project(db, project_id, user)
    context = assistant_context.build(db, project)
    return ProjectContextOut(**assistant_context.summarise_for_ui(context))


@router.get("/suggested-actions", response_model=list[SuggestedAction])
def suggested_actions() -> list[SuggestedAction]:
    return research_assistant_service.SUGGESTED_ACTIONS


# --------------------------------------------------------------------------- #
# Shared assembly
# --------------------------------------------------------------------------- #


def _detail(
    db: Session, conversation: AIConversation, project: Project | None
) -> ConversationDetail:
    context = None
    if project is not None:
        context = ProjectContextOut(
            **assistant_context.summarise_for_ui(assistant_context.build(db, project))
        )
    return ConversationDetail(
        id=conversation.id,
        title=conversation.title,
        project_id=conversation.project_id,
        shared_with_team=conversation.shared_with_team,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[
            MessageOut(**row)
            for row in research_assistant_service.messages_payload(conversation)
        ],
        context=context,
        suggested_actions=research_assistant_service.SUGGESTED_ACTIONS,
    )
