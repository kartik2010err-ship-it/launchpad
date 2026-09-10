import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { useAsync } from "../api/useAsync";
import { useAuth } from "../state/auth";
import {
  Callout,
  Card,
  ErrorNote,
  Gauge,
  Loading,
  Pill,
  formatDate,
  humanise,
} from "../components/ui";
import { StatusPill } from "../components/workspace-ui";
import type { Contribution, TeamDashboardData } from "../api/types";

/**
 * /workspaces/:workspaceId/teams/:teamId
 *
 * One screen showing the team's single shared project and who is doing what on
 * it. Two things it is written to make obvious: this project is one record that
 * every member edits, and the contribution log is per-person so a student can
 * explain their own part at a judging interview.
 */
export default function TeamDashboard() {
  const { workspaceId, teamId } = useParams();
  const wsId = Number(workspaceId);
  const tId = Number(teamId);
  const { user } = useAuth();

  const { data, error, loading, reload } = useAsync(
    () => api.teamDashboard(wsId, tId),
    [wsId, tId],
  );

  if (loading) return <Loading what="Loading team" />;
  if (error) return <ErrorNote message={error} />;
  if (!data) return null;

  const { team, members, capacity, project } = data;

  return (
    <div className="stack">
      <header className="page-head">
        <div className="row row--between">
          <div>
            <div className="faint">
              <Link to={`/workspaces/${wsId}/teams`}>Teams</Link>
            </div>
            <h1>{team.name}</h1>
            <p>{team.description ?? "A team sharing one research project."}</p>
          </div>
          <div className="row gap-2">
            {project && <StatusPill status={project.status} />}
            <Pill tone={capacity.is_full ? "inert" : "neutral"}>
              {capacity.member_count}/{capacity.max_team_size} members
            </Pill>
            {team.membership_locked && <Pill tone="warn">Roster locked</Pill>}
          </div>
        </div>
      </header>

      {project ? (
        <SharedProject data={data} wsId={wsId} />
      ) : (
        <StartProject wsId={wsId} teamId={tId} canStart={team.i_am_member} onDone={reload} />
      )}

      <Card
        title="Members"
        aside={team.join_code ? <code className="code">{team.join_code}</code> : undefined}
      >
        <div className="team-grid">
          {members.map((member) => (
            <div className="member" key={member.user_id}>
              <div className="member__name">
                <strong>{member.name}</strong>
                {member.role === "team_lead" && <Pill>Team lead</Pill>}
              </div>
              <div className="member__stats">
                {member.completed_count}/{member.contribution_count} tasks done
                {member.hours > 0 && ` · ${member.hours}h logged`}
              </div>
            </div>
          ))}
          {members.length === 0 && <p className="muted">Nobody has joined yet.</p>}
        </div>

        <div className="faint mt-4">
          {team.mentor_name ? `Mentor: ${team.mentor_name}.` : "No mentor assigned yet."}{" "}
          {capacity.seats_left > 0
            ? `${capacity.seats_left} seat(s) left.`
            : "This team is at its configured maximum."}
        </div>

        <details className="mt-3">
          <summary className="faint">How the team-size limit is set</summary>
          <div className="mt-2">
            <p className="muted">
              Research Coach is configured to allow up to {capacity.max_team_size} members for{" "}
              {capacity.rules.competition_name}
              {capacity.limit_source === "team_override"
                ? " (raised for this team by a workspace lead)"
                : ""}
              .
            </p>
            <Callout tone="warn" title="This is app configuration, not official eligibility">
              <p>{capacity.rules.notice}</p>
            </Callout>
          </div>
        </details>
      </Card>

      <Contributions
        wsId={wsId}
        teamId={tId}
        data={data}
        currentUserId={user?.id}
        onChange={reload}
      />

      <div className="grid-2">
        <Card title="Team tasks">
          {data.tasks.length === 0 && <p className="muted">No timeline generated yet.</p>}
          {data.tasks
            .filter((task) => task.status !== "complete")
            .slice(0, 8)
            .map((task) => (
              <div key={task.id} className="row row--between">
                <span>{task.title}</span>
                <span className="faint">{formatDate(task.due_date)}</span>
              </div>
            ))}
          {data.tasks.length > 0 && (
            <p className="faint mt-3">
              {data.tasks.filter((t) => t.status === "complete").length} of {data.tasks.length}{" "}
              complete.
            </p>
          )}
        </Card>

        <Card title="Mentor feedback">
          {data.comments.length === 0 && <p className="muted">No feedback yet.</p>}
          {data.comments.slice(0, 5).map((comment) => (
            <div className="mb-3" key={comment.id}>
              <div className="row faint">
                <strong>{comment.author_name}</strong>
                <span>·</span>
                <span>{formatDate(comment.created_at)}</span>
                {comment.requires_action && !comment.resolved && <Pill tone="warn">Action</Pill>}
              </div>
              <p style={{ margin: "0.2rem 0 0" }}>{comment.body}</p>
            </div>
          ))}
        </Card>
      </div>

      <div className="grid-2">
        <Card title="Shared research notebook">
          <p className="faint">One notebook for the whole team — everyone writes into it.</p>
          {data.notebook.length === 0 && <p className="muted">No entries yet.</p>}
          {data.notebook.map((entry) => (
            <div className="mb-3" key={entry.id}>
              <div className="faint">{formatDate(entry.entry_date)}</div>
              <div>{entry.what_was_done}</div>
              {entry.observations && <div className="faint">{entry.observations}</div>}
            </div>
          ))}
          {project && (
            <Link className="btn btn--quiet btn--small" to={`/projects/${project.id}/notebook`}>
              Open notebook
            </Link>
          )}
        </Card>

        <Card title="Recent activity">
          {data.activity.length === 0 && <p className="muted">Nothing yet.</p>}
          {data.activity.slice(0, 8).map((entry) => (
            <div key={entry.id} className="row row--between">
              <span>{entry.summary}</span>
              <span className="faint">{formatDate(entry.created_at)}</span>
            </div>
          ))}
        </Card>
      </div>
    </div>
  );
}

