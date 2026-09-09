import { useState } from "react";
import { api } from "../api/client";
import { useAsync } from "../api/useAsync";
import { useProject } from "./ProjectLayout";
import { Callout, Card, ErrorNote, Loading, formatDate } from "../components/ui";

const FIELDS: [string, string, string][] = [
  ["what_was_done", "What you did today", "The actual actions, in the order you did them."],
  ["procedure_changes", "Anything you changed from the plan", "Judges ask about this constantly. Write it down while you remember why."],
  ["observations", "What you observed", "Including things that seemed irrelevant."],
  ["raw_measurements", "Raw measurements", "Numbers with units. Paste them here even if messy."],
  ["problems", "What went wrong", "Failed runs count as data about your method."],
  ["open_questions", "Questions this raised", ""],
  ["next_steps", "What you will do next session", ""],
];

export default function Notebook() {
  const { project } = useProject();
  const entries = useAsync(() => api.notebook(project.id), [project.id]);
  const templates = useAsync(() => api.templates(project.id), [project.id]);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await api.addNotebookEntry(project.id, {
        entry_date: new Date().toISOString().slice(0, 10),
        ...draft,
      });
      setDraft({});
      entries.reload();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      <header className="page-head">
        <h1>Research notebook</h1>
        <p>
          A dated log of what you actually did. Judges ask what changed and why; this is the only reliable way to
          answer months later.
        </p>
      </header>

      <Card title="New entry">
        {FIELDS.map(([key, label, hint]) => (
          <label key={key} className="field">
            <span className="field__label">{label}</span>
            {hint && <span className="field__hint">{hint}</span>}
            <textarea
              value={draft[key] ?? ""}
              onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
              style={{ minHeight: key === "what_was_done" ? "5.5rem" : "3.5rem" }}
            />
          </label>
        ))}
        {error && <Callout tone="flag">{error}</Callout>}
        <button className="btn" onClick={save} disabled={busy || !(draft.what_was_done ?? "").trim()}>
          {busy ? "Saving…" : "Save entry"}
        </button>
      </Card>

      {templates.data && (
        <Card title="Data tables to set up" sunk>
          <p className="muted">
            Column headings built from your own variables. Copy these into a sheet before you start collecting.
          </p>
          {Object.entries(templates.data).map(([key, template]) => (
            <div key={key} style={{ marginBottom: "0.8rem" }}>
              <div className="faint">{template.title}</div>
              <table className="table">
                <thead>
                  <tr>
                    {template.columns.map((column, i) => (
                      <th key={i}>{column}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    {template.columns.map((_, i) => (
                      <td key={i} className="faint">
                        —
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          ))}
        </Card>
      )}

      {entries.loading && <Loading />}
      {entries.error && <ErrorNote message={entries.error} />}

      {entries.data?.length === 0 && (
        <Card sunk>
          <h3>Nothing logged yet</h3>
          <p className="muted">Start logging the day you first touch materials, not the day you get results.</p>
        </Card>
      )}

      {entries.data?.map((entry) => (
        <Card key={entry.id} title={formatDate(entry.entry_date)}>
          <table className="table">
            <tbody>
              {FIELDS.map(([key, label]) => {
                const value = (entry as unknown as Record<string, string | null>)[key];
                if (!value) return null;
                return (
                  <tr key={key}>
                    <th style={{ width: "26%", borderBottom: "1px solid var(--rule)" }}>{label}</th>
                    <td style={{ whiteSpace: "pre-wrap" }}>{value}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Card>
      ))}
    </div>
  );
}
