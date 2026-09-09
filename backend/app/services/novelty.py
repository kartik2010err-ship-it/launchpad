"""Novelty analysis.

Two rules govern this module:

1. The app never claims a project *is* novel. Absence of evidence is reported as
   absence of evidence, and the tier ceiling depends on whether a real literature
   source was consulted.
2. The app never invents citations. ``literature_search_performed`` is False
   unless a search provider actually ran, and ``sources`` only ever contains
   things the student typed or a real search returned.

What it *can* do honestly is recognise the archetypes that show up at every fair,
which is where most students actually lose creativity points.
"""

from __future__ import annotations

import re

from app.models.enums import NoveltyStatus
from app.schemas.evaluation import NoveltyAnalysis
from app.services.signals import ProjectSignals

# Each entry: all of `must` plus at least one of `any_of` must appear.
COMMON_ARCHETYPES: list[dict] = [
    {
        "key": "music_cognition",
        "must": ["music"],
        "any_of": ["concentration", "focus", "memory", "study", "test score", "homework", "learning"],
        "what_exists": (
            "Music-versus-silence effects on studying are one of the most entered behavioural "
            "projects at every level, usually with a self-reported or short quiz outcome."
        ),
    },
    {
        "key": "plant_music",
        "must": ["plant"],
        "any_of": ["music", "sound", "talking", "singing"],
        "what_exists": "Playing music to plants is a long-standing fair staple with weak effect sizes and heavy confounds.",
    },
    {
        "key": "plant_liquids",
        "must": ["plant"],
        "any_of": ["soda", "juice", "milk", "gatorade", "coffee", "energy drink", "different liquids"],
        "what_exists": "Watering plants with household liquids appears at nearly every middle-school fair.",
    },
    {
        "key": "plant_light",
        "must": ["plant"],
        "any_of": ["colored light", "coloured light", "light color", "led color", "wavelength", "grow light"],
        "what_exists": (
            "Coloured-light effects on plant growth are extremely common, and the underlying "
            "photosynthetic action spectrum is textbook material rather than an open question."
        ),
    },
    {
        "key": "fertilizer",
        "must": ["fertilizer"],
        "any_of": ["plant", "growth", "grow", "yield"],
        "what_exists": "Comparing fertiliser brands or doses on bean or radish seedlings is a standard entry.",
    },
    {
        "key": "paper_towel",
        "must": ["paper towel"],
        "any_of": ["absorb", "strong", "brand", "hold"],
        "what_exists": "Paper-towel absorbency brand comparisons are a canonical product-testing project.",
    },
    {
        "key": "battery_brand",
        "must": ["batter"],
        "any_of": ["brand", "last", "duracell", "energizer", "cheap"],
        "what_exists": "Battery brand endurance tests are common and largely reproduce manufacturer data.",
    },
    {
        "key": "mentos",
        "must": ["mentos"],
        "any_of": ["coke", "soda", "cola", "eruption", "fountain"],
        "what_exists": "The Mentos-and-soda geyser is a demonstration of nucleation rather than an open question.",
    },
    {
        "key": "bread_mold",
        "must": ["mold"],
        "any_of": ["bread", "food", "fruit", "grow"],
        "what_exists": "Mould growth on bread under different conditions is a very frequent microbiology entry.",
    },
    {
        "key": "sanitizer",
        "must": ["bacteria"],
        "any_of": ["hand sanitizer", "soap", "cleaner", "disinfectant", "germs"],
        "what_exists": "Comparing cleaning products against bacterial growth on agar is widespread.",
    },
    {
        "key": "screen_reaction",
        "must": ["reaction time"],
        "any_of": ["video game", "screen", "gamer", "phone", "caffeine"],
        "what_exists": "Reaction-time comparisons between gamers and non-gamers are a frequent behavioural entry.",
    },
    {
        "key": "sleep_performance",
        "must": ["sleep"],
        "any_of": ["memory", "grades", "test", "performance", "concentration"],
        "what_exists": "Self-reported sleep versus academic performance is common and usually correlational only.",
    },
    {
        "key": "insulation",
        "must": ["insulat"],
        "any_of": ["temperature", "cooler", "warm", "heat loss", "thermos"],
        "what_exists": "Comparing insulating materials on a cup of hot water is a standard physics entry.",
    },
    {
        "key": "solar_angle",
        "must": ["solar panel"],
        "any_of": ["angle", "tilt", "orientation", "voltage", "efficiency"],
        "what_exists": "Panel tilt versus output reproduces a well-characterised cosine relationship.",
    },
    {
        "key": "structure_strength",
        "must": ["bridge"],
        "any_of": ["popsicle", "spaghetti", "straw", "weight", "load", "strength"],
        "what_exists": "Model bridge load tests are a common engineering entry with well-known truss results.",
    },
    {
        "key": "crystals",
        "must": ["crystal"],
        "any_of": ["grow", "sugar", "salt", "borax", "size"],
        "what_exists": "Crystal growth under varying temperature or solute is a frequent chemistry entry.",
    },
    {
        "key": "acid_rain",
        "must": ["acid rain"],
        "any_of": ["plant", "seed", "growth", "ph", "marble"],
        "what_exists": "Simulated acid rain on seedlings appears regularly and rarely uses realistic pH ranges.",
    },
    {
        "key": "water_filter",
        "must": ["water"],
        "any_of": ["filter", "filtration", "purif", "charcoal", "sand filter"],
        "what_exists": "DIY multi-layer water filters are a common engineering entry judged mostly on turbidity.",
    },
    {
        "key": "egg_drop",
        "must": ["egg drop"],
        "any_of": ["protect", "container", "height", "crack"],
        "what_exists": "Egg-drop protection is a classroom design challenge more than a research project.",
    },
    {
        "key": "benchmark_ml",
        "must": ["neural network"],
        "any_of": ["mnist", "cifar", "iris", "titanic", "handwritten digit", "image classif"],
        "what_exists": (
            "Training a standard architecture on a benchmark dataset reproduces published baselines; "
            "judges will ask what question the model answers rather than what accuracy it reached."
        ),
    },
    {
        "key": "sentiment",
        "must": ["sentiment analysis"],
        "any_of": ["tweet", "twitter", "review", "movie", "reddit"],
        "what_exists": "Off-the-shelf sentiment classification of social media text is a very common CS entry.",
    },
    {
        "key": "caffeine_hr",
        "must": ["caffeine"],
        "any_of": ["heart rate", "daphnia", "pulse", "bpm"],
        "what_exists": "Caffeine and heart rate, including the daphnia version, is a standard biology entry.",
    },
]

