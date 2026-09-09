import { useState } from "react";
import { api } from "../api/client";
import { useAsync } from "../api/useAsync";
import { useProject } from "./ProjectLayout";
import type { TaskStatus, TimelineTask } from "../api/types";
import {
  Callout,
  Card,
  ErrorNote,
  Loading,
  Pill,
  SOURCE_COPY,
  STATUS_COPY,
  formatDate,
  humanise,
} from "../components/ui";

const STATUSES: TaskStatus[] = ["not_started", "in_progress", "blocked", "needs_mentor_review", "complete"];

function TaskRow({ task, onChange }: { task: TimelineTask; onChange: (status: TaskStatus) => void }) {
  const source = SOURCE_COPY[task.requirement_source];
  return (
    <div className={`task${task.status === "complete" ? " is-complete" : ""}`}>
      <input
        type="checkbox"
        checked={task.status === "complete"}
        onChange={(e) => onChange(e.target.checked ? "complete" : "in_progress")}
        style={{ width: "auto", marginTop: "0.35rem" }}
        aria-label={`Mark ${task.title} complete`}
      />
      <div className="task__body">
        <div className="task__title">{task.title}</div>
        {task.description && <div className="faint">{task.description}</div>}
        {task.ai_note && (
          <div className="faint" style={{ color: "var(--warn)" }}>
            {task.ai_note}
          </div>
        )}
        <div className="task__meta">
          <span className="faint num">
            {formatDate(task.start_date)} → {formatDate(task.due_date)} · {task.estimated_hours}h
          </span>
          <Pill tone={source.tone}>{source.label}</Pill>
          {task.priority === "critical" && <Pill tone="flag">Critical</Pill>}
          {task.depends_on.length > 0 && (
            <span className="faint">after: {task.depends_on.map((d) => humanise(d)).join(", ")}</span>
          )}
        </div>
      </div>
      <select
        value={task.status}
        onChange={(e) => onChange(e.target.value as TaskStatus)}
        style={{ width: "auto", fontSize: "0.82rem", padding: "0.15rem 0.4rem" }}
      >
        {STATUSES.map((status) => (
          <option key={status} value={status}>
            {STATUS_COPY[status]}
          </option>
        ))}
      </select>
    </div>
  );
}

export default function TimelinePage() {
  const { project, reload } = useProject();
  const timeline = useAsync(() => api.getTimeline(project.id).catch(() => null), [project.id]);
  const competitions = useAsync(() => api.competitions(), []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    competition_key: project.competition_key ?? "azsef",
    competition_date: project.competition_date ?? "",
    hours_per_week: project.hours_per_week ?? 5,
    trials_planned: project.trials_planned ?? 15,
    minutes_per_trial: project.minutes_per_trial ?? 20,
    teammates: project.teammates ?? 0,
  });

  async function generate() {
    setBusy(true);
    setError(null);
    try {
      const competition = competitions.data?.find((c) => c.key === form.competition_key);
      await api.generateTimeline(project.id, {
        ...form,
        competition_name: competition?.name ?? "Science fair",
        hours_per_week: Number(form.hours_per_week),
        trials_planned: Number(form.trials_planned),
        minutes_per_trial: Number(form.minutes_per_trial),
        teammates: Number(form.teammates),
      });
      timeline.reload();
      reload();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function setStatus(task: TimelineTask, status: TaskStatus) {
    await api.updateTask(project.id, task.id, { status });
    timeline.reload();
  }

  const phases = timeline.data
    ? timeline.data.tasks.reduce<Record<string, TimelineTask[]>>((acc, task) => {
        (acc[task.phase] ??= []).push(task);
        return acc;
      }, {})
    : {};

  return (
    <div className="stack">
      <header className="page-head">
        <h1>Timeline</h1>
        <p>
          Planned backwards from the fair date. Tasks that must happen before others are scheduled before them, and if
          the arithmetic does not work you get told rather than handed a comfortable-looking schedule.
        </p>
      </header>

      <Card title="Schedule inputs">
        <div className="grid-2">
          <label className="field">
            <span className="field__label">Competition</span>
            <select
              value={form.competition_key}
              onChange={(e) => setForm({ ...form, competition_key: e.target.value })}
            >
              {competitions.data?.map((competition) => (
                <option key={competition.key} value={competition.key}>
                  {competition.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field__label">Fair date</span>
            <input
              type="date"
              value={form.competition_date ?? ""}
              onChange={(e) => setForm({ ...form, competition_date: e.target.value })}
            />
          </label>
          <label className="field">
            <span className="field__label">Hours you can actually give it per week</span>
            <input
              type="number"
              min={1}
              max={40}
              value={form.hours_per_week}
              onChange={(e) => setForm({ ...form, hours_per_week: Number(e.target.value) })}
            />
          </label>
          <label className="field">
            <span className="field__label">Teammates</span>
            <input
              type="number"
              min={0}
              max={2}
              value={form.teammates}
              onChange={(e) => setForm({ ...form, teammates: Number(e.target.value) })}
            />
          </label>
          <label className="field">
            <span className="field__label">Trials planned</span>
            <input
              type="number"
              min={1}
              value={form.trials_planned}
              onChange={(e) => setForm({ ...form, trials_planned: Number(e.target.value) })}
            />
          </label>
          <label className="field">
            <span className="field__label">Minutes per trial</span>
            <input
              type="number"
              min={1}
              value={form.minutes_per_trial}
              onChange={(e) => setForm({ ...form, minutes_per_trial: Number(e.target.value) })}
            />
          </label>
        </div>
        <button className="btn" onClick={generate} disabled={busy || !form.competition_date}>
          {busy ? "Planning…" : timeline.data ? "Rebuild the schedule" : "Build the schedule"}
        </button>
      </Card>

      {error && <Callout tone="flag">{error}</Callout>}
      {timeline.loading && <Loading />}
      {timeline.error && <ErrorNote message={timeline.error} />}

      {timeline.data && (
        <>
          <Card sunk>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <span>
                {timeline.data.competition_name} · {formatDate(timeline.data.competition_date)}
              </span>
              <span className="num">
                {timeline.data.days_remaining} days · {timeline.data.total_estimated_hours}h of work vs{" "}
                {timeline.data.available_hours}h available
              </span>
            </div>
          </Card>

          {timeline.data.warnings.map((warning, i) => (
            <Callout key={i} tone={warning.severity === "high" ? "flag" : "warn"} title={warning.message}>
              <p style={{ marginBottom: 0 }}>{warning.recommendation}</p>
            </Callout>
          ))}

          <Callout tone="note" title="About the requirement labels">
            <p style={{ marginBottom: 0 }}>{timeline.data.requirement_disclaimer}</p>
          </Callout>

          {Object.entries(phases).map(([phase, tasks], index) => (
            <div key={phase} className="phase">
              <div className="phase__marker">{String(index + 1).padStart(2, "0")}</div>
              <div>
                <h3>{humanise(phase)}</h3>
                <div>
                  {tasks.map((task) => (
                    <TaskRow key={task.id} task={task} onChange={(status) => setStatus(task, status)} />
                  ))}
                </div>
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
