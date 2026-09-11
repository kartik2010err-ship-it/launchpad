"""The Research Assistant, offline.

This is the default. A club running the app on a school network with no API key
still gets a mentor that reads the project context, recognises what is being
asked, teaches the concept, challenges the student, and cites the right guide.

The design is intent routing, not text generation. Each intent owns:

* the patterns that select it,
* a short teaching passage written by a human,
* follow-up questions that push the work back to the student,
* guide ids from the Research Library.

Section 14 is enforced here rather than hoped for: a request to *produce* the
student's science ("write my hypothesis") is intercepted before any topic match
and redirected into a question. The assistant never hands over an answer the
student is supposed to arrive at.
"""

from __future__ import annotations

import re

from app.schemas.assistant import AssistantReply

# --------------------------------------------------------------------------- #
# Section 14 — do the teaching, not the project
# --------------------------------------------------------------------------- #

_DO_IT_FOR_ME = re.compile(
    r"\b(write|generate|create|make|give me|come up with|do)\b[^.?!]{0,40}\b"
    r"(my|the|a|an)\b[^.?!]{0,30}\b"
    r"(hypothesis|research question|question|abstract|procedure|methodology|method|"
    r"conclusion|analysis|project|experiment|title|poster)\b",
    re.IGNORECASE,
)

_REDIRECTS: dict[str, tuple[str, list[str], list[str]]] = {
    "hypothesis": (
        "I'm not going to write it for you — a hypothesis you didn't reason your way to "
        "falls apart in the first judge question. But I'll get you there fast.\n\n"
        "A hypothesis is a prediction plus a reason. The prediction says which way the "
        "measurement moves; the reason says why you expect that, based on something you "
        "already know about the mechanism.",
        [
            "What relationship do you expect between your variables — and in which direction?",
            "Why do you expect that? What's the underlying mechanism?",
        ],
        ["writing-a-hypothesis", "independent-dependent-variables"],
    ),
    "research question": (
        "That one has to be yours — it's the single thing judges probe hardest, and a "
        "question you can't defend the origin of is obvious within about thirty seconds.\n\n"
        "What I can do is take a rough idea and help you sharpen it until it names a "
        "population, a variable you change, and an outcome you can record as a number.",
        [
            "What's the rough version — even one messy sentence?",
            "What made you interested in this topic in the first place?",
        ],
        ["idea-to-research-question", "measurable-variables"],
    ),
    "abstract": (
        "An abstract is a compression of work only you did, so it has to come from you. "
        "The structure is fixed and short, though: purpose, method, results, conclusion — "
        "roughly one to two sentences each, usually under 250 words.\n\n"
        "Draft each of those four in your own words and I'll tell you which one is doing "
        "the least work.",
        [
            "In one sentence: what did you set out to find out?",
            "What's your single most important result?",
        ],
        ["abstract", "explaining-limitations"],
    ),
    "procedure": (
        "Your procedure has to be yours — it's the part a judge will ask you to walk "
        "through step by step, and it has to match what you actually did.\n\n"
        "Write it as though someone else has to reproduce your results without asking you "
        "a single question. Then I'll look for the gaps.",
        [
            "Walk me through what you'd physically do, start to finish.",
            "What would someone repeating this need to know that you haven't written down?",
        ],
        ["designing-a-controlled-experiment", "research-notebook"],
    ),
}

_REDIRECT_DEFAULT = (
    "I'd rather not hand you that outright — the point of this project is that the "
    "reasoning is yours, and it shows when it isn't.\n\n"
    "Tell me what you're thinking, even roughly, and I'll push on it until it's strong.",
    ["What's your current thinking, in whatever state it's in?"],
    [],
)


# --------------------------------------------------------------------------- #
# Topic intents
# --------------------------------------------------------------------------- #


class _Intent:
    __slots__ = ("key", "pattern", "teach", "follow_ups", "guide_ids")

    def __init__(
        self,
        key: str,
        pattern: str,
        teach: str,
        follow_ups: list[str],
        guide_ids: list[str],
    ) -> None:
        self.key = key
        self.pattern = re.compile(pattern, re.IGNORECASE)
        self.teach = teach
        self.follow_ups = follow_ups
        self.guide_ids = guide_ids


