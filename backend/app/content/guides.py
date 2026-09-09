"""The Research Library: teaching material, addressed by stable guide id.

Two things make this a module rather than a database table. It is authored
content that ships with the app, and — more importantly — the coach's feedback
links to it *by id*. ``variable_measurable`` in a rubric result resolves to
``measurable-variables`` here. Nothing in the UI hard-codes a link to a guide,
so renaming a guide's title never breaks a recommendation.

Weak/strong examples exist to teach, not to be copied. Every one carries a
``why``: what changed between the two versions and what that change buys. A
student who reads only the strong version has learned nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.enums import GuideCategory


@dataclass
class Comparison:
    """A weak version, a stronger version, and what actually changed."""

    label: str
    weak: str
    strong: str
    why: str


@dataclass
class Section:
    heading: str
    body: str
    points: list[str] = field(default_factory=list)


@dataclass
class Guide:
    id: str
    title: str
    category: GuideCategory
    summary: str
    read_minutes: int
    tags: list[str]
    sections: list[Section] = field(default_factory=list)
    comparisons: list[Comparison] = field(default_factory=list)
    related: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Research fundamentals
# --------------------------------------------------------------------------- #

_FUNDAMENTALS = [
    Guide(
        id="choosing-a-topic",
        title="Choosing a topic you can actually finish",
        category=GuideCategory.FUNDAMENTALS,
        summary="Pick a topic by what you can measure and access, not by what sounds impressive.",
        read_minutes=5,
        tags=["topic", "getting_started", "feasibility"],
        sections=[
            Section(
                "Start from constraints, not from interest alone",
                "Interest keeps you going in week six; constraints decide whether there is a "
                "week six. Before committing, write down what you can measure, what equipment "
                "you can reach, how many hours a week you have, and whether your idea needs "
                "approval to run at all.",
                [
                    "What is the measurement, and what instrument produces it?",
                    "Can you get 15-30 data points in the time you have?",
                    "Does it involve people, animals, tissue or hazardous material? That means forms.",
                    "Could you run one trial this week? If not, the project is too big.",
                ],
            ),
            Section(
                "Narrow until it is boring, then widen slightly",
                "Most strong projects started as a topic that felt too small. 'Water quality' is "
                "a subject, not a project. 'Does filter mesh size change microfibre capture from "
                "laundry water?' is a project. Narrow until you can name the measurement, then "
                "add back just enough scope to be interesting.",
            ),
        ],
        comparisons=[
            Comparison(
                label="Topic scope",
                weak="I want to study climate change.",
                strong="I want to test whether tree canopy cover predicts air temperature along "
                "a 1 km transect through my neighbourhood.",
                why="The second names a measurable outcome (air temperature), a comparison "
                "(canopy cover), and a boundary (1 km transect). The first names a field of "
                "study. You cannot design a procedure for a field of study.",
            )
        ],
        related=["idea-to-research-question", "pilot-experiments", "measurable-variables"],
    ),
    Guide(
        id="idea-to-research-question",
        title="Turning an idea into a research question",
        category=GuideCategory.FUNDAMENTALS,
        summary="A research question names what you change, what you measure, and in what population.",
        read_minutes=6,
        tags=["research_question", "getting_started", "scope"],
        sections=[
            Section(
                "The three slots",
                "Almost every good science-fair question fills three slots: how does "
                "[what you change] affect [what you measure] in [what population or system]. "
                "If a reader cannot point at each slot, the question is not finished.",
                [
                    "What you change — the independent variable, with actual levels.",
                    "What you measure — the dependent variable, with a unit.",
                    "Where — the sample, organism, material or system, defined tightly enough to repeat.",
                ],
            ),
            Section(
                "Questions that cannot be answered",
                "Watch for questions that are really opinions ('what is the best…'), questions "
                "with no comparison ('does X work?'), and questions whose answer you already "
                "know. A question worth running is one where you can honestly describe two "
                "different outcomes and would believe either.",
            ),
        ],
        comparisons=[
            Comparison(
                label="Research question",
                weak="Does music affect concentration?",
                strong="Does instrumental background music at 60 dB change the number of correct "
                "answers on a 3-minute arithmetic task, compared with silence, in 14-16 year olds?",
                why="Three fixes. 'Music' became a specific, reproducible condition (instrumental, "
                "60 dB). 'Concentration' — which nobody can measure directly — became a countable "
                "outcome on a fixed task. And a comparison group (silence) appeared, without which "
                "there is no way to say the music did anything.",
            )
        ],
        related=["measurable-variables", "writing-a-hypothesis", "research-gaps"],
    ),
    Guide(
        id="writing-a-hypothesis",
        title="Writing a hypothesis that predicts something",
        category=GuideCategory.FUNDAMENTALS,
        summary="A hypothesis states a direction and a reason, and it must be able to be wrong.",
        read_minutes=5,
        tags=["hypothesis", "prediction", "mechanism"],
        sections=[
            Section(
                "Direction plus mechanism",
                "A hypothesis is not a restatement of the question. It commits to an outcome "
                "('increasing X will decrease Y') and says why you expect it ('because X reduces "
                "the surface area available for the reaction'). The mechanism is what a judge will "
                "ask about, and it is what makes the result interesting when you are wrong.",
            ),
            Section(
                "Falsifiability in practice",
                "Ask: what result would make me say the hypothesis was wrong? If no result could, "
                "rewrite it. 'Some effect may occur' cannot fail. 'Germination rate will be highest "
                "at 20 °C and fall at both 10 °C and 30 °C' can fail in several specific ways, which "
                "is exactly what makes it useful.",
            ),
        ],
        comparisons=[
            Comparison(
                label="Hypothesis",
                weak="I think the water temperature will affect how the radish seeds grow.",
                strong="Germination rate will peak near 20 °C and fall at 10 °C and 30 °C, because "
                "germination depends on enzyme activity, which slows when cold and denatures when hot.",
                why="The weak version cannot be wrong — any result 'affects' growth somehow. The "
                "strong version predicts a shape (a peak, not a straight line), names the "
                "temperatures, and gives a mechanism you can be judged on. If the result comes out "
                "flat, you have learned something specific.",
            )
        ],
        related=["idea-to-research-question", "independent-dependent-variables", "statistical-significance"],
    ),
    Guide(
        id="independent-dependent-variables",
        title="Independent and dependent variables",
        category=GuideCategory.FUNDAMENTALS,
        summary="You set the independent variable. You measure the dependent one. Confusing them breaks the design.",
        read_minutes=4,
        tags=["variables", "independent_variable", "dependent_variable"],
        sections=[
            Section(
                "Which is which",
                "The independent variable is the one you deliberately set to different levels — "
                "the thing under your control. The dependent variable is what you read off an "
                "instrument afterwards. A simple test: if you had to write your procedure, the "
                "independent variable appears in the setup steps and the dependent variable "
                "appears in the recording steps.",
                [
                    "Independent: at least two levels, ideally three or more.",
                    "Dependent: one primary outcome, with a unit and an instrument.",
                    "Everything else: held constant, or you cannot attribute the change.",
                ],
            ),
            Section(
                "One primary outcome",
                "Measuring six things and reporting whichever moved is a way to find noise. "
                "Name one primary dependent variable before you collect data. Secondary measures "
                "are fine, but say up front which one the project stands on.",
            ),
        ],
        related=["measurable-variables", "controlled-variables", "cherry-picking"],
    ),
    Guide(
        id="measurable-variables",
        title="Making a variable measurable",
        category=GuideCategory.FUNDAMENTALS,
        summary="If you cannot name the instrument and the unit, it is not yet a variable.",
        read_minutes=5,
        tags=["variables", "dependent_variable", "measurement", "operational_definition"],
        sections=[
            Section(
                "Operational definitions",
                "An operational definition replaces a concept with a procedure. 'Stress' is a "
                "concept. 'Resting heart rate in beats per minute, measured with a pulse oximeter "
                "after two minutes seated' is an operational definition. You are not claiming they "
                "are the same thing — you are stating exactly what you recorded, so someone else "
                "can record it too.",
                [
                    "Name the instrument and its precision.",
                    "Name the unit.",
                    "Name when and how often the reading is taken.",
                    "Name what counts as one observation.",
                ],
            ),
            Section(
                "Concepts that hide from measurement",
                "Words like effectiveness, quality, health, concentration, performance and "
                "efficiency all need replacing before you collect data. Each can be operationalised "
                "several ways, and the choice is yours to defend — but it has to be made.",
            ),
        ],
        comparisons=[
            Comparison(
                label="Dependent variable",
                weak="I will measure how healthy the plants are.",
                strong="I will measure total fresh mass of above-soil growth in grams on day 21, "
                "on a scale accurate to 0.01 g, harvesting each plant at the soil line.",
                why="'Healthy' cannot be written into a procedure — two people would measure it "
                "differently, and so would you on two different days. The strong version fixes the "
                "quantity, the unit, the instrument precision, the day, and the cut point. It is "
                "now repeatable, which is the whole point.",
            )
        ],
        related=["independent-dependent-variables", "data-collection", "choosing-a-graph"],
    ),
    Guide(
        id="controlled-variables",
        title="Controlled variables: what you hold still",
        category=GuideCategory.FUNDAMENTALS,
        summary="Anything that could plausibly change your outcome must be held constant or measured.",
        read_minutes=4,
        tags=["variables", "controlled_variables", "confounding"],
        sections=[
            Section(
                "Listing them honestly",
                "Write out everything that could affect your dependent variable. For each item, "
                "choose one of three: hold it constant, measure it and account for it, or "
                "randomise it. Anything that gets none of the three is a hole in the design, and "
                "it is better to name it in your limitations than to have a judge find it.",
            ),
            Section(
                "Constant does not mean ignored",
                "Holding temperature constant means recording that you did, and how. 'Room "
                "temperature' is not a controlled variable; '21 ± 1 °C, logged hourly' is.",
            ),
        ],
        related=["confounding-variables", "designing-a-controlled-experiment", "explaining-limitations"],
    ),
    Guide(
        id="correlation-vs-causation",
        title="Correlation is not causation",
        category=GuideCategory.FUNDAMENTALS,
        summary="Only a controlled manipulation licenses a causal claim. Observational work gets careful language.",
        read_minutes=5,
        tags=["causation", "correlation", "conclusions", "observational"],
        sections=[
            Section(
                "What earns a causal claim",
                "You may say X caused Y when you set X yourself, assigned units to conditions "
                "without bias, and held the plausible alternatives constant. If you observed both "
                "X and Y in the wild, you may say they are associated, and you should say what "
                "else could explain it.",
            ),
            Section(
                "Language that stays honest",
                "'Was associated with', 'predicted', 'co-varied with' are accurate for "
                "observational data. 'Caused', 'led to', 'improved' claim more than the design "
                "supports. Judges notice this quickly, and correcting your own language is a "
                "strength, not an admission.",
            ),
        ],
        comparisons=[
            Comparison(
                label="Conclusion wording",
                weak="Students who slept more had faster reaction times, so more sleep improves "
                "reaction time.",
                strong="Self-reported sleep duration was associated with faster reaction times "
                "(r = -0.41). Because sleep was not assigned, this study cannot separate sleep from "
                "correlated factors such as caffeine use, screen time before bed, or overall health.",
                why="Same data, honest claim. The weak version turns an observed association into a "
                "causal one in a single word ('improves'). The strong version reports the "
                "association, then names the specific alternatives it cannot rule out — which is "
                "the part that shows you understand your own design.",
            )
        ],
        related=["confounding-variables", "correlation", "explaining-limitations"],
    ),
]


# --------------------------------------------------------------------------- #
# Experimental design
# --------------------------------------------------------------------------- #

_DESIGN = [
    Guide(
        id="designing-a-controlled-experiment",
        title="Designing a controlled experiment",
        category=GuideCategory.EXPERIMENTAL_DESIGN,
        summary="One variable changes on purpose, everything else is pinned down, and the comparison is built in.",
        read_minutes=7,
        tags=["experimental_design", "methodology", "procedure"],
        sections=[
            Section(
                "The skeleton",
                "A controlled experiment has levels of one independent variable, a control "
                "condition, replicate units at each level, a fixed procedure applied identically, "
                "and one primary measurement taken the same way every time.",
                [
                    "Three or more levels beat two: they show shape, not just difference.",
                    "Decide the number of replicates before you start, not after you peek.",
                    "Randomise which unit gets which condition.",
                    "Write the procedure so someone else could run it without asking you anything.",
                ],
            ),
            Section(
                "Order and timing matter",
                "If you run all your control trials on Monday and all your treatment trials on "
                "Friday, day is confounded with condition. Interleave conditions, and record the "
                "order you actually ran them in.",
            ),
        ],
        comparisons=[
            Comparison(
                label="Procedure detail",
                weak="I watered the plants with different water temperatures and recorded growth.",
                strong="Each of 24 pots received 50 mL of water at 10, 20 or 30 °C (8 pots per "
                "level, assigned by drawing lots), delivered at 08:00 daily for 21 days; water "
                "temperature was checked with a thermocouple immediately before pouring.",
                why="The strong version fixes the volume, the schedule, the assignment method, the "
                "replicate count and the verification step. Every one of those was a choice the "
                "weak version made silently — and silent choices are the ones that turn out to "
                "explain your results.",
            )
        ],
        related=["choosing-a-control-group", "repeated-trials", "avoiding-bias", "sample-size"],
    ),
    Guide(
        id="choosing-a-control-group",
        title="Choosing a control group",
        category=GuideCategory.EXPERIMENTAL_DESIGN,
        summary="The control tells you what would have happened anyway. Without it you have a story, not a result.",
        read_minutes=5,
        tags=["control_group", "experimental_design", "comparison"],
        sections=[
            Section(
                "What a control is for",
                "The control isolates your treatment from everything else that was going on: time "
                "passing, handling, the act of measuring, seasonal drift. It should be identical "
                "to your treatment groups in every respect except the one variable you are testing.",
            ),
            Section(
                "Common control mistakes",
                "A control run in a different room, on different days, or by a different person is "
                "not a control. A 'no treatment' group when your treatment involves handling should "
                "usually be a sham-handled group instead — otherwise you have measured handling.",
            ),
        ],
        related=["designing-a-controlled-experiment", "confounding-variables", "avoiding-bias"],
    ),
    Guide(
        id="sample-size",
        title="How many samples do you need?",
        category=GuideCategory.EXPERIMENTAL_DESIGN,
        summary="Enough that a real difference would show, and few enough that you finish. Say how you chose.",
        read_minutes=6,
        tags=["sample_size", "replicates", "statistics", "power"],
        sections=[
            Section(
                "The honest science-fair answer",
                "You will rarely have enough for a formal power calculation, and that is fine. "
                "What is not fine is picking a number without a reason. State the reason: time per "
                "trial, material cost, or a pilot estimate of how variable your measurements are.",
                [
                    "Noisier measurement means more replicates are needed to see the same effect.",
                    "Below about 5 per group, one odd value dominates everything.",
                    "More levels with fewer replicates each is usually worse than fewer levels done properly.",
                ],
            ),
            Section(
                "Report it, don't hide it",
                "n = 6 per condition, honestly reported alongside the spread, is stronger than "
                "n = 6 presented as though it settled the question. Small samples do not disqualify "
                "a project. Overclaiming from small samples does.",
            ),
        ],
        related=["repeated-trials", "pilot-experiments", "statistical-significance", "confidence-intervals"],
    ),
    Guide(
        id="repeated-trials",
        title="Repeated trials and what they buy you",
        category=GuideCategory.EXPERIMENTAL_DESIGN,
        summary="Repeats measure your noise. Without them you cannot tell a real difference from a lucky one.",
        read_minutes=4,
        tags=["replicates", "trials", "variability", "reliability"],
        sections=[
            Section(
                "Replicates vs repeated measurements",
                "Measuring the same plant three times tells you about your ruler. Growing three "
                "plants under the same condition tells you about plants. Both are useful and they "
                "are not interchangeable — say which you did.",
            ),
            Section(
                "What the spread is telling you",
                "If the variation within one condition is as large as the difference between "
                "conditions, you do not have a result yet. That comparison — spread within versus "
                "difference between — is the single most useful thing repeated trials give you.",
            ),
        ],
        related=["sample-size", "error-bars", "descriptive-statistics"],
    ),
    Guide(
        id="confounding-variables",
        title="Finding confounding variables before a judge does",
        category=GuideCategory.EXPERIMENTAL_DESIGN,
        summary="A confound is anything that changed alongside your treatment and could explain the result instead.",
        read_minutes=6,
        tags=["confounding", "validity", "experimental_design", "limitations"],
        sections=[
            Section(
                "How to hunt for them",
                "Take your result and try to explain it without your hypothesis. Anything that "
                "works as an alternative explanation is a confound. Then check: did that thing "
                "differ systematically between your groups?",
                [
                    "Position: were treatment samples all nearer the window?",
                    "Time: were conditions run on different days?",
                    "Person: did different people measure different groups?",
                    "Batch: did one condition use a different bag of soil, roll of wire, jar of reagent?",
                ],
            ),
            Section(
                "What to do once you find one",
                "Fix it if you can still collect data, and rerun. If you cannot, measure it and "
                "report it as a limitation with an estimate of which direction it would push your "
                "result. Naming the confound and its direction is a mark of a strong project.",
            ),
        ],
        related=["controlled-variables", "correlation-vs-causation", "explaining-limitations", "avoiding-bias"],
    ),
    Guide(
        id="pilot-experiments",
        title="Run a pilot before you run the study",
        category=GuideCategory.EXPERIMENTAL_DESIGN,
        summary="A few throwaway trials will tell you what is broken while it is still cheap to fix.",
        read_minutes=4,
        tags=["pilot", "planning", "feasibility", "methodology"],
        sections=[
            Section(
                "What a pilot answers",
                "How long one trial really takes. Whether your instrument resolves the differences "
                "you care about. Whether your extreme levels produce anything at all. How variable "
                "your measurements are, which sets your replicate count.",
            ),
            Section(
                "Pilot data are not results",
                "Keep pilot trials out of your final dataset unless the procedure was identical. "
                "Record them in your notebook — they are excellent evidence of iteration, and "
                "judges like seeing that the procedure was refined for a stated reason.",
            ),
        ],
        related=["sample-size", "designing-a-controlled-experiment", "research-notebook"],
    ),
    Guide(
        id="avoiding-bias",
        title="Keeping your own expectations out of the data",
        category=GuideCategory.EXPERIMENTAL_DESIGN,
        summary="You want a particular result. Design so that wanting it cannot influence what you record.",
        read_minutes=5,
        tags=["bias", "blinding", "randomisation", "validity"],
        sections=[
            Section(
                "Where bias gets in",
                "In assignment (putting the healthier-looking seedlings in the treatment group), in "
                "measurement (rounding kindly for the condition you like), in stopping (collecting "
                "until the result looks right), and in selection (dropping trials that 'went wrong').",
            ),
            Section(
                "Cheap countermeasures",
                "Randomise assignment with a coin or a random number, not by feel. Label samples "
                "with codes so you do not know which condition you are measuring. Fix your stopping "
                "rule in advance. Write down every excluded trial and the reason, before you look "
                "at the numbers.",
            ),
        ],
        related=["choosing-a-control-group", "cherry-picking", "outliers", "confounding-variables"],
    ),
]


# --------------------------------------------------------------------------- #
# Statistics
# --------------------------------------------------------------------------- #

_STATISTICS = [
    Guide(
        id="descriptive-statistics",
        title="Mean, median and standard deviation",
        category=GuideCategory.STATISTICS,
        summary="Centre and spread together. A mean without a spread hides everything interesting.",
        read_minutes=5,
        tags=["statistics", "mean", "median", "standard_deviation", "spread"],
        sections=[
            Section(
                "Centre",
                "The mean is the balance point and uses every value, which is why one extreme "
                "reading drags it. The median is the middle value and ignores how extreme the "
                "extremes are. Report the median when your data are skewed or you have a value you "
                "cannot justify removing — and say which you used and why.",
            ),
            Section(
                "Spread",
                "Standard deviation is roughly the typical distance of a value from the mean. It "
                "is the number that tells a reader whether your conditions really differ. Two "
                "groups with means of 40 and 46 are a different story when the standard deviation "
                "is 2 than when it is 20.",
                [
                    "Always report n alongside mean and standard deviation.",
                    "Range (min-max) is fine for very small samples, and honest about it.",
                    "Standard error is not standard deviation — say which your error bars show.",
                ],
            ),
        ],
        comparisons=[
            Comparison(
                label="Reporting a result",
                weak="The treatment group grew more (52 mm vs 45 mm).",
                strong="Treatment mean 52 mm (SD 4.1, n = 8); control mean 45 mm (SD 3.8, n = 8). "
                "The groups overlap little relative to their spread.",
                why="The weak version gives a reader no way to judge whether 7 mm is a real "
                "difference or ordinary variation. Adding SD and n turns an assertion into "
                "evidence a reader can evaluate for themselves.",
            )
        ],
        related=["error-bars", "statistical-significance", "outliers"],
    ),
    Guide(
        id="statistical-significance",
        title="What statistical significance does and does not mean",
        category=GuideCategory.STATISTICS,
        summary="Significance is about how surprising your data would be if there were no effect. It is not importance.",
        read_minutes=6,
        tags=["statistics", "significance", "p_value", "inference"],
        sections=[
            Section(
                "The actual question a test answers",
                "A significance test asks: if there were genuinely no difference, how often would "
                "random sampling alone produce a difference at least this large? A small answer "
                "means your data would be unusual under 'no effect'. That is all it means.",
            ),
            Section(
                "Three things it is not",
                "It is not the probability your hypothesis is true. It is not a measure of how big "
                "the effect is. And a non-significant result is not proof of no effect — with n = 6 "
                "you may simply lack the sensitivity to see a real difference.",
                [
                    "Report the effect size (the actual difference, in units) alongside any test.",
                    "With small n, say 'we could not detect a difference', not 'there is no difference'.",
                    "Decide your threshold before you look, and stick with it.",
                ],
            ),
        ],
        comparisons=[
            Comparison(
                label="Interpreting a test",
                weak="p = 0.03, so the treatment works and the hypothesis is proven.",
                strong="p = 0.03 for a difference of 7 mm (95% CI 1-13 mm). A difference this large "
                "would be uncommon if the treatment had no effect, though with n = 8 per group the "
                "interval is wide and the size of the effect is not well pinned down.",
                why="'Proven' overclaims twice: a single test never proves anything, and a p-value "
                "says nothing about the size of the effect. The strong version reports how big the "
                "difference was, how uncertain that estimate is, and what the sample size limits.",
            )
        ],
        related=["p-values", "confidence-intervals", "choosing-a-statistical-test", "sample-size"],
    ),
    Guide(
        id="p-values",
        title="P-values at science-fair level",
        category=GuideCategory.STATISTICS,
        summary="A p-value is a surprise index under the assumption of no effect. Use it, but do not lean on it.",
        read_minutes=5,
        tags=["statistics", "p_value", "significance"],
        sections=[
            Section(
                "Reading one aloud",
                "p = 0.04 reads as: 'if the conditions truly did not differ, I would see a "
                "difference this large or larger about 4 times in 100 by chance alone.' Practise "
                "saying it that way — a judge who asks what your p-value means is usually checking "
                "whether you can.",
            ),
            Section(
                "The 0.05 line is a convention",
                "There is nothing magic about 0.05. p = 0.06 is not 'no effect' and p = 0.049 is not "
                "'proof'. Report the number itself rather than only 'significant', and never test "
                "several outcomes and report the one that crossed the line.",
            ),
        ],
        related=["statistical-significance", "cherry-picking", "choosing-a-statistical-test"],
    ),
    Guide(
        id="confidence-intervals",
        title="Confidence intervals",
        category=GuideCategory.STATISTICS,
        summary="An interval shows how precisely you pinned the effect down — usually more useful than a p-value.",
        read_minutes=5,
        tags=["statistics", "confidence_interval", "uncertainty", "effect_size"],
        sections=[
            Section(
                "What it communicates",
                "A 95% confidence interval of 1-13 mm says your data are consistent with an effect "
                "anywhere from barely-there to substantial. That is honest and informative in a way "
                "'p < 0.05' is not. A wide interval is not a failure — it is a measured statement "
                "about how much your sample size could resolve.",
            ),
            Section(
                "Reading overlap carefully",
                "If an interval for a difference includes zero, your data are compatible with no "
                "effect. Comparing two separate group intervals by eye is a rougher check: "
                "non-overlap suggests a difference, but overlap does not rule one out.",
            ),
        ],
        related=["statistical-significance", "error-bars", "sample-size"],
    ),
    Guide(
        id="correlation",
        title="Correlation and what r actually says",
        category=GuideCategory.STATISTICS,
        summary="r measures how tightly points follow a straight line, between -1 and 1. It says nothing about cause or slope.",
        read_minutes=5,
        tags=["statistics", "correlation", "relationship", "scatter"],
        sections=[
            Section(
                "Sign, strength, shape",
                "The sign says direction. The magnitude says tightness, not steepness — a shallow "
                "line can have r = 0.99. And r only sees straight lines: a perfect U-shaped "
                "relationship can produce r near zero. Always plot the scatter before trusting r.",
            ),
            Section(
                "Reporting it",
                "Give r, n, and the scatter plot. In a science-fair context r = 0.4 with n = 20 is "
                "worth discussing as a modest association, not announcing as a finding.",
            ),
        ],
        related=["correlation-vs-causation", "regression", "choosing-a-graph"],
    ),
    Guide(
        id="regression",
        title="Regression: fitting a line and reading it",
        category=GuideCategory.STATISTICS,
        summary="The slope is the effect per unit. R² is how much of the variation the line accounts for.",
        read_minutes=6,
        tags=["statistics", "regression", "slope", "r_squared", "model"],
        sections=[
            Section(
                "Slope is the interesting number",
                "'Temperature rose 0.8 °C for every 10% drop in canopy cover' is a scientific "
                "statement with units. R² alone is not — it tells you about scatter around the "
                "line, not about the size of the relationship.",
            ),
            Section(
                "Do not extrapolate",
                "A line fitted between 10 and 30 °C says nothing about 45 °C. Say what range your "
                "data cover and refuse to predict outside it. Judges test this.",
            ),
        ],
        related=["correlation", "choosing-a-graph", "explaining-limitations"],
    ),
    Guide(
        id="choosing-a-statistical-test",
        title="Choosing a statistical test",
        category=GuideCategory.STATISTICS,
        summary="The test follows from your design: what kind of data, how many groups, paired or not.",
        read_minutes=6,
        tags=["statistics", "test_selection", "t_test", "chi_square", "anova"],
        sections=[
            Section(
                "Answer four questions first",
                "What kind is your outcome — a measurement, or a count/category? How many groups "
                "are you comparing? Are the observations paired (same unit measured twice) or "
                "independent? Is your sample big enough and roughly symmetric?",
                [
                    "Measurement, two independent groups: t-test (or Mann-Whitney if very skewed/small).",
                    "Measurement, same units before and after: paired t-test.",
                    "Measurement, three or more groups: ANOVA, then say which pairs you compared.",
                    "Counts in categories: chi-square, provided expected counts are not tiny.",
                    "Two measurements per unit, looking for a relationship: correlation or regression.",
                ],
            ),
            Section(
                "Say why you chose it",
                "Judges rarely ask whether you used the fanciest test. They ask why that test suits "
                "your data. Having a one-sentence answer ready is worth more than the test itself.",
            ),
        ],
        related=["statistical-significance", "descriptive-statistics", "sample-size"],
    ),
    Guide(
        id="error-bars",
        title="Error bars and how to label them",
        category=GuideCategory.STATISTICS,
        summary="Unlabelled error bars are unreadable. Say whether they show SD, SE or a confidence interval.",
        read_minutes=4,
        tags=["statistics", "error_bars", "graphs", "uncertainty"],
        sections=[
            Section(
                "Three different bars",
                "Standard deviation bars show how spread out your individual values are. Standard "
                "error bars show how precisely you know the mean, and are always smaller. "
                "Confidence interval bars show a range compatible with your data. They tell "
                "different stories, so the caption must say which one you plotted.",
            ),
            Section(
                "What a reader does with them",
                "They compare bar length to the gap between your conditions. If the gap is small "
                "relative to the bars, your figure is honestly telling the reader to be cautious — "
                "which is better than a bare bar chart that implies more than you found.",
            ),
        ],
        related=["descriptive-statistics", "confidence-intervals", "choosing-a-graph"],
    ),
]


# --------------------------------------------------------------------------- #
# Research and literature
# --------------------------------------------------------------------------- #

_LITERATURE = [
    Guide(
        id="finding-credible-sources",
        title="Finding sources you can actually cite",
        category=GuideCategory.LITERATURE,
        summary="Prefer peer-reviewed work and primary sources. Judge a source by its methods, not its confidence.",
        read_minutes=6,
        tags=["literature", "sources", "credibility", "background_research"],
        sections=[
            Section(
                "Where to look",
                "Google Scholar, PubMed, arXiv, and your library's databases will find primary "
                "research. A news article about a study is not the study — follow it back to the "
                "paper. Review articles are excellent starting points because their reference lists "
                "are a curated map of the field.",
            ),
            Section(
                "Judging a source",
                "Check whether it was peer reviewed, whether the methods section lets you see what "
                "was actually done, how many subjects or samples there were, and who funded it. A "
                "small, careful, clearly-reported study beats a large one that hides its methods.",
                [
                    "Primary research > review > textbook > news > blog > AI summary.",
                    "If you cannot see the methods, you cannot evaluate the claim.",
                    "Note the date: in fast-moving fields a 2009 result may be superseded.",
                ],
            ),
        ],
        related=["reading-a-scientific-paper", "literature-review", "citations"],
    ),
    Guide(
        id="reading-a-scientific-paper",
        title="Reading a scientific paper without drowning",
        category=GuideCategory.LITERATURE,
        summary="Read out of order: abstract, figures, methods, then discussion. Skip the rest until you need it.",
        read_minutes=6,
        tags=["literature", "reading", "papers", "background_research"],
        sections=[
            Section(
                "The order that works",
                "Abstract to decide whether it is relevant. Figures and captions to see what they "
                "actually found — the figures usually carry the whole result. Methods to see how, "
                "and whether you could adapt any of it. Discussion last, and read it sceptically: "
                "it is where authors are most speculative.",
            ),
            Section(
                "Three questions to write down for each paper",
                "What exactly did they measure? What did they find, with numbers? What did they say "
                "was still unknown? That third answer is where your own research gap usually comes "
                "from.",
            ),
        ],
        related=["literature-review", "research-gaps", "finding-credible-sources"],
    ),
    Guide(
        id="literature-review",
        title="Writing a literature review that has a point",
        category=GuideCategory.LITERATURE,
        summary="Organise by idea, not by paper. The review should end by making your question necessary.",
        read_minutes=7,
        tags=["literature", "literature_review", "background_research", "writing"],
        sections=[
            Section(
                "Structure by theme",
                "A list of paragraphs each summarising one paper is a reading log, not a review. "
                "Group sources by what they claim, note where they agree and disagree, and let the "
                "disagreements do the work — an unresolved disagreement is a research opportunity.",
            ),
            Section(
                "Land on your question",
                "The last paragraph should make your research question feel inevitable: here is "
                "what is known, here is what nobody has tested in this setting, and that is what "
                "this project does.",
            ),
        ],
        comparisons=[
            Comparison(
                label="Literature review paragraph",
                weak="Smith (2019) studied biochar and found it helped. Jones (2021) also studied "
                "biochar and found it helped. Lee (2022) studied biochar in sandy soil.",
                strong="Biochar reduces nitrate leaching in temperate soils under moderate rainfall "
                "(Smith 2019; Jones 2021), but both studies used steady irrigation. Lee (2022) "
                "found the effect weakened in sandy soil, suggesting infiltration rate matters — "
                "which leaves open whether the effect survives the high-intensity bursts typical of "
                "monsoon rainfall.",
                why="The weak version reports three papers separately and reaches no conclusion. The "
                "strong version synthesises them into one claim, identifies the shared limitation "
                "(steady irrigation), uses the third paper to explain why that limitation matters, "
                "and arrives at a gap. Same three sources, entirely different value.",
            )
        ],
        related=["research-gaps", "determining-novelty", "reading-a-scientific-paper", "citations"],
    ),
    Guide(
        id="research-gaps",
        title="Identifying a research gap",
        category=GuideCategory.LITERATURE,
        summary="A gap is a specific question the literature raises and does not answer — usually a changed condition.",
        read_minutes=6,
        tags=["novelty", "research_gap", "literature", "differentiation"],
        sections=[
            Section(
                "Where gaps come from",
                "The 'future work' sentences at the end of papers. Conditions nobody tested — a "
                "different climate, material, population, concentration range or timescale. Results "
                "that conflict between studies. Methods that were expensive and could be done "
                "cheaply.",
            ),
            Section(
                "A gap is not 'nobody has done exactly this'",
                "Nobody has tested your specific brand of soil in your specific backyard, and that "
                "is not interesting. A real gap comes with a reason the answer might differ from "
                "what is known — a mechanism that plausibly changes the outcome.",
            ),
        ],
        related=["determining-novelty", "literature-review", "explaining-novelty"],
    ),
    Guide(
        id="determining-novelty",
        title="Working out whether your project is novel",
        category=GuideCategory.LITERATURE,
        summary="Novelty is relative to what is published, and you can only claim it after searching properly.",
        read_minutes=6,
        tags=["novelty", "differentiation", "literature", "search"],
        sections=[
            Section(
                "Search before you claim",
                "Search your dependent variable and independent variable together, then with "
                "synonyms, then in the scientific vocabulary of the field rather than everyday "
                "words. If you find nothing, that usually means your search terms are wrong, not "
                "that the area is untouched.",
            ),
            Section(
                "Degrees of novelty, all legitimate",
                "Replicating a published result in a new setting is real science. Extending a range, "
                "combining two known approaches, or applying an expensive method cheaply are all "
                "defensible. Claiming nobody has ever studied your topic almost never is.",
            ),
        ],
        related=["research-gaps", "explaining-novelty", "literature-review"],
    ),
    Guide(
        id="citations",
        title="Citing properly, and why it protects you",
        category=GuideCategory.LITERATURE,
        summary="Cite every claim you did not generate. A traceable reference list is part of the evidence.",
        read_minutes=4,
        tags=["citations", "references", "ethics", "writing"],
        sections=[
            Section(
                "What needs a citation",
                "Any fact, number, method or idea that came from somewhere else — including "
                "background statements that feel like common knowledge but are not. Methods you "
                "adapted need a citation even if you changed them.",
            ),
            Section(
                "Practical hygiene",
                "Pick one style and use it consistently. Record the full reference the moment you "
                "read something. Never cite a paper from its abstract alone or from a summary you "
                "did not verify — including one produced by an AI tool.",
            ),
        ],
        related=["finding-credible-sources", "literature-review", "research-notebook"],
    ),
]


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #

_DATA = [
    Guide(
        id="data-collection",
        title="Collecting data you will still trust in March",
        category=GuideCategory.DATA,
        summary="Design the table before the first trial. Record conditions, not just outcomes.",
        read_minutes=5,
        tags=["data", "data_collection", "measurement", "notebook"],
        sections=[
            Section(
                "Build the sheet first",
                "Make your data table before you collect anything: one row per observation, columns "
                "for date, time, condition, replicate id, the measurement, the units, and a notes "
                "column for anything odd. If you find yourself inventing a column mid-experiment, "
                "you have found a variable you had not thought about.",
            ),
            Section(
                "Raw stays raw",
                "Keep the original readings untouched and do calculations in a separate column or "
                "sheet. Being able to show a judge your raw numbers, exactly as recorded, is worth "
                "more than a tidy summary.",
            ),
        ],
        related=["data-cleaning", "research-notebook", "measurable-variables"],
    ),
    Guide(
        id="data-cleaning",
        title="Cleaning data without deleting your result",
        category=GuideCategory.DATA,
        summary="Fix recording errors, document every change, and never remove a value for being inconvenient.",
        read_minutes=5,
        tags=["data", "data_cleaning", "integrity", "outliers"],
        sections=[
            Section(
                "Legitimate cleaning",
                "Correcting a transcription error against your notebook. Standardising units. "
                "Marking a trial as invalid because you recorded at the time that the equipment "
                "failed. All of these are fine, and all of them get written down.",
            ),
            Section(
                "The rule",
                "Every change gets a reason recorded before you know what it does to your result. "
                "Keep the original file. If you cannot explain an exclusion to a judge without "
                "referring to the result, the exclusion is not defensible.",
            ),
        ],
        related=["outliers", "cherry-picking", "data-collection"],
    ),
    Guide(
        id="choosing-a-graph",
        title="Choosing the right graph",
        category=GuideCategory.DATA,
        summary="The graph type follows from the comparison you want the reader to make.",
        read_minutes=5,
        tags=["data", "graphs", "visualisation", "poster"],
        sections=[
            Section(
                "Match the graph to the question",
                "Comparing a few categories: bar chart with error bars. Relationship between two "
                "measurements: scatter plot, with a fitted line only if a line is justified. "
                "Change over time: line chart. Distribution shape: histogram or box plot. Showing "
                "every point when n is small is almost always better than showing only a mean.",
                [
                    "Label both axes with units. Every time.",
                    "Start bar charts at zero; truncating the axis exaggerates differences.",
                    "One message per figure — if it needs two paragraphs to explain, split it.",
                ],
            ),
            Section(
                "Pie charts and 3D effects",
                "Pie charts make comparison hard and are rarely the right answer. 3D bars distort "
                "the very quantity they are supposed to show. Neither belongs on a research poster.",
            ),
        ],
        related=["error-bars", "poster", "descriptive-statistics"],
    ),
    Guide(
        id="outliers",
        title="What to do with an outlier",
        category=GuideCategory.DATA,
        summary="Investigate first, and only exclude for a documented procedural reason — never for being extreme.",
        read_minutes=5,
        tags=["data", "outliers", "integrity", "analysis"],
        sections=[
            Section(
                "Investigate before deciding",
                "Go back to your notebook for that trial. Was there a recorded problem — equipment, "
                "contamination, a misread scale? A documented cause justifies exclusion. 'It doesn't "
                "fit' does not.",
            ),
            Section(
                "If you cannot explain it",
                "Keep it, and report both analyses: with and without. Then say which you based your "
                "conclusion on and why. An outlier you cannot explain may be the most scientifically "
                "interesting thing you found.",
            ),
        ],
        related=["data-cleaning", "cherry-picking", "descriptive-statistics", "explaining-limitations"],
    ),
    Guide(
        id="cherry-picking",
        title="Avoiding cherry-picking",
        category=GuideCategory.DATA,
        summary="Report everything you measured, including the parts that did not support your hypothesis.",
        read_minutes=5,
        tags=["data", "integrity", "bias", "reporting"],
        sections=[
            Section(
                "The forms it takes",
                "Reporting the one outcome of six that moved. Showing the trial that worked. "
                "Stopping collection when the result looks good. Choosing the analysis after seeing "
                "which one gives a smaller p-value. Each is easy to do without meaning to, which is "
                "why the countermeasure is written down in advance.",
            ),
            Section(
                "The fix",
                "Before collecting, record your primary outcome, your planned analysis, your "
                "stopping rule and your exclusion criteria. Then report everything against that "
                "plan. A hypothesis that was not supported, reported clearly, is a genuinely good "
                "science-fair project.",
            ),
        ],
        related=["avoiding-bias", "outliers", "p-values", "explaining-limitations"],
    ),
]


# --------------------------------------------------------------------------- #
# Science fair
# --------------------------------------------------------------------------- #

_SCIENCE_FAIR = [
    Guide(
        id="research-plan",
        title="Writing a research plan",
        category=GuideCategory.SCIENCE_FAIR,
        summary="The document you write before you start: question, procedure, risks and analysis, in enough detail to be approved.",
        read_minutes=7,
        tags=["science_fair", "research_plan", "approval", "forms"],
        sections=[
            Section(
                "What it must contain",
                "Your question and hypothesis. The procedure in numbered steps with quantities. "
                "Your variables and controls. How many trials and why. Risk assessment and safety "
                "handling. What data you will collect and how you will analyse it. What you will do "
                "with the material afterwards.",
            ),
            Section(
                "Approval comes before data",
                "Projects involving people, vertebrates, tissue, or hazardous materials usually "
                "require sign-off before any data are collected — data collected early may be "
                "disqualified. Confirm what applies to your project with your fair's rules and "
                "your advisor; do not rely on this app for eligibility.",
            ),
        ],
        related=["designing-a-controlled-experiment", "research-notebook", "abstract"],
    ),
    Guide(
        id="abstract",
        title="Writing an abstract",
        category=GuideCategory.SCIENCE_FAIR,
        summary="Roughly 250 words: purpose, procedure, results with numbers, conclusion. Results are not optional.",
        read_minutes=5,
        tags=["science_fair", "abstract", "writing", "communication"],
        sections=[
            Section(
                "The four moves",
                "One or two sentences on why the question matters and what it is. Two or three on "
                "what you actually did, with the key quantities. Two or three on what you found, "
                "with numbers. One on what it means and what is next. Word limits vary by fair — "
                "check yours.",
            ),
            Section(
                "The most common failure",
                "Abstracts that describe the method and then say 'results will be discussed'. The "
                "result is the reason anyone reads it. Put the numbers in.",
            ),
        ],
        comparisons=[
            Comparison(
                label="Abstract result sentence",
                weak="The data were analysed and the results showed that the biochar had an effect "
                "on nitrate levels.",
                strong="Nitrate in leachate fell from 41.2 mg/L (control, SD 3.9) to 26.8 mg/L at "
                "the 4% biochar rate (SD 4.4, n = 6 per rate), a 35% reduction; the effect did not "
                "increase further at 8%.",
                why="The weak sentence could describe any experiment ever run. The strong one gives "
                "the direction, the magnitude, the units, the spread, the sample size, and a "
                "genuinely interesting detail — that the effect plateaus. A judge reading 200 "
                "abstracts remembers the second one.",
            )
        ],
        related=["poster", "explaining-novelty", "descriptive-statistics"],
    ),
    Guide(
        id="poster",
        title="Building a poster that works from two metres away",
        category=GuideCategory.SCIENCE_FAIR,
        summary="Figures carry the project. Text is caption-length. Judges read the board before they meet you.",
        read_minutes=6,
        tags=["science_fair", "poster", "communication", "figures"],
        sections=[
            Section(
                "Layout and hierarchy",
                "Question at the top, large enough to read across the aisle. Then method as a "
                "compact diagram or numbered list, results as your best two or three figures, and "
                "conclusion in a sentence that answers the question directly. Anything a judge has "
                "to lean in to read is competing with your figures for attention.",
                [
                    "Body text no smaller than about 24 pt; title much larger.",
                    "Every figure gets a caption that states the finding, not just the axes.",
                    "Leave white space; a full board reads as an unedited one.",
                ],
            ),
            Section(
                "What to cut",
                "Long background paragraphs, the full procedure, raw data tables, and clip art. "
                "Those belong in your notebook or a handout. The board's job is to make a judge "
                "want to ask you a question.",
            ),
        ],
        comparisons=[
            Comparison(
                label="Figure caption",
                weak="Figure 2: Graph of results.",
                strong="Figure 2: Nitrate in leachate by biochar rate. Reduction plateaus above 4% "
                "(mean ± SD, n = 6 per rate).",
                why="A caption is often the only text a judge reads on a figure. The strong version "
                "states the finding, names what the error bars are, and gives the sample size — so "
                "the figure stands alone if you are talking to someone else when they walk past.",
            )
        ],
        related=["choosing-a-graph", "abstract", "judge-interview"],
    ),
    Guide(
        id="research-notebook",
        title="Keeping a research notebook judges will believe",
        category=GuideCategory.SCIENCE_FAIR,
        summary="Dated, contemporaneous, and honest about what went wrong. It is evidence, not a report.",
        read_minutes=5,
        tags=["science_fair", "notebook", "documentation", "integrity"],
        sections=[
            Section(
                "Write it as you go",
                "Every entry dated, written the day it happened. Record what you did, what you "
                "observed, raw numbers, what went wrong, what you changed and why, and what you "
                "plan next. A notebook reconstructed the week before the fair reads exactly like "
                "one, and judges have seen many.",
            ),
            Section(
                "Failures are the valuable part",
                "The entries where the procedure broke and you fixed it are the strongest evidence "
                "that the work is yours. Do not tidy them out.",
            ),
        ],
        related=["data-collection", "pilot-experiments", "judge-interview"],
    ),
    Guide(
        id="judge-interview",
        title="The judge interview",
        category=GuideCategory.SCIENCE_FAIR,
        summary="Judges are testing whether you understand your own project. Say 'I don't know' when it is true.",
        read_minutes=6,
        tags=["science_fair", "judging", "interview", "communication"],
        sections=[
            Section(
                "Prepare four answers",
                "Your project in 60 seconds without jargon. Why this question mattered. Your single "
                "biggest limitation. What you would do next with more time. Almost every interview "
                "is a variation on those four.",
            ),
            Section(
                "Questions designed to probe",
                "'Why that control?' 'How do you know it wasn't X?' 'What does your p-value mean?' "
                "'What would change your conclusion?' These are checking understanding, not "
                "attacking you. A confident 'I don't know, and here is how I would find out' scores "
                "better than a guess, and far better than a bluff.",
            ),
        ],
        related=["explaining-limitations", "explaining-novelty", "statistical-significance"],
    ),
    Guide(
        id="explaining-limitations",
        title="Explaining limitations without undermining yourself",
        category=GuideCategory.SCIENCE_FAIR,
        summary="Name the limitation, say which direction it would push your result, and say what would fix it.",
        read_minutes=5,
        tags=["science_fair", "limitations", "judging", "communication"],
        sections=[
            Section(
                "The three-part form",
                "What the limitation is, what effect it plausibly had on your result, and what you "
                "would do differently. That third part turns an apology into evidence of judgement.",
            ),
            Section(
                "Own them before you are asked",
                "A judge who finds a limitation you did not mention wonders what else you missed. "
                "A student who raises it first looks like they understand their own design — which "
                "is precisely what is being assessed.",
            ),
        ],
        comparisons=[
            Comparison(
                label="Limitation statement",
                weak="A limitation is that we only had a small sample size, so the results may not "
                "be accurate.",
                strong="With 8 plants per condition, the confidence interval on the difference "
                "(1-13 mm) is wide, so the size of the effect is poorly pinned down even though its "
                "direction was consistent across all three replicate blocks. Running 20 per "
                "condition, which needs a second grow shelf, would roughly halve that interval.",
                why="The weak version is vague enough to apply to any project and quietly implies "
                "the whole result is untrustworthy. The strong version quantifies the imprecision, "
                "separates what is uncertain (magnitude) from what is not (direction), and names a "
                "concrete fix with its real-world constraint.",
            )
        ],
        related=["confounding-variables", "sample-size", "judge-interview", "confidence-intervals"],
    ),
    Guide(
        id="explaining-novelty",
        title="Explaining what is new about your project",
        category=GuideCategory.SCIENCE_FAIR,
        summary="Say what is known, what you changed, and why that change might matter. Do not overclaim.",
        read_minutes=5,
        tags=["science_fair", "novelty", "differentiation", "judging"],
        sections=[
            Section(
                "The sentence to have ready",
                "'Previous work shows [X] under [condition A]. My project tests whether that holds "
                "under [condition B], which matters because [mechanism].' That sentence is "
                "defensible, specific, and does not require you to have invented a field.",
            ),
            Section(
                "Modesty reads as competence",
                "Claiming your project is unprecedented invites a judge to name the paper that "
                "precedes it. Placing your work accurately within existing literature shows you "
                "read it — which is the thing actually being scored.",
            ),
        ],
        related=["determining-novelty", "research-gaps", "literature-review", "judge-interview"],
    ),
]


ALL_GUIDES: list[Guide] = (
    _FUNDAMENTALS + _DESIGN + _STATISTICS + _LITERATURE + _DATA + _SCIENCE_FAIR
)

GUIDES_BY_ID: dict[str, Guide] = {g.id: g for g in ALL_GUIDES}


def get(guide_id: str) -> Guide | None:
    return GUIDES_BY_ID.get(guide_id)


def by_category(category: GuideCategory) -> list[Guide]:
    return [g for g in ALL_GUIDES if g.category == category]


def search(
    query: str | None = None,
    category: GuideCategory | None = None,
    tag: str | None = None,
) -> list[Guide]:
    results = ALL_GUIDES
    if category is not None:
        results = [g for g in results if g.category == category]
    if tag:
        results = [g for g in results if tag in g.tags]
    if query:
        needle = query.lower().strip()
        results = [
            g
            for g in results
            if needle in g.title.lower()
            or needle in g.summary.lower()
            or any(needle in t for t in g.tags)
            or any(needle in s.body.lower() or needle in s.heading.lower() for s in g.sections)
        ]
    return results

