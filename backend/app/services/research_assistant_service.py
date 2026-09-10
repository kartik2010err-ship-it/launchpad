"""The Research Assistant's application layer (sections 11-15, 36-37).

Routes talk to this module; this module talks to the provider. No route handler
anywhere in the codebase constructs a prompt or calls an LLM directly.

The authorization rule implemented here is stricter than the rest of the app on
purpose. Everywhere else, a workspace OWNER or LEAD can see any project — that is
oversight, and it is correct. A conversation with the assistant is not part of
the project. It is a student thinking, and a student who believes their teacher
is reading their questions stops asking the useful ones. So:

    a conversation is readable by its author, and by nobody else,
    unless the author has explicitly shared it with their team.

Oversight roles get no special path in. That is deliberate and tested.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.content import guides
from app.models.assistant import AIConversation, AIMessage
from app.models.project import Project, User
from app.schemas.assistant import AssistantReply, SuggestedAction
from app.services import assistant_context, team_service
from app.services.ai.factory import get_provider

# Section 13. Prompts are written as the student would say them, so the
# transcript reads like a conversation rather than a menu selection.
SUGGESTED_ACTIONS: list[SuggestedAction] = [
    SuggestedAction(
        key="next_step",
        label="What should I do next?",
        prompt="What should I do next on this project?",
    ),
    SuggestedAction(
        key="review_question",
        label="Review my question",
        prompt="Is my research question specific and measurable enough? What's weak about it?",
    ),
    SuggestedAction(
        key="challenge_method",
        label="Challenge my methodology",
        prompt="Challenge my methodology. What would you attack if you were a judge?",
    ),
    SuggestedAction(
        key="check_variables",
        label="Check my variables",
        prompt="Are my independent, dependent and controlled variables properly defined?",
    ),
    SuggestedAction(
        key="explain_stats",
        label="Explain my statistics",
        prompt="What statistical test fits my data, and what would significance actually mean here?",
    ),
    SuggestedAction(
        key="find_weaknesses",
        label="Find weaknesses",
        prompt="What are the weaknesses in my project right now?",
    ),
    SuggestedAction(
        key="judge_questions",
        label="Ask me judge questions",
        prompt="What would a judge ask me about this project?",
    ),
    SuggestedAction(
        key="explain_back",
        label="Explain my methodology back to me",
        prompt="Explain my methodology back to me so I can check you understood it.",
    ),
]

_TITLE_CHARS = 60


# --------------------------------------------------------------------------- #
# Authorization
# --------------------------------------------------------------------------- #


def can_read(db: Session, conversation: AIConversation, user: User) -> bool:
    """Private by default. Oversight roles are deliberately not a way in."""

    if conversation.user_id == user.id:
        return True
    if not conversation.shared_with_team or conversation.project_id is None:
        return False
    project = db.get(Project, conversation.project_id)
    if project is None:
        return False
    # A shared thread is visible to the people who share the project itself:
    # the team, or the individual owner. Not the workspace at large.
    if getattr(project, "owner_team_id", None):
        return team_service.is_team_member(db, project.owner_team_id, user.id)
    return project.owner_id == user.id


def can_write(conversation: AIConversation, user: User) -> bool:
    """Only the author adds turns, even to a shared thread.

    A shared conversation is a transcript others may read, not a group chat: two
    students interleaving turns would produce a history the model cannot
    attribute, and one student's mentoring would silently become another's.
    """

    return conversation.user_id == user.id


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #


def list_for_user(
    db: Session, user: User, project_id: int | None = None, limit: int = 50
) -> list[dict]:
    stmt = select(AIConversation).where(AIConversation.user_id == user.id)
    if project_id is not None:
        stmt = stmt.where(AIConversation.project_id == project_id)
    rows = db.scalars(stmt.order_by(AIConversation.updated_at.desc()).limit(limit)).all()

    if not rows:
        return []

    ids = [row.id for row in rows]
    counts = dict(
        db.execute(
            select(AIMessage.conversation_id, func.count(AIMessage.id))
            .where(AIMessage.conversation_id.in_(ids))
            .group_by(AIMessage.conversation_id)
        ).all()
    )
    titles = dict(
        db.execute(
            select(Project.id, Project.title).where(
                Project.id.in_([r.project_id for r in rows if r.project_id])
            )
        ).all()
    )

    out: list[dict] = []
    for row in rows:
        last = row.messages[-1] if row.messages else None
        out.append(
            {
                "id": row.id,
                "title": row.title,
                "project_id": row.project_id,
                "project_title": titles.get(row.project_id),
                "shared_with_team": row.shared_with_team,
                "message_count": counts.get(row.id, 0),
                "last_message_preview": _clip(last.content, 120) if last else None,
                "updated_at": row.updated_at,
            }
        )
    return out


def messages_payload(conversation: AIConversation) -> list[dict]:
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "follow_ups": m.follow_ups or [],
            "provider": m.provider,
            "created_at": m.created_at,
            "guides": resolve_guides(m.guide_ids or []),
        }
        for m in conversation.messages
    ]


def resolve_guides(guide_ids: list[str]) -> list[dict]:
    """Ids to guide cards. An id with no matching guide is dropped, not faked."""

    out: list[dict] = []
    for guide_id in guide_ids:
        guide = guides.get(guide_id)
        if guide is None:
            continue
        out.append(
            {
                "guide_id": guide.id,
                "title": guide.title,
                "category": str(guide.category),
                "summary": guide.summary,
                "read_minutes": guide.read_minutes,
            }
        )
    return out


# --------------------------------------------------------------------------- #
# Writes
# --------------------------------------------------------------------------- #


def create(
    db: Session, user: User, project_id: int | None = None, title: str | None = None
) -> AIConversation:
    conversation = AIConversation(
        user_id=user.id,
        project_id=project_id,
        title=title or "New conversation",
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def send(
    db: Session, conversation: AIConversation, project: Project | None, message: str
) -> AIMessage:
    """Persist the student's turn, generate the reply, persist that too."""

    context = assistant_context.build(db, project) if project is not None else None
    history = [
        {"role": m.role, "content": m.content} for m in conversation.messages
    ]

    db.add(
        AIMessage(conversation_id=conversation.id, role="user", content=message.strip())
    )

    provider = get_provider()
    try:
        result: AssistantReply = provider.assistant_reply(message, context, history)
    except Exception:  # noqa: BLE001 — a provider fault must not lose the student's turn
        from app.services.ai import assistant_heuristic

        result = assistant_heuristic.reply(message, context, history)

    # Drop any guide id the model invented rather than rendering a dead card.
    valid_ids = [gid for gid in (result.guide_ids or []) if guides.get(gid) is not None]

    reply_row = AIMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=result.reply,
        follow_ups=list(result.follow_ups or []),
        guide_ids=valid_ids,
        provider=getattr(provider, "name", None),
    )
    db.add(reply_row)

    if conversation.title == "New conversation":
        conversation.title = _clip(message, _TITLE_CHARS) or "New conversation"
    db.add(conversation)
    db.commit()
    db.refresh(reply_row)
    return reply_row


def set_shared(db: Session, conversation: AIConversation, shared: bool) -> AIConversation:
    conversation.shared_with_team = shared
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def delete(db: Session, conversation: AIConversation) -> None:
    db.delete(conversation)
    db.commit()


def _clip(text: str | None, limit: int) -> str | None:
    value = (text or "").strip().replace("\n", " ")
    if not value:
        return None
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"