# Axes along which a project can be meaningfully differentiated (section 5).
DIFFERENTIATION_AXES: list[dict] = [
    {"key": "population", "label": "Different population or system", "terms": ["population", "species", "strain", "age group", "cohort", "cultivar", "demographic"]},
    {"key": "condition", "label": "New environmental condition", "terms": ["temperature", "humidity", "altitude", "salinity", "ph", "pressure", "drought", "light cycle", "microgravity"]},
    {"key": "method", "label": "New algorithm, model or method", "terms": ["algorithm", "model", "architecture", "transformer", "autoencoder", "regression model", "simulation", "novel method", "pipeline"]},
    {"key": "material", "label": "Different material", "terms": ["material", "alloy", "polymer", "composite", "coating", "substrate", "biochar"]},
    {"key": "multivariable", "label": "Multi-variable comparison", "terms": ["interaction", "two variables", "factorial", "combined effect", "both", "multiple variables"]},
    {"key": "dataset", "label": "New dataset", "terms": ["dataset", "database", "records", "satellite", "sensor data", "open data", "corpus"]},
    {"key": "measurement", "label": "New measurement method", "terms": ["spectromet", "sensor", "image analysis", "microscop", "assay", "instrument", "colorimet", "titrat"]},
    {"key": "longitudinal", "label": "Longitudinal testing", "terms": ["over weeks", "over months", "longitudinal", "repeated measure", "time series", "long-term"]},
    {"key": "combination", "label": "Combining two separate approaches", "terms": ["combining", "combined with", "integrat", "hybrid", "coupling", "together with"]},
    {"key": "mechanism", "label": "Testing an unexplored mechanism", "terms": ["mechanism", "why it happens", "underlying cause", "pathway", "explanation for"]},
]

GAP_LANGUAGE = ("has not been", "no study", "gap", "unexplored", "little research", "not been tested", "unknown whether")

STATUS_HEADLINES = {
    NoveltyStatus.LIKELY_COMMON: "This is one of the most frequently entered project types.",
    NoveltyStatus.INCREMENTAL: "A familiar project with one small change on top.",
    NoveltyStatus.MODERATELY_DIFFERENTIATED: "Recognisable territory, but you have changed enough to have your own angle.",
    NoveltyStatus.POTENTIALLY_NOVEL: "This may be genuinely uncommon, pending a real literature check.",
    NoveltyStatus.STRONG_RESEARCH_GAP: "You have articulated a specific gap and a specific way to address it.",
    NoveltyStatus.INSUFFICIENT_EVIDENCE: "There is not yet enough detail here to judge originality.",
}


def _matched_archetypes(text: str) -> list[dict]:
    lower = text.lower()
    hits = []
    for arch in COMMON_ARCHETYPES:
        if all(m in lower for m in arch["must"]) and any(a in lower for a in arch["any_of"]):
            hits.append(arch)
    return hits


def _matched_axes(text: str) -> list[dict]:
    lower = text.lower()
    return [ax for ax in DIFFERENTIATION_AXES if any(t in lower for t in ax["terms"])]


