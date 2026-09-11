import { api } from "../api/client";
import { useAsync } from "../api/useAsync";
import { useProject } from "./ProjectLayout";
import { Callout, Card, Empty, ErrorNote, Loading, NOVELTY_COPY, Pill } from "../components/ui";
import type { NoveltyAnalysis } from "../api/types";

export default function Novelty() {
  const { project } = useProject();
  const { data, error, loading } = useAsync(() => api.latestEvaluation(project.id).catch(() => null), [project.id]);

  if (loading) return <Loading />;
  if (error) return <ErrorNote message={error} />;
  if (!data) return <Empty title="No evaluation yet"><p className="muted">Run an evaluation first.</p></Empty>;

  const novelty = data.novelty as NoveltyAnalysis;
  const copy = NOVELTY_COPY[novelty.status];

  return (
    <div className="stack">
      <header className="page-head">
        <h1>Novelty check</h1>
        <p>Whether this idea is likely to look familiar to a judge who has seen a hundred projects.</p>
      </header>

      <Card>
        <div className="row row--between">
          <h2>{copy.label}</h2>
          <Pill tone={copy.tone}>confidence: {novelty.confidence}</Pill>
        </div>
        <p className="mt-3 mb-0">{novelty.headline}</p>
      </Card>

      <Callout tone="warn" title="What this assessment is based on">
        <p className="mb-0">{novelty.evidence_note}</p>
        {novelty.literature_search_performed ? null : (
          <p className="muted mt-2 mb-0">
            No literature search was run and no papers are being cited. This is pattern-matching against ideas that are
            common at fairs, not a claim about what exists in the published record. Searching Google Scholar yourself is
            still the only way to know.
          </p>
        )}
      </Callout>

      <div className="grid-2">
        {novelty.similar_existing_ideas.length > 0 && (
          <Card title="Projects that look like yours">
            <ul className="tight-list">
              {novelty.similar_existing_ideas.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </Card>
        )}

        {novelty.whats_different.length > 0 && (
          <Card title="What is arguably different">
            <ul className="tick-list tick-list--plus">
              {novelty.whats_different.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </Card>
        )}

        {novelty.novelty_risks.length > 0 && (
          <Card title="Where this gets challenged">
            <ul className="tick-list tick-list--minus">
              {novelty.novelty_risks.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </Card>
        )}

        {novelty.ways_to_increase.length > 0 && (
          <Card title="How to make it more distinct">
            <ul className="tick-list tick-list--arrow">
              {novelty.ways_to_increase.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </Card>
        )}
      </div>
    </div>
  );
}
