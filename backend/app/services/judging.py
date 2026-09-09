"""Interview preparation and mock judging (sections 28-30)."""

from __future__ import annotations

from app.models.enums import Category, ProjectType
from app.schemas.evaluation import (
    InterviewPrepSet,
    JudgeQuestion,
    MockJudgeReply,
    MockJudgeReport,
)
from app.services.signals import (
    MECHANISM_WORDS,
    STATS_WORDS,
    ProjectSignals,
    contains_any,
    has_number,
    is_substantive,
)

HEDGES = ("i think", "maybe", "probably", "kind of", "sort of", "i guess", "i'm not sure", "hopefully")

CATEGORY_PROBES: dict[str, list[str]] = {
    Category.COMPUTER_SCIENCE: [
        "What is your baseline, and would a much simpler model have done just as well?",
        "How did you split your data, and could anything have leaked between the splits?",
        "What does your error analysis show about which cases the model gets wrong?",
    ],
    Category.BIOMEDICAL: [
        "What is the biological mechanism you are relying on, and where did you read about it?",
        "How did you keep your biological replicates independent of each other?",
        "What would this result mean clinically, and what would it definitely not mean?",
    ],
    Category.ENVIRONMENTAL: [
        "How do your laboratory conditions compare with the field conditions you are generalising to?",
        "What is the natural range of this variable, and did you test inside it?",
        "How did you handle seasonal or site-to-site variation?",
    ],
    Category.PHYSICS: [
        "What is your dominant source of uncertainty, and how did you estimate it?",
        "Does your result agree with the theoretical prediction, and if not, by how many error bars?",
        "What assumption in your model breaks first as you push the range?",
    ],
    Category.CHEMISTRY: [
        "How did you verify the purity or concentration of what you started with?",
        "What side reactions could be competing with the one you are measuring?",
        "How reproducible was your yield between runs?",
    ],
    Category.ENGINEERING: [
        "Which requirement did your final design fail, and what did you trade to get there?",
        "How do you know the test rig is not the thing limiting your measurement?",
        "What would break first if this were used every day for a year?",
    ],
    Category.BEHAVIORAL_SOCIAL: [
        "How did you prevent participants from guessing what you were testing?",
        "What is your evidence that this is causal rather than correlational?",
        "How representative is your sample of the population in your conclusion?",
    ],
    Category.MATHEMATICS: [
        "Where exactly does your proof use the hypothesis, and does it fail without it?",
        "What is the smallest counterexample you looked for, and how far did you search?",
        "Is your result tight, or is there slack in the bound?",
    ],
}


def prep_set(s: ProjectSignals) -> InterviewPrepSet:
    engineering = s.project_type == ProjectType.ENGINEERING
    iv = (s.get("independent_variable") or s.get("alternatives") or "your main variable")[:60]
    dv = (s.get("dependent_variable") or s.get("comparison_metric") or "your outcome")[:60]

    questions = [
        JudgeQuestion(category="Basic understanding", text="Tell me about your project.", what_theyre_probing="Whether you can state the question and the finding without notes.", difficulty="warm-up"),
        JudgeQuestion(category="Basic understanding", text="Why did you choose this topic?", what_theyre_probing="Genuine interest, and whether the project is yours.", difficulty="warm-up"),
        JudgeQuestion(category="Basic understanding", text="What did you predict, and why?", what_theyre_probing="Whether the hypothesis had reasoning behind it.", difficulty="warm-up"),
        JudgeQuestion(category="Methodology", text=f"Why did you test {iv} the way you did rather than another way?", what_theyre_probing="Whether design choices were deliberate.", difficulty="standard"),
        JudgeQuestion(category="Methodology", text="Why is that the right control?", what_theyre_probing="Understanding of what a control is for.", difficulty="standard"),
        JudgeQuestion(category="Methodology", text="How did you decide your sample size?", what_theyre_probing="Whether the number was reasoned or convenient.", difficulty="standard"),
        JudgeQuestion(category="Methodology", text="Which variables did you hold constant, and how did you verify that?", what_theyre_probing="Rigour beyond the written procedure.", difficulty="standard"),
        JudgeQuestion(category="Results", text=f"What is your most important result in {dv}?", what_theyre_probing="Whether you can identify the headline finding.", difficulty="standard"),
        JudgeQuestion(category="Results", text="Is that difference bigger than your measurement error?", what_theyre_probing="Honest handling of uncertainty.", difficulty="hard"),
        JudgeQuestion(category="Results", text="What surprised you?", what_theyre_probing="Engagement with the actual data.", difficulty="standard"),
        JudgeQuestion(category="Critical thinking", text="What is the biggest weakness in your experiment?", what_theyre_probing="Self-awareness. Claiming none is the wrong answer.", difficulty="hard"),
        JudgeQuestion(category="Critical thinking", text="What else could have produced this result?", what_theyre_probing="Whether you have considered confounds.", difficulty="hard"),
        JudgeQuestion(category="Critical thinking", text="If you repeated this, what would you change first?", what_theyre_probing="Whether you learned from doing it.", difficulty="standard"),
        JudgeQuestion(category="Novelty", text="What does your project do that existing work does not?", what_theyre_probing="Whether the originality claim survives contact.", difficulty="hard"),
        JudgeQuestion(category="Novelty", text="Why does this result matter to anyone outside this room?", what_theyre_probing="Significance, stated without overclaiming.", difficulty="hard"),
    ]

    for probe in CATEGORY_PROBES.get(Category(s.category), CATEGORY_PROBES[Category.PHYSICS]):
        questions.append(JudgeQuestion(category="Advanced", text=probe, what_theyre_probing="Domain-specific depth.", difficulty="hard"))

    if engineering:
        questions.append(JudgeQuestion(category="Advanced", text="How many design iterations did you run, and what did each one teach you?", what_theyre_probing="Whether the design cycle was real.", difficulty="hard"))

    return InterviewPrepSet(
        questions=questions,
        pitch_prompts=[
            "In 15 seconds: what you tested and what you found.",
            "In 30 seconds: add why the question was worth asking.",
            "In 1 minute: add how you tested it and what your control was.",
            "In 2 minutes: add your mechanism, your main limitation and what you would do next.",
            "Full walkthrough: everything above, in the order your poster reads.",
        ],
    )


