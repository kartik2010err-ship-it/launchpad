/*
  The logged-in home (sections 34-35).

  Four questions, in this order: what am I working on, what should I do next,
  what needs attention, what is coming up. The discipline is subtraction — a
  student who opens this and sees twelve cards learns nothing, so exactly one
  thing on this page is large and everything else is quiet.

  "What should I do next" comes from the same service the Research Assistant
  uses, so the two surfaces can never give contradictory advice.
*/

import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../api/useAsync";
import { useAuth } from "../state/auth";
import { useWorkspace } from "../state/workspace";
import AppRail from "../components/AppRail";
import { Card, ErrorNote, Loading, Pill, humanise } from "../components/ui";
import { StatusPill } from "../components/workspace-ui";

function firstName(name: string | undefined): string {
  return (name ?? "").split(" ")[0] || "there";
}

export default function Home() {
  const { user } = useAuth();
  const { current } = useWorkspace();
  const navigate = useNavigate();
  const { data, error, loading } = useAsync(() => api.homeDashboard(), []);

  return (
    <div className="shell">
      <AppRail />
      <main className="main">
        <div className="main__inner stack">
          <header className="page-head">
            <div className="row row--between">
              <div>
                <h1>Good to see you, {firstName(user?.name)}</h1>
                <p>{current ? `Working in ${current.name}.` : "Pick a workspace to get started."}</p>
              </div>
              <button className="btn btn--small" onClick={() => navigate("/projects/new")}>
                Start a project
              </button>
            </div>
          </header>

          {loading && <Loading what="Loading your work" />}
          {error && <ErrorNote message={error} />}

          {data && !data.has_project && (
            <Card sunk>
              <h3>No project yet</h3>
              <p className="muted">
                Start one and this page becomes useful: what you are working on, what to do
                next, and what is coming up.
              </p>
              <button className="btn btn--small" onClick={() => navigate("/projects/new")}>
                Start a project
              </button>
            </Card>
          )}

          {data?.project && (
            <>
              {/* 1. What am I working on? */}
              <Card
                title={data.project.title}
                aside={
                  <div className="row gap-2">
                    {data.project.is_team_project && <Pill tone="neutral">Team project</Pill>}
                    <StatusPill status={data.project.status} />
                  </div>
                }
              >
                <p className="home__question">{data.project.question}</p>

                <div className="home__stats">
                  <Stat label="Stage" value={humanise(data.project.stage)} />
                  <Stat
                    label="Readiness"
                    value={
                      data.project.readiness === null ? "Not scored yet" : `${data.project.readiness}%`
                    }
                  />
                  <Stat
                    label="Interview"
                    value={
                      data.project.information_completeness === null
                        ? "—"
                        : `${data.project.information_completeness}% answered`
                    }
                  />
                  {data.project.competition && (
                    <Stat label="Competition" value={data.project.competition} />
                  )}
                </div>

                <div className="row gap-2 row--wrap">
                  <Link className="btn btn--small" to={`/projects/${data.project.id}`}>
                    Open project
                  </Link>
                  <Link
                    className="btn btn--quiet btn--small"
                    to={`/projects/${data.project.id}/assistant`}
                  >
                    Ask the Assistant
                  </Link>
                </div>
              </Card>

              {/* 2. What should I do next? The one large thing on this page. */}
              <section className="home__next">
                <span className="home__next-label">What should I do next?</span>
                <h2>{data.next_action.primary.action}</h2>
                <p>{data.next_action.primary.why}</p>

                {data.next_action.primary.guide_ids.length > 0 && (
                  <div className="row gap-2 row--wrap">
                    {data.next_action.primary.guide_ids.map((id) => (
                      <Link className="btn btn--ghost btn--small" key={id} to={`/library/${id}`}>
                        Read: {humanise(id.replace(/-/g, " "))}
                      </Link>
                    ))}
                  </div>
                )}

                {data.next_action.secondary.length > 0 && (
                  <div className="home__then">
                    <span className="faint">After that</span>
                    <ul className="tight-list">
                      {data.next_action.secondary.map((item) => (
                        <li key={item.action}>{item.action}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </section>

              <div className="grid-2">
                {/* 3. What needs attention? */}
                <Card title="Needs attention" sunk>
                  {data.attention.length === 0 ? (
                    <p className="muted">Nothing flagged. That is a good place to be.</p>
                  ) : (
                    <ul className="home__attention">
                      {data.attention.map((item) => (
                        <li key={item.label}>
                          <Pill
                            tone={
                              item.kind === "safety"
                                ? "flag"
                                : item.kind === "overdue"
                                  ? "warn"
                                  : "neutral"
                            }
                          >
                            {humanise(item.kind)}
                          </Pill>
                          <span>
                            <strong>{item.label}</strong>
                            <span className="faint"> {item.detail}</span>
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </Card>

                {/* 4. What is coming up? */}
                <Card title="Coming up" sunk>
                  {data.upcoming.length === 0 ? (
                    <p className="muted">Nothing due in the next two weeks.</p>
                  ) : (
                    <ul className="home__upcoming">
                      {data.upcoming.map((item) => (
                        <li key={`${item.title}-${item.due_date}`}>
                          <span className="home__days">{item.days_away}d</span>
                          <span>
                            <strong>{item.title}</strong>
                            <span className="faint"> · {item.due_date}</span>
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </Card>
              </div>

              {(data.suggested_guides.length > 0 || data.similar_historical_count > 0) && (
                <div className="grid-2">
                  {data.suggested_guides.length > 0 && (
                    <Card title="Worth reading now" sunk>
                      <ul className="tight-list">
                        {data.suggested_guides.map((guide) => (
                          <li key={guide.guide_id}>
                            <Link to={`/library/${guide.guide_id}`}>{guide.title}</Link>
                            <span className="faint"> · {guide.read_minutes} min</span>
                          </li>
                        ))}
                      </ul>
                    </Card>
                  )}

                  {data.similar_historical_count > 0 && (
                    <Card title="Related previous research" sunk>
                      <p className="muted">
                        {data.similar_historical_count} project
                        {data.similar_historical_count === 1 ? "" : "s"} in the catalogue look
                        related to yours.
                      </p>
                      <Link className="btn btn--quiet btn--small" to="/isef">
                        Open the explorer
                      </Link>
                    </Card>
                  )}
                </div>
              )}

              {data.other_projects.length > 0 && (
                <Card title="Your other projects" sunk>
                  <ul className="home__others">
                    {data.other_projects.map((project) => (
                      <li key={project.id}>
                        <Link to={`/projects/${project.id}`}>{project.title}</Link>
                        <span className="faint">{humanise(project.stage)}</span>
                      </li>
                    ))}
                  </ul>
                </Card>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="home__stat">
      <span className="faint">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
