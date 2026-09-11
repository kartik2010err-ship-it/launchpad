"""Wire contracts for the Research Assistant.

``AssistantReply`` is the important one: it is the provider contract. Both the
heuristic and the hosted provider must return exactly this shape, so the chat UI
renders identically whether or not an API key is configured, and a hosted reply
that fails validation can be discarded in favour of the offline one.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AssistantReply(BaseModel):
    """One assistant turn, structured so the UI can render more than prose."""

    reply: str = Field(description="The mentor's answer. Markdown-light prose.")
    follow_ups: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="Questions back to the student, offered as one-tap replies.",
    )
    guide_ids: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="Research Library guide ids to recommend. Ids only, never URLs.",
    )


class GuideReference(BaseModel):
    """A resolved guide, built from an id at render time."""

    guide_id: str
    title: str
    category: str
    summary: str
    read_minutes: int


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    follow_ups: list[str] = Field(default_factory=list)
    provider: str | None = None
    created_at: datetime
    guides: list[GuideReference] = Field(default_factory=list)


class ConversationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    project_id: int | None = None
    project_title: str | None = None
    shared_with_team: bool = False
    message_count: int = 0
    last_message_preview: str | None = None
    updated_at: datetime


class ProjectContextOut(BaseModel):
    """What the assistant already knows, shown to the student as a chip row.

    Section 11: a student should never have to re-explain their project, and
    should be able to see exactly what was handed over.
    """

    project_id: int
    title: str
    question: str
    project_type: str
    category: str
    grade_level: int
    stage: str
    competition: str | None = None
    readiness: int | None = None
    answered_count: int = 0
    total_questions: int = 0
    known_fields: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    safety_flags: list[str] = Field(default_factory=list)
    next_deadline: str | None = None


class ConversationDetail(BaseModel):
    id: int
    title: str
    project_id: int | None = None
    shared_with_team: bool = False
    created_at: datetime
    updated_at: datetime
    messages: list[MessageOut] = Field(default_factory=list)
    context: ProjectContextOut | None = None
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)


class SuggestedAction(BaseModel):
    """Section 13's one-tap starters."""

    key: str
    label: str
    prompt: str


class NewConversationIn(BaseModel):
    project_id: int | None = None
    title: str | None = None


class SendMessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class ShareIn(BaseModel):
    shared_with_team: bool


ConversationDetail.model_rebuild()