INTENTS: list[_Intent] = [
    _Intent(
        "control",
        r"\bcontrol(s|led)?\b|\bbaseline\b|\bcomparison group\b",
        "A control is the version of your experiment where the thing you're testing "
        "*isn't* applied. It exists to answer one question: would this have happened "
        "anyway?\n\n"
        "Without it, any result you get has an obvious alternative explanation, and a "
        "judge will find it before you finish your second sentence. With it, you can say "
        "what your treatment actually caused, because you have something to subtract.",
        [
            "In your experiment, what's the version where nothing is changed?",
            "If your result showed up in the control too, what would that tell you?",
        ],
        ["choosing-a-control-group", "designing-a-controlled-experiment"],
    ),
    _Intent(
        "confound",
        r"\bconfound|\blurking variable|\bthird variable|\bsomething else caus",
        "A confounding variable is something that changes alongside your independent "
        "variable and could explain your result on its own.\n\n"
        "The classic shape: you water plants with different fertilisers, but the "
        "fertiliser you expect to win happens to sit closest to the window. Now light and "
        "fertiliser move together, and your data can't separate them. The fix is either to "
        "hold the confound constant for every group, or to randomise which group gets which "
        "condition so it can't line up systematically.",
        [
            "What else differs between your groups besides the thing you're testing?",
            "Which of those could you hold constant, and which would you have to randomise?",
        ],
        ["confounding-variables", "controlled-variables", "avoiding-bias"],
    ),
    _Intent(
        "testable",
        r"\btestab|\bfalsifiab|\bis my hypothesis (good|ok|any good|valid)|\bcan i test\b",
        "A hypothesis is testable when you can state, in advance, a result that would "
        "prove it wrong.\n\n"
        "That's the whole test. \"Music affects plant growth\" isn't testable — any outcome "
        "confirms it, including no change. \"Plants exposed to 60 dB of classical music for "
        "6 hours daily will grow taller than silent controls over 21 days\" is testable, "
        "because if they don't, you were wrong, and you'll know.",
        [
            "What specific result would mean your hypothesis was wrong?",
            "Could you state your prediction with a number and a timeframe in it?",
        ],
        ["writing-a-hypothesis", "measurable-variables"],
    ),
    _Intent(
        "graph",
        r"\bgraph\b|\bchart\b|\bplot\b|\bbar (graph|chart)|\bscatter|\bhistogram|\bvisuali[sz]",
        "Pick the graph from the shape of your data, not from what looks impressive.\n\n"
        "Comparing a measurement across a handful of distinct groups → bar chart with error "
        "bars. Two continuous variables where you're looking for a relationship → scatter "
        "plot, with a fitted line only if a relationship is actually there. Something "
        "measured repeatedly over time → line graph. The distribution of one variable → "
        "histogram. Pie charts almost never earn their place in a science fair poster.",
        [
            "Is your independent variable a set of categories, or a continuous number?",
            "Are you showing a comparison, a relationship, or a change over time?",
        ],
        ["choosing-a-graph", "error-bars"],
    ),
    _Intent(
        "stat_test",
        r"\bstatistical test\b|\bt-?test\b|\banova\b|\bchi.?squar|\bwhat test\b|\bwhich test\b",
        "The test follows from three things: how many groups you're comparing, whether your "
        "outcome is a number or a category, and whether the groups are independent.\n\n"
        "Two independent groups, numeric outcome → t-test. Three or more → ANOVA. Same "
        "subjects measured twice → paired t-test. Counts falling into categories → "
        "chi-square. Two continuous variables → correlation, or regression if you want to "
        "predict one from the other. Small or badly-skewed samples push you towards the "
        "non-parametric versions like Mann-Whitney.",
        [
            "How many groups are you comparing, and is your outcome a number or a category?",
            "Are the same subjects measured more than once, or is each one in only one group?",
        ],
        ["choosing-a-statistical-test", "statistical-significance"],
    ),
    _Intent(
        "significance",
        r"\bsignifican|\bp.?value\b|\bp *[<=] *0?\.0",
        "Statistical significance answers exactly one narrow question: if there were really "
        "no effect at all, how surprising would data like mine be?\n\n"
        "That's what a p-value measures. p = 0.03 means data this extreme would turn up 3% "
        "of the time by chance alone if nothing real were happening. It does **not** mean "
        "there's a 97% chance you're right, and it says nothing about whether the effect is "
        "big enough to matter. A tiny, useless difference can be significant with a large "
        "enough sample; a large, important one can miss significance with a small sample.",
        [
            "How large is your effect in real units — not just whether it passed 0.05?",
            "What would you conclude if your p-value came out at 0.06?",
        ],
        ["statistical-significance", "p-values", "confidence-intervals"],
    ),
    _Intent(
        "sample_size",
        r"\bsample size\b|\bhow many (trials|samples|participants|subjects|plants|replicate)|"
        r"\benough (data|trials|samples)\b|\breplicate",
        "There's no universal right number, but there is a floor: enough trials that you can "
        "see how much your measurement varies when nothing is changed.\n\n"
        "If your control group's own values scatter across a range wider than the difference "
        "you're claiming between groups, you don't have a result yet. For a school-level "
        "experiment, three trials per condition is usually the minimum anyone will take "
        "seriously and five or more is noticeably stronger. What matters more than the raw "
        "number is that you report the variation, not just the average.",
        [
            "How much do your repeated measurements of the *same* condition differ from each other?",
            "Is that spread smaller or larger than the difference you're trying to detect?",
        ],
        ["sample-size", "repeated-trials", "error-bars"],
    ),
    _Intent(
        "novelty",
        r"\bnovel|\boriginal|\bunique\b|\bdone before\b|\bmore innovative|\bstand out\b",
        "Novelty at a science fair almost never means nobody has ever studied your topic. It "
        "means you can say precisely what your version does that the existing work doesn't.\n\n"
        "The strongest and most achievable form is a specific combination: an established "
        "method applied to a population, material, or condition it hasn't been applied to, "
        "where there's a real reason to think the result might differ. That's defensible, and "
        "it's within reach in a season. Claiming nobody has done it is not defensible, because "
        "you can't prove a negative about all of published science.",
        [
            "What's the closest existing study you've found, and what exactly does yours do differently?",
            "Why would you expect your version to give a different result than theirs?",
        ],
        ["determining-novelty", "explaining-novelty", "research-gaps"],
    ),
    _Intent(
        "judge",
        r"\bjudge|\binterview\b|\bwhat will they ask|\bquestions? (i|they).{0,15}(get|ask)",
        "Judges are mostly probing one thing: do you understand your own project deeply "
        "enough that you could have made different choices and know why you didn't?\n\n"
        "The questions that catch people out are rarely about results. They're \"why did you "
        "choose that control?\", \"what would you do differently with another month?\", "
        "\"what's the biggest weakness here?\", and \"what surprised you?\". A student who "
        "names a real limitation before being asked reads as more credible, not less.",
        [
            "What's the weakest part of your project — and what would you say if a judge named it first?",
            "Why did you choose your specific method over the obvious alternative?",
        ],
        ["judge-interview", "explaining-limitations"],
    ),
    _Intent(
        "variables",
        r"\bvariable|\bindependent\b|\bdependent\b|\bwhat (am i|i'm) (chang|measur)",
        "Three roles, and every experiment needs all three named.\n\n"
        "The **independent** variable is the one thing you deliberately change. The "
        "**dependent** variable is what you measure to see if that mattered — and it has to "
        "come out as a number, with a unit. **Controlled** variables are everything else you "
        "hold fixed so they can't explain your result. If you can't say what unit your "
        "dependent variable is recorded in, that's the thing to fix before anything else.",
        [
            "What's the one thing you change, and what exactly do you record as a number?",
            "What unit is that measurement in?",
        ],
        ["independent-dependent-variables", "measurable-variables", "controlled-variables"],
    ),
    _Intent(
        "paper",
        r"\b(read|understand|reading).{0,20}(paper|study|article|journal)|"
        r"\bpaper i (found|read)\b|\bhelp me understand this (paper|study)",
        "Don't read a paper front to back on the first pass — almost nobody does.\n\n"
        "Read the abstract, then jump to the figures and their captions. The figures are the "
        "actual findings; the discussion is the authors' interpretation of them, which is a "
        "different thing. Then read the methods only for the part you need. On a first pass "
        "your goal is three sentences: what question they asked, what they did, what they "
        "found. If you can't write those three, you haven't got it yet — and that's normal.",
        [
            "What question were the authors trying to answer?",
            "Which figure carries their main result, and what does it actually show?",
        ],
        ["reading-a-scientific-paper", "finding-credible-sources", "literature-review"],
    ),
    _Intent(
        "correlation",
        r"\bcorrelation|\bcausation|\bcaus(e|es|ed) (it|the)|\bdoes .{0,20} cause\b",
        "A correlation says two things move together. Causation says one makes the other "
        "happen. Observational data gets you the first and almost never the second.\n\n"
        "Three things can produce a correlation without causation: coincidence, reverse "
        "causation (your outcome is actually driving your predictor), or a third variable "
        "driving both. The only clean way to earn a causal claim is to manipulate the "
        "independent variable yourself and randomise who gets what — which, if your project "
        "is an experiment rather than a survey, you can actually do.",
        [
            "Did you manipulate your independent variable, or observe it as it already was?",
            "What third factor could be driving both of the things you measured?",
        ],
        ["correlation-vs-causation", "confounding-variables"],
    ),
    _Intent(
        "outliers",
        r"\boutlier|\bweird (data|point|result)|\banomal|\bthrow (out|away) .{0,15}data|"
        r"\bdata (point )?(looks|seems) wrong",
        "Never delete a data point because it's inconvenient. That's the line between "
        "analysis and misconduct, and it's not a fine one.\n\n"
        "You may exclude a point when you can name a documented reason it isn't valid data — "
        "the equipment misread, the sample was contaminated, you recorded it wrong and the "
        "notebook says so. Decide the rule before you look at the results, write down every "
        "exclusion with its reason, and report your analysis both with and without it. An "
        "outlier you can explain is often the most interesting thing in the dataset.",
        [
            "Is there a documented reason that point is invalid, or does it just look wrong?",
            "How does your conclusion change if you keep it in?",
        ],
        ["outliers", "data-cleaning", "cherry-picking"],
    ),
    _Intent(
        "limitations",
        r"\blimitation|\bweakness|\bwhat.{0,15}wrong with my|\bcritique|\bcriticis|\bcriticiz|"
        r"\bfind (the )?(flaws|weaknesses|problems)",
        "Naming your own limitations makes you more credible, not less. Judges already know "
        "a high-school project has constraints; what they're testing is whether you do.\n\n"
        "A good limitation is specific and paired with its consequence: not \"my sample was "
        "small\" but \"with 5 plants per group I could only detect a difference of about 20%, "
        "so a smaller real effect would have been invisible to me\". That sentence shows you "
        "understand what your design could and couldn't have found.",
        [
            "What's the one result you're least confident in, and why?",
            "What would you need — time, equipment, samples — to close that gap?",
        ],
        ["explaining-limitations", "sample-size"],
    ),
    _Intent(
        "citations",
        r"\bcitation|\bcite\b|\bbibliograph|\breference list|\bworks cited|\bplagiar",
        "Cite anything that isn't your own data or common knowledge — including ideas you "
        "paraphrased, not just sentences you quoted.\n\n"
        "Pick one style and hold it consistently across the whole document; APA is the usual "
        "default for science fair work. Record the citation at the moment you read the source, "
        "not at the end — reconstructing where a fact came from three months later is how "
        "students accidentally end up unable to cite their own background section.",
        [
            "Are you recording sources as you read them, or planning to reconstruct them later?",
            "Which claims in your background do you not currently have a source for?",
        ],
        ["citations", "finding-credible-sources"],
    ),
    _Intent(
        "notebook",
        r"\bnotebook|\blog ?book|\bjournal entries|\brecord keeping|\blab notebook",
        "The notebook is contemporaneous evidence that you did the work — which is exactly "
        "why it has to be written as you go and never reconstructed afterwards.\n\n"
        "Date every entry. Record what you actually did, including the parts that went wrong, "
        "what you changed and why, raw numbers before any analysis, and what you plan next. "
        "Failed attempts belong in there. A notebook with no problems in it reads as fiction, "
        "and judges have seen enough of them to know.",
        [
            "When did you last write an entry — and was it on the day you did the work?",
            "Are your raw measurements in there, or only the processed results?",
        ],
        ["research-notebook", "data-collection"],
    ),
]