def analyse(signals: ProjectSignals, literature_sources: list[str] | None = None) -> NoveltyAnalysis:
    haystack = signals.any_text()
    archetypes = _matched_archetypes(haystack)
    axes = _matched_axes(" ".join([signals.get("differentiator"), signals.get("existing_weaknesses"), signals.question, signals.topic]))
    all_axes = _matched_axes(haystack)
    gap_stated = any(g in haystack.lower() for g in GAP_LANGUAGE)
    sources = literature_sources or []
    searched = bool(literature_sources)

    differentiator = signals.differentiator_stated
    grounded = signals.literature_grounded
    axis_count = len(axes) if axes else len(all_axes) // 2

    # --- tiering ---------------------------------------------------------- #
    if signals.completeness < 30 and not differentiator:
        status = NoveltyStatus.INSUFFICIENT_EVIDENCE
    elif archetypes and not differentiator:
        status = NoveltyStatus.LIKELY_COMMON
    elif archetypes and axis_count <= 1:
        status = NoveltyStatus.INCREMENTAL
    elif axis_count >= 3 and grounded and gap_stated:
        status = NoveltyStatus.STRONG_RESEARCH_GAP if searched else NoveltyStatus.POTENTIALLY_NOVEL
    elif axis_count >= 2 and (grounded or differentiator):
        status = NoveltyStatus.MODERATELY_DIFFERENTIATED
    elif differentiator:
        status = NoveltyStatus.INCREMENTAL
    else:
        status = NoveltyStatus.INSUFFICIENT_EVIDENCE

    # Ceiling: without a real literature check we cannot award the top tier.
    if not searched and status == NoveltyStatus.STRONG_RESEARCH_GAP:
        status = NoveltyStatus.POTENTIALLY_NOVEL

    similar = [a["what_exists"] for a in archetypes]
    if not similar:
        similar = [
            "No match against the app's list of frequently entered project archetypes. That is a "
            "weak signal, not a clean bill of health — the list is short and your description is brief."
        ]

    whats_different: list[str] = []
    for ax in axes or all_axes[:3]:
        whats_different.append(f"{ax['label']}: your description touches this axis.")
    if differentiator:
        whats_different.insert(0, f"You stated the difference yourself: {signals.get('differentiator')[:220]}")
    if not whats_different:
        whats_different = ["Nothing in the project description yet separates this from the standard version."]

    risks: list[str] = []
    if archetypes:
        risks.append(
            "A judge who has seen this project before will start from scepticism. You will spend "
            "your interview justifying why it was worth redoing."
        )
    if not grounded:
        risks.append(
            "With no background sources cited, you cannot show that the answer is not already known, "
            "which is the specific thing creativity points reward."
        )
    if signals.question_analysis.vague_verbs and not signals.quantitative_outcome:
        risks.append(
            "A broadly phrased question reads as a topic rather than a gap, which judges tend to "
            "score as derivative even when the execution is good."
        )
    if not risks:
        risks.append("Main risk is scope: differentiated projects are easy to under-execute.")

    used_axes = {a["key"] for a in axes}
    ways = [
        f"{ax['label']} — {_axis_prompt(ax['key'], signals)}"
        for ax in DIFFERENTIATION_AXES
        if ax["key"] not in used_axes
    ][:6]

    evidence_note = (
        "Based on a real literature search."
        if searched
        else (
            "No literature search was performed. This assessment compares your description against a "
            "built-in list of common science-fair archetypes only. Before claiming originality, search "
            "Google Scholar and PubMed yourself and record what you find."
        )
    )

    return NoveltyAnalysis(
        status=status,
        confidence="low" if not searched else "moderate",
        headline=STATUS_HEADLINES[status],
        similar_existing_ideas=similar,
        whats_different=whats_different,
        novelty_risks=risks,
        ways_to_increase=ways,
        literature_search_performed=searched,
        sources=sources,
        evidence_note=evidence_note,
    )


def _axis_prompt(key: str, signals: ProjectSignals) -> str:
    population = signals.get("population") or "your current system"
    prompts = {
        "population": f"run the same comparison on a population nobody bothers with instead of {population[:60] or 'the obvious one'}.",
        "condition": "hold your main variable fixed and vary a background condition (temperature, pH, light cycle) that the standard version ignores.",
        "method": "replace the off-the-shelf method with one you build or tune, and report what the change buys you.",
        "material": "swap the material for one with a different structure, then explain the difference from that structure.",
        "multivariable": "test two variables together and look for interaction, not just two separate effects.",
        "dataset": "bring in a public dataset that nobody in your category is using and state why it is the right one.",
        "measurement": "measure the outcome a more precise way — an instrument reading instead of a visual score.",
        "longitudinal": "extend the observation window so you capture a trend rather than a single endpoint.",
        "combination": "join two approaches that are usually studied separately and test whether the combination behaves additively.",
        "mechanism": "stop at the effect and design a second experiment that discriminates between two explanations for it.",
    }
    return prompts.get(key, "")


NOVELTY_SCORE_MAP = {
    NoveltyStatus.LIKELY_COMMON: 25,
    NoveltyStatus.INCREMENTAL: 42,
    NoveltyStatus.MODERATELY_DIFFERENTIATED: 62,
    NoveltyStatus.POTENTIALLY_NOVEL: 78,
    NoveltyStatus.STRONG_RESEARCH_GAP: 88,
    NoveltyStatus.INSUFFICIENT_EVIDENCE: 30,
}
