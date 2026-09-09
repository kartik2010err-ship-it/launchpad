"""AzSEF rubric projection (section 4).

The rubric weights are the published category weights. Everything else here is
this app's projection, not a score from a fair.

The central rule: a category is only marked ``current_evidence`` when the
student has actually produced the thing being judged. A project at the
question-refinement stage has no execution, no poster and no interview, so those
categories report ``not_yet_assessable`` and contribute nothing to the projected
total. Pretending otherwise would teach students that a plan is a finished
project.
"""

from __future__ import annotations

from app.models.enums import EvidenceBasis, ProjectType, Stage
from app.schemas.evaluation import AzsefRubric, DimensionScore, RubricLine
from app.services.signals import ProjectSignals

DISCLAIMER = (
    "Projection only. These are not official AzSEF scores and no judge has seen this project. "
    "Category weights follow the published rubric; the points shown are this app's estimate of "
    "what your current evidence would support, and categories you have not started are left "
    "unscored rather than guessed."
)

CATEGORY_WEIGHTS = [
    ("research_question", "Research question", "Research problem / engineering goal", 10),
    ("design", "Design and methodology", "Design and methodology", 15),
    ("execution", "Execution", "Execution: construction and testing", 20),
    ("creativity", "Creativity", "Creativity", 20),
    ("poster", "Poster presentation", "Poster presentation", 10),
    ("interview", "Interview presentation", "Interview presentation", 25),
]

EXECUTION_STAGES = {Stage.EXPERIMENTATION, Stage.DATA_ANALYSIS, Stage.POSTER, Stage.INTERVIEW_PREP, Stage.COMPLETE}
POSTER_STAGES = {Stage.POSTER, Stage.INTERVIEW_PREP, Stage.COMPLETE}
INTERVIEW_STAGES = {Stage.INTERVIEW_PREP, Stage.COMPLETE}


def build(
    signals: ProjectSignals,
    dimensions: dict[str, DimensionScore],
    stage: Stage,
    has_poster_draft: bool = False,
    mock_interview_done: bool = False,
) -> AzsefRubric:
    engineering = signals.project_type == ProjectType.ENGINEERING
    lines: list[RubricLine] = []
    assessable = 0

    for key, sci_label, eng_label, possible in CATEGORY_WEIGHTS:
        label = eng_label if engineering else sci_label
        line = _line_for(key, label, possible, signals, dimensions, stage, has_poster_draft, mock_interview_done)
        lines.append(line)
        if line.basis != EvidenceBasis.NOT_YET_ASSESSABLE:
            assessable += possible

    return AzsefRubric(
        lines=lines,
        points_possible=sum(w for *_, w in CATEGORY_WEIGHTS),
        points_projected=sum(line.points_projected for line in lines),
        assessable_points=assessable,
        disclaimer=DISCLAIMER,
    )


def _scale(score: int, possible: int) -> int:
    return max(0, min(possible, round(score / 100 * possible)))


def _line_for(key, label, possible, s, dims, stage, has_poster, mock_done) -> RubricLine:
    engineering = s.project_type == ProjectType.ENGINEERING

    if key == "research_question":
        d = dims["research_question"]
        return RubricLine(
            key=key, label=label, points_possible=possible,
            points_projected=_scale(d.score, possible),
            basis=EvidenceBasis.CURRENT_EVIDENCE,
            strengths=d.strengths[:3],
            weaknesses=d.weaknesses[:3],
            to_improve=d.improvements[:3],
        )

    if key == "design":
        d = dims["methodology"]
        core = s.has("test_method") if engineering else s.control_defined
        return RubricLine(
            key=key, label=label, points_possible=possible,
            points_projected=_scale(d.score, possible),
            basis=EvidenceBasis.CURRENT_EVIDENCE if core else EvidenceBasis.PROJECTED_POTENTIAL,
            strengths=d.strengths[:3],
            weaknesses=d.weaknesses[:3],
            to_improve=d.improvements[:3],
        )

    if key == "execution":
        if stage not in EXECUTION_STAGES:
            return RubricLine(
                key=key, label=label, points_possible=possible, points_projected=0,
                basis=EvidenceBasis.NOT_YET_ASSESSABLE,
                strengths=[],
                weaknesses=["No data have been collected, so execution cannot be evidenced."],
                to_improve=[
                    "Keep a dated research notebook from your first pilot trial onward — execution "
                    "points are largely awarded for documented, systematic work.",
                    "Photograph your setup before you change anything.",
                ],
            )
        methodology = dims["methodology"].score
        projected = _scale(int(methodology * 0.85), possible)
        return RubricLine(
            key=key, label=label, points_possible=possible, points_projected=projected,
            basis=EvidenceBasis.PROJECTED_POTENTIAL,
            strengths=["Experimentation has begun, so execution can start to be evidenced."],
            weaknesses=["Execution is judged on completeness and documentation of the actual work, not the plan."],
            to_improve=["Record every deviation from your procedure and why you made it."],
        )

    if key == "creativity":
        d = dims["creativity"]
        return RubricLine(
            key=key, label=label, points_possible=possible,
            points_projected=_scale(d.score, possible),
            basis=EvidenceBasis.CURRENT_EVIDENCE,
            strengths=d.strengths[:3],
            weaknesses=d.weaknesses[:3],
            to_improve=d.improvements[:3],
        )

    if key == "poster":
        if not has_poster and stage not in POSTER_STAGES:
            return RubricLine(
                key=key, label=label, points_possible=possible, points_projected=0,
                basis=EvidenceBasis.NOT_YET_ASSESSABLE,
                strengths=[],
                weaknesses=["No poster exists yet."],
                to_improve=["Build your main results graph before you design the board — the graph decides the layout."],
            )
        return RubricLine(
            key=key, label=label, points_possible=possible, points_projected=_scale(60, possible),
            basis=EvidenceBasis.PROJECTED_POTENTIAL,
            strengths=["A draft exists, which is the only way to get useful feedback on it."],
            weaknesses=["Poster points depend on visual hierarchy and restraint, which need a real draft to assess."],
            to_improve=["Run the poster critique tool and fix the text-length flags first."],
        )

    # interview
    if not mock_done and stage not in INTERVIEW_STAGES:
        return RubricLine(
            key=key, label=label, points_possible=possible, points_projected=0,
            basis=EvidenceBasis.NOT_YET_ASSESSABLE,
            strengths=[],
            weaknesses=[
                "No interview evidence exists. This is the largest single category at 25 points, "
                "and it is the one students most often leave until the last week."
            ],
            to_improve=[
                "Being able to explain your mechanism out loud is the highest-leverage preparation. "
                "Run a mock judging session once your design is settled.",
            ],
        )
    depth = dims["scientific_depth"].score
    return RubricLine(
        key=key, label=label, points_possible=possible,
        points_projected=_scale(int(depth * 0.8), possible),
        basis=EvidenceBasis.PROJECTED_POTENTIAL,
        strengths=["You have practised, which is most of the difference in this category."],
        weaknesses=["Interview points depend on live reasoning that cannot be scored from text."],
        to_improve=["Practise the mechanism and limitations answers until they are 30 seconds each."],
    )
