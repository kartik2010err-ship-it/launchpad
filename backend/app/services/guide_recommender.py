"""Connect coach feedback to the Research Library, by id.

The rule this module exists to enforce: a weakness never carries a hard-coded
link. The scoring engine produces `(dimension, criterion)` pairs — those are
stable identifiers — and this table maps them to guide ids. Rewording a
weakness message changes nothing here; renaming a guide changes one line.

Nothing is invented at call time. If a criterion has no mapping, the student
gets no recommendation rather than a guess.
"""

from __future__ import annotations

from app.content import guides

# (dimension key, criterion key) -> ordered guide ids, most relevant first.
CRITERION_GUIDES: dict[tuple[str, str], list[str]] = {
    ("research_question", "clarity"): ["idea-to-research-question", "writing-a-hypothesis"],
    ("research_question", "specificity"): ["idea-to-research-question", "choosing-a-topic"],
    ("research_question", "testability"): [
        "designing-a-controlled-experiment",
        "choosing-a-control-group",
    ],
    ("research_question", "measurability"): [
        "measurable-variables",
        "independent-dependent-variables",
    ],
    ("research_question", "scope"): ["choosing-a-topic", "sample-size"],
    ("research_question", "variables_defined"): [
        "independent-dependent-variables",
        "controlled-variables",
    ],
    ("research_question", "significance"): ["research-gaps", "determining-novelty"],
    ("methodology", "answers_the_question"): [
        "designing-a-controlled-experiment",
        "measurable-variables",
    ],
    ("methodology", "controls"): ["choosing-a-control-group", "controlled-variables"],
    ("methodology", "quantitative_data"): ["measurable-variables", "data-collection"],
    ("methodology", "sample_size"): ["sample-size", "repeated-trials"],
    ("methodology", "reproducibility"): [
        "designing-a-controlled-experiment",
        "research-notebook",
    ],
    ("methodology", "confound_awareness"): ["confounding-variables", "avoiding-bias"],
    ("methodology", "design_structure"): [
        "designing-a-controlled-experiment",
        "pilot-experiments",
    ],
    ("creativity", "not_a_common_archetype"): ["research-gaps", "choosing-a-topic"],
    ("creativity", "articulated_difference"): ["explaining-novelty", "determining-novelty"],
    ("creativity", "research_gap"): ["research-gaps", "literature-review"],
    ("creativity", "useful_new_information"): ["determining-novelty", "explaining-novelty"],
    ("feasibility", "time"): ["pilot-experiments", "choosing-a-topic"],
    ("feasibility", "cost"): ["choosing-a-topic"],
    ("feasibility", "equipment_access"): ["choosing-a-topic", "pilot-experiments"],
    ("feasibility", "expertise"): ["reading-a-scientific-paper", "finding-credible-sources"],
    ("feasibility", "data_availability"): ["data-collection", "sample-size"],
    ("feasibility", "complexity"): ["sample-size", "pilot-experiments"],
    ("feasibility", "safety_and_approvals"): ["research-plan"],
    ("scientific_depth", "mechanism_understood"): [
        "writing-a-hypothesis",
        "reading-a-scientific-paper",
    ],
    ("scientific_depth", "beyond_demonstration"): ["research-gaps", "explaining-novelty"],
    ("scientific_depth", "competing_hypotheses"): [
        "confounding-variables",
        "correlation-vs-causation",
    ],
    ("scientific_depth", "analysis_potential"): [
        "choosing-a-statistical-test",
        "statistical-significance",
        "descriptive-statistics",
    ],
}

# Rubric line keys (app.services.rubric) -> guides, for the rubric screen.
RUBRIC_GUIDES: dict[str, list[str]] = {
    "research_question": ["idea-to-research-question", "measurable-variables"],
    "design": ["designing-a-controlled-experiment", "choosing-a-control-group"],
    "execution": ["repeated-trials", "data-collection", "research-notebook"],
    "creativity": ["determining-novelty", "explaining-novelty"],
    "poster": ["poster", "choosing-a-graph"],
    "interview": ["judge-interview", "explaining-limitations"],
}