function SharedProject({ data, wsId }: { data: TeamDashboardData; wsId: number }) {
  const project = data.project!;
  return (
    <Card
      title="The team's shared project"
      aside={
        <Link className="btn btn--small" to={`/projects/${project.id}`}>
          Open project
        </Link>
      }
    >
      <div className="question-hero mb-4">
        <q>{project.current_question}</q>
      </div>

      <p className="faint">
        {data.can_edit_project
          ? "Every member of this team edits this same record. There is no separate copy per person."
          : "You can read this project but not change it — only members of this team can."}
      </p>

      {project.readiness !== null && (
        <div style={{ margin: "0.9rem 0" }}>
          <Gauge label="Readiness" value={project.readiness} />
        </div>
      )}

      <div className="row faint">
        <span>{humanise(project.stage)}</span>
        <span>·</span>
        <span>{humanise(project.category)}</span>
        {project.competition_name && (
          <>
            <span>·</span>
            <span>{project.competition_name}</span>
          </>
        )}
        {project.days_to_competition !== null && (
          <>
            <span>·</span>
            <span>{project.days_to_competition} days to competition</span>
          </>
        )}
      </div>

      {project.next_task && (
        <p className="mt-3">
          <strong>Next up:</strong> {project.next_task}
          {project.next_deadline && ` — due ${formatDate(project.next_deadline)}`}
        </p>
      )}
    </Card>
  );
}

function StartProject({
  wsId,
  teamId,
  canStart,
  onDone,
}: {
  wsId: number;
  teamId: number;
  canStart: boolean;
  onDone: () => void;
}) {
  const [title, setTitle] = useState("");
  const [question, setQuestion] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.createTeamProject(wsId, teamId, { title, initial_question: question });
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start the project.");
    } finally {
      setBusy(false);
    }
  }

  if (!canStart)
    return (
      <Card sunk>
        <h3>No shared project yet</h3>
        <p className="muted">This team has not started its research project.</p>
      </Card>
    );

  return (
    <Card title="Start the team's shared project">
      <p className="muted">
        A team owns exactly one project. Everyone who joins this team will open this same record.
      </p>
      <form className="mt-4" onSubmit={submit}>
        <label className="field">
          <span>Project title</span>
          <input
            className="input"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Coral Bleaching Research Project"
          />
        </label>
        <label className="field">
          <span>Your starting research question</span>
          <textarea
            rows={3}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="It can be rough. The interview is what sharpens it."
          />
        </label>
        {error && <ErrorNote message={error} />}
        <button className="btn btn--small" disabled={busy || title.length < 3 || question.length < 5}>
          {busy ? "Starting…" : "Start shared project"}
        </button>
      </form>
    </Card>
  );
}

