import { api } from "../api/client";
import { useAsync } from "../api/useAsync";
import { useProject } from "./ProjectLayout";
import { BasisChip, Callout, Card, Empty, ErrorNote, Findings, Loading } from "../components/ui";

export default function Rubric() {
  const { project } = useProject();
  const { data, error, loading } = useAsync(() => api.latestEvaluation(project.id).catch(() => null), [project.id]);

  if (loading) return <Loading />;
  if (error) return <ErrorNote message={error} />;
  if (!data) return <Empty title="No evaluation yet"><p className="muted">Run an evaluation first.</p></Empty>;

  const rubric = data.rubric;
  const assessable = rubric.lines.filter((line) => line.basis !== "not_yet_assessable");
  const pending = rubric.lines.filter((line) => line.basis === "not_yet_assessable");

  return (
    <div className="stack">
      <header className="page-head">
        <h1>AzSEF rubric projection</h1>
        <p>
          Where your points would land today, category by category, and why the missing ones are missing.
        </p>
      </header>

      <Card>
        <div className="readout">
          <div>
            <span className="readout__number">{rubric.points_projected}</span>
            <span className="readout__denominator"> / {rubric.assessable_points}</span>
          </div>
          <p className="readout__caption">
            Out of the {rubric.assessable_points} points that can honestly be judged right now. The other{" "}
            {rubric.points_possible - rubric.assessable_points} points sit in categories you have not produced work for
            yet — they are shown unscored below rather than counted as zero, because zero would be a lie in the other
            direction.
          </p>
        </div>
      </Card>

      <Callout tone="warn" title="Read this before you quote the number">
        <p className="mb-0">{rubric.disclaimer}</p>
      </Callout>

      <Card title="Categories being judged now">
        <div className="stack">
          {assessable.map((line) => (
            <div className="divided-top" key={line.key}>
              <div className="row row--between">
                <h3>
                  {line.label} <BasisChip basis={line.basis} />
                </h3>
                <span className="num">
                  {line.points_projected} / {line.points_possible}
                </span>
              </div>
              <div className="mt-3">
                <Findings
                  strengths={line.strengths}
                  weaknesses={line.weaknesses}
                  improvements={line.to_improve}
                />
              </div>
            </div>
          ))}
        </div>
      </Card>

      {pending.length > 0 && (
        <Card title="Not yet assessable" sunk>
          <p className="muted">
            These are worth {pending.reduce((sum, line) => sum + line.points_possible, 0)} points at the fair. Nothing
            is being predicted for them, because you have not made the thing they judge.
          </p>
          <div className="stack">
            {pending.map((line) => (
              <div key={line.key}>
                <div className="row row--between">
                  <span>
                    {line.label} <BasisChip basis={line.basis} />
                  </span>
                  <span className="num muted">— / {line.points_possible}</span>
                </div>
                {line.to_improve.length > 0 && (
                  <ul className="tick-list tick-list--arrow faint">
                    {line.to_improve.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
