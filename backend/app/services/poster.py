"""Poster planning and coaching (sections 21-27)."""

from __future__ import annotations

import re

from app.models.enums import EvidenceBasis, ProjectType
from app.schemas.evaluation import (
    FigureSuggestion,
    PosterCritique,
    PosterLayout,
    PosterPlan,
    PosterSectionGuide,
)
from app.services.signals import ProjectSignals

SCIENTIFIC_SECTIONS = [
    ("title", "Title", "The question, compressed. Readable from three metres.", 15),
    ("identity", "Student and school", "Who did the work.", 12),
    ("question", "Research question", "The single sentence a judge should leave remembering.", 30),
    ("background", "Background", "Only what is needed to understand why the question is open.", 110),
    ("hypothesis", "Hypothesis", "Your prediction and the reasoning behind it.", 45),
    ("variables", "Variables", "Independent, dependent and controlled, as a table.", 50),
    ("materials", "Materials", "A list, not prose.", 45),
    ("methods", "Methods", "What you did, in enough detail to be repeated.", 130),
    ("setup", "Experimental setup", "A photo or diagram carries this better than text.", 30),
    ("results", "Results", "Numbers and figures. Describe what the graph shows, do not restate it.", 110),
    ("graphs", "Graphs", "Your main finding as one large figure.", 25),
    ("stats", "Statistical analysis", "The test, the value, the sample size.", 55),
    ("discussion", "Discussion", "What the result means and why it came out that way.", 130),
    ("conclusion", "Conclusion", "Answer your question directly.", 70),
    ("limitations", "Limitations", "What your design cannot tell you. Judges reward candour here.", 70),
    ("future", "Future research", "The experiment you would run next.", 55),
    ("references", "References", "Consistent format, real sources.", 45),
    ("acknowledgements", "Acknowledgements", "Anyone who supervised or supplied materials.", 30),
]

ENGINEERING_SECTIONS = [
    ("title", "Title", "The problem and your approach in one line.", 15),
    ("identity", "Student and school", "Who did the work.", 12),
    ("problem", "Problem", "Who has this problem and what it costs them.", 80),
    ("requirements", "Design requirements", "Measurable thresholds, as a table.", 60),
    ("constraints", "Constraints", "Cost, size, power, time, materials.", 45),
    ("existing", "Existing solutions", "What is already available and where it fails.", 90),
    ("alternatives", "Design alternatives", "The options you considered and why you rejected some.", 90),
    ("prototype", "Prototype", "Photographs and a labelled diagram.", 60),
    ("testing", "Testing methodology", "Protocol, benchmark and decision metric.", 110),
    ("results", "Results", "Performance against requirements, per variant.", 100),
    ("iterations", "Iterations", "Each change and the evidence that motivated it.", 100),
    ("final", "Final design", "What you would hand to the user.", 70),
    ("limitations", "Limitations", "Conditions where your design fails.", 65),
    ("future", "Future improvements", "The next iteration.", 50),
    ("references", "References", "Papers, patents, datasheets.", 40),
    ("acknowledgements", "Acknowledgements", "Supervision and materials.", 30),
]


def plan(s: ProjectSignals) -> PosterPlan:
    engineering = s.project_type == ProjectType.ENGINEERING
    spec = ENGINEERING_SECTIONS if engineering else SCIENTIFIC_SECTIONS

    sections = [
        PosterSectionGuide(
            key=key,
            title=title,
            purpose=purpose,
            target_words=words,
            currently_has="Not drafted yet.",
            should_add=_should_add(key, s),
            should_remove=_should_remove(key),
            judge_questions=_judge_questions(key, s),
        )
        for key, title, purpose, words in spec
    ]

    return PosterPlan(
        sections=sections,
        layouts=_layouts(s, engineering),
        figures=_figures(s),
        visual_assets=_assets(s, engineering),
    )


def _should_add(key: str, s: ProjectSignals) -> list[str]:
    iv = s.get("independent_variable") or s.get("alternatives") or "your variable"
    table = {
        "question": ["The exact levels or conditions you compared, inside the question itself."],
        "background": [
            "One sentence naming the gap your project addresses.",
            "Citations for any mechanism you assert.",
        ],
        "hypothesis": ["The reasoning, not only the prediction — 'because' is the important word."],
        "variables": ["A three-column table. Controlled variables belong here, not buried in Methods."],
        "methods": [
            f"Why you chose these specific levels of {iv[:60]} rather than a continuous range.",
            "Sample size per condition and how run order was decided.",
        ],
        "results": ["Means with a measure of spread. A mean with no spread tells a judge nothing."],
        "stats": ["The test name, the statistic, the p-value and n, in that order."],
        "discussion": ["A named alternative explanation and why your data argue against it."],
        "limitations": ["At least one limitation that genuinely constrains your conclusion."],
        "conclusion": ["A direct answer to your research question in the first sentence."],
        "testing": ["The benchmark you compared against and why it is the right benchmark."],
        "iterations": ["The failure that motivated each change, not just the change."],
        "existing": ["A measured weakness of the existing solution, not an asserted one."],
    }
    return table.get(key, ["Draft this section once the preceding sections are settled."])


