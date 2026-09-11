"""Research outreach: templates, the email builder, and follow-up timing.

The builder is deliberately hard to misuse for mass mail. It refuses to produce
a draft without a specific reference to the recipient's own work, because the
one thing that distinguishes a message worth reading from spam is evidence that
the student read something. That refusal is a product decision, not a
limitation — a generic email sent to forty professors damages the student's
reputation and the school's.

Drafts are composed deterministically from the student's own answers. The app
does not invent a professor's research interests, publications or availability.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.models.enums import OutreachStatus

SPAM_WARNING = (
    "Send these one at a time. A message that could have been sent to any researcher will be "
    "read as one that was — most academics receive several a week and can spot a template "
    "instantly. One specific, well-researched email is worth more than forty generic ones, and "
    "mass-mailing a department can get you blocked by the whole institution."
)

ETIQUETTE = [
    "Read at least one of their recent papers or project pages before writing. Say which.",
    "Keep it under 200 words. Busy people reply to short emails first.",
    "Ask for one specific, small thing — 15 minutes, one question, or a pointer to a paper.",
    "Use your school email address and sign with your full name, school and grade.",
    "Say you understand they are busy and that no reply is a fine answer.",
    "Wait 7-10 working days before a single follow-up. One follow-up, not three.",
    "Never attach large files or send the same message to a whole department.",
]


# Section 39. The library is grouped by what the student actually wants, not by
# who they are writing to — a student knows "I want feedback on my stats", not
# "I need the technical-feedback template".
CATEGORIES: list[tuple[str, str]] = [
    ("research_advice", "Research advice"),
    ("mentorship", "Mentorship"),
    ("lab_experience", "Lab and research experience"),
    ("resources", "Resources"),
    ("academic_questions", "Academic questions"),
    ("meetings", "Meetings"),
    ("follow_up", "Follow-up"),
    ("competition_prep", "Competition prep"),
]

CATEGORY_LABELS: dict[str, str] = dict(CATEGORIES)


@dataclass
class OutreachTemplate:
    key: str
    name: str
    when_to_use: str
    subject_pattern: str
    # Section name -> guidance shown alongside the generated draft.
    structure: list[tuple[str, str]] = field(default_factory=list)
    ask_examples: list[str] = field(default_factory=list)

    # ---- section 39/40: the preview a student reads before choosing -------- #
    category: str = "research_advice"
    avoid_when: str = ""
    required_personalisation: list[str] = field(default_factory=list)
    example_subjects: list[str] = field(default_factory=list)
    why_it_works: str = ""
    common_mistakes: list[str] = field(default_factory=list)
    # Postdocs and graduate students get a different register from professors.
    register: str = "formal"


TEMPLATES: dict[str, OutreachTemplate] = {
    "research_guidance": OutreachTemplate(
        key="research_guidance",
        name="Asking a professor for research guidance",
        when_to_use="You have a defined question and want feedback on whether the approach is sound.",
        subject_pattern="Question about {topic} — {grade} student at {school}",
        structure=[
            ("Introduction", "Who you are in one sentence: name, grade, school."),
            ("Connection", "The specific paper or project of theirs you read, and what struck you."),
            ("Project", "Your research question in one or two sentences, with your method."),
            ("Specific request", "One narrow question they can answer in a short reply."),
            ("Closing", "Thanks, acknowledgement that they are busy, your full signature."),
        ],
        ask_examples=[
            "Whether measuring X by method Y is a reasonable proxy for Z",
            "Whether a known confound in this area would invalidate my design",
            "Which of two approaches would be more defensible at my scale",
        ],
    ),
    "mentorship": OutreachTemplate(
        key="mentorship",
        name="Asking about mentorship",
        when_to_use="You are looking for ongoing guidance across a project, not a one-off answer.",
        subject_pattern="Mentorship enquiry — {grade} student researching {topic}",
        structure=[
            ("Introduction", "Name, grade, school, and that you are asking about mentorship."),
            ("Connection", "Why their lab specifically, based on their published work."),
            ("Project", "Your question, your timeline, and what you have already done alone."),
            ("Specific request", "What mentorship would mean concretely: how often, for how long."),
            ("Closing", "Thanks, and that a referral to a graduate student is equally welcome."),
        ],
        ask_examples=[
            "A 20-minute call once a month between now and the fair",
            "Feedback on my research plan before I begin data collection",
            "A referral to a graduate student who might have more time",
        ],
    ),
    "paper_question": OutreachTemplate(
        key="paper_question",
        name="Asking a question about their published research",
        when_to_use="You read one of their papers and something specific is unclear or unstated.",
        subject_pattern="Question about your {year} paper on {topic}",
        structure=[
            ("Introduction", "Name, grade, school, in one line."),
            ("Connection", "The exact paper, and the passage or figure your question is about."),
            ("Project", "One sentence on why you are reading it — your own project."),
            ("Specific request", "The question itself, precise enough to answer in two sentences."),
            ("Closing", "Thanks and signature."),
        ],
        ask_examples=[
            "Whether the effect in Figure 3 held at the lowest concentration",
            "Why a particular control was chosen over an alternative",
            "Whether the dataset used is available anywhere public",
        ],
    ),
    "equipment_access": OutreachTemplate(
        key="equipment_access",
        name="Requesting access to specialised equipment",
        when_to_use="Your design needs an instrument your school does not have.",
        subject_pattern="Request to use {equipment} for a {grade} science-fair project",
        structure=[
            ("Introduction", "Name, grade, school, and what you are asking for up front."),
            ("Connection", "Why their facility, and how you found it."),
            ("Project", "Your question, and exactly why this instrument is required."),
            ("Specific request", "What you need, how many samples, roughly how long, and when."),
            ("Closing", "Note that you will follow all safety and supervision requirements."),
        ],
        ask_examples=[
            "One afternoon on the SEM for 12 samples, supervised",
            "Access to a calibrated balance for a single measurement session",
            "Use of a temperature-controlled chamber for two weeks",
        ],
    ),
    "short_meeting": OutreachTemplate(
        key="short_meeting",
        name="Requesting a short meeting",
        when_to_use="Your questions need a conversation rather than an email reply.",
        subject_pattern="15-minute meeting request — {grade} student, {topic}",
        structure=[
            ("Introduction", "Name, grade, school."),
            ("Connection", "Their work, and specifically what you want to discuss with them."),
            ("Project", "Two sentences on where your project is."),
            ("Specific request", "A named duration and your flexibility. Offer video."),
            ("Closing", "Thanks, and that you will send questions in advance."),
        ],
        ask_examples=[
            "15 minutes by video, any time in the next three weeks",
            "A short conversation after a seminar you are already attending",
        ],
    ),
    "follow_up": OutreachTemplate(
        key="follow_up",
        name="Following up after no response",
        when_to_use="Seven to ten working days have passed with no reply. Send once.",
        subject_pattern="Following up: {original_subject}",
        structure=[
            ("Introduction", "One line: you wrote on a date, following up once."),
            ("Connection", "Re-state your original ask in a single sentence."),
            ("Project", "Any genuine update since — progress makes the follow-up worth reading."),
            ("Specific request", "Repeat the one small ask, and lower the cost of saying no."),
            ("Closing", "Say explicitly this is your only follow-up. Then mean it."),
        ],
        ask_examples=[
            "If now is not a good time, I completely understand and will not write again",
            "Even a one-line pointer to a paper would help a great deal",
        ],
    ),
}


# --------------------------------------------------------------------------- #
# Section 32: the rest of the library.
#
# Every template below was derived from the common structure published by
# university undergraduate-research offices and career centres (see SOURCES).
# None of them reproduces any source's wording — what carried over is the
# shape: short, specific, one ask, easy to decline.
# --------------------------------------------------------------------------- #

TEMPLATES.update({
    "lab_experience": OutreachTemplate(
        key="lab_experience",
        name="Asking to help in a research lab",
        category="lab_experience",
        when_to_use="You want hands-on research experience, not just advice.",
        avoid_when=(
            "You only have one question. Asking to join a lab is a much larger request than "
            "asking a question, and the larger ask makes the small one less likely to be answered."
        ),
        subject_pattern="High school student interested in your {topic} work",
        structure=[
            ("Introduction", "Name, grade, school — one sentence."),
            ("Connection", "The specific project or paper of theirs that interested you, and why."),
            ("What you can do", "Skills you actually have. Do not inflate them."),
            ("Availability", "Real hours per week and which months."),
            ("Specific request", "Ask whether there is any appropriate way to contribute or observe."),
        ],
        ask_examples=[
            "Whether there is any task in the lab a high-school student could usefully help with",
            "Whether I could observe for a few sessions to understand how the work is done",
        ],
        required_personalisation=[
            "A specific paper, project or lab page you read",
            "What genuinely interested you about it",
            "Your real availability in hours per week",
        ],
        example_subjects=[
            "High school student interested in your plant pathology work",
            "Prospective volunteer — question about your imaging lab",
        ],
        why_it_works=(
            "It is honest about experience level and concrete about availability, which is what "
            "makes it possible for a PI to say yes. Vague enthusiasm gives them nothing to act on."
        ),
        common_mistakes=[
            "Overstating your skills. You will be found out in the first week.",
            "Asking to 'do research' without saying what you can offer or when.",
            "Framing it as a college-application step rather than genuine interest.",
        ],
    ),
    "dataset_request": OutreachTemplate(
        key="dataset_request",
        name="Asking for access to a dataset",
        category="resources",
        when_to_use="A research group holds data you may be able to analyse.",
        avoid_when="The data involves identifiable human subjects and you have no approval route.",
        subject_pattern="Data access question — {grade} student studying {topic}",
        structure=[
            ("Introduction", "Name, grade, school."),
            ("Connection", "Which dataset or paper, and how you found it."),
            ("Proposed use", "Exactly what you would compute, in one or two sentences."),
            ("Scope", "State if de-identified or public-compatible data would be enough."),
            ("Specific request", "Ask what the access requirements are — not for the data itself."),
        ],
        ask_examples=[
            "What the process is for a student to request access to this dataset",
            "Whether a de-identified subset would be available for a school project",
        ],
        required_personalisation=[
            "The specific dataset or the paper it came from",
            "What you would actually do with it",
        ],
        example_subjects=[
            "Access question about the reef imagery dataset",
            "High school project — question about your published dataset",
        ],
        why_it_works=(
            "Asking about the *process* rather than for the data assumes nothing. Researchers "
            "often cannot share data even when willing, and giving them an easy procedural answer "
            "is more likely to get a reply than a request they must refuse."
        ),
        common_mistakes=[
            "Implying you are entitled to the data.",
            "Not saying what you would do with it, which makes the request impossible to assess.",
            "Asking for identifiable human data with no ethics approval in place.",
        ],
    ),
    "methodology_feedback": OutreachTemplate(
        key="methodology_feedback",
        name="Asking for technical or methodology feedback",
        category="research_advice",
        when_to_use="You have a proposed method and want an expert to find the flaw in it.",
        avoid_when="You have not designed anything yet — there is nothing to critique.",
        subject_pattern="Request for brief methodology advice — {topic}",
        structure=[
            ("Introduction", "One sentence: who you are."),
            ("Connection", "Why their expertise fits this particular method."),
            ("Question and method", "Research question plus a very short method summary."),
            ("Specific request", "One or two concrete concerns. Not 'any thoughts?'"),
        ],
        ask_examples=[
            "Whether a control of untreated samples is sufficient, or whether I need a sham treatment",
            "Whether 5 trials per condition is defensible for this kind of measurement",
        ],
        required_personalisation=[
            "Their relevant expertise, specifically",
            "Your actual method in two or three sentences",
            "One or two specific concerns",
        ],
        example_subjects=[
            "Question about controls in a leaf-disease imaging study",
            "Brief methodology question — sample size for a behavioural task",
        ],
        why_it_works=(
            "Experts enjoy answering a sharp technical question and ignore requests to review "
            "everything. One concern, clearly stated, is a two-minute reply."
        ),
        common_mistakes=[
            "Attaching a full research plan unasked.",
            "Asking 'does this look okay?', which is not answerable.",
            "Describing the method in so much detail the question gets buried.",
        ],
    ),
    "grad_student": OutreachTemplate(
        key="grad_student",
        name="Asking a graduate student or postdoc",
        category="mentorship",
        register="direct",
        when_to_use=(
            "You want practical, technical help. Graduate students and postdocs run the "
            "day-to-day work, often have more time than the PI, and are usually closer to the "
            "methods you are trying to copy."
        ),
        avoid_when="You need something only a PI can authorise, like lab access or equipment.",
        subject_pattern="Question about your {topic} work — high school researcher",
        structure=[
            ("Introduction", "Name, grade, school. Keep it to a line."),
            ("Connection", "Their specific project or paper — often their thesis work."),
            ("Question", "The technical thing you are stuck on."),
            ("Specific request", "A short, concrete ask."),
        ],
        ask_examples=[
            "How you handled calibration drift in that setup",
            "Which package you used for the analysis in figure 3",
        ],
        required_personalisation=[
            "Their own project, not their supervisor's",
            "The specific technical point you are stuck on",
        ],
        example_subjects=[
            "Question about your hyperspectral calibration method",
            "High school student — quick question about your analysis pipeline",
        ],
        why_it_works=(
            "Slightly less formal than a professor email, and aimed at the person who actually "
            "ran the experiment. They remember being new at this."
        ),
        common_mistakes=[
            "Writing to them as though they were the professor.",
            "Asking about the lab's direction rather than their own work.",
        ],
    ),
    "thank_you": OutreachTemplate(
        key="thank_you",
        name="Thank you after a reply or meeting",
        category="follow_up",
        when_to_use="Someone answered, met you, or gave you something useful.",
        avoid_when="Never — always send this. It takes two minutes and people remember it.",
        subject_pattern="Thank you — {topic}",
        structure=[
            ("Thanks", "Short and specific."),
            ("What you took from it", "One concrete thing you learned or changed."),
            ("Next step", "Anything you agreed to do, if applicable."),
        ],
        ask_examples=[
            "Nothing — this email asks for nothing, which is what makes it welcome",
        ],
        required_personalisation=["One specific thing you learned from them"],
        example_subjects=["Thank you — controls advice", "Thank you for your time yesterday"],
        why_it_works=(
            "Naming one specific thing you took away proves you listened, which is the only "
            "thing that distinguishes a real thank-you from a formality."
        ),
        common_mistakes=[
            "Generic gratitude with no specifics.",
            "Using it to sneak in three more questions.",
        ],
    ),
    "second_meeting": OutreachTemplate(
        key="second_meeting",
        name="Asking for a second meeting",
        category="meetings",
        when_to_use="You met once, did the work, and have something new to discuss.",
        avoid_when="You have not acted on their first round of advice yet.",
        subject_pattern="Follow-up conversation about {topic}?",
        structure=[
            ("Reminder", "When you last spoke and what about."),
            ("Progress", "What you did with their advice. This is the part that earns the meeting."),
            ("Why now", "The new question that has come up."),
            ("Specific request", "Another short meeting, with flexible scheduling."),
        ],
        ask_examples=[
            "Another 15 minutes in the next couple of weeks, whenever suits you",
        ],
        required_personalisation=[
            "What you discussed last time",
            "What you actually did since",
        ],
        example_subjects=[
            "Follow-up on our conversation about sample size",
            "Update and a question — reef imaging project",
        ],
        why_it_works=(
            "Showing that their first hour produced something is the strongest possible argument "
            "for a second one."
        ),
        common_mistakes=[
            "Asking again without having acted on the first conversation.",
            "Treating them as an ongoing mentor when they only agreed to one meeting.",
        ],
    ),
    "results_feedback": OutreachTemplate(
        key="results_feedback",
        name="Asking for feedback on your results",
        category="research_advice",
        when_to_use="You have data and are unsure whether your interpretation holds up.",
        avoid_when="You have not analysed the data yourself yet.",
        subject_pattern="Question about interpreting my {topic} results",
        structure=[
            ("Introduction", "One sentence."),
            ("Question and test", "What you asked and what you did."),
            ("Main result", "One sentence, with the number."),
            ("Specific uncertainty", "The thing you are not sure about."),
            ("Specific request", "Whether the interpretation is reasonable, or what else could explain it."),
        ],
        ask_examples=[
            "Whether a difference this size is meaningful given my sample",
            "What alternative explanation I might be missing",
        ],
        required_personalisation=[
            "Your actual result, with numbers",
            "The specific thing you are unsure about",
        ],
        example_subjects=[
            "Interpretation question — bleaching prediction results",
            "Is this result what it looks like? High school project",
        ],
        why_it_works=(
            "A concrete number and a named uncertainty give the expert something to react to in "
            "one sentence."
        ),
        common_mistakes=[
            "Sending raw data and asking what it means.",
            "Asking them to check your statistics without saying which test you used.",
        ],
    ),
    "poster_feedback": OutreachTemplate(
        key="poster_feedback",
        name="Asking for poster or presentation feedback",
        category="competition_prep",
        when_to_use="Competition is close and you want a specific kind of review.",
        avoid_when="The poster does not exist yet.",
        subject_pattern="Poster feedback before {topic} — short request",
        structure=[
            ("Introduction", "One sentence, plus the competition and date."),
            ("Connection", "Why their perspective in particular."),
            ("What kind of feedback", "Scientific content, clarity, or delivery — pick one."),
            ("Specific request", "A bounded ask with a deadline that gives them room."),
        ],
        ask_examples=[
            "Whether the methods panel is understandable to someone outside the field",
            "Whether my central claim is stated too strongly for the evidence",
        ],
        required_personalisation=[
            "The competition and its date",
            "Which of the three kinds of feedback you want",
        ],
        example_subjects=[
            "Poster feedback before AzSEF — 15 minutes?",
            "Quick clarity check on a science fair poster",
        ],
        why_it_works=(
            "Naming which kind of feedback you want turns an open-ended favour into a bounded "
            "task. 'Can you review everything?' is the version that gets no reply."
        ),
        common_mistakes=[
            "Asking with three days' notice.",
            "Asking for 'any feedback', which makes them decide what to look at.",
        ],
    ),
    "interdisciplinary": OutreachTemplate(
        key="interdisciplinary",
        name="Contacting someone outside your field",
        category="academic_questions",
        when_to_use="Your project crosses into an area you do not know well.",
        avoid_when="The connection is not real. Do not stretch for one.",
        subject_pattern="{topic} project — question from outside your field",
        structure=[
            ("Introduction", "Who you are and what field your project is mainly in."),
            ("The bridge", "Explicitly why their work is relevant to yours. This is the whole email."),
            ("Question", "The thing you cannot answer from inside your own field."),
            ("Specific request", "One narrow question."),
        ],
        ask_examples=[
            "Whether the disease signatures I am classifying are actually distinguishable visually",
            "Whether my assumption about how the material behaves is roughly right",
        ],
        required_personalisation=[
            "An explicit sentence connecting your field to theirs",
            "The specific gap in your own knowledge",
        ],
        example_subjects=[
            "Computer science project, plant pathology question",
            "Materials question from an engineering student",
        ],
        why_it_works=(
            "Someone outside your field cannot guess why you are writing. Stating the bridge "
            "explicitly — 'my project is mostly X, but your work on Y matters because…' — is "
            "what stops the email looking misdirected."
        ),
        common_mistakes=[
            "Assuming the relevance is obvious. It is not.",
            "Using jargon from your field that they will not know.",
        ],
    ),
})


# Existing templates predate the richer metadata; fill it in rather than
# rewriting them, so their wording and keys stay stable.
_BACKFILL: dict[str, dict] = {
    "research_guidance": {
        "category": "research_advice",
        "avoid_when": "You want ongoing mentorship — that is a bigger ask and a different template.",
        "required_personalisation": ["A specific paper or project of theirs", "Your research question"],
        "example_subjects": [
            "High school research question about plant pathology",
            "Science fair project — question about your computer vision work",
        ],
        "why_it_works": (
            "It asks for something small enough to answer in a short reply, which is the single "
            "biggest predictor of getting one."
        ),
        "common_mistakes": [
            "Asking for 'any advice', which makes the expert decide what to say.",
            "Describing the whole project before getting to the question.",
        ],
    },
    "mentorship": {
        "category": "mentorship",
        "avoid_when": "You have not yet defined a question — mentorship requests need something to mentor.",
        "required_personalisation": [
            "Why their expertise matches your project specifically",
            "What you mean by mentorship, in hours",
            "Your competition and timeline",
        ],
        "example_subjects": [
            "Science fair mentorship — coral bleaching project, AzSEF",
            "Request for occasional guidance on a high school research project",
        ],
        "why_it_works": (
            "Defining mentorship concretely — one email a month, one short meeting — turns an "
            "open-ended commitment into one a busy person can actually evaluate."
        ),
        "common_mistakes": [
            "Asking 'will you be my mentor?' with no definition of what that means.",
            "Not mentioning the timeline, so they cannot tell what they are agreeing to.",
        ],
    },
    "paper_question": {
        "category": "academic_questions",
        "avoid_when": "Your question is answered in the abstract. Read it again first.",
        "required_personalisation": [
            "The paper by title or topic",
            "What you understood from it",
            "A question not answered in the abstract",
        ],
        "example_subjects": [
            "Question about your 2024 paper on fungal resistance",
            "High school student — question about figure 3 in your paper",
        ],
        "why_it_works": (
            "Authors are pleased that someone read the paper carefully. Showing what you "
            "understood before asking proves you did."
        ),
        "common_mistakes": [
            "Asking something the abstract answers.",
            "Saying you 'read their work' without naming which.",
        ],
    },
    "equipment_access": {
        "category": "resources",
        "avoid_when": "You have not checked whether your school or a local college already has it.",
        "required_personalisation": [
            "Exactly which instrument",
            "Why your project needs it",
            "Roughly how much access time",
        ],
        "example_subjects": [
            "Equipment access question — SEM time for a school project",
            "High school student — spectrometer access enquiry",
        ],
        "why_it_works": (
            "Naming the instrument and the hours makes it a scheduling question rather than an "
            "open-ended favour."
        ),
        "common_mistakes": [
            "Assuming access will be granted.",
            "Not mentioning supervision, training or safety, which are the actual blockers.",
        ],
    },
    "short_meeting": {
        "category": "meetings",
        "avoid_when": "Your question could be answered in an email. Ask that instead.",
        "required_personalisation": ["Why a conversation beats an email here"],
        "example_subjects": [
            "15 minutes about a high school research project?",
            "Short meeting request — science fair methodology",
        ],
        "why_it_works": (
            "Naming a length and leaving the scheduling open makes it easy to say yes to, and "
            "easy to decline without awkwardness."
        ),
        "common_mistakes": [
            "Not saying how long you want.",
            "Proposing specific times, which makes them work around you.",
        ],
    },
    "follow_up": {
        "category": "follow_up",
        "avoid_when": "It has been less than a week, or you have already followed up once.",
        "required_personalisation": ["What your original email asked"],
        "example_subjects": ["Following up — question about your imaging work"],
        "why_it_works": (
            "Short, unguilty, and repeats the ask so they do not have to scroll back."
        ),
        "common_mistakes": [
            "Guilt. 'I know you're busy but I haven't heard back' reads as a complaint.",
            "Following up more than once.",
        ],
    },
}

for _key, _extra in _BACKFILL.items():
    _template = TEMPLATES.get(_key)
    if _template is not None:
        for _field, _value in _extra.items():
            setattr(_template, _field, _value)


# Section 45. Template *design* was informed by these; no wording is copied.
SOURCES: list[dict[str, str]] = [
    {
        "name": "UNC Office for Undergraduate Research — Tips for Writing an Email to Faculty",
        "url": "https://our.unc.edu/find/emails-to-faculty/",
    },
    {
        "name": "UT Austin College of Natural Sciences — How to Reach Out to Professors",
        "url": "https://exl.cns.utexas.edu/do-research/find-research-lab/how-reach-out-professors",
    },
    {
        "name": "University of Illinois Grainger URSA — Emailing Professors",
        "url": "https://ursa.grainger.illinois.edu/emailing-professors/",
    },
    {
        "name": "Tufts University Career Center — Contacting Faculty About Research Opportunities",
        "url": "https://careers.tufts.edu/blog/2025/09/16/contacting-faculty-about-research-opportunities/",
    },
]

SOURCES_NOTE = (
    "Template design informed by academic outreach best practices published by university "
    "undergraduate-research offices and career centres. No source's wording is reproduced."
)

def listing() -> list[dict]:
    return [
        {
            "key": t.key,
            "name": t.name,
            "category": t.category,
            "category_label": CATEGORY_LABELS.get(t.category, t.category),
            "when_to_use": t.when_to_use,
            "avoid_when": t.avoid_when,
            "structure": [{"section": s, "guidance": g} for s, g in t.structure],
            "ask_examples": t.ask_examples,
            "required_personalisation": t.required_personalisation,
            "example_subjects": t.example_subjects,
            "why_it_works": t.why_it_works,
            "common_mistakes": t.common_mistakes,
            "register": t.register,
        }
        for t in TEMPLATES.values()
    ]


class DraftError(ValueError):
    """Raised when a draft would be generic enough to read as spam."""


def build_draft(
    *,
    template_key: str,
    student_name: str,
    school: str,
    grade_level: int | str,
    research_topic: str,
    research_question: str | None,
    researcher_name: str,
    their_work: str,
    specific_request: str,
    timeline: str | None = None,
    original_subject: str | None = None,
    tone: str = "standard",
) -> dict:
    """Compose a professional email from the student's own answers.

    ``their_work`` and ``specific_request`` are mandatory and are the two fields
    that make the message not-spam. Refusing to generate without them is the
    point of this function.
    """

    template = TEMPLATES.get(template_key)
    if template is None:
        raise DraftError(f"No outreach template called {template_key!r}.")
    if len((their_work or "").strip()) < 25:
        raise DraftError(
            "Write at least a sentence about what you actually read of theirs. A message with no "
            "specific reference to their work reads as a mass email, and gets deleted like one."
        )
    if len((specific_request or "").strip()) < 10:
        raise DraftError(
            "Name one specific thing you are asking for. 'Any advice you have' puts the work of "
            "deciding what to say onto a stranger, and usually gets no reply."
        )

    if tone not in TONE_KEYS:
        tone = "standard"

    grade = f"grade {grade_level}" if str(grade_level).isdigit() else str(grade_level)
    subject = template.subject_pattern.format(
        topic=research_topic,
        grade=grade,
        school=school,
        year="",
        equipment=research_topic,
        original_subject=original_subject or research_topic,
    ).replace("  ", " ").strip()

    # Section 33: never open with "I hope this email finds you well". Every
    # variant below starts with who the student is, because that is the first
    # thing the recipient needs and the last thing filler provides.
    salutation = f"Dear {researcher_name},"
    if template.register == "direct":
        salutation = f"Hi {researcher_name},"

    if tone == "concise":
        intro = (
            f"My name is {student_name}, a {grade} student at {school} working on a research "
            f"project on {research_topic}."
        )
    elif tone == "warmer":
        intro = (
            f"My name is {student_name} and I am a {grade} student at {school}. I have spent "
            f"this year working on a research project on {research_topic}, and your work is "
            f"part of why I chose it."
        )
    else:
        intro = (
            f"My name is {student_name}. I am a {grade} student at {school}, working on an "
            f"independent research project on {research_topic}."
        )

    connection = f"I read {their_work.strip().rstrip('.')}."
    if tone == "warmer":
        connection = f"I read {their_work.strip().rstrip('.')}, and it changed how I was thinking about my own design."
    project_lines = []
    if research_question:
        project_lines.append(f"My research question is: {research_question.strip().rstrip('.')}.")
    if timeline:
        project_lines.append(f"My timeline is {timeline.strip().rstrip('.')}.")
    project = " ".join(project_lines) or (
        f"I am in the early stages of designing a study on {research_topic}."
    )
    request = f"{specific_request.strip().rstrip('.')}."
    if tone == "concise":
        closing = (
            "I know you are busy, and no reply is a fine answer. Thank you.\n\n"
            f"{student_name}\n{grade.capitalize()}, {school}"
        )
    elif tone == "warmer":
        closing = (
            "I know your time is limited and I would be grateful for even a couple of "
            "sentences. Either way, thank you for the work — it has been genuinely useful to "
            "read.\n\n"
            f"{student_name}\n{grade.capitalize()}, {school}"
        )
    else:
        closing = (
            "I know your time is limited, and I would be grateful for even a brief reply. "
            "Thank you for considering it.\n\n"
            f"{student_name}\n{grade.capitalize()}, {school}"
        )

    paragraphs = [salutation, intro, connection, project, request, closing]
    if tone == "concise" and research_question:
        # Two short paragraphs is the shape the university guides recommend for
        # a small ask: who I am plus the connection, then the question.
        paragraphs = [salutation, f"{intro} {connection}", project, request, closing]

    body = "\n\n".join(paragraphs)

    return {
        "template_key": template.key,
        "subject": subject,
        "body": body,
        "sections": [
            {"section": "Subject", "content": subject},
            {"section": "Introduction", "content": intro},
            {"section": "Connection", "content": connection},
            {"section": "Project", "content": project},
            {"section": "Specific request", "content": request},
            {"section": "Closing", "content": closing},
        ],
        "tone": tone,
        "tones": TONES,
        "word_count": len(body.split()),
        "quality": score_draft(
            body=body,
            subject=subject,
            their_work=their_work,
            specific_request=specific_request,
        ),
        "sources_note": SOURCES_NOTE,
        "spam_warning": SPAM_WARNING,
        "etiquette": ETIQUETTE,
        "before_you_send": [
            "Read it once as if you were the recipient. Would you reply?",
            "Check the spelling of their name and their institution.",
            "Confirm the ask is answerable in under five minutes.",
            f"Personalise further if any sentence would work for a different researcher.",
        ],
    }


# --------------------------------------------------------------------------- #
# Section 36: "why this person?"
# --------------------------------------------------------------------------- #

# Phrases that describe a field rather than a person's work. "They study
# biology" is true of thousands of people and is the signature of a mass email.
_GENERIC_CONNECTIONS = (
    "they study", "their research", "your research", "their work", "your work",
    "interested in your field", "work in this area", "expert in", "your lab",
    "i saw your profile", "found you online", "your website",
)

# Evidence the student read something specific rather than a department page.
_SPECIFIC_MARKERS = (
    "paper", "study", "article", "figure", "your 20", "published", "journal",
    "abstract", "preprint", "thesis", "chapter", "doi", "et al", "titled",
)


def assess_personalisation(their_work: str | None) -> dict:
    """Judge whether the 'why this person' answer is actually about this person.

    Section 36. The check is deliberately blunt: a student who cannot name
    something specific has not done the reading, and no amount of polish on the
    rest of the email will fix that.
    """

    text = (their_work or "").strip()
    lowered = text.lower()
    words = len(text.split())

    specific = [m for m in _SPECIFIC_MARKERS if m in lowered]
    generic = [g for g in _GENERIC_CONNECTIONS if g in lowered]
    # A quoted or capitalised phrase usually means a real title.
    names_a_title = bool(re.search(r"[\"\u201c][^\"\u201d]{8,}[\"\u201d]", text)) or bool(
        re.search(r"\b[A-Z][a-z]+ (?:of|and|in|for) [A-Z][a-z]+", text)
    )

    if words < 6:
        verdict = "too_short"
    elif specific or names_a_title:
        verdict = "specific"
    elif generic and words < 25:
        verdict = "generic"
    else:
        verdict = "unclear"

    messages = {
        "too_short": (
            "That is not yet an answer. Name the specific paper, project or lab page you "
            "read, and what in it connected to your project."
        ),
        "generic": (
            "This email is likely too generic. \"They study biology\" is true of thousands of "
            "people. Add one specific thing of theirs you read and why it relates to your work "
            "before sending."
        ),
        "unclear": (
            "This reads as though it could have been written about several researchers. If any "
            "sentence would work for a different person, it is not personalised yet."
        ),
        "specific": (
            "Good — this names something specific enough that the recipient will know you read "
            "their work."
        ),
    }

    return {
        "verdict": verdict,
        "is_specific": verdict == "specific",
        "message": messages[verdict],
        "word_count": words,
    }


# --------------------------------------------------------------------------- #
# Section 41: tone
# --------------------------------------------------------------------------- #

TONES: list[dict[str, str]] = [
    {
        "key": "concise",
        "name": "Concise",
        "description": "Very short and direct. Best when the ask is small and the recipient is senior.",
    },
    {
        "key": "standard",
        "name": "Standard",
        "description": "The recommended default. Professional, specific, about 130-160 words.",
    },
    {
        "key": "warmer",
        "name": "Warmer",
        "description": "Slightly more conversational. Never flattering — enthusiasm about the work, not about them.",
    },
]

TONE_KEYS = {t["key"] for t in TONES}


# --------------------------------------------------------------------------- #
# Section 37: outreach quality score
# --------------------------------------------------------------------------- #

# Openings that mark an email as unread-before-sent. Section 33 forbids the
# first one outright.
_WEAK_OPENINGS = (
    "i hope this email finds you well",
    "i hope you are doing well",
    "i hope this message finds you",
    "to whom it may concern",
    "dear sir or madam",
)

_FLATTERY = (
    "world-renowned", "world renowned", "brilliant", "genius", "greatest",
    "i am a huge fan", "biggest fan", "honoured to even", "honored to even",
    "your groundbreaking", "legendary",
)

_BUZZWORDS = (
    "synergy", "leverage", "cutting-edge", "paradigm", "revolutionary",
    "passionate about learning", "reach out to you regarding", "circle back",
)


def score_draft(
    *,
    body: str,
    subject: str,
    their_work: str | None,
    specific_request: str | None,
) -> dict:
    """An honest 0-100 read on whether this email is worth sending.

    Weighted towards the two things that actually decide it: whether the
    recipient can tell it was written for them, and whether the ask is small
    enough to answer. Length and polish matter far less and are scored that way.
    """

    text = (body or "").strip()
    lowered = text.lower()
    words = len(text.split())

    strengths: list[str] = []
    improvements: list[str] = []
    score = 0

    # -- personalisation: 35 -------------------------------------------------
    personal = assess_personalisation(their_work)
    if personal["is_specific"]:
        score += 35
        strengths.append("Names something specific of theirs, so it cannot read as a mass email")
    elif personal["verdict"] == "unclear":
        score += 15
        improvements.append("Name the specific paper or project — not just their field")
    else:
        improvements.append(personal["message"])

    # -- a real, small ask: 25 ----------------------------------------------
    ask = (specific_request or "").strip()
    if len(ask) >= 25:
        score += 20
        strengths.append("Asks for one specific thing")
        if any(marker in ask.lower() for marker in ("15", "20", "brief", "short", "one ", "a pointer")):
            score += 5
            strengths.append("The request is small enough to say yes to")
    elif ask:
        score += 8
        improvements.append("Make the request more concrete — name the one thing you want")
    else:
        improvements.append("There is no specific request. Add one.")

    # -- length: 15 ----------------------------------------------------------
    if 100 <= words <= 180:
        score += 15
        strengths.append(f"Good length at {words} words")
    elif words < 100:
        score += 8
        improvements.append(f"At {words} words this may be too thin to explain the connection")
    elif words <= 230:
        score += 8
        improvements.append(f"At {words} words, cut two sentences of project background")
    else:
        improvements.append(f"At {words} words this is too long. Aim for 100-180.")

    # -- opening: 10 ---------------------------------------------------------
    if any(phrase in lowered for phrase in _WEAK_OPENINGS):
        improvements.append(
            "Replace the opening. \"I hope this email finds you well\" signals a template; "
            "start with who you are instead."
        )
    else:
        score += 10
        strengths.append("Opens directly instead of with filler")

    # -- subject: 10 ---------------------------------------------------------
    subject_words = len((subject or "").split())
    if subject and 3 <= subject_words <= 12:
        score += 10
        strengths.append("Subject line is specific and short")
    elif subject:
        score += 4
        improvements.append("Tighten the subject line to roughly 4-10 words")
    else:
        improvements.append("Add a specific subject line")

    # -- tone: 5 -------------------------------------------------------------
    flattery = [f for f in _FLATTERY if f in lowered]
    buzzwords = [b for b in _BUZZWORDS if b in lowered]
    if flattery:
        improvements.append(f"Cut the flattery ({flattery[0]}). Interest in the work reads better.")
    elif buzzwords:
        improvements.append(f"Cut '{buzzwords[0]}' — it reads as filler.")
    else:
        score += 5
        strengths.append("No flattery or buzzwords")

    score = max(0, min(100, score))
    if score >= 80:
        verdict = "Ready to send once you have proofread it."
    elif score >= 60:
        verdict = "Close. Fix the points below and it will be worth sending."
    else:
        verdict = "Not ready. As written, this is likely to be deleted unread."

    return {
        "score": score,
        "verdict": verdict,
        "strengths": strengths,
        "improvements": improvements,
        "word_count": words,
        "personalisation": personal,
    }


def suggested_follow_up(sent_on: date | None) -> date | None:
    """One follow-up, roughly ten calendar days out. Not a nagging schedule."""

    return (sent_on + timedelta(days=10)) if sent_on else None


def follow_ups_due(rows, today: date | None = None) -> list[int]:
    """Ids of contacts whose single follow-up is due and not yet done."""

    today = today or date.today()
    return [
        row.id
        for row in rows
        if row.status == OutreachStatus.SENT
        and not row.follow_up_done
        and row.follow_up_on is not None
        and row.follow_up_on <= today
    ]