function Contributions({
  wsId,
  teamId,
  data,
  currentUserId,
  onChange,
}: {
  wsId: number;
  teamId: number;
  data: TeamDashboardData;
  currentUserId: number | undefined;
  onChange: () => void;
}) {
  const [task, setTask] = useState("");
  const [description, setDescription] = useState("");
  const [hours, setHours] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const canLog = data.team.i_am_member || data.can_manage_team;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.addContribution(wsId, teamId, {
        task,
        description: description || null,
        hours: hours ? Number(hours) : null,
      });
      setTask("");
      setDescription("");
      setHours("");
      onChange();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not log that.");
    } finally {
      setBusy(false);
    }
  }

  async function toggle(row: Contribution) {
    try {
      await api.updateContribution(wsId, teamId, row.id, { completed: !row.completed });
      onChange();
    } catch {
      /* the row simply stays as it was */
    }
  }

  const byMember = data.contribution_rollup;

  return (
    <Card title="Team contributions">
      <p className="muted">
        The project is shared, but the work is individual. Judges ask each member what{" "}
        <em>they</em> did — this is where that answer comes from.
      </p>

      {byMember.length > 0 && (
        <div className="team-grid" style={{ margin: "0.9rem 0" }}>
          {byMember.map((row) => (
            <div className="member" key={row.user_id}>
              <div className="member__name">
                <strong>{row.name}</strong>
              </div>
              <div className="member__stats">
                {row.completed}/{row.tasks} complete
                {row.hours > 0 && ` · ${row.hours}h`}
              </div>
            </div>
          ))}
        </div>
      )}

      {data.contributions.length === 0 && (
        <p className="muted">Nothing logged yet.</p>
      )}

      {data.contributions.map((row) => (
        <div className="contrib" key={row.id}>
          <div className="contrib__who">{row.user_name}</div>
          <div>
            <div className="contrib__task">
              {row.task}
              {row.requested_by_name && (
                <span className="faint"> · requested by {row.requested_by_name}</span>
              )}
            </div>
            {row.description && <div className="contrib__detail">{row.description}</div>}
          </div>
          <div className="contrib__meta">
            {row.hours ? `${row.hours}h · ` : ""}
            {formatDate(row.contribution_date)}
            {" · "}
            {row.user_id === currentUserId || data.can_manage_team ? (
              <button className="btn btn--quiet btn--small" onClick={() => toggle(row)}>
                {row.completed ? "Done" : "Mark done"}
              </button>
            ) : (
              <span>{row.completed ? "Done" : "Open"}</span>
            )}
          </div>
        </div>
      ))}

      {canLog && (
        <form className="divided-top" onSubmit={submit}>
          <div className="row" style={{ gap: "0.5rem", alignItems: "flex-end" }}>
            <label className="field" style={{ flex: "1 1 200px", marginBottom: 0 }}>
              <span>What you did</span>
              <input
                className="input"
                value={task}
                onChange={(e) => setTask(e.target.value)}
                placeholder="Data analysis"
              />
            </label>
            <label className="field" style={{ flex: "2 1 260px", marginBottom: 0 }}>
              <span>Detail</span>
              <input
                className="input"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Wrote the pipeline that extracts the features"
              />
            </label>
            <label className="field" style={{ flex: "0 0 90px", marginBottom: 0 }}>
              <span>Hours</span>
              <input
                className="input"
                value={hours}
                onChange={(e) => setHours(e.target.value)}
                inputMode="decimal"
                placeholder="4"
              />
            </label>
            <button className="btn btn--small" disabled={busy || task.trim().length < 2}>
              Log
            </button>
          </div>
          {error && <div className="mt-3"><ErrorNote message={error} /></div>}
        </form>
      )}
    </Card>
  );
}
