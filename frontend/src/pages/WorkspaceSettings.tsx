import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../api/useAsync";
import { Callout, Card, ErrorNote, Loading } from "../components/ui";
import { useWorkspace } from "../state/workspace";

export default function WorkspaceSettings() {
  const { workspaceId } = useParams();
  const id = Number(workspaceId);
  const { reload: reloadWorkspaces } = useWorkspace();
  const { data, error, loading, reload } = useAsync(() => api.workspace(id), [id]);
  const [form, setForm] = useState<Record<string, unknown>>({});
  const [saved, setSaved] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    if (data) {
      setForm({
        name: data.name,
        organization_name: data.organization_name ?? "",
        description: data.description ?? "",
        default_project_visibility: data.default_project_visibility,
        leads_can_assign_mentors: data.leads_can_assign_mentors,
      });
    }
  }, [data]);

  async function save() {
    setProblem(null);
    try {
      await api.updateWorkspace(id, form);
      setSaved(true);
      reload();
      reloadWorkspaces();
    } catch (err) {
      setProblem((err as Error).message);
    }
  }

  if (loading) return <Loading />;
  if (error) return <ErrorNote message={error} />;
  if (!data) return null;

  return (
    <div className="stack">
      <header className="page-head">
        <h1>Settings</h1>
        <p>Only the workspace owner can change these.</p>
      </header>

      {problem && <Callout tone="flag">{problem}</Callout>}
      {saved && <Callout tone="note">Saved.</Callout>}

      <Card title="Details">
        <label className="field">
          <span className="field__label">Name</span>
          <input
            type="text"
            value={String(form.name ?? "")}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
        </label>
        <label className="field">
          <span className="field__label">Organization</span>
          <input
            type="text"
            value={String(form.organization_name ?? "")}
            onChange={(e) => setForm({ ...form, organization_name: e.target.value })}
          />
        </label>
        <label className="field">
          <span className="field__label">Description</span>
          <textarea
            value={String(form.description ?? "")}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            style={{ minHeight: "4rem" }}
          />
        </label>
      </Card>

      <Card title="Project visibility">
        <label className="field">
          <span className="field__label">Default for new projects</span>
          <select
            value={String(form.default_project_visibility ?? "private")}
            onChange={(e) => setForm({ ...form, default_project_visibility: e.target.value })}
          >
            <option value="private">Student, mentor and leads only</option>
            <option value="workspace">Everyone in the workspace</option>
          </select>
          <span className="field__hint">
            Changing this affects new projects. Existing ones keep their own setting.
          </span>
        </label>
        <label className="row gap-2">
          <input className="w-auto"
            type="checkbox"
            checked={Boolean(form.leads_can_assign_mentors)}
            onChange={(e) => setForm({ ...form, leads_can_assign_mentors: e.target.checked })}
          />
          <span>Leads can assign mentors</span>
        </label>
      </Card>

      <Card title="Join code" sunk>
        <p className="muted mb-2">
          Anyone with this code can join as a member.
        </p>
        <code className="text-lg">{data.join_code}</code>
      </Card>

      <div className="row">
        <button className="btn" onClick={save}>
          Save changes
        </button>
      </div>
    </div>
  );
}
