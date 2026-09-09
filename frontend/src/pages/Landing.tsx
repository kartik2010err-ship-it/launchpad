import { useNavigate } from "react-router-dom";
import { Gauge, Pill } from "../components/ui";
import { Meter, Stat, StatusPill } from "../components/workspace-ui";

/**
 * The signed-out home page. Reuses the real Gauge/Meter/StatusPill/Stat
 * components for the previews below rather than screenshots, so the mockups
 * never drift out of sync with what the product actually looks like.
 */
export default function Landing() {
  const navigate = useNavigate();
  const go = (path: string) => () => navigate(path);

  return (
    <div className="landing">
      <nav className="landing__nav">
        <div className="landing__nav-inner">
          <a href="#top" className="landing__mark">
            Research Coach
          </a>
          <div className="landing__nav-links">
            <a href="#how-it-works">Features</a>
            <a href="#for-students">For Students</a>
            <a href="#for-clubs">For Schools &amp; Clubs</a>
          </div>
          <div className="landing__nav-actions">
            <button className="btn btn--quiet btn--small" onClick={go("/sign-in")}>
              Sign In
            </button>
            <button className="btn btn--small" onClick={go("/sign-in?mode=up")}>
              Get Started
            </button>
          </div>
        </div>
      </nav>

      {/* -------------------------------------------------------------- hero */}
      <header id="top" className="landing__section">
        <div className="landing__hero">
          <div>
            <span className="landing__kicker">Research mentoring, not answer generation</span>
            <h1 className="landing__h1">
              Turn a research idea into a competition-ready project.
            </h1>
            <p className="landing__lede">
              Plan, evaluate, manage, and improve science fair projects with AI-powered
              research coaching, competition timelines, rubric feedback, poster guidance,
              and collaborative workspaces.
            </p>
            <div className="landing__cta-row">
              <button className="btn btn--lg" onClick={go("/sign-in?mode=up&intent=project")}>
                Start a Project
              </button>
              <button className="btn btn--lg btn--ghost" onClick={go("/sign-in?mode=up&intent=workspace")}>
                Create a Workspace
              </button>
            </div>
            <p className="landing__fineprint">
              Free to start. No credit card. Works for a single student or an entire club.
            </p>
          </div>

          <div>
            <div className="mock-window">
              <div className="mock-window__bar">
                <span className="mock-window__dot" />
                <span className="mock-window__dot" />
                <span className="mock-window__dot" />
                <span className="mock-window__title">research-coach — readiness</span>
              </div>
              <div className="mock-window__body">
                <div className="row" style={{ justifyContent: "space-between", marginBottom: "0.6rem" }}>
                  <strong style={{ fontSize: "0.86rem" }}>Coral bleaching signatures</strong>
                  <StatusPill status="needs_attention" />
                </div>
                <Gauge label="Research question" value={71} animate={false} />
                <div style={{ height: 10 }} />
                <Gauge label="Methodology" value={64} animate={false} />
                <div style={{ height: 10 }} />
                <Gauge
                  label="Poster"
                  value={0}
                  basis="not_yet_assessable"
                  animate={false}
                />
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* -------------------------------------------------------- how it works */}
      <section id="how-it-works" className="landing__section landing__section--sunk">
        <span className="landing__kicker">How it works</span>
        <h2 style={{ marginBottom: "2.2rem", maxWidth: "36ch" }}>
          Four stages, the same ones a good mentor would walk you through.
        </h2>
        <div className="steps">
          <div className="step">
            <span className="step__num">01</span>
            <div className="step__title">Start with an idea</div>
            <p className="step__text">
              Enter a research question or engineering problem — rough is fine. An
              adaptive interview turns it into something testable.
            </p>
          </div>
          <div className="step">
            <span className="step__num">02</span>
            <div className="step__title">Improve your project</div>
            <p className="step__text">
              Get targeted follow-up questions, a novelty check against common fair
              archetypes, and methodology feedback graded against real rubric criteria.
            </p>
          </div>
          <div className="step">
            <span className="step__num">03</span>
            <div className="step__title">Build a plan</div>
            <p className="step__text">
              Generate a competition-aware timeline, milestone by milestone, plus a
              forms checklist and a full research plan draft.
            </p>
          </div>
          <div className="step">
            <span className="step__num">04</span>
            <div className="step__title">Prepare to compete</div>
            <p className="step__text">
              Get poster layout guidance, graph recommendations, a mock judge
              interview, and interview-readiness coaching.
            </p>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------ students */}
      <section id="for-students" className="landing__section">
        <div className="feature-split">
          <div>
            <span className="landing__kicker">For students</span>
            <h2 style={{ marginBottom: "0.8rem" }}>
              A mentor that pushes back, on your own schedule.
            </h2>
            <p style={{ color: "var(--ink-soft)", maxWidth: "44ch" }}>
              The tool never tells you a weak project is great. It shows you exactly
              where the gaps are and what a judge would ask.
            </p>
            <ul className="feature-list">
              <li>Research question coaching, with a full revision history</li>
              <li>Novelty analysis against common fair archetypes</li>
              <li>AzSEF-style rubric feedback, scored line by line</li>
              <li>Competition-aware timeline planning</li>
              <li>Experiment and research notebook tracking</li>
              <li>Poster layout and section-by-section support</li>
              <li>Judge interview practice with a mock interviewer</li>
            </ul>
          </div>
          <div className="feature-split__art">
            <div className="feature-art-card">
              <div className="row" style={{ justifyContent: "space-between", marginBottom: "0.7rem" }}>
                <span className="faint">Novelty check</span>
                <Pill tone="warn">Incremental</Pill>
              </div>
              <p style={{ fontSize: "0.9rem", marginBottom: "0.9rem" }}>
                This is a well-executed version of a common project type. A judge who
                has seen this before will ask what makes your angle different.
              </p>
              <div className="row" style={{ justifyContent: "space-between", marginBottom: "0.5rem" }}>
                <span className="faint">Methodology</span>
              </div>
              <Meter percent={64} />
              <div className="row" style={{ justifyContent: "space-between", marginTop: "0.7rem" }}>
                <span className="faint">Feasibility</span>
              </div>
              <Meter percent={82} />
            </div>
          </div>
        </div>
      </section>

      {/* --------------------------------------------------------------- clubs */}
      <section id="for-clubs" className="landing__section landing__section--sunk">
        <div className="feature-split is-reversed">
          <div className="feature-split__art">
            <div className="feature-art-card">
              <div className="mock-stat-row">
                <Stat value={18} label="Active projects" tone="accent" />
                <Stat value={12} label="On track" tone="ok" />
                <Stat value={4} label="Need attention" tone="attention" />
                <Stat value={2} label="Deadlines near" tone="risk" />
              </div>
              <div className="mock-row">
                <div className="mock-row__name">
                  <div className="mock-row__title">Maya Patel — Coral bleaching signatures</div>
                  <div className="mock-row__sub">Environmental science · AzSEF</div>
                </div>
                <div className="mock-row__meter">
                  <Meter percent={71} />
                </div>
                <StatusPill status="on_track" />
              </div>
              <div className="mock-row">
                <div className="mock-row__name">
                  <div className="mock-row__title">Daniel Okafor — Battery efficiency</div>
                  <div className="mock-row__sub">Physics · AzSEF</div>
                </div>
                <div className="mock-row__meter">
                  <Meter percent={58} />
                </div>
                <StatusPill status="at_risk" />
              </div>
              <div className="mock-row">
                <div className="mock-row__name">
                  <div className="mock-row__title">Sarah Kim — Ceramic water filtration</div>
                  <div className="mock-row__sub">Engineering · AzSEF</div>
                </div>
                <div className="mock-row__meter">
                  <Meter percent={48} />
                </div>
                <StatusPill status="blocked" />
              </div>
            </div>
          </div>
          <div>
            <span className="landing__kicker">For clubs, schools &amp; mentors</span>
            <h2 style={{ marginBottom: "0.8rem" }}>
              One place to see every project in your club.
            </h2>
            <p style={{ color: "var(--ink-soft)", maxWidth: "44ch" }}>
              Create a workspace for a school, class, club, or competition team.
              Authority lives with the workspace, not the person — the same student
              can lead one team and just be a member of another.
            </p>
            <ul className="feature-list">
              <li>Create a school, class, club, or research workspace</li>
              <li>Invite students and mentors by link or join code</li>
              <li>See every project's status, readiness and stage in one table</li>
              <li>Get an attention queue: who is behind, blocked, or quiet</li>
              <li>Leave feedback directly on a project without logging in as the student</li>
              <li>Assign mentors and track their workload</li>
              <li>Watch readiness trend across the whole group before a deadline</li>
            </ul>
          </div>
        </div>
      </section>

      {/* --------------------------------------------------------- competitions */}
      <section className="landing__section landing__section--tight">
        <span className="landing__kicker">Competition support</span>
        <h2 style={{ marginBottom: "0.7rem", maxWidth: "38ch" }}>
          Built around how fairs like AzSEF actually score projects.
        </h2>
        <p style={{ color: "var(--ink-soft)", maxWidth: "58ch" }}>
          Timelines, milestone checklists, and rubric projections are structured around
          common science-fair formats such as AzSEF and ISEF-style judging criteria,
          so the work you do here maps onto what a judge will actually ask.
        </p>
        <p className="disclaimer-note">
          Research Coach is an independent planning and coaching tool. It is not
          affiliated with, endorsed by, or officially connected to AzSEF, ISEF, or any
          competition organizer. Always confirm requirements against your fair's
          official rules.
        </p>
      </section>

      {/* -------------------------------------------------------------- final */}
      <section className="landing__final">
        <h2>Ready to start your research project?</h2>
        <p>
          Bring a rough idea or a half-finished draft. The first thing this tool does
          is interview you about it.
        </p>
        <div className="landing__cta-row">
          <button className="btn btn--lg" onClick={go("/sign-in?mode=up&intent=project")}>
            Start a Project
          </button>
          <button className="btn btn--lg btn--ghost" onClick={go("/sign-in?mode=up&intent=workspace")}>
            Create a Workspace
          </button>
        </div>
      </section>

      <footer className="landing__footer">
        Research Coach — a research mentoring tool. Not affiliated with AzSEF or ISEF.
      </footer>
    </div>
  );
}
