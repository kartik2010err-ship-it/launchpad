"""Domain vocabulary.

These enums are the shared language of the whole system: ORM models, Pydantic
schemas, the AI provider contract and the frontend all speak them. Adding a new
project stage or novelty tier happens here once.
"""

from enum import StrEnum


class Role(StrEnum):
    """How a person describes themselves at signup.

    This is a UX hint only — it changes default copy and nothing else. Every
    authorization decision in this app comes from ``WorkspaceRole`` on a
    membership row, because the same person is legitimately a student in one
    workspace and the lead of another.
    """

    STUDENT = "student"
    MENTOR = "mentor"


class WorkspaceRole(StrEnum):
    """Authority, scoped to a single workspace. The only thing authz reads."""

    OWNER = "owner"
    LEAD = "lead"
    MENTOR = "mentor"
    MEMBER = "member"


WORKSPACE_ROLE_LABELS: dict[WorkspaceRole, str] = {
    WorkspaceRole.OWNER: "Owner",
    WorkspaceRole.LEAD: "Lead",
    WorkspaceRole.MENTOR: "Mentor",
    WorkspaceRole.MEMBER: "Member",
}

# Ordered most to least authority. Used for "at least this role" checks.
WORKSPACE_ROLE_RANK: dict[WorkspaceRole, int] = {
    WorkspaceRole.OWNER: 3,
    WorkspaceRole.LEAD: 2,
    WorkspaceRole.MENTOR: 1,
    WorkspaceRole.MEMBER: 0,
}

# Roles that may see every project in the workspace regardless of visibility.
OVERSIGHT_ROLES: frozenset[WorkspaceRole] = frozenset(
    {WorkspaceRole.OWNER, WorkspaceRole.LEAD}
)


class WorkspaceType(StrEnum):
    SCHOOL = "school"
    RESEARCH_CLUB = "research_club"
    CLASSROOM = "classroom"
    SCIENCE_FAIR_TEAM = "science_fair_team"
    INDEPENDENT_GROUP = "independent_group"
    PERSONAL = "personal"


WORKSPACE_TYPE_LABELS: dict[WorkspaceType, str] = {
    WorkspaceType.SCHOOL: "School",
    WorkspaceType.RESEARCH_CLUB: "Research club",
    WorkspaceType.CLASSROOM: "Classroom",
    WorkspaceType.SCIENCE_FAIR_TEAM: "Science fair team",
    WorkspaceType.INDEPENDENT_GROUP: "Independent group",
    WorkspaceType.PERSONAL: "Personal",
}


class ProjectVisibility(StrEnum):
    """Who inside a workspace can open a project that is not their own.

    Defaults to ``PRIVATE`` because a half-finished research question is not
    something a student should have to share with thirty classmates.
    """

    PRIVATE = "private"  # owner + assigned mentor + owner/lead only
    WORKSPACE = "workspace"  # every member can read


class ProjectStatus(StrEnum):
    """How a project is tracking, derived rather than hand-set.

    The logic lives in ``app.services.project_status_service`` so the club can
    change what "at risk" means without hunting through routes and components.
    """

    ON_TRACK = "on_track"
    NEEDS_ATTENTION = "needs_attention"
    AT_RISK = "at_risk"
    BLOCKED = "blocked"
    COMPLETE = "complete"


STATUS_ORDER: list[ProjectStatus] = [
    ProjectStatus.BLOCKED,
    ProjectStatus.AT_RISK,
    ProjectStatus.NEEDS_ATTENTION,
    ProjectStatus.ON_TRACK,
    ProjectStatus.COMPLETE,
]


class CommentType(StrEnum):
    GENERAL = "general"
    NEEDS_ACTION = "needs_action"
    IMPORTANT = "important"
    RESOLVED = "resolved"


class ActivityKind(StrEnum):
    """Coarse buckets so the club-wide feed can be filtered without parsing text."""

    MILESTONE = "milestone"
    COMMENT = "comment"
    PROJECT_CHANGE = "project_change"
    OVERDUE = "overdue"


class ProjectType(StrEnum):
    SCIENTIFIC = "scientific"
    ENGINEERING = "engineering"


class Category(StrEnum):
    COMPUTER_SCIENCE = "computer_science"
    BIOMEDICAL = "biomedical_science"
    ENVIRONMENTAL = "environmental_science"
    PHYSICS = "physics"
    CHEMISTRY = "chemistry"
    ENGINEERING = "engineering"
    BEHAVIORAL_SOCIAL = "behavioral_social_science"
    MATHEMATICS = "mathematics"
    OTHER = "other"


class Stage(StrEnum):
    IDEA = "idea"
    QUESTION_REFINEMENT = "question_refinement"
    BACKGROUND_RESEARCH = "background_research"
    EXPERIMENTAL_DESIGN = "experimental_design"
    APPROVAL_REQUIRED = "approval_required"
    EXPERIMENTATION = "experimentation"
    DATA_ANALYSIS = "data_analysis"
    POSTER = "poster"
    INTERVIEW_PREP = "interview_preparation"
    COMPLETE = "complete"


STAGE_ORDER: list[Stage] = list(Stage)


class EvidenceBasis(StrEnum):
    """How much a score can honestly be trusted at this point in the project."""

    CURRENT_EVIDENCE = "current_evidence"
    PROJECTED_POTENTIAL = "projected_potential"
    NOT_YET_ASSESSABLE = "not_yet_assessable"


class NoveltyStatus(StrEnum):
    LIKELY_COMMON = "likely_common"
    INCREMENTAL = "incremental"
    MODERATELY_DIFFERENTIATED = "moderately_differentiated"
    POTENTIALLY_NOVEL = "potentially_novel"
    STRONG_RESEARCH_GAP = "strong_research_gap_potential"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class TaskStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    NEEDS_MENTOR_REVIEW = "needs_mentor_review"
    COMPLETE = "complete"


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RequirementSource(StrEnum):
    """Section 16: never blur official rules with our own suggestions."""

    VERIFIED_COMPETITION_REQUIREMENT = "verified_competition_requirement"
    UNVERIFIED_COMPETITION_ITEM = "unverified_competition_item"
    RECOMMENDED_CLUB_MILESTONE = "recommended_club_milestone"


class Phase(StrEnum):
    IDEA = "idea_and_research_question"
    RULES = "rules_and_approval"
    DESIGN = "experimental_design"
    EXPERIMENTATION = "experimentation"
    ANALYSIS = "analysis"
    WRITE_UP = "final_research_materials"
    POSTER = "poster"
    INTERVIEW = "interview_preparation"
    COMPETITION = "competition"


PHASE_ORDER: list[Phase] = list(Phase)

PHASE_LABELS: dict[Phase, str] = {
    Phase.IDEA: "Idea & research question",
    Phase.RULES: "Rules & approval",
    Phase.DESIGN: "Experimental design",
    Phase.EXPERIMENTATION: "Experimentation",
    Phase.ANALYSIS: "Analysis",
    Phase.WRITE_UP: "Final research materials",
    Phase.POSTER: "Poster",
    Phase.INTERVIEW: "Interview preparation",
    Phase.COMPETITION: "Competition",
}
