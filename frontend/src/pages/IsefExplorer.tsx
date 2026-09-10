/*
  ISEF Project Explorer (sections 22-25, 30).

  The design problem this page solves is credibility. A student looking at a
  historical project needs to know, without thinking about it, which sentences
  the fair published and which the app inferred. So source information and AI
  analysis are never interleaved: they are separate blocks, separately headed,
  and the AI block is visually quieter than the record it is commenting on.

  The empty state matters as much as the populated one. This catalogue is empty
  until someone imports data they are permitted to store, and saying that
  plainly is better than a page that looks broken.
*/

import { useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../api/useAsync";
import AppRail from "../components/AppRail";
import { Callout, Card, ErrorNote, Loading, Pill } from "../components/ui";
import type { HistoricalProjectCard } from "../api/types";

const PAGE = 24;

function ProjectCard({ project }: { project: HistoricalProjectCard }) {
  return (
    <Link
      to={`/isef/${project.id}`}
      className="isef-card plain-link"
    >
      <div className="isef-card__head">
        <h3>{project.title}</h3>
        {project.awards ? <Pill tone="ok">Awarded</Pill> : null}
      </div>
      <div className="isef-card__meta">
        {project.year ? <span>{project.year}</span> : null}
        {project.category ? <span>{project.category}</span> : null}
        {project.team_project !== null ? (
          <span>{project.team_project ? "Team" : "Individual"}</span>
        ) : null}
        {!project.has_abstract ? <span className="faint">No abstract on record</span> : null}
      </div>
      {project.derived_tags.length > 0 ? (
        <div className="isef-card__tags">
          {project.derived_tags.slice(0, 3).map((tag) => (
            <Pill key={tag} tone="neutral">
              {tag}
            </Pill>
          ))}
        </div>
      ) : null}
    </Link>
  );
}

export default function IsefExplorer() {
  const [params, setParams] = useSearchParams();
  const [draft, setDraft] = useState(params.get("q") ?? "");
  const [offset, setOffset] = useState(0);

  const query = {
    q: params.get("q") ?? undefined,
    category: params.get("category") ?? undefined,
    year: params.get("year") ?? undefined,
    tag: params.get("tag") ?? undefined,
    team: params.get("team") ?? undefined,
    awarded: params.get("awarded") === "1" || undefined,
    limit: PAGE,
    offset,
  };
  const key = JSON.stringify(query);

  const { data, error, loading } = useAsync(() => api.historicalProjects(query), [key]);
  const { data: facets } = useAsync(() => api.historicalFacets(), []);

  function setFilter(name: string, value: string | null) {
    const next = new URLSearchParams(params);
    if (value === null || value === "") next.delete(name);
    else next.set(name, value);
    setParams(next);
    setOffset(0);
  }

  const active = useMemo(
    () => ["q", "category", "year", "tag", "team", "awarded"].filter((k) => params.get(k)),
    [params],
  );

  return (
    <div className="shell">
      <AppRail subtitle="ISEF Project Explorer" />
      <main className="main">
        <div className="main__inner stack">
          <header className="page-head">
            <h1>Explore previous ISEF research</h1>
            <p>
              Read past projects to understand what research quality, methodology and
              presentation actually look like at this level.
            </p>
          </header>

          <Callout tone="note">
            <p>
              Use previous projects to understand research quality, methodology and
              presentation — not to copy another student's research.
            </p>
          </Callout>

          <form
            className="row gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              setFilter("q", draft.trim() || null);
            }}
          >
            <input
              className="input"
              style={{ flex: 1 }}
              placeholder="Search projects, topics, methods…"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              aria-label="Search the catalogue"
            />
            <button className="btn" type="submit">
              Search
            </button>
          </form>

          {facets && facets.total > 0 ? (
            <div className="isef-filters">
              <select
                className="input"
                value={params.get("category") ?? ""}
                onChange={(e) => setFilter("category", e.target.value || null)}
                aria-label="Category"
              >
                <option value="">All categories</option>
                {facets.categories.map((row) => (
                  <option key={String(row.value)} value={String(row.value)}>
                    {row.value} ({row.count})
                  </option>
                ))}
              </select>

              <select
                className="input"
                value={params.get("year") ?? ""}
                onChange={(e) => setFilter("year", e.target.value || null)}
                aria-label="Year"
              >
                <option value="">All years</option>
                {facets.years.map((row) => (
                  <option key={String(row.value)} value={String(row.value)}>
                    {row.value} ({row.count})
                  </option>
                ))}
              </select>

              <select
                className="input"
                value={params.get("tag") ?? ""}
                onChange={(e) => setFilter("tag", e.target.value || null)}
                aria-label="Research area"
              >
                <option value="">All research areas</option>
                {facets.derived_tags.map((row) => (
                  <option key={String(row.value)} value={String(row.value)}>
                    {row.value} ({row.count})
                  </option>
                ))}
              </select>

              <select
                className="input"
                value={params.get("team") ?? ""}
                onChange={(e) => setFilter("team", e.target.value || null)}
                aria-label="Team or individual"
              >
                <option value="">Team and individual</option>
                <option value="true">Team projects</option>
                <option value="false">Individual projects</option>
              </select>

              <label className="row gap-2">
                <input
                  type="checkbox"
                  checked={params.get("awarded") === "1"}
                  onChange={(e) => setFilter("awarded", e.target.checked ? "1" : null)}
                />
                <span className="faint">Awarded only ({facets.awarded})</span>
              </label>

              {active.length > 0 ? (
                <button
                  className="btn btn--quiet btn--small"
                  type="button"
                  onClick={() => {
                    setParams(new URLSearchParams());
                    setDraft("");
                    setOffset(0);
                  }}
                >
                  Clear filters
                </button>
              ) : null}
            </div>
          ) : null}

          {loading && <Loading what="Searching the catalogue" />}
          {error && <ErrorNote message={error} />}

          {data && data.total === 0 && active.length === 0 ? (
            <Card sunk>
              <h3>The catalogue is empty</h3>
              <p className="muted">
                No historical projects have been imported yet. This app does not scrape the
                ISEF abstract database: Society for Science's terms forbid automated access
                and forbid storing their material without written permission.
              </p>
              <p className="muted">
                A workspace owner or lead can add projects the club is permitted to store —
                one at a time, or as a CSV — from{" "}
                <Link to="/isef/import">Import projects</Link>.
              </p>
            </Card>
          ) : null}

          {data && data.total === 0 && active.length > 0 ? (
            <Card sunk>
              <h3>Nothing matched those filters</h3>
              <p className="muted">
                Widen the search. Note that an empty result here is not evidence that an idea
                is new — this catalogue holds only what we are permitted to store.
              </p>
            </Card>
          ) : null}

          {data && data.results.length > 0 ? (
            <>
              <div className="section-head">
                <h2>
                  {data.total} project{data.total === 1 ? "" : "s"}
                </h2>
                <span className="faint">
                  Showing {offset + 1}–{Math.min(offset + PAGE, data.total)}
                </span>
              </div>

              <div className="isef-grid">
                {data.results.map((project) => (
                  <ProjectCard key={project.id} project={project} />
                ))}
              </div>

              {data.total > PAGE ? (
                <div className="row gap-2">
                  <button
                    className="btn btn--quiet btn--small"
                    disabled={offset === 0}
                    onClick={() => setOffset(Math.max(0, offset - PAGE))}
                  >
                    Previous
                  </button>
                  <button
                    className="btn btn--quiet btn--small"
                    disabled={offset + PAGE >= data.total}
                    onClick={() => setOffset(offset + PAGE)}
                  >
                    Next
                  </button>
                </div>
              ) : null}
            </>
          ) : null}
        </div>
      </main>
    </div>
  );
}

