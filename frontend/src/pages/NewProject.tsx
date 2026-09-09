import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { Callout, Card } from "../components/ui";
import { useWorkspace } from "../state/workspace";

const CATEGORIES = [
  ["computer_science", "Computer science"],
  ["biomedical_science", "Biomedical science"],
  ["environmental_science", "Environmental science"],
  ["physics", "Physics"],
  ["chemistry", "Chemistry"],
  ["engineering", "Engineering"],
  ["behavioral_social_science", "Behavioural / social science"],
  ["mathematics", "Mathematics"],
  ["other", "Other"],
];

export default function NewProject() {
  const navigate = useNavigate();
  const { workspaces, current } = useWorkspace();
  const [form, setForm] = useState({
    title: "",
    topic: "",
    initial_question: "",
    grade_level: 10,
    project_type: "scientific",
    category: "other",
    background_knowledge: "",
    workspace_id: current?.id ?? null as number | null,
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const project = await api.createProject({
        ...form,
        grade_level: Number(form.grade_level),
        workspace_id: form.workspace_id ?? current?.id ?? null,
      });
      navigate(`/projects/${project.id}/interview`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="main">
      <div className="main__inner stack">
        <header className="page-head">
          <h1>Start a project</h1>
          <p>
            Write down what you have now, in whatever state it is in. A vague question is a normal starting point — the
            next screen is an interview that turns it into something testable.
          </p>
        </header>

        <Card>
          <label className="field">
            <span className="field__label">Where should this live?</span>
            <span className="field__hint">
              A club workspace shares progress with your mentor and lead. Your personal
              workspace stays private.
            </span>
            <select
              value={form.workspace_id ?? ""}
              onChange={(e) => setForm({ ...form, workspace_id: Number(e.target.value) })}
            >
              {workspaces.map((workspace) => (
                <option key={workspace.id} value={workspace.id}>
                  {workspace.name}
                  {workspace.is_personal ? " (private)" : ""}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span className="field__label">Project title or rough topic</span>
            <input type="text" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          </label>

          <label className="field">
            <span className="field__label">Your research question, as you would say it out loud</span>
            <span className="field__hint">Do not polish it. This version gets saved as version 1 either way.</span>
            <textarea
              value={form.initial_question}
              onChange={(e) => setForm({ ...form, initial_question: e.target.value })}
            />
          </label>

          <div className="grid-2">
            <label className="field">
              <span className="field__label">Grade</span>
              <input
                type="number"
                min={5}
                max={12}
                value={form.grade_level}
                onChange={(e) => setForm({ ...form, grade_level: Number(e.target.value) })}
              />
            </label>

            <label className="field">
              <span className="field__label">Project kind</span>
              <select
                value={form.project_type}
                onChange={(e) => setForm({ ...form, project_type: e.target.value })}
              >
                <option value="scientific">Scientific research — I am testing a question</option>
                <option value="engineering">Engineering — I am building and testing a design</option>
              </select>
            </label>
          </div>

          <label className="field">
            <span className="field__label">Category</span>
            <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
              {CATEGORIES.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span className="field__label">What do you already know about this topic? (optional)</span>
            <span className="field__hint">
              Anything you have read, tried before, or half-remember. It changes which questions you get asked.
            </span>
            <textarea
              value={form.background_knowledge}
              onChange={(e) => setForm({ ...form, background_knowledge: e.target.value })}
            />
          </label>

          {error && <Callout tone="flag">{error}</Callout>}

          <button
            className="btn"
            onClick={submit}
            disabled={busy || form.title.length < 3 || form.initial_question.length < 5}
          >
            {busy ? "Creating…" : "Start the interview"}
          </button>
        </Card>
      </div>
    </div>
  );
}
