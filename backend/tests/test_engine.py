"""Tests concentrate on the claims the app makes to students.

A wrong colour in the UI is a bug. Telling a student their project needs no
approval, or that it is novel, is a different kind of failure — so those
properties are tested directly rather than assumed.
"""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.models.enums import Category, EvidenceBasis, NoveltyStatus, ProjectType, Stage
from app.services import novelty, rubric, safety, scoring, timeline
from app.services.ai.heuristic import HeuristicProvider
from app.services.signals import analyse_question, build_signals

WEAK_ANSWERS = {
    "goal": "I want to see if music helps concentration.",
    "independent_variable": "music",
    "dependent_variable": "concentration",
    "population": "students",
}

STRONG_ANSWERS = {
    "goal": "Determine whether biochar rate reduces nitrate leaching under high rainfall intensity.",
    "independent_variable": "Biochar rate at 0, 1, 2 and 4 percent, crossed with rainfall at 20 and 60 mm/hour",
    "dependent_variable": "Nitrate concentration in leachate in mg/L",
    "measurement": "Leachate sampled every 5 minutes for 40 minutes; nitrate by spectrophotometer at 220 nm in mg/L.",
    "population": "Repacked desert soil columns, 10 cm diameter, single collection site",
    "prediction": "Nitrate loss falls about 30 percent at 2 percent biochar and the benefit shrinks at 60 mm/hour.",
    "mechanism": "Because biochar raises cation exchange capacity and micropore volume, increasing solute residence time.",
    "control": "Unamended columns at both intensities plus a deionised water blank.",
    "trials": "6 replicate columns per cell",
    "resources": "Rainfall simulator and spectrophotometer at a university outreach lab; sponsor supervises.",
    "time_budget": "14 weeks, 8 hours a week",
    "regulated": "Dilute acid and nitrate reagent used under supervision in the university lab.",
    "prior_work": "Three studies on biochar nitrate retention in temperate soils; a review notes arid data are sparse.",
    "differentiator": "No published work crosses amendment rate with rainfall intensity in arid soils.",
}


def make_project(question: str, project_type=ProjectType.SCIENTIFIC, category=Category.ENVIRONMENTAL):
    return SimpleNamespace(
        current_question=question,
        project_type=project_type,
        category=category,
        topic="",
        background_knowledge="",
        grade_level=11,
    )


def weak_signals():
    return build_signals(make_project("Does music affect concentration?", category=Category.BEHAVIORAL_SOCIAL), WEAK_ANSWERS)


def strong_signals():
    return build_signals(
        make_project("How does biochar amendment rate affect nitrate leaching under monsoon rainfall intensity?"),
        STRONG_ANSWERS,
    )


# --------------------------------------------------------------------------- #
# Question analysis
# --------------------------------------------------------------------------- #


def test_vague_question_is_flagged():
    qa = analyse_question("Does music affect concentration?")
    assert "affect" in qa.vague_verbs
    assert not qa.names_levels
    assert qa.issues


def test_specific_question_has_fewer_issues():
    qa = analyse_question(
        "How do 60, 100 and 140 BPM instrumental conditions affect n-back accuracy in 30 tenth-grade students?"
    )
    assert qa.names_levels
    assert len(qa.issues) < len(analyse_question("Does music affect concentration?").issues)


# --------------------------------------------------------------------------- #
# Safety screening: one-directional by design
# --------------------------------------------------------------------------- #


def test_human_participants_are_flagged():
    result = safety.screen("I will survey 30 students in my class about their sleep.")
    categories = {f.category for f in result.flags}
    assert "human_participants" in categories or "surveys" in categories
    assert result.preapproval_possible


def test_clean_screen_never_claims_exemption():
    result = safety.screen("I will drop steel balls from a ladder and time the fall with a stopwatch.")
    assert not result.determination_made
    assert "not an exemption" in result.notice.lower()


def test_bacteria_culturing_is_flagged():
    result = safety.screen("I will grow bacteria on agar plates from door handles.")
    assert any(f.category == "biological_agents" for f in result.flags)


# --------------------------------------------------------------------------- #
# Novelty: never overclaims
# --------------------------------------------------------------------------- #


def test_common_archetype_is_recognised():
    result = novelty.analyse(weak_signals())
    assert result.status in (NoveltyStatus.LIKELY_COMMON, NoveltyStatus.INSUFFICIENT_EVIDENCE)
    assert not result.literature_search_performed


def test_top_tier_requires_a_real_search():
    result = novelty.analyse(strong_signals())
    assert result.status != NoveltyStatus.STRONG_RESEARCH_GAP
    assert "no literature search" in result.evidence_note.lower()


def test_novelty_never_invents_sources():
    assert novelty.analyse(strong_signals()).sources == []


# --------------------------------------------------------------------------- #
# Scoring discriminates
# --------------------------------------------------------------------------- #


def test_strong_project_outscores_weak_project():
    provider = HeuristicProvider()
    weak = provider.evaluate(weak_signals(), Stage.QUESTION_REFINEMENT)
    strong = provider.evaluate(strong_signals(), Stage.EXPERIMENTAL_DESIGN)
    assert strong.overall_score - weak.overall_score > 25
    for key in ("research_question", "methodology", "scientific_depth"):
        w = next(d for d in weak.dimensions if d.key == key)
        s = next(d for d in strong.dimensions if d.key == key)
        assert s.score > w.score


