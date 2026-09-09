"""Competition registry (section 16).

Competitions are data, not code. Adding one means appending a dict here or
loading a JSON file at startup; no UI changes.

Every item carries a ``source``. The app ships with **no verified requirements**
because it has not loaded any official rulebook. Items that are widely
understood to apply are marked ``unverified_competition_item`` and rendered with
a "confirm this" warning; everything the club invented is marked
``recommended_club_milestone``. Nothing is ever presented as an official
requirement on the strength of the model's memory.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.enums import RequirementSource

UNVERIFIED_NOTICE = (
    "Research Coach has not loaded official requirements for this competition. Items below are "
    "starting points only — confirm every deadline, form and display rule on the official "
    "competition website or with your advisor before you rely on them."
)


@dataclass
class CompetitionItem:
    key: str
    label: str
    source: RequirementSource
    days_before_fair: int | None = None
    note: str = ""


@dataclass
class Competition:
    key: str
    name: str
    official_source_loaded: bool
    items: list[CompetitionItem] = field(default_factory=list)
    notice: str = UNVERIFIED_NOTICE


_COMMON_UNVERIFIED = [
    CompetitionItem("registration", "Registration / entry submitted", RequirementSource.UNVERIFIED_COMPETITION_ITEM, 45,
                    "Registration windows close earlier than students expect. Check the exact date."),
    CompetitionItem("forms", "Required forms identified and signed", RequirementSource.UNVERIFIED_COMPETITION_ITEM, 60,
                    "Which forms apply depends on your project classification. Ask your SRC."),
    CompetitionItem("research_plan", "Research plan approved before experimentation", RequirementSource.UNVERIFIED_COMPETITION_ITEM, 70,
                    "Regulated projects generally must be approved before any data are collected."),
    CompetitionItem("abstract", "Abstract submitted", RequirementSource.UNVERIFIED_COMPETITION_ITEM, 21,
                    "Word limits and submission portals vary. Confirm both."),
    CompetitionItem("display", "Display and safety rules checked", RequirementSource.UNVERIFIED_COMPETITION_ITEM, 14,
                    "Board dimensions and prohibited display items are competition-specific."),
    CompetitionItem("interview", "Judging interview", RequirementSource.UNVERIFIED_COMPETITION_ITEM, 0, ""),
]

_CLUB_MILESTONES = [
    CompetitionItem("club_question_review", "Research question reviewed by a club mentor", RequirementSource.RECOMMENDED_CLUB_MILESTONE, 80),
    CompetitionItem("club_pilot", "Pilot trial completed and reviewed", RequirementSource.RECOMMENDED_CLUB_MILESTONE, 55),
    CompetitionItem("club_data_check", "Data collection checkpoint with mentor", RequirementSource.RECOMMENDED_CLUB_MILESTONE, 35),
    CompetitionItem("club_poster_review", "Poster draft reviewed by the club", RequirementSource.RECOMMENDED_CLUB_MILESTONE, 12),
    CompetitionItem("club_mock_judging", "Mock judging session with the club", RequirementSource.RECOMMENDED_CLUB_MILESTONE, 7),
]


REGISTRY: dict[str, Competition] = {
    "azsef": Competition(
        key="azsef",
        name="Arizona Science and Engineering Fair (AzSEF)",
        official_source_loaded=False,
        items=_COMMON_UNVERIFIED + _CLUB_MILESTONES,
    ),
    "isef_style": Competition(
        key="isef_style",
        name="ISEF-affiliated regional or state fair",
        official_source_loaded=False,
        items=_COMMON_UNVERIFIED + _CLUB_MILESTONES,
    ),
    "school": Competition(
        key="school",
        name="School science fair",
        official_source_loaded=False,
        items=[
            CompetitionItem("school_signup", "Sign-up submitted to the school coordinator", RequirementSource.UNVERIFIED_COMPETITION_ITEM, 30),
            CompetitionItem("school_approval", "Teacher or sponsor approval of the research plan", RequirementSource.UNVERIFIED_COMPETITION_ITEM, 45),
            CompetitionItem("school_display", "Board size and display rules checked", RequirementSource.UNVERIFIED_COMPETITION_ITEM, 10),
        ] + _CLUB_MILESTONES,
    ),
    "custom": Competition(
        key="custom",
        name="Custom competition",
        official_source_loaded=False,
        items=_CLUB_MILESTONES,
        notice=(
            "You have entered a competition Research Coach knows nothing about. Every requirement "
            "here is a club milestone we made up. Add the real deadlines yourself from the official "
            "rules."
        ),
    ),
}


def get(key: str) -> Competition:
    return REGISTRY.get(key, REGISTRY["custom"])


def listing() -> list[dict]:
    return [
        {
            "key": c.key,
            "name": c.name,
            "official_source_loaded": c.official_source_loaded,
            "notice": c.notice,
            "item_count": len(c.items),
        }
        for c in REGISTRY.values()
    ]