# --------------------------------------------------------------------------- #
# Context-driven answers
# --------------------------------------------------------------------------- #

_NEXT_STEP = re.compile(
    r"\bwhat (should|do) i (do|work on)\b|\bnext step\b|\bwhat.?s next\b|\bwhere (do|should) i start",
    re.IGNORECASE,
)
_EXPLAIN_BACK = re.compile(
    r"\bexplain (my|the) (methodolog|method|project|design|experiment).{0,20}back\b|"
    r"\bexplain (my|the) (methodolog|method|design)\b|\bsummari[sz]e my (project|method)",
    re.IGNORECASE,
)

_STAGE_ADVICE: dict[str, tuple[str, list[str]]] = {
    "idea": (
        "You're at the idea stage, so the next move is narrowing — one topic, one measurable "
        "outcome.",
        ["choosing-a-topic", "idea-to-research-question"],
    ),
    "question_refinement": (
        "Your question is the active piece of work. It needs a named population, a variable "
        "you change, and an outcome recorded in a unit.",
        ["idea-to-research-question", "measurable-variables"],
    ),
    "background_research": (
        "Background research is the current phase: find the closest existing studies, because "
        "they define what counts as new about yours.",
        ["finding-credible-sources", "reading-a-scientific-paper", "literature-review"],
    ),
    "experimental_design": (
        "You're designing. The pieces that have to be nailed down are your control, your "
        "trial count, and what you're holding constant.",
        ["designing-a-controlled-experiment", "choosing-a-control-group", "sample-size"],
    ),
    "approval_required": (
        "Approval forms are blocking you. Nothing downstream can legitimately start until "
        "those are signed.",
        ["research-plan"],
    ),
    "experimentation": (
        "You're collecting data. The thing that matters now is discipline: same procedure "
        "every trial, notebook written the same day.",
        ["data-collection", "repeated-trials", "research-notebook"],
    ),
    "data_analysis": (
        "You're in analysis. Describe the data before you test it — means, spread, and a plot "
        "come before any p-value.",
        ["descriptive-statistics", "choosing-a-statistical-test", "choosing-a-graph"],
    ),
    "poster": (
        "Poster stage. The figures carry the project; the text exists to explain them.",
        ["poster", "choosing-a-graph", "abstract"],
    ),
    "interview_preparation": (
        "You're preparing for judging. Practise defending choices, not reciting results.",
        ["judge-interview", "explaining-limitations", "explaining-novelty"],
    ),
    "complete": (
        "The project is complete — the remaining value is in being able to discuss its limits "
        "honestly.",
        ["explaining-limitations", "judge-interview"],
    ),
}

