import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { WorkspaceType } from "../api/types";
import { Callout, Card } from "../components/ui";
import { useWorkspace } from "../state/workspace";

const TYPES: [WorkspaceType, string, string][] = [
  ["school", "School", "A whole school's research programme."],
  ["research_club", "Research club", "A club that meets and competes together."],
  ["classroom", "Classroom", "One class, one teacher, one semester."],
  ["science_fair_team", "Science fair team", "A small team entering a specific fair."],
  ["independent_group", "Independent group", "Anything else — a study group, a lab."],
];

export default function WorkspaceNew() {
  const navigate = useNavigate();
  const { reload, select } = useWorkspace();
  const [form, setForm] = useState({
    name: "",
    organization_name: "",
    workspace_type: "research_club" as WorkspaceType,
    description: "",
    default_project_visibility: "private" as "private" | "workspace",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const workspace = await api.createWorkspace(form);
      await reload();
      select(workspace.id);
      navigate(`/workspaces/${workspace.id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="main">
      <div className="main__inner stack" style={{ maxWidth: 640 }}>
        <header className="page-head">
          <h1>Create a workspace</h1>
          <p>
            A shared space for a school, club, class or team. You become its owner, and you can
            invite people afterwards.
          </p>
        </header>

        <Card>
          <label className="field">
            <span className="field__label">Workspace name</span>
            <input
              type="text"
              placeholder="Hamilton High Science Fair Club"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </label>

          <label className="field">
            <span className="field__label">School or organization</span>
            <input
              type="text"
              value={form.organization_name}
              onChange={(e) => setForm({ ...form, organization_name: e.target.value })}
            />
          </label>

          <label className="field">
            <span className="field__label">What kind of space is this?</span>
            <select
              value={form.workspace_type}
              onChange={(e) =>
                setForm({ ...form, workspace_type: e.target.value as WorkspaceType })
              }
            >
              {TYPES.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
            <span className="field__hint">
              {TYPES.find(([v]) => v === form.workspace_type)?.[2]}
            </span>
          </label>

          <label className="field">
            <span className="field__label">Description (optional)</span>
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              style={{ minHeight: "4rem" }}
            />
          </label>

          <label className="field">
            <span className="field__label">Who can read a project by default?</span>
            <select
              value={form.default_project_visibility}
              onChange={(e) =>
                setForm({
                  ...form,
                  default_project_visibility: e.target.value as "private" | "workspace",
                })
              }
            >
              <option value="private">The student, their mentor and workspace leads</option>
              <option value="workspace">Everyone in the workspace</option>
            </select>
            <span className="field__hint">
              Private is the safer default for real research. Students can open their own
              projects up later.
            </span>
          </label>

          {error && <Callout tone="flag">{error}</Callout>}

          <button className="btn" onClick={submit} disabled={busy || form.name.trim().length < 2}>
            {busy ? "Creating…" : "Create workspace"}
          </button>
        </Card>
      </div>
    </div>
  );
}
