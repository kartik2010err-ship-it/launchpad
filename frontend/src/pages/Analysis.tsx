import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../api/useAsync";
import { useProject } from "./ProjectLayout";
import { BasisChip, Callout, Card, ErrorNote, Findings, Gauge, Loading, Pill, formatDate } from "../components/ui";
import CoachRecommendations from "../components/CoachRecommendations";

function scoreCaption(score: number, completeness: number): string {
  if (completeness < 60) {
    return "This is a provisional reading. The engine is still missing answers it needs, so the score is capped below what the project could earn.";
  }
  if (score < 45) return "As it stands this would not be competitive. The specific gaps are listed below, in order.";
  if (score < 68) return "A workable project with real holes in it. The weaknesses below are the difference between this and a competitive entry.";
  if (score < 82) return "Strong. What is left is mostly depth and defence, not repair.";
  return "Very strong on the evidence you have given. Keep the standard up through execution and presentation.";
}

export default function Analysis() {
  const { project } = useProject();
  const [busy, setBusy] = useState(false);
  const evaluation = useAsync(() => api.latestEvaluation(project.id).catch(() => null), [project.id]);
  const history = useAsync(() => api.scoreHistory(project.id), [project.id]);

  async function reevaluate() {
    setBusy(true);
    try {
      await api.evaluate(project.id);
      evaluation.reload();
      history.reload();
    } finally {
      setBusy(false);
    }
  }

  if (evaluation.loading) return <Loading what="Loading evaluation" />;
  if (evaluation.error) return <ErrorNote message={evaluation.error} />;

  const result = evaluation.data;

  if (!result) {
    return (
      <div className="stack">
        <header className="page-head">
          <h1>Research readiness</h1>
        </header>
        <Card sunk>
          <h3>Not evaluated yet</h3>
          <p className="muted">Answer some interview questions first, then run an evaluation.</p>
          <Link className="btn" to={`/projects/${project.id}/interview`}>
            Go to the interview
          </Link>
        </Card>
      </div>
    );
  }

  const previous = history.data && history.data.length > 1 ? history.data[history.data.length - 2] : null;
  const delta = previous ? result.overall_score - previous.overall_score : null;

  return (
    <div className="stack">
      <header className="page-head">
        <div className="row row--between">
          <div>
            <h1>Research readiness</h1>
            <p>Last evaluated {formatDate(result.created_at)}.</p>
          </div>
          <button className="btn btn--quiet btn--small" onClick={reevaluate} disabled={busy}>
            {busy ? "Re-evaluating…" : "Re-evaluate"}
          </button>
        </div>
      </header>

      <Card>
        <div className="readout">
          <div>
            <span className="readout__number">{result.overall_score}</span>
            <span className="readout__denominator"> / 100</span>
            {delta !== null && delta !== 0 && (
              <div className="faint num mt-1">
                {delta > 0 ? "+" : ""}
                {delta} since last time
              </div>
            )}
          </div>
          <p className="readout__caption">{scoreCaption(result.overall_score, result.information_completeness)}</p>
        </div>
        <div className="mt-5">
          <Gauge
            label="Information the engine has to work with"
            value={result.information_completeness}
            suffix="%"
          />
        </div>
      </Card>

      <Card title="Mentor summary">
        <p className="mb-0">{result.mentor_summary}</p>
      </Card>

      <CoachRecommendations projectId={project.id} />

      {result.safety.flags.length > 0 && (
        <Callout tone="flag" title="Rules and safety screening">
          <p>{result.safety.notice}</p>
          {result.safety.flags.map((flag) => (
            <div className="mt-3" key={flag.category}>
              <div>
                <strong>{flag.label}</strong>{" "}
                <span className="faint">triggered by: {flag.matched_terms.join(", ")}</span>
              </div>
              <div className="muted">{flag.why_it_matters}</div>
              <ul className="tight-list muted">
                {flag.likely_paperwork.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          ))}
        </Callout>
      )}

      {result.safety.flags.length === 0 && (
        <Callout tone="note" title="Rules and safety screening">
          <p className="mb-0">{result.safety.notice}</p>
        </Callout>
      )}

      <Card title="The five dimensions">
        <div className="stack">
          {result.dimensions.map((dimension) => (
            <div className="divided-top" key={dimension.key}>
              <Gauge
                label={
                  <span>
                    {dimension.label} <BasisChip basis={dimension.basis} />
                  </span>
                }
                value={dimension.score}
                basis={dimension.basis}
              />
              <p className="muted" style={{ margin: "0.5rem 0 0.6rem" }}>
                {dimension.summary}
              </p>
              <Findings
                strengths={dimension.strengths}
                weaknesses={dimension.weaknesses}
                improvements={dimension.improvements}
              />
            </div>
          ))}
        </div>
      </Card>

      <div className="grid-2">
        <Card title="Do next, in this order">
          <ol className="tight-list">
            {result.next_actions.map((action, i) => (
              <li key={i}>{action}</li>
            ))}
          </ol>
        </Card>

        <Card title="Questions to sit with">
          <p className="faint">Not homework. These are the questions a judge would push on.</p>
          <ul className="tick-list tick-list--arrow">
            {result.socratic_questions.map((question, i) => (
              <li key={i}>{question}</li>
            ))}
          </ul>
        </Card>
      </div>

      {history.data && history.data.length > 1 && (
        <Card title="Score history">
          <table className="table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Overall</th>
                <th>Question</th>
                <th>Method</th>
                <th>Creativity</th>
                <th>Feasibility</th>
                <th>Depth</th>
              </tr>
            </thead>
            <tbody>
              {history.data.map((point, i) => (
                <tr key={i}>
                  <td>{formatDate(point.created_at)}</td>
                  <td className="num">{point.overall_score}</td>
                  <td className="num">{point.dimensions.research_question}</td>
                  <td className="num">{point.dimensions.methodology}</td>
                  <td className="num">{point.dimensions.creativity}</td>
                  <td className="num">{point.dimensions.feasibility}</td>
                  <td className="num">{point.dimensions.scientific_depth}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      <div className="row">
        <Link className="btn btn--quiet btn--small" to={`/projects/${project.id}/rubric`}>
          See the AzSEF rubric projection
        </Link>
        <Link className="btn btn--quiet btn--small" to={`/projects/${project.id}/novelty`}>
          Novelty check <Pill>{result.novelty.status.replace(/_/g, " ")}</Pill>
        </Link>
      </div>
    </div>
  );
}
