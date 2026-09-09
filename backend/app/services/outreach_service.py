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


@dataclass
class OutreachTemplate:
    key: str
    name: str
    when_to_use: str
    subject_pattern: str
    # Section name -> guidance shown alongside the generated draft.
    structure: list[tuple[str, str]] = field(default_factory=list)
    ask_examples: list[str] = field(default_factory=list)


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


def listing() -> list[dict]:
    return [
        {
            "key": t.key,
            "name": t.name,
            "when_to_use": t.when_to_use,
            "structure": [{"section": s, "guidance": g} for s, g in t.structure],
            "ask_examples": t.ask_examples,
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

    grade = f"grade {grade_level}" if str(grade_level).isdigit() else str(grade_level)
    subject = template.subject_pattern.format(
        topic=research_topic,
        grade=grade,
        school=school,
        year="",
        equipment=research_topic,
        original_subject=original_subject or research_topic,
    ).replace("  ", " ").strip()

    salutation = f"Dear {researcher_name},"

    intro = (
        f"My name is {student_name}. I am a {grade} student at {school}, working on an "
        f"independent research project on {research_topic}."
    )
    connection = f"I read {their_work.strip().rstrip('.')}."
    project_lines = []
    if research_question:
        project_lines.append(f"My research question is: {research_question.strip().rstrip('.')}.")
    if timeline:
        project_lines.append(f"My timeline is {timeline.strip().rstrip('.')}.")
    project = " ".join(project_lines) or (
        f"I am in the early stages of designing a study on {research_topic}."
    )
    request = f"{specific_request.strip().rstrip('.')}."
    closing = (
        "I know your time is limited, and I would be grateful for even a brief reply. "
        "Thank you for considering it.\n\n"
        f"{student_name}\n{grade.capitalize()}, {school}"
    )

    body = "\n\n".join([salutation, intro, connection, project, request, closing])

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
        "word_count": len(body.split()),
        "spam_warning": SPAM_WARNING,
        "etiquette": ETIQUETTE,
        "before_you_send": [
            "Read it once as if you were the recipient. Would you reply?",
            "Check the spelling of their name and their institution.",
            "Confirm the ask is answerable in under five minutes.",
            f"Personalise further if any sentence would work for a different researcher.",
        ],
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
