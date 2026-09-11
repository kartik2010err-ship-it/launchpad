"""The single answer to "what should I do next?" (section 35).

This exists so that the Home dashboard, the Research Assistant and any future
surface all give the *same* recommendation. Two implementations would diverge
within a month and a student would be told two different things on two screens.

The rule is one primary action and at most two secondary ones. A project has
dozens of unfinished things at any moment; listing them is not advice, it is a
backlog, and a backlog is what a stuck student already has.

Priority order, highest first:

1. A safety or approval flag. Nothing downstream legitimately proceeds.
2. A structural hole in the science — no control, no measurable outcome, no
   mechanism, no prior work, no stated differentiator.
3. A missing interview answer, which is what makes the scores unreliable.
4. Whatever the current stage says to do.

Deadlines never become the primary action. A deadline is a constraint on when,
not an answer to what.
"""

from __future__ import annotations

from app.services.guide_recommender import STAGE_GUIDES

# Structural gaps, in the order they block the work.
GAP_ORDER: list[str] = [
    "control_defined",
    "quantitative_outcome",
    "mechanism_explained",
    "literature_grounded",
    "differentiator_stated",
]

GAP_ACTION: dict[str, str] = {
    "control_defined": (
        "define your control — the version of the experiment where the thing you are testing "
        "is not applied"
    ),
    "quantitative_outcome": (
        "state your outcome as something you record as a number, with a unit"
    ),
    "mechanism_explained": (
        "write down why you expect what you expect — the mechanism, not just the prediction"
    ),
    "literature_grounded": (
        "find and log the closest existing studies, because novelty cannot be assessed without them"
    ),
    "differentiator_stated": (
        "write one sentence on what your version does that the existing work does not"
    ),
}

GAP_WHY: dict[str, str] = {
    "control_defined": "Without it, every result you get has an obvious alternative explanation.",
    "quantitative_outcome": "An outcome with no unit cannot be analysed, graphed or defended.",
    "mechanism_explained": "This is the first thing a judge asks after your result.",
    "literature_grounded": "You cannot claim anything is new against work you have not read.",
    "differentiator_stated": "This is the sentence that answers 'why does this project exist?'",
}

GAP_GUIDES: dict[str, list[str]] = {
    "control_defined": ["choosing-a-control-group", "designing-a-controlled-experiment"],
    "quantitative_outcome": ["measurable-variables", "independent-dependent-variables"],
    "mechanism_explained": ["writing-a-hypothesis"],
    "literature_grounded": ["finding-credible-sources", "literature-review"],
    "differentiator_stated": ["explaining-novelty", "determining-novelty"],
}

STAGE_ACTION: dict[str, str] = {
    "idea": "narrow your topic to one thing you could actually measure",
    "question_refinement": "tighten your question until it names a population, a variable and a unit",
    "background_research": "find three relevant peer-reviewed papers and log what each one found",
    "experimental_design": "write your procedure so someone else could repeat it without asking you",
    "approval_required": "complete the approval forms — nothing downstream can legitimately start first",
    "experimentation": "run the next block of trials and write the notebook entry the same day",
    "data_analysis": "describe the data before testing it: means, spread, and a plot",
    "poster": "build the figures first; the text exists to explain them",
    "interview_preparation": "practise defending your choices, not reciting your results",
    "complete": "write your limitations honestly — it is what makes the rest credible",
}


def _primary_from_gaps(derived: dict) -> str | None:
    for key in GAP_ORDER:
        if key in derived and not derived[key]:
            return key
    return None


def compute(context: dict | None) -> dict:
    """One primary action, up to two secondary. Never a task list."""

    if not context:
        return {
            "primary": {
                "action": "Open a project so the app can answer this from your actual work",
                "why": "Advice with no project attached is generic by definition.",
                "guide_ids": [],
            },
            "secondary": [],
            "source": "no_project",
        }

    derived = context.get("derived") or {}
    missing = context.get("missing") or []
    stage = str(context.get("stage") or "")
    evaluation = context.get("evaluation") or {}
    safety_flags = evaluation.get("safety_flags") or []
    deadline = context.get("next_deadline") or {}

    secondary: list[dict] = []

    # 1. Safety and approval outrank everything — but only while they are
    #    plausibly still open. A project already collecting data has passed
    #    approval, and a flag that leads forever is a flag nobody reads. Past
    #    that point it stays visible under "needs attention" instead.
    from app.models.enums import STAGE_ORDER, Stage

    try:
        stage_index = STAGE_ORDER.index(Stage(stage))
    except (ValueError, KeyError):
        stage_index = 0
    approval_index = STAGE_ORDER.index(Stage.APPROVAL_REQUIRED)
    approval_still_open = stage_index <= approval_index

    if approval_still_open and (safety_flags or stage == "approval_required"):
        label = safety_flags[0] if safety_flags else "approval paperwork"
        primary = {
            "action": f"Resolve the approval requirement: {label}",
            "why": (
                "Work done before approval usually cannot be entered. This blocks everything "
                "downstream of it."
            ),
            "guide_ids": ["research-plan"],
        }
        source = "safety"
    else:
        gap = _primary_from_gaps(derived)
        if gap is not None:
            primary = {
                "action": GAP_ACTION[gap].capitalize(),
                "why": GAP_WHY[gap],
                "guide_ids": GAP_GUIDES[gap][:2],
            }
            source = "gap"
            # The next gap becomes the first secondary, if there is one.
            remaining = [k for k in GAP_ORDER if k in derived and not derived[k] and k != gap]
            if remaining:
                secondary.append(
                    {
                        "action": GAP_ACTION[remaining[0]].capitalize(),
                        "why": GAP_WHY[remaining[0]],
                        "guide_ids": GAP_GUIDES[remaining[0]][:1],
                    }
                )
        elif missing:
            primary = {
                "action": f"Answer the interview question about {missing[0].lower()}",
                "why": (
                    "It is the biggest hole in what the app knows, which makes every score you "
                    "are looking at less reliable than it appears."
                ),
                "guide_ids": STAGE_GUIDES.get(stage, [])[:1],
            }
            source = "missing_answer"
        else:
            primary = {
                "action": STAGE_ACTION.get(stage, "Keep going — the project is on track").capitalize(),
                "why": "This is the work the current stage is for.",
                "guide_ids": STAGE_GUIDES.get(stage, [])[:2],
            }
            source = "stage"

    # Deadlines and weak scores inform, never lead.
    if deadline.get("due_date") and len(secondary) < 2:
        secondary.append(
            {
                "action": f"Due {deadline['due_date']}: {deadline.get('title')}",
                "why": "From your timeline.",
                "guide_ids": [],
            }
        )
    weak = (evaluation.get("weak_criteria") or [])[:1]
    if weak and len(secondary) < 2:
        item = weak[0]
        secondary.append(
            {
                "action": (
                    f"Improve {str(item.get('criterion', '')).replace('_', ' ')} "
                    f"({item.get('score')}/100)"
                ),
                "why": "Lowest-scoring criterion in your last evaluation.",
                "guide_ids": [],
            }
        )

    return {"primary": primary, "secondary": secondary[:2], "source": source}
