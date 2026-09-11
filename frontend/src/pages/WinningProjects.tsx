import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../api/useAsync";
import { Callout, Card, ErrorNote, Loading, Pill, humanise } from "../components/ui";
import { GlobalShell } from "./ResearchLibrary";
import type { SourceConfidence, WinningProjectSummary } from "../api/types";

/**
 * Winning Projects.
 *
 * This page has one unusual responsibility: it must never let a reader mistake
 * something we wrote for something a competition published. Provenance is shown
 * on every field rather than summarised once at the top, and the app ships with
 * no real winners loaded — so the empty state has to explain itself properly
 * instead of looking broken.
 */

const PROVENANCE_LABEL: Record<SourceConfidence, string> = {
  verified_source: "From the source",
  unverified: "Unverified",
  ai_analysis: "Research Coach analysis",
  not_available: "Not in the source",
};

function Provenance({ value }: { value: SourceConfidence }) {
  return <span className={`prov prov--${value}`}>{PROVENANCE_LABEL[value]}</span>;
}

function ProjectCard({ project }: { project: WinningProjectSummary }) {
  return (
    <Link className="guide-card" to={`/winning-projects/${project.id}`}>
      <div className="guide-card__meta">
        <span>{humanise(project.category)}</span>
        <span>·</span>
        <span>{project.is_team ? `Team of ${project.team_size ?? "?"}` : "Individual"}</span>
        {project.year && (
          <>
            <span>·</span>
            <span>{project.year}</span>
          </>
        )}
      </div>
      <div className="guide-card__title">{project.title}</div>
      <div className="guide-card__summary">
        {project.competition_name ?? project.source_name}
      </div>
      <div className="mt-2">
        {project.is_illustrative ? (
          <Pill tone="warn">Teaching example — not a real project</Pill>
        ) : (
          <Pill tone="ok">Verified source</Pill>
        )}
      </div>
    </Link>
  );
}

