"""Rules screening.

Deliberately one-directional. A match raises a *possible* approval requirement;
no combination of non-matches is ever allowed to conclude that a project is
exempt. The app has no authoritative copy of the ISEF rules, so it can flag and
point at the real rulebook, and nothing more.
"""

from __future__ import annotations

import re

from app.schemas.evaluation import SafetyFlag, SafetyScreening

VERIFY_NOTICE = (
    "Possible pre-approval required. Do not begin experimentation until you verify the "
    "applicable AzSEF/ISEF requirements with your teacher, sponsor, SRC or IRB."
)

CLEAR_NOTICE = (
    "This screening found no obvious pre-approval triggers in what you have written so far. "
    "That is not an exemption: Research Coach does not hold the official rulebook, and your "
    "project description is still incomplete. Confirm your classification and required forms "
    "with your sponsor or SRC before you start."
)

# term -> matched with word boundaries, lowercase
RULES: list[dict] = [
    {
        "category": "human_participants",
        "label": "Human participants",
        "terms": [
            "human participant", "participants", "volunteers", "subjects", "students",
            "classmates", "children", "adults", "test subjects", "recruit",
        ],
        "why": (
            "Any data collected from living people — including your friends and classmates — "
            "generally falls under human participants rules and needs review before you start."
        ),
        "paperwork": ["Human Participants form", "Informed consent / assent documents", "IRB review"],
    },
    {
        "category": "surveys",
        "label": "Surveys, questionnaires or interviews",
        "terms": ["survey", "questionnaire", "interview", "poll", "focus group", "google form"],
        "why": (
            "Surveys are human participants research even when they feel casual, and questions "
            "about sensitive topics raise the review level."
        ),
        "paperwork": ["Human Participants form", "Copy of your survey instrument", "IRB review"],
    },
    {
        "category": "medical_data",
        "label": "Medical or personally identifiable information",
        "terms": [
            "medical record", "patient", "diagnosis", "health data", "hipaa", "phi",
            "clinical data", "blood pressure", "heart rate", "bmi", "ekg", "eeg",
        ],
        "why": "Identifiable health information carries privacy obligations on top of the usual review.",
        "paperwork": ["Human Participants form", "Data confidentiality plan", "IRB review"],
    },
    {
        "category": "vertebrates",
        "label": "Vertebrate animals",
        "terms": [
            "mice", "mouse", "rat", "rats", "fish", "zebrafish", "frog", "chicken", "chick",
            "bird", "lizard", "dog", "cat", "rabbit", "vertebrate", "hamster", "guppy", "tadpole",
        ],
        "why": "Vertebrate animal studies have strict housing, welfare and supervision requirements.",
        "paperwork": ["Vertebrate Animal form", "Qualified Scientist form", "SRC review before starting"],
    },
    {
        "category": "biological_agents",
        "label": "Potentially hazardous biological agents",
        "terms": [
            "bacteria", "e. coli", "e.coli", "coli", "culture", "petri", "agar", "mold",
            "fungus", "fungi", "yeast", "virus", "pathogen", "microbe", "microorganism",
            "biofilm", "sourdough starter", "compost",
        ],
        "why": (
            "Culturing microorganisms — even from a kitchen or a pond — is treated as work with "
            "potentially hazardous biological agents and usually needs a BSL-appropriate site."
        ),
        "paperwork": [
            "Potentially Hazardous Biological Agent form",
            "Risk Assessment form",
            "Qualified Scientist / Designated Supervisor",
            "SRC review before starting",
        ],
    },
    {
        "category": "tissue",
        "label": "Human or animal tissue",
        "terms": ["tissue", "blood", "saliva", "cheek cell", "cell line", "serum", "plasma", "bone"],
        "why": "Fresh or frozen tissue, including your own cheek cells, is separately regulated.",
        "paperwork": ["Potentially Hazardous Biological Agent form", "Qualified Scientist form"],
    },
    {
        "category": "rdna",
        "label": "Recombinant DNA or genetic modification",
        "terms": ["recombinant", "plasmid", "crispr", "transformation", "gmo", "gene edit", "transgenic"],
        "why": "rDNA work has its own biosafety level requirements and supervision rules.",
        "paperwork": ["Potentially Hazardous Biological Agent form", "Institutional biosafety review"],
    },
    {
        "category": "drugs",
        "label": "Drugs or controlled substances",
        "terms": [
            "prescription", "medication", "drug", "antibiotic", "caffeine", "nicotine",
            "alcohol", "ethanol", "supplement", "dosage", "controlled substance", "vape",
        ],
        "why": "Administering any substance to a person or animal raises both safety and legal issues.",
        "paperwork": ["Risk Assessment form", "Qualified Scientist form", "SRC review"],
    },
    {
        "category": "chemicals",
        "label": "Hazardous chemicals",
        "terms": [
            "acid", "base", "hydroxide", "solvent", "acetone", "methanol", "chloroform",
            "corrosive", "flammable", "toxic", "carcinogen", "reagent", "bleach", "ammonia",
            "hydrogen peroxide", "nanoparticle",
        ],
        "why": "Chemical work needs a documented risk assessment, SDS review and a supervised site.",
        "paperwork": ["Risk Assessment form", "Safety Data Sheets", "Designated Supervisor"],
    },
    {
        "category": "radiation",
        "label": "Radiation or lasers",
        "terms": ["radiation", "radioactive", "uv light", "ultraviolet", "x-ray", "laser", "gamma", "microwave"],
        "why": "Sources of ionising or high-intensity radiation require supervision and shielding review.",
        "paperwork": ["Risk Assessment form", "Designated Supervisor"],
    },
    {
        "category": "equipment",
        "label": "Dangerous equipment, drones or firearms",
        "terms": [
            "drone", "uav", "firearm", "gun", "projectile", "high voltage", "kv", "furnace",
            "kiln", "table saw", "3d printer", "lithium battery", "combustion", "rocket", "propellant",
        ],
        "why": "Powered, pressurised or airborne equipment needs a supervised setup and may need FAA or local clearance.",
        "paperwork": ["Risk Assessment form", "Designated Supervisor"],
    },
    {
        "category": "data_privacy",
        "label": "Pre-existing datasets about people",
        "terms": ["dataset of", "public dataset", "scraped", "social media data", "user data", "kaggle"],
        "why": (
            "Analysis of existing human data can still count as human participants research "
            "depending on whether the data are public and de-identified."
        ),
        "paperwork": ["Human Participants form (may be waived — confirm)", "Documentation of data source"],
    },
]


def _match_terms(text: str, terms: list[str]) -> list[str]:
    found = []
    for term in terms:
        pattern = re.escape(term).replace(r"\ ", r"\s+")
        if re.search(rf"(?<!\w){pattern}(?!\w)", text):
            found.append(term)
    return found


def screen(text: str) -> SafetyScreening:
    haystack = (text or "").lower()
    flags: list[SafetyFlag] = []

    for rule in RULES:
        matched = _match_terms(haystack, rule["terms"])
        if matched:
            flags.append(
                SafetyFlag(
                    category=rule["category"],
                    label=rule["label"],
                    matched_terms=sorted(set(matched))[:6],
                    why_it_matters=rule["why"],
                    likely_paperwork=rule["paperwork"],
                )
            )

    return SafetyScreening(
        flags=flags,
        preapproval_possible=bool(flags),
        determination_made=False,
        notice=VERIFY_NOTICE if flags else CLEAR_NOTICE,
    )
