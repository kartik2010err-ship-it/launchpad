import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../api/useAsync";
import type { CommentType, WorkspaceComment } from "../api/types";
import {
  BasisChip,
  Callout,
  Card,
  ErrorNote,
  Findings,
  Gauge,
  Loading,
  NOVELTY_COPY,
  Pill,
  formatDate,
  humanise,
} from "../components/ui";
import { Meter, StatusPill, humanStage, relativeTime } from "../components/workspace-ui";
import { isOversight, useWorkspace } from "../state/workspace";

const COMMENT_TYPES: [CommentType, string][] = [
  ["general", "General"],
  ["needs_action", "Needs action"],
  ["important", "Important"],
  ["resolved", "Resolved"],
];

const TYPE_TONE: Record<CommentType, "neutral" | "warn" | "flag" | "ok"> = {
  general: "neutral",
  needs_action: "warn",
  important: "flag",
  resolved: "ok",
};

/**
 * Everything a lead or mentor needs about one project, read-only, without
 * logging in as the student. Feedback is the one thing they can write here.
 */
export default function WorkspaceProjectDetail() {
  const { workspaceId, projectId } = useParams();
  const wsId = Number(workspaceId);
  const pid = Number(projectId);
  const navigate = useNavigate();
  const { current } = useWorkspace();

  const detail = useAsync(() => api.getProject(pid), [pid]);
  const progress = useAsync(() => api.projectProgress(wsId, pid), [wsId, pid]);
  const evaluation = useAsync(() => api.latestEvaluation(pid).catch(() => null), [pid]);
  const timeline = useAsync(() => api.getTimeline(pid).catch(() => null), [pid]);
  const comments = useAsync(() => api.workspaceComments(wsId, pid), [wsId, pid]);
  const members = useAsync(
    () => (isOversight(current?.my_role) ? api.members(wsId) : Promise.resolve([])),
    [wsId, current?.my_role],
  );

  const [draft, setDraft] = useState("");
  const [type, setType] = useState<CommentType>("general");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function post() {
    if (!draft.trim()) return;
    setBusy(true);
    setProblem(null);
    try {
      await api.addWorkspaceComment(wsId, pid, {
        body: draft.trim(),
        comment_type: type,
        section: "general",
      });
      setDraft("");
      comments.reload();
    } catch (err) {
      setProblem((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function assign(mentorId: string) {
    setProblem(null);
    try {
      await api.assignMentor(wsId, pid, mentorId ? Number(mentorId) : null);
      progress.reload();
      detail.reload();
    } catch (err) {
      setProblem((err as Error).message);
    }
  }

  if (detail.loading) return <Loading what="Loading project" />;
  if (detail.error) return <ErrorNote message={detail.error} />;
  if (!detail.data) return null;

  const project = detail.data;
  const evalData = evaluation.data;
  const mentors = (members.data ?? []).filter(
    (m) => m.role === "mentor" || m.role === "lead" || m.role === "owner",
  );
  const overdue = (timeline.data?.tasks ?? []).filter(
    (t) =>
      t.status !== "complete" && t.due_date && new Date(t.due_date) < new Date(),
  );
  const revisions = [...project.revisions].sort((a, b) => b.version - a.version);

  return (
    <div className="stack">
      <header className="page-head">
        <div className="row row--between">
          <div>
            <button
              className="btn btn--quiet btn--small mb-2"
              onClick={() => navigate(`/workspaces/${wsId}/projects`)}
            >
              ← All projects
            </button>
            <h1>{project.title}</h1>
            <p>
              {humanise(project.category)} · Grade {project.grade_level} ·{" "}
              {humanStage(project.stage)}
            </p>
          </div>
          {progress.data && <StatusPill status={progress.data.status} />}
        </div>
      </header>

      {problem && <Callout tone="flag">{problem}</Callout>}

      <div className="question-hero">
        <q>{project.current_question}</q>
        {revisions.length > 1 && (
          <div className="faint mt-2">
            Version {revisions[0].version} of {revisions.length}
          </div>
        )}
      </div>

      {progress.data?.current_risk && progress.data.status !== "on_track" && (
        <Callout
          tone={progress.data.status === "blocked" ? "flag" : "warn"}
          title="Why this is flagged"
        >
          <p className="mb-0">{progress.data.current_risk}</p>
        </Callout>
      )}

      <div className="split">
        <div className="stack">
          {progress.data && (
            <Card title="Progress">
              <div className="stack gap-3">
                {progress.data.areas.map((area) => (
                  <div key={area.key}>
                    <div className="row row--between">
                      <span className="text-sm">{area.label}</span>
                    </div>
                    <Meter percent={area.percent} />
                    <div className="faint">{area.note}</div>
                  </div>
                ))}
              </div>
              <div className="divided-top">
                <div className="faint">Current priority</div>
                <div>{progress.data.current_priority ?? "Nothing scheduled."}</div>
                {progress.data.next_deadline && (
                  <div className="faint mt-1">
                    Next deadline {formatDate(progress.data.next_deadline)}
                    {progress.data.days_to_next_deadline !== null
                      ? ` — ${progress.data.days_to_next_deadline} days`
                      : ""}
                  </div>
                )}
              </div>
            </Card>
          )}

          {evalData && (
            <>
              <Card title="AI evaluation" aside={<span className="num">{evalData.overall_score}/100</span>}>
                <p className="muted">{evalData.mentor_summary}</p>
                <div className="stack gap-4 mt-4">
                  {evalData.dimensions.map((dimension) => (
                    <div key={dimension.key}>
                      <Gauge
                        label={
                          <span>
                            {dimension.label} <BasisChip basis={dimension.basis} />
                          </span>
                        }
                        value={dimension.score}
                        basis={dimension.basis}
                        animate={false}
                      />
                      <Findings weaknesses={dimension.weaknesses.slice(0, 2)} />
                    </div>
                  ))}
                </div>
              </Card>

              <Card title="AzSEF rubric projection">
                <table className="table">
                  <tbody>
                    {evalData.rubric.lines.map((line) => (
                      <tr key={line.key}>
                        <td>
                          <div className="dt__primary">{line.label}</div>
                          <div className="dt__sub">
                            {line.weaknesses[0] ?? line.strengths[0] ?? "—"}
                          </div>
                        </td>
                        <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                          <BasisChip basis={line.basis} />
                          <div className="num" style={{ marginTop: 3 }}>
                            {line.basis === "not_yet_assessable"
                              ? `— / ${line.points_possible}`
                              : `${line.points_projected} / ${line.points_possible}`}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>

              <Card
                title="Novelty"
                aside={
                  <Pill tone={NOVELTY_COPY[evalData.novelty.status].tone}>
                    {NOVELTY_COPY[evalData.novelty.status].label}
                  </Pill>
                }
              >
                <p className="mb-2">{evalData.novelty.headline}</p>
                <p className="faint mb-0">
                  {evalData.novelty.evidence_note}
                </p>
              </Card>

              {evalData.safety.flags.length > 0 && (
                <Callout tone="flag" title="Rules and safety flags">
                  <ul className="tight-list">
                    {evalData.safety.flags.map((flag) => (
                      <li key={flag.category}>
                        <strong>{flag.label}</strong> — {flag.why_it_matters}
                      </li>
                    ))}
                  </ul>
                </Callout>
              )}
            </>
          )}

          {revisions.length > 1 && (
            <Card title="Question history">
              <div className="lineage">
                {revisions.map((revision, index) => (
                  <div
                    key={revision.id}
                    className={`lineage__item${index === 0 ? " is-current" : ""}`}
                  >
                    <div className="lineage__version">
                      v{revision.version} · {humanise(revision.source)} ·{" "}
                      {formatDate(revision.created_at)}
                    </div>
                    <div className="lineage__text">{revision.text}</div>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>

        <div className="stack">
          <Card title="Assignment">
            <div className="faint">Mentor</div>
            {isOversight(current?.my_role) ? (
              <select className="mt-1"
                value={project.mentor_id ?? ""}
                onChange={(e) => assign(e.target.value)}
              >
                <option value="">Unassigned</option>
                {mentors.map((m) => (
                  <option key={m.user_id} value={m.user_id}>
                    {m.name}
                  </option>
                ))}
              </select>
            ) : (
              <div>{project.mentor_id ? "Assigned" : "Unassigned"}</div>
            )}
            <div className="faint mt-3">
              Competition
            </div>
            <div>{project.competition_name ?? "Not set"}</div>
            {project.competition_date && (
              <div className="faint">{formatDate(project.competition_date)}</div>
            )}
          </Card>

          {overdue.length > 0 && (
            <Card title={`Missed deadlines (${overdue.length})`}>
              <ul className="tight-list">
                {overdue.slice(0, 6).map((task) => (
                  <li key={task.id}>
                    {task.title} <span className="faint">— due {formatDate(task.due_date)}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <Card title="Feedback">
            {comments.data && comments.data.length > 0 ? (
              <div className="stack gap-3 mb-4">
                {comments.data.map((comment: WorkspaceComment) => (
                  <div key={comment.id} className="turn">
                    <div className="turn__who">
                      {comment.author_name} · {comment.author_role} ·{" "}
                      {relativeTime(comment.created_at)}
                    </div>
                    <div>{comment.body}</div>
                    <div className="mt-2">
                      <Pill tone={TYPE_TONE[comment.comment_type]}>
                        {humanise(comment.comment_type)}
                      </Pill>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted">No feedback yet.</p>
            )}

            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Be specific about what to change and why."
              style={{ minHeight: "4.5rem" }}
            />
            <div className="row mt-2">
              <select className="w-auto"
                value={type}
                onChange={(e) => setType(e.target.value as CommentType)}
              >
                {COMMENT_TYPES.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
              <button
                className="btn btn--small"
                onClick={post}
                disabled={busy || draft.trim().length < 3}
              >
                Post
              </button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