export default function WinningProjects() {
  const [category, setCategory] = useState("");
  const [year, setYear] = useState("");
  const [competition, setCompetition] = useState("");
  const [projectType, setProjectType] = useState("");
  const [team, setTeam] = useState("");
  const [query, setQuery] = useState("");

  const { data, error, loading } = useAsync(
    () => api.winningProjects({ category, year, competition, project_type: projectType, team, q: query }),
    [category, year, competition, projectType, team, query],
  );

  return (
    <GlobalShell subtitle="Winning Projects">
      <div className="stack">
        <header className="page-head">
          <h1>Winning Projects</h1>
          <p>
            Examples of what strong science-fair research looks like, broken down so you can see
            the choices behind them.
          </p>
        </header>

        {data?.empty_notice && (
          <Callout tone="warn" title="No verified past winners are loaded">
            <p>{data.empty_notice}</p>
            <p>
              The examples below are clearly-labelled teaching examples written by Research
              Coach. They show the standard of write-up to aim for; they are not real projects
              and did not win anything.
            </p>
          </Callout>
        )}

        <Callout tone="note" title="Learn from these — do not copy them">
          <p>{data?.copying_warning}</p>
        </Callout>

        <Card title="Filter">
          <div className="row gap-2">
            <input
              className="input"
              style={{ maxWidth: "240px" }}
              type="search"
              placeholder="Search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="Search projects"
            />
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              style={{ maxWidth: "200px" }}
              aria-label="Category"
            >
              <option value="">All categories</option>
              {data?.filters.categories.map((value) => (
                <option key={value} value={value}>
                  {humanise(value)}
                </option>
              ))}
            </select>
            <select
              value={year}
              onChange={(e) => setYear(e.target.value)}
              style={{ maxWidth: "130px" }}
              aria-label="Year"
            >
              <option value="">Any year</option>
              {data?.filters.years.map((value) => (
                <option key={value} value={String(value)}>
                  {value}
                </option>
              ))}
            </select>
            <select
              value={competition}
              onChange={(e) => setCompetition(e.target.value)}
              style={{ maxWidth: "200px" }}
              aria-label="Competition"
            >
              <option value="">Any competition</option>
              {data?.filters.competitions.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
            <select
              value={projectType}
              onChange={(e) => setProjectType(e.target.value)}
              style={{ maxWidth: "160px" }}
              aria-label="Project type"
            >
              <option value="">Any type</option>
              <option value="scientific">Scientific</option>
              <option value="engineering">Engineering</option>
            </select>
            <select
              value={team}
              onChange={(e) => setTeam(e.target.value)}
              style={{ maxWidth: "160px" }}
              aria-label="Individual or team"
            >
              <option value="">Individual or team</option>
              <option value="false">Individual</option>
              <option value="true">Team</option>
            </select>
          </div>
        </Card>

        {loading && <Loading what="Loading projects" />}
        {error && <ErrorNote message={error} />}

        {data?.projects.length === 0 && (
          <Card sunk>
            <h3>Nothing matches those filters</h3>
            <p className="muted">Clear a filter to see more.</p>
          </Card>
        )}

        <div className="guide-grid">
          {data?.projects.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      </div>
    </GlobalShell>
  );
}

const FACT_LABELS: Record<string, string> = {
  research_question: "Research question",
  problem_statement: "Problem",
  methodology: "Methodology",
  variables: "Variables",
  data_summary: "Data",
  results_summary: "Results",
  abstract: "Abstract",
  award_title: "Award",
  judging_commentary: "Judging commentary",
};

const FACT_ORDER = [
  "research_question",
  "problem_statement",
  "methodology",
  "variables",
  "data_summary",
  "results_summary",
  "abstract",
  "award_title",
];

export function WinningProjectDetail() {
  const { winnerId } = useParams();
  const { data, error, loading } = useAsync(
    () => api.winningProject(Number(winnerId)),
    [winnerId],
  );

  return (
    <GlobalShell subtitle="Winning Projects">
      {loading && <Loading what="Loading breakdown" />}
      {error && <ErrorNote message={error} />}
      {data && (
        <div className="stack">
          <header className="page-head">
            <div className="faint">
              <Link to="/winning-projects">Winning Projects</Link> · {humanise(data.category)}
            </div>
            <h1>{data.title}</h1>
            <div className="row faint">
              <span>{data.is_team ? `Team of ${data.team_size ?? "?"}` : "Individual"}</span>
              <span>·</span>
              <span>{humanise(data.project_type)}</span>
              {data.year && (
                <>
                  <span>·</span>
                  <span>{data.year}</span>
                </>
              )}
              {data.competition_name && (
                <>
                  <span>·</span>
                  <span>{data.competition_name}</span>
                </>
              )}
            </div>
          </header>

          {data.is_illustrative && (
            <Callout tone="warn" title="Constructed teaching example">
              <p>{data.notice}</p>
            </Callout>
          )}

          <Card title="Source">
            <p className="muted">
              {data.source_name}
              {data.source_url && (
                <>
                  {" — "}
                  <a href={data.source_url} target="_blank" rel="noreferrer">
                    check it yourself
                  </a>
                </>
              )}
            </p>
          </Card>

          {data.insufficient_notice && (
            <Callout tone="warn" title="Not enough detail for a breakdown">
              <p>{data.insufficient_notice}</p>
            </Callout>
          )}

          <Card title="What the source says">
            <p className="muted">
              Each field is tagged with where it came from. Anything the source did not contain
              is marked as missing rather than filled in.
            </p>
            {FACT_ORDER.map((key) => {
              const field = data.facts[key];
              if (!field) return null;
              return (
                <div className="fact" key={key}>
                  <div className="fact__head">
                    <span className="fact__label">{FACT_LABELS[key] ?? key}</span>
                    <Provenance value={field.provenance} />
                  </div>
                  {field.value === null ? (
                    <p className="faint m-0">
                      Not available from this source.
                    </p>
                  ) : typeof field.value === "string" ? (
                    <p className="m-0">{field.value}</p>
                  ) : (
                    <ul className="tick-list tick-list--arrow">
                      {Object.entries(field.value).map(([label, text]) => (
                        <li key={label}>
                          <strong>{humanise(label)}:</strong> {text}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              );
            })}
          </Card>

          <Card title="Judging">
            <div className="fact__head">
              <span className="fact__label">{FACT_LABELS.judging_commentary}</span>
              <Provenance value={data.judging.provenance} />
            </div>
            {data.judging.commentary ? (
              <p>{data.judging.commentary}</p>
            ) : (
              <p className="muted">{data.judging.notice}</p>
            )}
          </Card>

          {data.lessons.length > 0 && (
            <Card
              title="Lessons for your project"
              aside={<Provenance value={data.lessons_provenance} />}
            >
              <Callout tone="note">
                <p>{data.analysis_notice}</p>
              </Callout>
              <div className="mt-4">
                {data.lessons.map((lesson) => (
                  <div key={lesson.lesson} className="guide-section">
                    <h3>{lesson.lesson}</h3>
                    <p>{lesson.detail}</p>
                    <Link className="btn btn--quiet btn--small" to={`/library/${lesson.guide_id}`}>
                      Learn how →
                    </Link>
                  </div>
                ))}
              </div>
            </Card>
          )}

          <Callout tone="flag" title="Learn from this — do not copy it">
            <p>{data.copying_warning}</p>
          </Callout>
        </div>
      )}
    </GlobalShell>
  );
}