def test_incomplete_interview_caps_the_score():
    provider = HeuristicProvider()
    weak = provider.evaluate(weak_signals(), Stage.IDEA)
    assert weak.information_completeness < 50
    assert weak.overall_score <= 55 + weak.information_completeness * 0.45


def test_missing_control_is_named_not_glossed():
    provider = HeuristicProvider()
    result = provider.evaluate(weak_signals(), Stage.IDEA)
    methodology = next(d for d in result.dimensions if d.key == "methodology")
    assert any("control" in w.lower() or "baseline" in w.lower() for w in methodology.weaknesses)


# --------------------------------------------------------------------------- #
# Rubric honesty
# --------------------------------------------------------------------------- #


def test_unstarted_categories_are_not_scored():
    provider = HeuristicProvider()
    result = provider.evaluate(strong_signals(), Stage.EXPERIMENTAL_DESIGN)
    by_key = {line.key: line for line in result.rubric.lines}
    for key in ("execution", "poster", "interview"):
        assert by_key[key].basis == EvidenceBasis.NOT_YET_ASSESSABLE
        assert by_key[key].points_projected == 0
    assert result.rubric.assessable_points == 45
    assert result.rubric.points_possible == 100


def test_execution_becomes_assessable_once_experimenting():
    provider = HeuristicProvider()
    result = provider.evaluate(strong_signals(), Stage.EXPERIMENTATION)
    execution = next(line for line in result.rubric.lines if line.key == "execution")
    assert execution.basis == EvidenceBasis.PROJECTED_POTENTIAL


# --------------------------------------------------------------------------- #
# Timeline
# --------------------------------------------------------------------------- #


def test_schedule_respects_phase_dependencies():
    tasks, _warnings = timeline.generate(
        strong_signals(),
        competition_date=date.today() + timedelta(days=120),
        today=date.today(),
        hours_per_week=8,
        trials=48,
        minutes_per_trial=45,
        teammates=1,
        regulated=True,
        already_experimenting=False,
    )
    by_key = {t.template.key: t for t in tasks}
    assert by_key["sponsor_approval"].due_date <= by_key["pilot"].start_date
    assert by_key["main_trials"].due_date <= by_key["clean_data"].start_date
    assert by_key["graphs"].due_date <= by_key["poster_final"].due_date
    assert all(t.start_date <= t.due_date for t in tasks)


def test_unrealistic_plan_produces_a_warning():
    _tasks, warnings = timeline.generate(
        strong_signals(),
        competition_date=date.today() + timedelta(days=18),
        today=date.today(),
        hours_per_week=3,
        trials=40,
        minutes_per_trial=30,
        teammates=0,
        regulated=True,
        already_experimenting=False,
    )
    assert any(w.severity == "high" for w in warnings)
    assert any("approval" in w.message.lower() for w in warnings)


def test_regulated_projects_get_a_review_task():
    tasks, _ = timeline.generate(
        strong_signals(),
        competition_date=date.today() + timedelta(days=100),
        today=date.today(),
        hours_per_week=6,
        trials=10,
        minutes_per_trial=20,
        teammates=0,
        regulated=True,
        already_experimenting=False,
    )
    assert "src_irb" in {t.template.key for t in tasks}


def test_unregulated_projects_skip_the_review_task():
    tasks, _ = timeline.generate(
        strong_signals(),
        competition_date=date.today() + timedelta(days=100),
        today=date.today(),
        hours_per_week=6,
        trials=10,
        minutes_per_trial=20,
        teammates=0,
        regulated=False,
        already_experimenting=False,
    )
    assert "src_irb" not in {t.template.key for t in tasks}


# --------------------------------------------------------------------------- #
# Interview behaviour
# --------------------------------------------------------------------------- #


def test_interview_pushes_back_on_a_thin_answer():
    provider = HeuristicProvider()
    signals = weak_signals()
    step = provider.next_questions(signals, 3, ["dependent_variable"])
    critique = next(c for c in step.critiques if c.question_key == "dependent_variable")
    assert critique.follow_up is not None
    assert not step.ready_to_evaluate


def test_interview_does_not_ask_answered_questions_again():
    provider = HeuristicProvider()
    step = provider.next_questions(strong_signals(), 3)
    assert step.ready_to_evaluate
    assert not step.questions


def test_refinement_preserves_the_original():
    provider = HeuristicProvider()
    signals = weak_signals()
    result = provider.refine(signals)
    assert result.original_question == signals.question
    assert {v.variant for v in result.variants} == {"safe", "competitive", "ambitious"}
    for variant in result.variants:
        assert variant.controls and variant.hypothesis and variant.primary_measurement


def test_plan_does_not_invent_missing_answers():
    provider = HeuristicProvider()
    plan = provider.research_plan(weak_signals(), "Does music affect concentration?")
    text = plan.model_dump_json()
    assert "you have not answered this yet" in text
    assert plan.disclaimer