_GAP_GUIDES: dict[str, list[str]] = {
    "control_defined": ["choosing-a-control-group"],
    "quantitative_outcome": ["measurable-variables"],
    "mechanism_explained": ["writing-a-hypothesis"],
    "literature_grounded": ["finding-credible-sources", "literature-review"],
    "differentiator_stated": ["explaining-novelty", "determining-novelty"],
}

_GAP_TEXT: dict[str, str] = {
    "control_defined": "you haven't defined a control yet",
    "quantitative_outcome": "your outcome isn't yet stated as something recordable as a number",
    "mechanism_explained": "there's no mechanism on record — why you expect what you expect",
    "literature_grounded": "no prior work is logged, so novelty can't be assessed",
    "differentiator_stated": "you haven't said what makes your version different",
}


def _next_step_reply(context: dict | None) -> AssistantReply:
    """Section 35. Delegates to the shared recommendation so the assistant and
    the Home dashboard can never tell a student two different things."""

    from app.services import next_action

    plan = next_action.compute(context)
    primary = plan["primary"]

    lines = [f"**Do this first:** {primary['action']}.", "", primary["why"]]
    if plan["secondary"]:
        lines.append("")
        lines.append("After that:")
        lines.extend(f"- {item['action']}" for item in plan["secondary"])

    guide_ids = list(primary.get("guide_ids") or [])
    for item in plan["secondary"]:
        for gid in item.get("guide_ids") or []:
            if gid not in guide_ids:
                guide_ids.append(gid)

    return AssistantReply(
        reply="\n".join(lines),
        follow_ups=[
            "Why does that matter for my project?",
            "What would a judge ask me about this?",
        ],
        guide_ids=guide_ids[:3],
    )


