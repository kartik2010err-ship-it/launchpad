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
    OutreachStatus,
    ProjectType,
    ProjectVisibility,
    Role,
    Stage,
    TaskStatus,
    TeamRole,
    WorkspaceRole,
    WorkspaceType,
)
from app.models.outreach import OutreachContact
from app.models.project import Project, User, utcnow
from app.models.team import TeamContribution
from app.models.workspace import MentorComment, NotebookEntry, PosterDraft, TimelineTask
from app.models.workspace_org import ProjectActivity
from app.schemas.project import InterviewAnswer, TimelineRequest
from app.services import (
    project_service,
    project_status_service,
    team_service,
    winners_service,
    workspace_service,
)

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

    # The workspace that exercises teams: it holds both team-owned and
    # individually-owned projects, which is the case the project catalog has to
    # render in one table.
    basis = workspace_service.create_workspace(
        db, creator=users["priyanka@example.edu"],
        name="BASIS Phoenix Science Fair", organization_name="BASIS Phoenix",
        workspace_type=WorkspaceType.SCIENCE_FAIR_TEAM,
        description="Team and individual entries for this season's regional fair.",
        default_visibility=ProjectVisibility.WORKSPACE)
    basis.join_code = "BASIS-SF-27"
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

    workspace_service.add_member(db, basis, users["andre@example.edu"], WorkspaceRole.MENTOR)
    workspace_service.add_member(db, basis, users["mentor@example.edu"], WorkspaceRole.MENTOR)
    workspace_service.add_member(db, basis, users["jordan@example.edu"], WorkspaceRole.LEAD)
    for email in (
        "maya@example.edu", "arjun@example.edu", "sarah@example.edu",
        "kevin@example.edu", "grace@example.edu", "daniel@example.edu",
        "liam@example.edu", "marcus@example.edu", "emma@example.edu",
        "priya@example.edu",
    ):
        workspace_service.add_member(db, basis, users[email], WorkspaceRole.MEMBER)

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

    # ---- teams and their shared projects ---------------------------------- #
    #
    # Each team owns exactly ONE project row. Every member opens that same row —
    # nothing is copied per member, which is the whole point of owner_team_id.
    team_specs = [
        {
            "name": "Team Coral",
            "code": "CORAL-8K2P",
            "description": "Reef imagery and early bleaching signatures.",
            "mentor": "priyanka@example.edu",
            "members": ["maya@example.edu", "arjun@example.edu", "sarah@example.edu"],
            "lead": "maya@example.edu",
            "title": "Coral Bleaching Research Project",
            "question": "Can sparse autoencoder features of reef imagery predict temperature "
                        "and CO2 stress before visible bleaching appears?",
            "category": Category.ENVIRONMENTAL,
            "ptype": ProjectType.SCIENTIFIC,
            "stage": Stage.EXPERIMENTATION,
            "weeks": 7,
            "contributions": [
                ("maya@example.edu", "Literature review", "Read 14 papers on bleaching indices; "
                 "built the summary table the research gap came from.", 11.0, True),
                ("maya@example.edu", "Experiment setup", "Configured the imaging rig and the "
                 "temperature-controlled tanks.", 8.5, True),
                ("arjun@example.edu", "Data analysis", "Wrote the autoencoder training pipeline "
                 "and the feature extraction step.", 14.0, True),
                ("arjun@example.edu", "Python visualisation", "Built the figure set: feature "
                 "trajectories against measured stress.", 6.0, False),
                ("sarah@example.edu", "Sample collection", "Ran the weekly imaging sessions and "
                 "logged tank conditions.", 9.0, True),
                ("sarah@example.edu", "Poster design", "Drafted the board layout and the method "
                 "diagram.", 4.0, False),
            ],
        },
        {
            "name": "Team Neuro",
            "code": "NEURO-4T7M",
            "description": "Sleep, memory and reaction time in adolescents.",
            "mentor": "mentor@example.edu",
            "members": ["kevin@example.edu", "grace@example.edu"],
            "lead": "kevin@example.edu",
            "title": "Sleep and Memory Research Project",
            "question": "Does self-reported sleep duration the previous night predict recall "
                        "accuracy on a standard word-list task in 14-16 year olds?",
            "category": Category.BEHAVIORAL_SOCIAL,
            "ptype": ProjectType.SCIENTIFIC,
            "stage": Stage.EXPERIMENTAL_DESIGN,
            "weeks": 9,
            "contributions": [
                ("kevin@example.edu", "Protocol design", "Wrote the recall task protocol and the "
                 "counterbalancing scheme.", 7.0, True),
                ("kevin@example.edu", "Ethics paperwork", "Prepared the human-participants forms "
                 "for review.", 3.5, False),
                ("grace@example.edu", "Literature review", "Summarised prior sleep-and-recall "
                 "studies and their sample sizes.", 8.0, True),
                ("grace@example.edu", "Statistics plan", "Chose the paired analysis and wrote the "
                 "pre-registration of the primary outcome.", 4.5, False),
            ],
        },
        {
            "name": "Team Aero",
            "code": "AERO-9P3K",
            "description": "Propeller geometry and hover efficiency.",
            "mentor": "andre@example.edu",
            "members": ["liam@example.edu", "marcus@example.edu", "emma@example.edu"],
            "lead": "marcus@example.edu",
            "title": "Drone Efficiency Engineering Project",
            "question": "How does propeller pitch angle affect hover current draw at a fixed "
                        "thrust on a 250 g quadcopter frame?",
            "category": Category.ENGINEERING,
            "ptype": ProjectType.ENGINEERING,
            "stage": Stage.DATA_ANALYSIS,
            "weeks": 5,
            "contributions": [
                ("marcus@example.edu", "Test rig build", "Built the thrust stand and wired the "
                 "current logging.", 12.0, True),
                ("liam@example.edu", "Trial runs", "Ran 30 hover trials across five pitch angles.",
                 10.0, True),
                ("emma@example.edu", "Data analysis", "Fitted current against pitch and produced "
                 "the efficiency curve.", 7.5, True),
                ("emma@example.edu", "Abstract draft", "Wrote the first abstract for mentor "
                 "review.", 2.0, False),
            ],
        },
    ]

    teams = {}
    for spec in team_specs:
        team = team_service.create_team(
            db, workspace=basis, creator=users[spec["mentor"]], name=spec["name"],
            description=spec["description"], competition_key="azsef")
        team.join_code = spec["code"]
        team_service.assign_mentor(db, team, users[spec["mentor"]].id)
        for email in spec["members"]:
            team_service.add_team_member(
                db, team, users[email],
                TeamRole.TEAM_LEAD if email == spec["lead"] else TeamRole.MEMBER)
        db.flush()
        teams[spec["name"]] = team

        project = Project(
            owner_id=None, owner_team_id=team.id, workspace_id=basis.id,
            mentor_id=team.mentor_id, visibility=ProjectVisibility.WORKSPACE,
            title=spec["title"], grade_level=11, project_type=spec["ptype"],
            category=spec["category"], current_question=spec["question"], stage=spec["stage"],
            competition_key="azsef",
            competition_name="Arizona Science and Engineering Fair (AzSEF)",
            competition_date=today + timedelta(weeks=spec["weeks"]),
            hours_per_week=9.0, trials_planned=24, minutes_per_trial=25,
            teammates=len(spec["members"]) - 1,
            last_activity_at=utcnow() - timedelta(days=1))
        db.add(project)
        db.flush()

        project_service.add_revision(db, project, spec["question"], source="student",
                                     rationale="The team's starting question.")
        project_service.record_answers(db, project, [
            InterviewAnswer(question_key=k, answer=v)
            for k, v in _answers_for(
                (None, None, None, None, spec["question"], None, None, None, None, None,
                 0.9, None, None, None, spec["category"] == Category.BEHAVIORAL_SOCIAL)
            ).items()
        ])
        project_service.evaluate(db, project)
        project_service.regenerate_timeline(db, project, TimelineRequest(
            competition_key="azsef",
            competition_name="Arizona Science and Engineering Fair (AzSEF)",
            competition_date=project.competition_date, hours_per_week=9.0,
            trials_planned=24, minutes_per_trial=25, teammates=len(spec["members"]) - 1))

        tasks = sorted(
            db.query(TimelineTask).filter(TimelineTask.project_id == project.id).all(),
            key=lambda t: (t.phase_index, t.id))
        for task in tasks[: int(len(tasks) * STAGE_FRACTION[spec["stage"]])]:
            task.status = TaskStatus.COMPLETE

        for email, task_name, detail, hours, done in spec["contributions"]:
            db.add(TeamContribution(
                project_id=project.id, team_id=team.id, user_id=users[email].id,
                task=task_name, description=detail, hours=hours, completed=done,
                contribution_date=today - timedelta(days=random.randint(1, 30))))

        db.add(NotebookEntry(
            project_id=project.id, entry_date=today - timedelta(days=3),
            what_was_done=f"Team working session: {spec['title']}.",
            observations="Logged in the shared notebook — every member writes into the same one.",
            next_steps="Split the next analysis block between members."))
        db.flush()
        project_status_service.refresh(db, project)
        created.append(project)

    # Individual projects in the same workspace, so the catalog has to render
    # both ownership modes side by side.
    for email, title, question, category, ptype, stage, weeks in [
        ("daniel@example.edu", "Battery Degradation Analysis",
         "How does repeated deep discharge affect usable capacity in 18650 cells over 60 cycles?",
         Category.PHYSICS, ProjectType.SCIENTIFIC, Stage.DATA_ANALYSIS, 6),
        ("priya@example.edu", "Monsoon Runoff Nitrate Study",
         "How does ground cover type affect nitrate concentration in runoff after monsoon rainfall?",
         Category.ENVIRONMENTAL, ProjectType.SCIENTIFIC, Stage.EXPERIMENTATION, 8),
    ]:
        project = Project(
            owner_id=users[email].id, owner_team_id=None, workspace_id=basis.id,
            mentor_id=users["andre@example.edu"].id,
            visibility=ProjectVisibility.WORKSPACE, title=title, grade_level=11,
            project_type=ptype, category=category, current_question=question, stage=stage,
            competition_key="azsef",
            competition_name="Arizona Science and Engineering Fair (AzSEF)",
            competition_date=today + timedelta(weeks=weeks),
            hours_per_week=6.0, trials_planned=18, minutes_per_trial=20,
            last_activity_at=utcnow() - timedelta(days=2))
        db.add(project)
        db.flush()
        project_service.add_revision(db, project, question, source="student")
        project_service.record_answers(db, project, [
            InterviewAnswer(question_key="goal", answer=question),
            InterviewAnswer(question_key="independent_variable", answer="Four levels plus a control"),
            InterviewAnswer(question_key="dependent_variable", answer="Primary outcome in mg/L"),
            InterviewAnswer(question_key="control", answer="An untreated group run alongside"),
            InterviewAnswer(question_key="trials", answer="6 replicates per condition"),
        ])
        project_service.evaluate(db, project)
        project_status_service.refresh(db, project)
        created.append(project)

    # ---- outreach ---------------------------------------------------------- #
    db.add(OutreachContact(
        user_id=users["maya@example.edu"].id,
        researcher_name="Dr. Elena Marsh", institution="Arizona State University",
        their_work="your 2023 paper on thermal stress indices in reef imagery, particularly the "
                   "point that visible bleaching lags measurable stress by several days",
        template_key="paper_question",
        subject="Question about your 2023 paper on reef thermal stress",
        body="(draft in progress)", status=OutreachStatus.SENT,
        sent_on=today - timedelta(days=12), follow_up_on=today - timedelta(days=2),
        notes="Asked whether the lag held at the lowest stress level."))
    db.add(OutreachContact(
        user_id=users["arjun@example.edu"].id,
        researcher_name="Dr. Samuel Okonkwo", institution="University of Arizona",
        their_work="your lab's work on lightweight vision models for field deployment",
        template_key="research_guidance", subject="Question about quantisation trade-offs",
        body="(draft in progress)", status=OutreachStatus.REPLIED,
        sent_on=today - timedelta(days=25),
        notes="Replied with two papers and offered a 15-minute call."))

    # ---- reference library ------------------------------------------------- #
    # Ships with teaching examples only. No real past winners are fabricated;
    # see backend/data/winning_projects.json.
    winners_service.ingest_file(db)

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
    team_count = sum(1 for p in created if p.owner_team_id is not None)
    print(
        f"Seeded {len(users)} people across 5 workspaces "
        f"({club_count} club projects, {team_count} team projects, {len(created)} total). "
        f"Password: {PASSWORD}\n"
        "  jordan@example.edu   student — LEAD of the club, OWNER of Robotics\n"
        "  mentor@example.edu   OWNER of the club, plain MEMBER of Robotics\n"
        "  priya@example.edu    strong project       ava@example.edu   weak project\n"
        "  sarah@example.edu    blocked on approval  riley@example.edu another school\n"
        "  BASIS Phoenix Science Fair (BASIS-SF-27): Team Coral (CORAL-8K2P),\n"
        "    Team Neuro (NEURO-4T7M), Team Aero (AERO-9P3K) + 2 individual projects.\n"
        "    maya/arjun/sarah share ONE Coral project row."
    )


if __name__ == "__main__":
    run()
