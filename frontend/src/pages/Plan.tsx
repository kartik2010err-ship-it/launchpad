import { useState } from "react";
import { api } from "../api/client";
import { useAsync } from "../api/useAsync";
import { useProject } from "./ProjectLayout";
import { Callout, Card, ErrorNote, Loading, formatDate } from "../components/ui";

const ORDER: [string, string][] = [
  ["research_question", "Research question"],
  ["background_problem", "Background and problem"],
  ["purpose", "Purpose"],
  ["hypothesis", "Hypothesis or engineering goal"],
  ["independent_variable", "Independent variable"],
  ["dependent_variable", "Dependent variable"],
  ["controlled_variables", "Controlled variables"],
  ["experimental_group", "Experimental group"],
  ["control_group", "Control group"],
  ["materials", "Materials"],
  ["procedure", "Procedure"],
  ["trials", "Trials and replication"],
  ["data_to_collect", "Data to collect"],
  ["suggested_graphs", "Suggested graphs"],
  ["statistical_analysis", "Statistical analysis"],
  ["sources_of_error", "Sources of error"],
  ["confounding_variables", "Confounding variables"],
  ["safety_concerns", "Safety and rules"],
  ["limitations", "Limitations"],
  ["expected_contribution", "Expected contribution"],
  ["future_research", "Future research"],
];

function Value({ value }: { value: string | string[] }) {
  if (Array.isArray(value)) {
    return (
      <ul className="tight-list">
        {value.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    );
  }
  const unknown = value.toLowerCase().includes("not answered") || value.toLowerCase().includes("you have not");
  return <span className={unknown ? "faint" : undefined}>{value}</span>;
}

export default function Plan() {
  const { project } = useProject();
  const [busy, setBusy] = useState(false);
  const { data, error, loading, reload } = useAsync(() => api.getPlan(project.id).catch(() => null), [project.id]);

  async function generate() {
    setBusy(true);
    try {
      await api.createPlan(project.id);
      reload();
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <Loading />;
  if (error) return <ErrorNote message={error} />;

  return (
    <div className="stack">
      <header className="page-head">
        <div className="row row--between">
          <div>
            <h1>Research plan</h1>
            <p>
              A draft of the twenty-one sections most fairs ask for, filled from your own answers.
              {data ? ` Generated ${formatDate(data.created_at)}.` : ""}
            </p>
          </div>
          <button className="btn btn--quiet btn--small" onClick={generate} disabled={busy}>
            {busy ? "Building…" : data ? "Rebuild from latest answers" : "Generate the plan"}
          </button>
        </div>
      </header>

      {!data && (
        <Card sunk>
          <h3>No plan yet</h3>
          <p className="muted">
            Generate one once you have answered a decent share of the interview. Sections you have not answered will be
            marked as gaps rather than filled in with plausible-sounding invention.
          </p>
        </Card>
      )}

      {data && (
        <>
          <Callout tone="warn" title="This is a planning aid, not a submission">
            <p className="mb-0">{String(data.content.disclaimer ?? "")}</p>
          </Callout>

          <Card>
            <table className="table">
              <tbody>
                {ORDER.map(([key, label]) => (
                  <tr key={key}>
                    <th style={{ width: "27%", borderBottom: "1px solid var(--rule)" }}>{label}</th>
                    <td>
                      <Value value={data.content[key] ?? "—"} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          <p className="faint">
            Written against the question on file at the time: “{data.question}”. Rebuild it after you change your
            question or answer more interview questions.
          </p>
        </>
      )}
    </div>
  );
}