def _explain_back_reply(context: dict | None) -> AssistantReply:
    if not context:
        return AssistantReply(
            reply="Open this from inside a project and I'll read your methodology back to you.",
            follow_ups=[],
            guide_ids=[],
        )

    known = context.get("known") or {}
    derived = context.get("derived") or {}
    lines = [
        "Here's your project as the app currently has it on record. If any of this is "
        "wrong, that's the most useful thing you could tell me.",
        "",
        f"**Question:** {context.get('question')}",
    ]
    for key, label in (
        ("independent_variable", "You change"),
        ("dependent_variable", "You measure"),
        ("measurement", "Measured by"),
        ("population", "In"),
        ("control", "Control"),
        ("trials", "Trials"),
        ("test_method", "Test method"),
        ("success_metric", "Success metric"),
    ):
        if known.get(key):
            lines.append(f"**{label}:** {known[key]}")

    gaps = [_GAP_TEXT[k] for k, ok in derived.items() if k in _GAP_TEXT and not ok]
    if gaps:
        lines.append("")
        lines.append("What's missing from that picture: " + "; ".join(gaps) + ".")

    return AssistantReply(
        reply="\n".join(lines),
        follow_ups=[
            "Which part of that is weakest?",
            "What would a judge push on first?",
        ],
        guide_ids=["designing-a-controlled-experiment"],
    )


