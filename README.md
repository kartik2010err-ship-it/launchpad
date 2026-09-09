# Research Coach

A mentoring tool for a high-school science fair club. It interviews a student
about their idea, scores how ready the research actually is, projects an AzSEF
rubric, checks how novel the idea probably is, rewrites the research question,
builds a plan and a backwards-planned timeline, coaches the poster, and runs a
mock judge interview.

The design constraint that shaped everything: **it never flatters, and it never
pretends to know things it does not know.** A tool that tells a student their
project is great when it is not is worse than no tool, because they find out at
the fair.

---

## Running it

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.seed          # creates the demo data
uvicorn app.main:app --reload

# frontend, in a second terminal
cd frontend
npm install
npm run dev                 # http://localhost:5173, proxies /api to :8000
```

With no `DATABASE_URL` set it uses SQLite, so nothing else needs installing.
For Postgres: `docker compose up db` and point `DATABASE_URL` at it.

Demo logins, password `coach1234` for all of them:

| Account | What it shows |
|---|---|
| `ava@example.edu` | A weak project (score 41) — vague question, no controls, human participants flagged |
| `noah@example.edu` | Competent but unoriginal (73) — good method, novelty is the problem |
| `priya@example.edu` | Sophisticated (79) — factorial design, real differentiation argument |
| `marcus@example.edu` | An engineering project (68) — different rubric path entirely |
| `mentor@example.edu` | The advisor roster across all four |

Tests: `cd backend && python -m pytest`.

---

## Architecture

### Where the intelligence lives

The AI layer is a `ResearchAIProvider` protocol
(`app/services/ai/base.py`) with two implementations:

- **`HeuristicProvider`** (default) — a deterministic engine built from a dozen
  analysis services. No API key, no network, reproducible. A mentor and a
  student looking at the same project see the same numbers, which matters when
  they are arguing about a score.
- **`AnthropicProvider`** — sends structured signals to a model, validates the
  response against the *same* Pydantic schemas, and falls back to the heuristic
  result when validation fails.

Two things are deliberately never delegated to the model: **safety screening**
and **whether a literature search happened**. A hallucinated "no approval
needed" is the single most damaging output this app could produce, so it comes
from explicit rules in `services/safety.py` and nowhere else.

### The pipeline

```
text answers
    ↓  services/signals.py      → ProjectSignals (coverage, units, mechanism,
    ↓                              control, rigour markers, factorial design…)
    ├→ services/interview_bank.py → critiques each answer, picks what to ask next
    ├→ services/scoring.py        → 5 dimensions, weighted overall
    ├→ services/rubric.py         → AzSEF categories with evidence basis
    ├→ services/novelty.py        → tiering against 22 common fair archetypes
    ├→ services/safety.py         → 13 rule categories
    ├→ services/refine.py         → safe / competitive / ambitious rewrites
    ├→ services/plan_builder.py   → 21-field research plan
    ├→ services/poster.py         → sections, layouts, figures, critique
    ├→ services/judging.py        → question bank + escalating mock judge
    └→ services/timeline.py       → backward pass from the fair date
```

`services/project_service.py` is the only place that touches both the ORM and
the services; routes stay thin.

### Design decisions worth knowing about

**The interview is adaptive, not a form.** Each answer is run through a
validator (`interview_bank.py`). A rejected answer goes back on the queue at
higher weight, so the student is re-asked the thing they dodged. "idk" is
caught, and so is a dependent variable with no unit attached.

**Scores are capped by information.** `overall()` applies a ceiling of
`55 + completeness × 0.45`. A project that has answered four questions cannot
score 80, because the engine does not know enough to justify it.

**Every rubric line carries an evidence basis.** `current_evidence`,
`projected_potential`, or `not_yet_assessable`. Execution, Poster and Interview
are worth 55 of the 100 AzSEF points, and before a student has run an
experiment those categories are shown *unscored* rather than as zeros — a zero
would be as misleading as a guess. The UI renders them as a hatched, greyed
gauge so the absence is visible.

**Novelty has a hard ceiling.** No literature search is performed, so the top
tier (`strong_research_gap_potential`) is unreachable and `sources` is always
empty. The tiering is pattern-matching against archetypes that show up at every
fair (music and studying, paper towel brands, Mentos and cola…), and the UI says
so in plain language on the novelty page.

**Timeline plans backwards and admits when it fails.** Phases have dependencies
and minimum durations; experiment hours are computed from trials × minutes;
regulated projects get a mandatory 21-day approval window before any
experimentation task can start. If the arithmetic does not fit before the fair
date, you get a high-severity warning rather than a compressed schedule that
looks achievable.

**Competition requirements are labelled by source.** Nothing in the registry is
loaded from an official document, so every item is tagged
`unverified_competition_item` or `recommended_club_milestone`, and the
`verified_competition_requirement` tag exists but is unused until someone wires
in a real source. The student is told to confirm anything that affects
eligibility.

### Frontend

React + TypeScript + Vite, no UI framework. `src/api/client.ts` is the only
place that knows about HTTP. The visual system treats the app as an instrument:
hairline rules, near-square corners, one deep green accent, a signal palette
reserved for actual signals. Scores render as panel meters with ticks at the
45 and 68 band boundaries rather than progress bars. The single piece of
typographic weight is the student's research question, set large in serif with
its revision lineage beneath it — because watching the question get better is
the thing the whole app is for.

---

## What is not built

Being straight about the edges:

- **No real literature search.** Novelty is archetype matching. Wiring in
  Semantic Scholar or OpenAlex would make the top tier reachable and is the
  single highest-value addition.
- **No official rule data.** The AzSEF and ISEF entries are a plausible
  structure, not scraped from official documents. Everything is labelled
  unverified for exactly this reason.
- **No migrations.** `create_all` on startup. Add Alembic before this holds
  data anyone cares about.
- **Auth is minimal.** PBKDF2 hashing and HMAC-signed tokens from the standard
  library, no refresh tokens, no password reset, no rate limiting.
- **Mentor comments are not threaded** and there are no notifications.
- **Nothing is exportable.** No PDF of the research plan, no poster export.
- The AI project manager (re-planning after a delay) recomputes downstream task
  dates but does not renegotiate scope.

## What this tool cannot do for a student

It cannot tell them whether their project needs SRC or IRB approval, whether
their idea has already been published, or what a judge will actually think.
It can tell them which questions they have not answered, which is most of the
value and all of the honesty.
