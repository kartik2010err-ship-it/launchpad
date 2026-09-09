"""The interview (section 2).

Not a fixed questionnaire. Each question carries a weight, an optional
prerequisite and a validator. On every turn the engine:

1. critiques the answers that just came in,
2. re-queues any answer that was too thin to use,
3. ranks the remaining unanswered questions by how much they would unblock the
   scoring engine, and asks the top few.

So a student who says "my dependent variable is how well the plant does" gets
pushed on that immediately instead of sailing through fourteen boxes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from app.models.enums import ProjectType
from app.schemas.evaluation import AnswerCritique, InterviewQuestion, InterviewStep
from app.services.signals import (
    MECHANISM_WORDS,
    ProjectSignals,
    contains_any,
    first_int,
    has_number,
    has_unit,
    is_quantitative,
    is_substantive,
)

Validator = Callable[[str, ProjectSignals], tuple[bool, str, str | None]]


@dataclass
class BankQuestion:
    key: str
    dimension: str
    text: str
    why_asked: str
    weight: int
    hint: str | None = None
    requires: list[str] = field(default_factory=list)
    validator: Validator | None = None
    input_type: str = "text"
    options: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Validators — the part that makes this an interview rather than a form
# --------------------------------------------------------------------------- #


def _generic(answer: str, _s: ProjectSignals) -> tuple[bool, str, str | None]:
    if not is_substantive(answer):
        return False, "That is too short to work with.", "Give me two or three sentences."
    return True, "Noted.", None


def _variable(answer: str, _s: ProjectSignals) -> tuple[bool, str, str | None]:
    if not is_substantive(answer, 8):
        return False, "I need an actual variable here.", "Name one thing, and how it changes."
    if len(answer.split()) > 25:
        return (
            True,
            "That reads more like a description than a variable.",
            "Can you compress it to a single noun phrase? A variable should fit in a column header.",
        )
    return True, "Clear enough to use.", None


def _dependent(answer: str, _s: ProjectSignals) -> tuple[bool, str, str | None]:
    ok, note, follow = _variable(answer, _s)
    if not ok:
        return ok, note, follow
    if not is_quantitative(answer):
        return (
            True,
            "This is stated qualitatively, so right now it is not something you can graph.",
            "What number would you write in the cell of your data table, and in what unit?",
        )
    return True, "Quantitative — good.", None


def _measurement(answer: str, _s: ProjectSignals) -> tuple[bool, str, str | None]:
    if not is_substantive(answer, 15):
        return False, "Not specific enough to score.", "What instrument, what unit, how often?"
    if not has_unit(answer) and not has_number(answer):
        return (
            True,
            "No unit or interval appears in this answer.",
            "Add the unit and how often you take the reading — 'mass in grams, every 48 hours'.",
        )
    return True, "Specific measurement recorded.", None


def _prediction(answer: str, _s: ProjectSignals) -> tuple[bool, str, str | None]:
    if not is_substantive(answer, 15):
        return False, "A prediction needs a direction.", "Which condition wins, and by roughly how much?"
    if not has_number(answer):
        return (
            True,
            "Directional but not quantitative.",
            "Predict a rough size of effect. Being wrong about a specific number teaches you more "
            "than being vaguely right.",
        )
    return True, "Testable prediction.", None


def _mechanism(answer: str, _s: ProjectSignals) -> tuple[bool, str, str | None]:
    if not is_substantive(answer, 20):
        return (
            False,
            "This is the answer judges push hardest on.",
            "Why would that happen? Name the process, not the outcome.",
        )
    if not contains_any(answer, MECHANISM_WORDS):
        return (
            True,
            "You restated the prediction rather than explaining it.",
            "Finish this sentence: 'this happens because ___'. If you cannot, that is your next "
            "piece of background research.",
        )
    return True, "You have a mechanism to defend.", None


def _control(answer: str, _s: ProjectSignals) -> tuple[bool, str, str | None]:
    if not is_substantive(answer, 12):
        return False, "Without a baseline you cannot attribute anything.", "What is the untreated case?"
    if answer.strip().lower().startswith(("no", "none", "i don't have")):
        return (
            False,
            "A missing control is the single most common reason a well-run project scores badly.",
            "What would you run that is identical except for the variable you are changing?",
        )
    return True, "Baseline defined.", None


def _trials(answer: str, _s: ProjectSignals) -> tuple[bool, str, str | None]:
    n = first_int(answer)
    if n is None:
        return False, "Give me a number.", "How many trials per condition, realistically?"
    if n < 3:
        return (
            True,
            f"{n} per condition cannot separate a real effect from noise.",
            "What would it take to get to at least 5, ideally 10, per condition?",
        )
    if n < 5:
        return True, f"{n} is workable but thin — expect a judge to ask about statistical power.", None
    return True, f"{n} per condition is a defensible sample.", None


def _prior_work(answer: str, _s: ProjectSignals) -> tuple[bool, str, str | None]:
    if not is_substantive(answer, 20):
        return (
            False,
            "You cannot argue originality without knowing what exists.",
            "Find two sources on Google Scholar and tell me what each one found.",
        )
    return True, "Background noted.", None


def _differentiator(answer: str, _s: ProjectSignals) -> tuple[bool, str, str | None]:
    if not is_substantive(answer, 20):
        return (
            False,
            "This is the creativity question, worth 20 rubric points.",
            "What does your version do that the standard version does not?",
        )
    if answer.strip().lower().startswith(("nobody has", "no one has", "it's never")):
        return (
            True,
            "Careful — 'nobody has done this' is a claim you have to support, and judges test it.",
            "What did you search, and what came back?",
        )
    return True, "Difference stated. It will need evidence behind it.", None


def _regulated(answer: str, _s: ProjectSignals) -> tuple[bool, str, str | None]:
    if not is_substantive(answer, 4):
        return False, "Answer this one before you start any work.", None
    return True, "Screened. See the rules panel for what this triggers.", None


# --------------------------------------------------------------------------- #
# Banks
# --------------------------------------------------------------------------- #

SCIENTIFIC_BANK: list[BankQuestion] = [
    BankQuestion("goal", "purpose", "In one sentence, what exactly are you trying to find out?",
                 "Everything else depends on whether you are testing a relationship, comparing options, or measuring something.",
                 weight=100, validator=_generic,
                 hint="Not the topic — the specific thing you would put in a results sentence."),
    BankQuestion("independent_variable", "design", "What is the one thing you will deliberately change?",
                 "One clean independent variable is what separates an experiment from a demonstration.",
                 weight=95, validator=_variable, hint="e.g. 'water temperature, at 15 °C, 25 °C and 35 °C'"),
    BankQuestion("dependent_variable", "design", "What will you measure as the outcome?",
                 "Rubric points for methodology depend on the outcome being a number, not an impression.",
                 weight=95, validator=_dependent, requires=["independent_variable"]),
    BankQuestion("measurement", "design", "How exactly will you measure that — what tool, what unit, how often?",
                 "Two students measuring 'plant health' differently will get different answers, which is why judges press on this.",
                 weight=85, validator=_measurement, requires=["dependent_variable"]),
    BankQuestion("population", "design", "What specific population, system or material are you studying?",
                 "'Plants' or 'students' is not sampleable. The specific choice is also where novelty often hides.",
                 weight=80, validator=_generic),
    BankQuestion("prediction", "depth", "What do you predict will happen?",
                 "A prediction you could be wrong about is what makes the project a test rather than a demonstration.",
                 weight=70, validator=_prediction, requires=["dependent_variable"]),
    BankQuestion("mechanism", "depth", "Why would that happen? What is the underlying mechanism?",
                 "This is the question that most often separates a first-place project from a competent one.",
                 weight=88, validator=_mechanism, requires=["prediction"]),
    BankQuestion("control", "design", "What is your control or baseline condition?",
                 "Without a baseline you cannot claim your variable caused anything.",
                 weight=90, validator=_control, requires=["independent_variable"]),
    BankQuestion("trials", "feasibility", "How many trials or samples can you realistically collect per condition?",
                 "Sample size decides whether your results can be analysed at all.",
                 weight=75, validator=_trials),
    BankQuestion("resources", "feasibility", "What equipment, software, datasets or materials do you need, and do you have access?",
                 "Feasibility is scored on what you can actually get hold of, not what would be ideal.",
                 weight=65, validator=_generic),
    BankQuestion("time_budget", "feasibility", "How many weeks until your fair, and how many hours a week can you work?",
                 "This drives your timeline and the honest warning about whether the plan fits.",
                 weight=60, validator=_generic),
    BankQuestion("regulated", "safety",
                 "Does your project involve humans, vertebrate animals, microorganisms, tissue, chemicals, "
                 "radiation, drones, firearms or other regulated activities? Describe anything that applies.",
                 "Some of these require approval before you touch anything, and starting early disqualifies projects.",
                 weight=92, validator=_regulated),
    BankQuestion("prior_work", "novelty", "What existing research have you found on this? Name specific sources and what they found.",
                 "You cannot claim a gap without knowing the field, and judges ask for sources directly.",
                 weight=78, validator=_prior_work),
    BankQuestion("differentiator", "novelty", "What makes your project different from the experiments that already exist?",
                 "Creativity is worth 20 points on the AzSEF rubric — the most of any category except the interview.",
                 weight=82, validator=_differentiator, requires=["prior_work"]),
]

ENGINEERING_BANK: list[BankQuestion] = [
    BankQuestion("problem", "purpose", "What real-world problem are you solving?",
                 "An engineering project is judged against a stated need, not a hypothesis.",
                 weight=100, validator=_generic),
    BankQuestion("who_experiences", "purpose", "Who actually has this problem, and how do you know?",
                 "A named user makes your design requirements defensible instead of arbitrary.",
                 weight=85, validator=_generic, requires=["problem"]),
    BankQuestion("constraints", "design", "What are your design constraints — cost, size, weight, power, time, materials?",
                 "Constraints are what turn 'build a thing' into an engineering problem.",
                 weight=88, validator=_generic),
    BankQuestion("existing_solutions", "novelty", "What solutions already exist?",
                 "Judges will know the existing products. Not knowing them is the fastest way to lose creativity points.",
                 weight=80, validator=_prior_work),
    BankQuestion("existing_weaknesses", "novelty", "What are the weaknesses of those existing solutions?",
                 "Your design only matters if it addresses a specific failure of what already exists.",
                 weight=82, validator=_differentiator, requires=["existing_solutions"]),
    BankQuestion("success_metric", "design", "What measurable requirements define success?",
                 "'Works better' is not testable. A number with a threshold is.",
                 weight=92, validator=_measurement),
    BankQuestion("alternatives", "depth", "What design alternatives could you test against each other?",
                 "Testing one prototype is a build. Comparing alternatives is engineering.",
                 weight=78, validator=_generic, requires=["constraints"]),
    BankQuestion("prototype", "feasibility", "What will your prototype actually be, and what will you build it from?",
                 "Feasibility depends on whether the prototype is buildable with what you have.",
                 weight=75, validator=_generic),
    BankQuestion("test_method", "design", "How will you test the prototype, and what is your baseline for comparison?",
                 "A test protocol with a baseline is the engineering equivalent of a control.",
                 weight=90, validator=_control, requires=["prototype"]),
    BankQuestion("comparison_metric", "design", "What single metric decides whether one design beats another?",
                 "Without a decision metric, iteration becomes tinkering.",
                 weight=85, validator=_dependent, requires=["success_metric"]),
    BankQuestion("resources", "feasibility", "What tools, parts, software or facilities do you need, and do you have access?",
                 "Access, not ambition, sets what you can build.",
                 weight=65, validator=_generic),
    BankQuestion("time_budget", "feasibility", "How many weeks until your fair, and how many hours a week can you work?",
                 "Iteration cycles take longer than students expect, and you need at least two.",
                 weight=60, validator=_generic),
    BankQuestion("regulated", "safety",
                 "Does your build involve drones, firearms, high voltage, lasers, chemicals, combustion, "
                 "human testers or other regulated elements?",
                 "Several of these need documented approval before you start building or testing.",
                 weight=92, validator=_regulated),
    BankQuestion("prior_work", "novelty", "What technical sources, papers or patents have you read?",
                 "Engineering judges expect you to know the state of the art in your niche.",
                 weight=70, validator=_prior_work),
]


def bank_for(project_type: ProjectType) -> list[BankQuestion]:
    return ENGINEERING_BANK if project_type == ProjectType.ENGINEERING else SCIENTIFIC_BANK


def question_by_key(project_type: ProjectType, key: str) -> BankQuestion | None:
    return next((q for q in bank_for(project_type) if q.key == key), None)


def critique_answers(signals: ProjectSignals, answered_keys: list[str]) -> list[AnswerCritique]:
    out: list[AnswerCritique] = []
    for key in answered_keys:
        bq = question_by_key(signals.project_type, key)
        if bq is None:
            continue
        validator = bq.validator or _generic
        accepted, note, follow = validator(signals.get(key), signals)
        out.append(AnswerCritique(question_key=key, accepted=accepted, note=note, follow_up=follow))
    return out


def select_questions(signals: ProjectSignals, max_questions: int = 3) -> list[InterviewQuestion]:
    bank = bank_for(signals.project_type)
    candidates: list[tuple[int, BankQuestion]] = []

    for bq in bank:
        if signals.has(bq.key):
            validator = bq.validator or _generic
            accepted, _, _ = validator(signals.get(bq.key), signals)
            if accepted:
                continue
            # Rejected answer: re-ask at boosted priority.
            candidates.append((bq.weight + 20, bq))
            continue
        # Do not ask a question whose prerequisite is still open.
        if any(not signals.has(dep) for dep in bq.requires):
            continue
        candidates.append((bq.weight, bq))

    candidates.sort(key=lambda pair: -pair[0])
    chosen = candidates[:max_questions]

    return [
        InterviewQuestion(
            key=bq.key,
            dimension=bq.dimension,
            text=bq.text,
            why_asked=bq.why_asked,
            hint=bq.hint,
            input_type=bq.input_type,
            options=bq.options,
        )
        for _, bq in chosen
    ]


def build_step(
    signals: ProjectSignals, newly_answered: list[str], max_questions: int = 3
) -> InterviewStep:
    critiques = critique_answers(signals, newly_answered)
    questions = select_questions(signals, max_questions)
    completeness = signals.completeness
    # Enough to score once the design-critical keys are in and coverage is broad.
    core = ["independent_variable", "dependent_variable", "measurement", "control"]
    if signals.project_type == ProjectType.ENGINEERING:
        core = ["problem", "constraints", "success_metric", "test_method"]
    ready = completeness >= 60 and all(signals.has(k) for k in core)

    return InterviewStep(
        questions=questions,
        critiques=critiques,
        completeness=completeness,
        ready_to_evaluate=ready,
        coverage=signals.coverage,
    )