def _weakness_reply(context: dict | None) -> AssistantReply | None:
    """Only fires with a project attached — otherwise the topic router handles it."""

    if not context:
        return None
    derived = context.get("derived") or {}
    evaluation = context.get("evaluation") or {}
    issues = context.get("question_issues") or []
    gaps = [_GAP_TEXT[k] for k, ok in derived.items() if k in _GAP_TEXT and not ok]

    if not gaps and not issues and not evaluation.get("weak_criteria"):
        return None

    lines = ["Reading your project as it stands, these are the things a judge would find:", ""]
    n = 0
    for issue in issues[:2]:
        n += 1
        lines.append(f"{n}. {issue}")
    for gap in gaps[:3]:
        n += 1
        lines.append(f"{n}. On the record, {gap}.")
    for item in (evaluation.get("weak_criteria") or [])[:2]:
        n += 1
        lines.append(
            f"{n}. {str(item.get('criterion', '')).replace('_', ' ').capitalize()} scored "
            f"{item.get('score')}/100 in the last evaluation."
        )
    lines.append("")
    lines.append(
        "None of these are fatal this far out. They're fatal on the morning of judging, "
        "which is why they're worth attacking now."
    )

    guide_ids: list[str] = []
    for key, ok in derived.items():
        if key in _GAP_GUIDES and not ok:
            guide_ids.extend(_GAP_GUIDES[key])
    return AssistantReply(
        reply="\n".join(lines),
        follow_ups=["How do I fix the first one?", "Which of these matters most?"],
        guide_ids=list(dict.fromkeys(guide_ids))[:3],
    )