def _should_remove(key: str) -> list[str]:
    table = {
        "background": ["Textbook definitions a judge already knows.", "History of the field."],
        "methods": ["Step-by-step narration of routine actions.", "Brand names of ordinary equipment."],
        "results": ["Sentences that restate what the graph already shows.", "Raw data tables — move them to an appendix."],
        "discussion": ["Repetition of the results section."],
        "conclusion": ["New information that has not appeared earlier on the board."],
    }
    return table.get(key, [])


def _judge_questions(key: str, s: ProjectSignals) -> list[str]:
    iv = (s.get("independent_variable") or "your variable")[:50]
    table = {
        "question": ["Why is this question still open?"],
        "background": ["Which of these sources actually shaped your design?"],
        "hypothesis": ["What result would have falsified your hypothesis?"],
        "variables": ["Which variable did you fail to control, and does it matter?"],
        "methods": [f"Why these levels of {iv} and not a continuous range?", "How did you decide your sample size?"],
        "results": ["Is this difference larger than your measurement error?"],
        "stats": ["Why this test rather than a non-parametric alternative?"],
        "discussion": ["What else could produce this result?"],
        "limitations": ["Which limitation worries you most?"],
        "testing": ["How do you know your test rig is not the thing you are measuring?"],
        "iterations": ["Which change made the largest difference, and why?"],
    }
    return table.get(key, [])


def _layouts(s: ProjectSignals, engineering: bool) -> list[PosterLayout]:
    has_strong_result = bool(s.get("measurement")) and s.quantitative_outcome
    layouts = [
        PosterLayout(
            key="traditional",
            name="Traditional research",
            columns={
                "left": ["Background", "Research question", "Hypothesis"],
                "centre": ["Methods", "Setup photo or diagram", "Main result graph"],
                "right": ["Additional results", "Discussion", "Conclusion", "Future work"],
            },
            why_it_fits=(
                "Reads left to right in the order a judge asks about. Safest choice when your "
                "result needs the background to be understood first."
            ),
            fit_score=75 if not engineering else 55,
        ),
        PosterLayout(
            key="results_first",
            name="Results first",
            columns={
                "centre": ["Primary result, large", "Key graph", "One-sentence takeaway"],
                "sides": ["Question", "Methods", "Supporting results", "Limitations"],
            },
            why_it_fits=(
                "Puts the finding where the eye lands. Worth it when a single graph carries the "
                "project; wasteful when the result needs setup to interpret."
            ),
            fit_score=85 if has_strong_result and not engineering else 50,
        ),
        PosterLayout(
            key="process",
            name="Process / engineering",
            columns={
                "flow": ["Problem", "Design criteria", "Prototype versions", "Testing", "Final prototype", "Performance comparison"],
            },
            why_it_fits=(
                "Follows the design cycle, which is the thing engineering judges are scoring. "
                "Makes iteration visible instead of hiding it in prose."
            ),
            fit_score=90 if engineering else 35,
        ),
    ]
    return sorted(layouts, key=lambda layout: -layout.fit_score)


def _figures(s: ProjectSignals) -> list[FigureSuggestion]:
    continuous_iv = any(c.isdigit() for c in s.get("independent_variable"))
    out: list[FigureSuggestion] = []
    if continuous_iv:
        out.append(FigureSuggestion(
            name="Scatter plot with fitted regression line",
            kind="scatter",
            why="Your independent variable is continuous and the outcome is numerical, so a scatter plot shows the shape of the relationship. A bar chart would throw that shape away.",
            where_on_poster="Centre, largest figure on the board",
        ))
    out.append(FigureSuggestion(
        name="Bar chart of condition means with error bars",
        kind="bar",
        why="Shows the comparison directly and the error bars make your variability visible, which judges ask about before they ask about the means.",
        where_on_poster="Centre or upper right",
    ))
    out.append(FigureSuggestion(
        name="Box plot per condition",
        kind="box",
        why="Reveals spread and outliers that a bar chart hides. Including one signals that you looked at your distribution.",
        where_on_poster="Beside the main figure, smaller",
    ))
    if s.category == "computer_science":
        out.append(FigureSuggestion(
            name="Confusion matrix",
            kind="matrix",
            why="If your outcome is a classification, accuracy alone conceals which classes fail. The matrix shows it in one glance.",
            where_on_poster="Results column",
        ))
    return out