# --------------------------------------------------------------------------- #
# Mock judging
# --------------------------------------------------------------------------- #

LADDER = [
    ("open", "Walk me through your project."),
    ("mechanism", "You have told me what happens. Tell me why it happens."),
    ("control", "What was your control, and why is it the right comparison?"),
    ("uncertainty", "How confident are you that your difference is real and not measurement noise?"),
    ("confound", "Give me one alternative explanation for your result, and tell me how you ruled it out."),
    ("novelty", "Someone did a version of this project last year. What is different about yours?"),
    ("limits", "What is the biggest thing your experiment cannot tell us?"),
    ("next", "If I gave you another two months, what is the single next experiment?"),
]


def _assess(answer: str) -> tuple[str, str]:
    """Return (quality, reaction) for one student answer."""
    if not is_substantive(answer, 25):
        return "weak", "That is short. A judge will read brevity as not knowing, so say more than you think you need to."
    hedges = contains_any(answer, HEDGES)
    if hedges and not has_number(answer):
        return "weak", f"You hedged ('{hedges[0]}') and gave no numbers. Hedging is fine once you have given the evidence, not instead of it."
    if contains_any(answer, MECHANISM_WORDS) and has_number(answer):
        return "strong", "Good — you gave a reason and a number in the same breath. That is what a judge is listening for."
    if has_number(answer):
        return "ok", "You have the numbers. Now attach the reasoning: say why the number came out that way."
    if contains_any(answer, MECHANISM_WORDS):
        return "ok", "The reasoning is there but unquantified. Anchor it to a value from your data."
    return "weak", "That is a description rather than an argument. What is your evidence, and what does it rule out?"


def mock_turn(s: ProjectSignals, transcript: list[dict], answer: str | None) -> MockJudgeReply:
    student_turns = [t for t in transcript if t.get("role") == "student"]
    index = len(student_turns)

    reaction = None
    if answer is not None:
        _quality, reaction = _assess(answer)

    if index >= len(LADDER) - 1:
        return MockJudgeReply(
            judge_question="",
            reaction=reaction,
            probing="",
            turn_index=index,
            finished=True,
        )

    key, question = LADDER[min(index, len(LADDER) - 1)]
    if key == "novelty" and s.differentiator_stated:
        question = (
            "You have said what makes yours different. Convince me that difference actually matters "
            "to the result, rather than just being a change."
        )
    return MockJudgeReply(
        judge_question=question,
        reaction=reaction,
        probing=key,
        turn_index=index,
        finished=False,
    )


def mock_report(s: ProjectSignals, transcript: list[dict]) -> MockJudgeReport:
    answers = [t.get("text", "") for t in transcript if t.get("role") == "student"]
    questions = [t.get("text", "") for t in transcript if t.get("role") == "judge"]

    strong, weak, struggled, comms = [], [], [], []
    for i, answer in enumerate(answers):
        quality, note = _assess(answer)
        label = questions[i][:70] if i < len(questions) else f"question {i + 1}"
        if quality == "strong":
            strong.append(f"{label} — {note}")
        elif quality == "weak":
            weak.append(f"{label} — {note}")
            struggled.append(label)
        if len(answer.split()) > 130:
            comms.append(f"Your answer to '{label}' ran long. Judges have a queue; lead with the answer, then elaborate if asked.")
        if contains_any(answer, HEDGES):
            comms.append("Hedging language appears more than once. State what you found, then state your uncertainty separately.")

    concepts = []
    if not any(contains_any(a, MECHANISM_WORDS) for a in answers):
        concepts.append("The mechanism behind your effect — you never explained why it happens.")
    if not any(contains_any(a, STATS_WORDS) or has_number(a) for a in answers):
        concepts.append("Your own numbers. Know your means, your spread and your sample size without looking.")
    if not s.control_defined:
        concepts.append("What a control is for, and which one your design actually uses.")

    answered = len(answers)
    quality_score = sum(1 for a in answers if _assess(a)[0] == "strong") * 12 + sum(1 for a in answers if _assess(a)[0] == "ok") * 7
    readiness = max(0, min(100, int(20 + quality_score - 4 * len(weak) + min(answered, 8) * 3)))

    return MockJudgeReport(
        readiness=readiness,
        strong_answers=strong or ["No answer yet showed both evidence and reasoning together."],
        weak_answers=weak[:6],
        concepts_to_review=concepts or ["Nothing obvious — run a harder mock session with your mentor."],
        struggled_with=struggled[:6],
        communication_problems=list(dict.fromkeys(comms))[:5] or ["Delivery was reasonable in length and directness."],
        better_explanations=[
            "Open with the finding, not the background. 'We found X; here is why' beats a chronological story.",
            "Every claim you make should be followed by the evidence for it in the same sentence.",
            "When you do not know, say what you would do to find out. That scores better than guessing.",
        ],
    )