_WEAKNESS = re.compile(
    r"\bweakness|\bwhat.{0,20}wrong|\bfind (the )?(flaws|problems|weaknesses)|"
    r"\bcritique my|\bchallenge my|\bpoke holes",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def reply(message: str, context: dict | None, history: list | None = None) -> AssistantReply:
    """Route one student message to a mentor response."""

    text = (message or "").strip()
    if not text:
        return AssistantReply(
            reply="Ask me anything about your project — or tell me what you're stuck on.",
            follow_ups=[],
            guide_ids=[],
        )

    # 1. Section 14 gate, before anything else.
    if _DO_IT_FOR_ME.search(text):
        lowered = text.lower()
        for needle, (body, follow_ups, guides) in _REDIRECTS.items():
            if needle in lowered:
                return AssistantReply(reply=body, follow_ups=follow_ups, guide_ids=guides)
        body, follow_ups, guides = _REDIRECT_DEFAULT
        return AssistantReply(reply=body, follow_ups=follow_ups, guide_ids=guides)

    # 2. Context-driven intents.
    if _NEXT_STEP.search(text):
        return _next_step_reply(context)
    if _EXPLAIN_BACK.search(text):
        return _explain_back_reply(context)
    if _WEAKNESS.search(text):
        found = _weakness_reply(context)
        if found is not None:
            return found

    # 3. Topic router — best match wins, ties broken by declaration order.
    best: _Intent | None = None
    best_hits = 0
    for intent in INTENTS:
        hits = len(intent.pattern.findall(text))
        if hits > best_hits:
            best, best_hits = intent, hits
    if best is not None:
        body = best.teach
        if context:
            note = _contextual_note(best.key, context)
            if note:
                body = f"{body}\n\n{note}"
        return AssistantReply(
            reply=body, follow_ups=best.follow_ups, guide_ids=best.guide_ids
        )

    # 4. Nothing matched. Say so honestly rather than improvising.
    return _fallback(text, context)


def _contextual_note(intent_key: str, context: dict) -> str | None:
    """Tie the general explanation back to this specific project."""

    derived = context.get("derived") or {}
    known = context.get("known") or {}
    if intent_key == "control" and not derived.get("control_defined"):
        return (
            "**In your project:** there's no control on record yet. That's the gap to close "
            "before you start collecting data, not after."
        )
    if intent_key == "variables" and not derived.get("quantitative_outcome"):
        return (
            "**In your project:** your dependent variable isn't yet recorded as something "
            "with a unit. That's the first thing to fix here."
        )
    if intent_key == "novelty" and not derived.get("literature_grounded"):
        return (
            "**In your project:** no prior work is logged yet, so there's nothing to compare "
            "against. Novelty can't honestly be assessed until there is."
        )
    if intent_key == "sample_size" and known.get("trials"):
        return f"**In your project:** you currently have \"{known['trials']}\" on record for trials."
    if intent_key == "stat_test" and not derived.get("stats_aware"):
        return (
            "**In your project:** no analysis plan is on record yet. Deciding the test before "
            "you collect data is what stops you fishing for a result afterwards."
        )
    return None


def _fallback(text: str, context: dict | None) -> AssistantReply:
    stage = (context or {}).get("stage", "")
    _lead, stage_guides = _STAGE_ADVICE.get(stage, ("", []))
    return AssistantReply(
        reply=(
            "I don't have a prepared answer for that one — this app is running its offline "
            "coach, which recognises a fixed set of research topics rather than answering "
            "open-ended questions.\n\n"
            "Try asking about controls, variables, sample size, statistical tests, "
            "significance, graphs, outliers, novelty, limitations, citations, reading a "
            "paper, or what to work on next. Or ask \"what should I do next?\" and I'll "
            "answer from your project's actual state."
        ),
        follow_ups=["What should I do next?", "What are the weaknesses in my project?"],
        guide_ids=stage_guides[:2],
    )