def _assets(s: ProjectSignals, engineering: bool) -> list[FigureSuggestion]:
    common = [
        FigureSuggestion(
            name="Experimental setup photograph",
            kind="photo",
            why="Proves the work happened and answers a dozen procedure questions before they are asked. Take it before you dismantle anything.",
            where_on_poster="Methods column",
        ),
        FigureSuggestion(
            name="Labelled setup diagram",
            kind="diagram",
            why="A photo shows what it looked like; a diagram shows what mattered. Label only the parts a judge needs.",
            where_on_poster="Beside the photograph",
        ),
    ]
    if engineering:
        common.append(FigureSuggestion(
            name="Prototype progression strip",
            kind="diagram",
            why="Three images in a row make the iteration cycle legible in two seconds, which is the core of engineering scoring.",
            where_on_poster="Across the centre band",
        ))
    else:
        common.append(FigureSuggestion(
            name="Mechanism diagram",
            kind="diagram",
            why="Shows you understand why the effect happens rather than only that it does. This is the depth judges probe for.",
            where_on_poster="Background column, small",
        ))
    if s.category == "computer_science":
        common.append(FigureSuggestion(
            name="Data and model pipeline",
            kind="diagram",
            why="Makes an otherwise invisible computational method concrete on a physical board.",
            where_on_poster="Methods column",
        ))
    return common


# --------------------------------------------------------------------------- #
# Critique
# --------------------------------------------------------------------------- #

WORDY_LIMIT = 1.6  # multiple of target before flagging


def critique(s: ProjectSignals, sections: dict[str, str]) -> PosterCritique:
    engineering = s.project_type == ProjectType.ENGINEERING
    spec = {k: (t, w) for k, t, _p, w in (ENGINEERING_SECTIONS if engineering else SCIENTIFIC_SECTIONS)}

    if not any(v.strip() for v in sections.values()):
        return PosterCritique(
            score=0,
            basis=EvidenceBasis.NOT_YET_ASSESSABLE,
            main_problems=["No poster text has been drafted, so there is nothing to critique yet."],
            text_length_flags=[],
            strengths=[],
            disclaimer=DISCLAIMER,
        )

    flags: list[str] = []
    problems: list[str] = []
    strengths: list[str] = []
    penalties = 0

    for key, text in sections.items():
        if key not in spec or not text.strip():
            continue
        title, target = spec[key]
        words = len(text.split())
        if words > target * WORDY_LIMIT:
            flags.append(f"{title}: {words} words against a {target}-word target. Cut to bullets or move detail to a figure.")
            penalties += 6
        longest_para = max((len(p.split()) for p in re.split(r"\n\s*\n", text)), default=0)
        if longest_para > 90:
            flags.append(f"{title}: contains a {longest_para}-word paragraph. Nobody reads a paragraph that long standing up.")
            penalties += 4
        if key == "results" and not re.search(r"\d", text):
            problems.append("Results contains no numbers. A results section without values is a discussion section.")
            penalties += 8
        if key == "results" and words > target:
            problems.append("Results is described in prose that a graph should be carrying.")
            penalties += 5
        if key == "conclusion" and "?" not in s.question[:0] and words and not re.search(r"\b(because|therefore|suggests|indicates|means)\b", text, re.I):
            problems.append("Conclusion repeats the result without interpreting it.")
            penalties += 5

    drafted = [k for k, v in sections.items() if v.strip()]
    coverage = len(drafted) / max(1, len(spec))
    if coverage > 0.7:
        strengths.append("Most sections are drafted, which is the hard part.")
    if "limitations" in drafted:
        strengths.append("Limitations is present. Many boards skip it and lose easy points.")
    if "stats" in drafted or "testing" in drafted:
        strengths.append("Analysis is given its own space rather than being folded into results.")

    missing_core = [k for k in ("question", "results", "conclusion", "problem", "testing") if k in spec and k not in drafted]
    for key in missing_core:
        problems.append(f"{spec[key][0]} is missing entirely.")
        penalties += 7

    score = max(0, min(100, int(45 + coverage * 55 - penalties)))
    return PosterCritique(
        score=score,
        basis=EvidenceBasis.CURRENT_EVIDENCE,
        main_problems=problems[:6] or ["No structural problems found in the drafted sections."],
        text_length_flags=flags[:6],
        strengths=strengths or ["Too little drafted to credit yet."],
        disclaimer=DISCLAIMER,
    )


DISCLAIMER = (
    "Coaching feedback on your draft, not an AzSEF poster score. Judges assess the physical board "
    "in front of them, including things this tool cannot see: type size, spacing, print quality and "
    "whether the figures are legible from a metre away."
)
