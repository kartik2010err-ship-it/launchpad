"""Demo data.

Built to exercise the permission model, not just to look full: there are four
workspaces, people who hold different roles in different workspaces, and a
student who exists only in a rival school so the authorization tests have
something real to fail against.

Run with ``python -m app.seed``. Safe to re-run: it drops and recreates.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.models.enums import (
    ActivityKind,
    Category,
    CommentType,
    ProjectType,
    ProjectVisibility,
    Role,
    Stage,
    TaskStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.models.project import Project, User, utcnow
from app.models.workspace import MentorComment, PosterDraft, TimelineTask
from app.models.workspace_org import ProjectActivity
from app.schemas.project import InterviewAnswer, TimelineRequest
from app.services import project_service, project_status_service, workspace_service

PASSWORD = "coach1234"

STAFF = [
    ("Dr. Lena Whitfield", "mentor@example.edu", Role.MENTOR),
    ("Mr. Andre Cole", "andre@example.edu", Role.MENTOR),
    ("Ms. Priyanka Raman", "priyanka@example.edu", Role.MENTOR),
    # A student who runs the club. A global "lead" role would model this badly.
    ("Jordan Smith", "jordan@example.edu", Role.STUDENT),
]

# name, email, grade, title, question, category, type, stage, mentor,
# weeks_to_fair, answer_ratio, days_quiet, overdue, blocked, regulated
STUDENTS = [
    ("Ava Ramirez", "ava@example.edu", 9, "Music and studying",
     "Does music affect concentration?",
     Category.BEHAVIORAL_SOCIAL, ProjectType.SCIENTIFIC, Stage.QUESTION_REFINEMENT,
     "mentor@example.edu", 9, 0.25, 12, 2, 0, True),
    ("Noah Berger", "noah@example.edu", 10, "Water temperature and radish germination",
     "How does irrigation water temperature affect radish germination rate?",
     Category.BIOMEDICAL, ProjectType.SCIENTIFIC, Stage.EXPERIMENTATION,
     "mentor@example.edu", 10, 1.0, 1, 0, 0, False),
    ("Priya Nair", "priya@example.edu", 11, "Biochar and nitrate retention under monsoon rainfall",
     "How does biochar amendment rate affect nitrate leaching under monsoon rainfall intensity?",
     Category.ENVIRONMENTAL, ProjectType.SCIENTIFIC, Stage.DATA_ANALYSIS,
     "priyanka@example.edu", 10, 1.0, 0, 0, 0, True),
    ("Marcus Bell", "marcus@example.edu", 11, "Low-cost evaporative cooling vest",
     "Can a low-cost evaporative cooling vest reduce skin-surface temperature in dry heat?",
     Category.ENGINEERING, ProjectType.ENGINEERING, Stage.EXPERIMENTATION,
     "andre@example.edu", 8, 1.0, 3, 1, 0, False),
    ("Maya Patel", "maya@example.edu", 11, "Coral bleaching signatures from reef imagery",
     "Can sparse autoencoder features of reef imagery predict temperature and CO2 stress "
     "before visible bleaching?",
     Category.ENVIRONMENTAL, ProjectType.SCIENTIFIC, Stage.EXPERIMENTAL_DESIGN,
     "priyanka@example.edu", 6, 0.8, 2, 0, 0, False),
    ("Daniel Okafor", "daniel@example.edu", 10, "Battery efficiency under cold cycling",
     "How does repeated cold-temperature cycling affect lithium-ion capacity retention?",
     Category.PHYSICS, ProjectType.SCIENTIFIC, Stage.EXPERIMENTATION,
     "andre@example.edu", 5, 0.9, 1, 4, 0, False),
    ("Arjun Mehta", "arjun@example.edu", 12, "AI crop disease detection on low-end phones",
     "Can a quantised CNN detect three tomato leaf diseases at usable accuracy on a sub-$80 phone?",
     Category.COMPUTER_SCIENCE, ProjectType.ENGINEERING, Stage.DATA_ANALYSIS,
     "mentor@example.edu", 4, 1.0, 0, 0, 0, False),
    ("Sarah Kim", "sarah@example.edu", 10, "Layered ceramic water filtration",
     "How does clay-to-sawdust ratio affect turbidity removal in a ceramic pot filter?",
     Category.ENGINEERING, ProjectType.ENGINEERING, Stage.APPROVAL_REQUIRED,
     None, 7, 0.6, 15, 3, 1, True),
    ("Kevin Zhao", "kevin@example.edu", 9, "Sleep duration and reaction time",
     "Does self-reported sleep duration predict simple reaction time in teenagers?",
     Category.BEHAVIORAL_SOCIAL, ProjectType.SCIENTIFIC, Stage.BACKGROUND_RESEARCH,
     "mentor@example.edu", 8, 0.4, 6, 1, 0, True),
    ("Emma Lindqvist", "emma@example.edu", 12, "Mycelium packaging compressive strength",
     "How does substrate composition affect compressive strength of mycelium-bound packaging?",
     Category.ENGINEERING, ProjectType.ENGINEERING, Stage.POSTER,
     "andre@example.edu", 3, 1.0, 1, 0, 0, False),
    ("Tomás Herrera", "tomas@example.edu", 11, "Urban heat island mapping",
     "How does tree canopy cover relate to air temperature across a 1 km urban transect?",
     Category.ENVIRONMENTAL, ProjectType.SCIENTIFIC, Stage.EXPERIMENTATION,
     "priyanka@example.edu", 9, 0.85, 4, 0, 0, False),
    ("Grace Adeyemi", "grace@example.edu", 10, "Enzyme activity across pH",
     "How does pH affect catalase reaction rate in potato extract?",
     Category.BIOMEDICAL, ProjectType.SCIENTIFIC, Stage.INTERVIEW_PREP,
     "mentor@example.edu", 2, 1.0, 0, 0, 0, False),
    ("Liam O'Connor", "liam@example.edu", 9, "Bridge truss geometry and load",
     "Which truss geometry carries the most load per gram of balsa?",
     Category.ENGINEERING, ProjectType.ENGINEERING, Stage.IDEA,
     None, 11, 0.2, 20, 0, 0, False),
    ("Sofia Rossi", "sofia@example.edu", 12, "Microplastic capture in laundry effluent",
     "How does filter mesh size affect microfibre capture from laundry effluent?",
     Category.ENVIRONMENTAL, ProjectType.ENGINEERING, Stage.COMPLETE,
     "priyanka@example.edu", 1, 1.0, 2, 0, 0, False),
]

OUTSIDER = ("Riley Chen", "riley@example.edu", 11)

STAGE_FRACTION = {
    Stage.IDEA: 0.05, Stage.QUESTION_REFINEMENT: 0.12, Stage.BACKGROUND_RESEARCH: 0.2,
    Stage.EXPERIMENTAL_DESIGN: 0.32, Stage.APPROVAL_REQUIRED: 0.38,
    Stage.EXPERIMENTATION: 0.6, Stage.DATA_ANALYSIS: 0.75, Stage.POSTER: 0.88,
    Stage.INTERVIEW_PREP: 0.95, Stage.COMPLETE: 1.0,
}


def _answers_for(student) -> dict[str, str]:
    """Interview answers, truncated by how far along the student actually is."""

    question, ratio, regulated = student[4], student[10], student[14]
    full = {
        "goal": f"Find out: {question}",
        "independent_variable": "Three levels of the main treatment plus an untreated control",
        "dependent_variable": "The primary outcome, recorded in mm",
        "measurement": "Calibrated instrument, three readings per sample in mm",
        "population": "A single well-defined sample group from one source",
        "prediction": "The middle level performs best; the effect flattens at the extreme",
        "mechanism": "Because the treatment changes the rate-limiting step in the process",
        "control": "An untreated group run alongside every trial in the same conditions",
        "trials": "6 replicates per condition",
        "resources": "School lab equipment plus a borrowed sensor",
        "time_budget": "8 hours a week",
        "regulated": (
            "Human participants complete a short survey under supervision."
            if regulated
            else "No regulated materials, organisms or participants."
        ),
        "prior_work": "Three prior studies looked at the general effect in other settings",
        "differentiator": "No published work has tested this combination in this context",
    }
    keys = list(full)
    return {k: full[k] for k in keys[: max(1, round(len(keys) * ratio))]}


def run() -> None:
    random.seed(11)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    today = date.today()

    users: dict[str, User] = {}
    for name, email, role in STAFF:
        users[email] = User(name=name, email=email, hashed_password=hash_password(PASSWORD),
                            role=role, school="Hamilton High School")
        db.add(users[email])
    for s in STUDENTS:
        users[s[1]] = User(name=s[0], email=s[1], hashed_password=hash_password(PASSWORD),
                           role=Role.STUDENT, school="Hamilton High School", grade_level=s[2])
        db.add(users[s[1]])
    users[OUTSIDER[1]] = User(name=OUTSIDER[0], email=OUTSIDER[1],
                              hashed_password=hash_password(PASSWORD), role=Role.STUDENT,
                              school="Westbrook Academy", grade_level=OUTSIDER[2])
    db.add(users[OUTSIDER[1]])
    db.flush()

    # ---- workspaces ------------------------------------------------------ #
    club = workspace_service.create_workspace(
        db, creator=users["mentor@example.edu"],
        name="Hamilton High Science Fair Club", organization_name="Hamilton High School",
        workspace_type=WorkspaceType.RESEARCH_CLUB,
        description="Everyone competing at AzSEF this season.")
    club.join_code = "HAMILTON-SCIENCE-27"

    robotics = workspace_service.create_workspace(
        db, creator=users["jordan@example.edu"],
        name="Robotics Research Team", organization_name="Hamilton High School",
        workspace_type=WorkspaceType.SCIENCE_FAIR_TEAM,
        description="Small team, shared build log.",
        default_visibility=ProjectVisibility.WORKSPACE)
    robotics.join_code = "ROBOTICS-TEAM-4K9"

    biology = workspace_service.create_workspace(
        db, creator=users["priyanka@example.edu"],
        name="Biology Honors Period 3", organization_name="Hamilton High School",
        workspace_type=WorkspaceType.CLASSROOM,
        description="Class research projects, spring semester.")
    biology.join_code = "BIO-HONORS-3F2"

    rival = workspace_service.create_workspace(
        db, creator=users[OUTSIDER[1]],
        name="Westbrook Academy Research", organization_name="Westbrook Academy",
        workspace_type=WorkspaceType.SCHOOL, description="A different school entirely.")
    db.flush()

    # Same people, different authority in each space.
    workspace_service.add_member(db, club, users["jordan@example.edu"], WorkspaceRole.LEAD)
    workspace_service.add_member(db, club, users["andre@example.edu"], WorkspaceRole.MENTOR)
    workspace_service.add_member(db, club, users["priyanka@example.edu"], WorkspaceRole.MENTOR)
    for s in STUDENTS:
        workspace_service.add_member(db, club, users[s[1]], WorkspaceRole.MEMBER)

    # Jordan owns robotics; the club owner is only a plain member there.
    workspace_service.add_member(db, robotics, users["mentor@example.edu"], WorkspaceRole.MEMBER)
    for email in ("daniel@example.edu", "liam@example.edu", "emma@example.edu"):
        workspace_service.add_member(db, robotics, users[email], WorkspaceRole.MEMBER)

    workspace_service.add_member(db, biology, users["mentor@example.edu"], WorkspaceRole.LEAD)
    for email in ("grace@example.edu", "kevin@example.edu", "noah@example.edu"):
        workspace_service.add_member(db, biology, users[email], WorkspaceRole.MEMBER)

    for email in list(users):
        workspace_service.ensure_personal_workspace(db, users[email])
    db.flush()

    # ---- club projects ---------------------------------------------------- #
    created: list[Project] = []
    for s in STUDENTS:
        (_n, email, grade, title, question, category, ptype, stage, mentor_email,
         weeks, _r, quiet, overdue, blocked, _reg) = s

        project = Project(
            owner_id=users[email].id, workspace_id=club.id,
            mentor_id=users[mentor_email].id if mentor_email else None,
            visibility=ProjectVisibility.PRIVATE, title=title, grade_level=grade,
            project_type=ptype, category=category, current_question=question, stage=stage,
            competition_key="azsef",
            competition_name="Arizona Science and Engineering Fair (AzSEF)",
            competition_date=today + timedelta(weeks=weeks),
            hours_per_week=random.choice([4.0, 5.0, 6.0, 8.0]),
            trials_planned=random.choice([12, 15, 24, 30]),
            minutes_per_trial=random.choice([15, 20, 30, 45]),
            last_activity_at=utcnow() - timedelta(days=quiet),
        )
        db.add(project)
        db.flush()
        created.append(project)

        project_service.add_revision(db, project, question, source="student",
                                     rationale="Your starting question, kept for the record.")
        project_service.record_answers(
            db, project,
            [InterviewAnswer(question_key=k, answer=v) for k, v in _answers_for(s).items()],
        )
        project_service.evaluate(db, project)
        project_service.regenerate_timeline(
            db, project,
            TimelineRequest(
                competition_key="azsef",
                competition_name="Arizona Science and Engineering Fair (AzSEF)",
                competition_date=project.competition_date,
                hours_per_week=project.hours_per_week,
                trials_planned=project.trials_planned,
                minutes_per_trial=project.minutes_per_trial,
                teammates=0,
            ),
        )

        tasks = sorted(
            db.query(TimelineTask).filter(TimelineTask.project_id == project.id).all(),
            key=lambda t: (t.phase_index, t.id),
        )
        cutoff = int(len(tasks) * STAGE_FRACTION[stage])
        for task in tasks[:cutoff]:
            task.status = TaskStatus.COMPLETE
        for task in tasks[cutoff : cutoff + overdue]:
            task.due_date = today - timedelta(days=random.randint(2, 12))
            task.status = TaskStatus.IN_PROGRESS
        for task in tasks[cutoff + overdue : cutoff + overdue + blocked]:
            task.status = TaskStatus.BLOCKED
            task.ai_note = "Waiting on the SRC to return the signed form."

        if stage in {Stage.POSTER, Stage.INTERVIEW_PREP, Stage.COMPLETE}:
            db.add(PosterDraft(
                project_id=project.id, layout_key="traditional",
                sections={
                    "title": title, "question": question,
                    "hypothesis": "Stated on the board.",
                    "materials": "Listed on the board.",
                    "procedure": "Six numbered steps.",
                    "results": "Two figures and a table.",
                    "conclusion": "Answers the question directly.",
                    "next_steps": "What a follow-up study would change.",
                }))
        db.flush()
        project_status_service.refresh(db, project)

    # ---- projects in the other workspaces --------------------------------- #
    for email, ws, title, question, category in [
        ("daniel@example.edu", robotics, "Drivetrain gear ratio testing",
         "Which gear ratio gives the best acceleration under a 12 kg load?", Category.ENGINEERING),
        ("grace@example.edu", biology, "Osmosis in potato cores",
         "How does solute concentration affect mass change in potato cores?", Category.BIOMEDICAL),
        (OUTSIDER[1], rival, "Solar panel dust accumulation",
         "How does dust accumulation affect panel output over two weeks?", Category.PHYSICS),
    ]:
        project = Project(
            owner_id=users[email].id, workspace_id=ws.id,
            visibility=ws.default_project_visibility, title=title, grade_level=11,
            project_type=ProjectType.SCIENTIFIC, category=category,
            current_question=question, stage=Stage.EXPERIMENTAL_DESIGN,
            last_activity_at=utcnow() - timedelta(days=2))
        db.add(project)
        db.flush()
        project_service.add_revision(db, project, question, source="student")
        project_service.record_answers(db, project, [
            InterviewAnswer(question_key="goal", answer=question),
            InterviewAnswer(question_key="independent_variable", answer="Three levels"),
        ])
        project_service.evaluate(db, project)
        project_status_service.refresh(db, project)
        created.append(project)

    # ---- feedback and activity -------------------------------------------- #
    for idx, email, role, ctype, body in [
        (0, "mentor@example.edu", WorkspaceRole.MENTOR, CommentType.NEEDS_ACTION,
         '"Concentration" is not measurable yet. Pick one task with a score.'),
        (2, "priyanka@example.edu", WorkspaceRole.MENTOR, CommentType.IMPORTANT,
         "Your differentiation argument is the strongest part. Lead the poster with it."),
        (5, "andre@example.edu", WorkspaceRole.MENTOR, CommentType.NEEDS_ACTION,
         "Four tasks are overdue. Tell me what you need to get the cold cycling started."),
        (7, "jordan@example.edu", WorkspaceRole.LEAD, CommentType.IMPORTANT,
         "You need SRC sign-off before any testing. This is blocking everything else."),
        (9, "andre@example.edu", WorkspaceRole.MENTOR, CommentType.GENERAL,
         "Poster draft reads well. Cut the intro by about a third."),
    ]:
        db.add(MentorComment(
            project_id=created[idx].id, author_id=users[email].id,
            author_name=users[email].name, author_role=role.value, section="methodology",
            comment_type=ctype, body=body,
            requires_action=ctype == CommentType.NEEDS_ACTION,
            resolved=ctype == CommentType.RESOLVED))

    for offset, (idx, email, kind, action, summary) in enumerate([
        (4, "maya@example.edu", ActivityKind.PROJECT_CHANGE, "question_updated",
         "Maya Patel updated her research question"),
        (5, "daniel@example.edu", ActivityKind.MILESTONE, "stage_advanced",
         "Daniel Okafor completed experimental design"),
        (6, "arjun@example.edu", ActivityKind.MILESTONE, "results_uploaded",
         "Arjun Mehta uploaded new results"),
        (7, "sarah@example.edu", ActivityKind.OVERDUE, "milestone_missed",
         "Sarah Kim missed a project milestone"),
        (5, "andre@example.edu", ActivityKind.COMMENT, "comment_added",
         "Mr. Andre Cole requested changes to Daniel's methodology"),
        (2, "priya@example.edu", ActivityKind.MILESTONE, "stage_advanced",
         "Priya Nair moved from Experimentation to Data Analysis"),
        (11, "grace@example.edu", ActivityKind.MILESTONE, "stage_advanced",
         "Grace Adeyemi started interview preparation"),
        (9, "emma@example.edu", ActivityKind.PROJECT_CHANGE, "poster_updated",
         "Emma Lindqvist updated her poster draft"),
    ]):
        db.add(ProjectActivity(
            workspace_id=created[idx].workspace_id, project_id=created[idx].id,
            project_title=created[idx].title, user_id=users[email].id,
            actor_name=users[email].name, kind=kind.value, action=action, summary=summary,
            created_at=utcnow() - timedelta(hours=offset * 7 + 1)))

    db.commit()

    club_count = sum(1 for p in created if p.workspace_id == club.id)
    print(
        f"Seeded {len(users)} people across 4 workspaces "
        f"({club_count} club projects, {len(created)} total). Password: {PASSWORD}\n"
        "  jordan@example.edu   student — LEAD of the club, OWNER of Robotics\n"
        "  mentor@example.edu   OWNER of the club, plain MEMBER of Robotics\n"
        "  priya@example.edu    strong project       ava@example.edu   weak project\n"
        "  sarah@example.edu    blocked on approval  riley@example.edu another school"
    )


if __name__ == "__main__":
    run()