/* ------------------------------------------------------------------ detail */

export function IsefProjectDetail() {
  const { historicalId } = useParams();
  const id = Number(historicalId);
  const { data, error, loading } = useAsync(() => api.historicalProject(id), [id]);

  return (
    <div className="shell">
      <AppRail subtitle="ISEF Project Explorer" />
      <main className="main">
        <div className="main__inner stack">
          <Link className="faint" to="/isef">
            ← Back to the explorer
          </Link>

          {loading && <Loading what="Loading project" />}
          {error && <ErrorNote message={error} />}

          {data ? (
            <>
              <header className="page-head">
                <h1>{data.source_information.title}</h1>
                <div className="isef-card__meta">
                  {data.source_information.year ? (
                    <span>{data.source_information.year}</span>
                  ) : null}
                  {data.source_information.category ? (
                    <span>{data.source_information.category}</span>
                  ) : null}
                  {data.source_information.team_project !== null ? (
                    <span>
                      {data.source_information.team_project ? "Team project" : "Individual project"}
                    </span>
                  ) : null}
                </div>
              </header>

              <Callout tone="note">
                <p>{data.copying_notice}</p>
              </Callout>

              {/* Everything in this card came from the source, verbatim. */}
              <Card title="Source information">
                <p className="faint mt-0">
                  Published by the fair. Blank fields were not provided by the source and have
                  not been filled in.
                </p>

                <dl className="isef-facts">
                  <Fact label="Category" value={data.source_information.category} />
                  <Fact label="Subcategory" value={data.source_information.subcategory} />
                  <Fact label="Awards" value={data.source_information.awards} />
                  <Fact label="Student(s)" value={data.source_information.student_display} />
                  <Fact label="School" value={data.source_information.school_display} />
                  <Fact
                    label="Location"
                    value={
                      [data.source_information.state, data.source_information.country]
                        .filter(Boolean)
                        .join(", ") || null
                    }
                  />
                  <Fact label="Source" value={data.source_information.source} />
                </dl>

                {data.source_information.abstract ? (
                  <>
                    <h3>Abstract</h3>
                    <p style={{ lineHeight: "var(--line-body)" }}>
                      {data.source_information.abstract}
                    </p>
                  </>
                ) : (
                  <p className="faint">No abstract on record.</p>
                )}

                {data.source_information.source_url ? (
                  <p className="faint">
                    <a href={data.source_information.source_url} target="_blank" rel="noreferrer">
                      Original record ↗
                    </a>
                  </p>
                ) : null}
              </Card>

              {data.derived_tags.length > 0 ? (
                <Card sunk title="Research areas (inferred)">
                  <p className="faint mt-0">
                    These tags were derived by this app from the title and abstract. They are
                    not the competition's official category.
                  </p>
                  <div className="row gap-2 row--wrap">
                    {data.derived_tags.map((tag) => (
                      <Pill key={tag} tone="neutral">
                        {tag}
                      </Pill>
                    ))}
                  </div>
                </Card>
              ) : null}

              {/* Deliberately a separate, quieter block from the record above. */}
              {data.ai_analysis ? (
                <Card sunk title="AI educational breakdown">
                  <p className="faint mt-0">
                    This section is this app's reading of the abstract, not information from
                    the fair. It cannot explain why any project placed — no judge commentary
                    exists in this catalogue.
                  </p>

                  <Section heading="Research question" body={data.ai_analysis.research_question} />
                  <Section heading="Why it matters" body={data.ai_analysis.why_it_matters} />
                  <Section heading="Methodology" body={data.ai_analysis.methodology} />
                  <Section heading="Scientific depth" body={data.ai_analysis.scientific_depth} />
                  <Section heading="Novelty" body={data.ai_analysis.novelty} />
                  <Section heading="Evidence" body={data.ai_analysis.evidence} />

                  {data.ai_analysis.lessons_for_students.length > 0 ? (
                    <>
                      <h3>What another student can learn from this</h3>
                      <ul className="tick-list tick-list--arrow">
                        {data.ai_analysis.lessons_for_students.map((lesson) => (
                          <li key={lesson}>{lesson}</li>
                        ))}
                      </ul>
                    </>
                  ) : null}
                </Card>
              ) : (
                <Card sunk title="AI educational breakdown">
                  <p className="muted">{data.analysis_unavailable_reason}</p>
                </Card>
              )}
            </>
          ) : null}
        </div>
      </main>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string | null }) {
  return (
    <>
      <dt>{label}</dt>
      <dd className={value ? "" : "faint"}>{value ?? "Not provided by the source"}</dd>
    </>
  );
}

function Section({ heading, body }: { heading: string; body: string | null }) {
  if (!body) return null;
  return (
    <>
      <h3>{heading}</h3>
      <p style={{ lineHeight: "var(--line-body)" }}>{body}</p>
    </>
  );
}