# Project stage -> what is worth reading right now, regardless of scores.
STAGE_GUIDES: dict[str, list[str]] = {
    "idea": ["choosing-a-topic", "idea-to-research-question"],
    "question_refinement": ["idea-to-research-question", "measurable-variables", "writing-a-hypothesis"],
    "background_research": ["finding-credible-sources", "reading-a-scientific-paper", "literature-review"],
    "experimental_design": ["designing-a-controlled-experiment", "choosing-a-control-group", "sample-size"],
    "approval_required": ["research-plan"],
    "experimentation": ["data-collection", "repeated-trials", "research-notebook"],
    "data_analysis": ["descriptive-statistics", "choosing-a-statistical-test", "choosing-a-graph"],
    "poster": ["poster", "choosing-a-graph", "abstract"],
    "interview_preparation": ["judge-interview", "explaining-limitations", "explaining-novelty"],
    "complete": ["explaining-limitations", "judge-interview"],
}

# Below this a criterion counts as a weakness worth a reading recommendation.
WEAK_THRESHOLD = 70


def _guide_payload(guide_id: str, reason: str) -> dict | None:
    guide = guides.get(guide_id)
    if guide is None:
        return None
    return {
        "guide_id": guide.id,
        "title": guide.title,
        "category": guide.category,
        "summary": guide.summary,
        "read_minutes": guide.read_minutes,
        "reason": reason,
    }


def for_evaluation(dimensions: list[dict], stage: str | None = None, limit: int = 6) -> list[dict]:
    """Guides for one evaluation, weakest criterion first.

    ``dimensions`` is the stored evaluation's dimension list: each has a ``key``
    and a ``criteria`` map of criterion key to 0-100 score.
    """

    # Grouped by dimension, then interleaved. Six guides that all address one
    # dimension would bury the fact that three separate things are weak, so each
    # dimension contributes its worst criterion before any contributes a second.
    per_dimension: list[tuple[int, list[tuple[int, str, str]]]] = []
    for dimension in dimensions or []:
        if not isinstance(dimension, dict):
            continue
        dim_key = dimension.get("key")
        label = dimension.get("label") or dim_key
        entries: list[tuple[int, str, str]] = []
        for criterion, score in (dimension.get("criteria") or {}).items():
            if not isinstance(score, int) or score >= WEAK_THRESHOLD:
                continue
            for guide_id in CRITERION_GUIDES.get((dim_key, criterion), []):
                reason = f"{label}: {criterion.replace('_', ' ')} scored {score}/100."
                entries.append((score, guide_id, reason))
        if entries:
            entries.sort(key=lambda row: row[0])
            per_dimension.append((entries[0][0], entries))

    # Dimensions with the single worst criterion get to go first.
    per_dimension.sort(key=lambda row: row[0])

    out: list[dict] = []
    seen: set[str] = set()
    depth = 0
    while len(out) < limit and any(len(entries) > depth for _, entries in per_dimension):
        for _worst, entries in per_dimension:
            if depth >= len(entries):
                continue
            _score, guide_id, reason = entries[depth]
            if guide_id in seen:
                continue
            payload = _guide_payload(guide_id, reason)
            if payload is None:
                continue
            seen.add(guide_id)
            out.append(payload)
            if len(out) >= limit:
                return out
        depth += 1

    # Top up with stage-appropriate reading rather than returning a short list.
    for guide_id in STAGE_GUIDES.get(stage or "", []):
        if guide_id in seen:
            continue
        payload = _guide_payload(guide_id, "Usually worth reading at this stage of a project.")
        if payload is None:
            continue
        seen.add(guide_id)
        out.append(payload)
        if len(out) >= limit:
            break
    return out


def for_rubric_line(line_key: str) -> list[dict]:
    return [
        payload
        for guide_id in RUBRIC_GUIDES.get(line_key, [])
        if (payload := _guide_payload(guide_id, f"Relevant to the {line_key.replace('_', ' ')} score."))
    ]


def for_stage(stage: str | None) -> list[dict]:
    return [
        payload
        for guide_id in STAGE_GUIDES.get(stage or "", [])
        if (payload := _guide_payload(guide_id, "Recommended for your current stage."))
    ]
