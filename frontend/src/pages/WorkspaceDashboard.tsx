import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../api/useAsync";
import { Card, ErrorNote, Loading, formatDate } from "../components/ui";
import {
  ActivityFeed,
  AttentionQueue,
  Meter,
  Stat,
  humanStage,
} from "../components/workspace-ui";
import { isOversight } from "../state/workspace";

/**
 * Answers three questions on sight: who is doing well, who needs help, and
 * what deserves attention today. Stats first, attention queue second, because
 * an advisor opening this at 7am wants the second one.
 */
export default function WorkspaceDashboard() {
  const { workspaceId } = useParams();
  const id = Number(workspaceId);
  const navigate = useNavigate();
  const { data, error, loading } = useAsync(() => api.workspaceDashboard(id), [id]);

  if (loading) return <Loading what="Loading workspace" />;
  if (error) return <ErrorNote message={error} />;
  if (!data) return null;

  const { workspace, stats, attention, upcoming_deadlines, mentors, recent_activity } = data;
  const oversight = isOversight(workspace.my_role);
  const openProject = (projectId: number) =>
    navigate(`/workspaces/${id}/projects/${projectId}`);

  return (
    <div className="stack">
      <header className="page-head">
        <div className="row row--between">
          <div>
            <h1>{workspace.name}</h1>
            <p>
              {workspace.organization_name ? `${workspace.organization_name} · ` : ""}
              {workspace.member_count} members · {stats.total_projects} projects
              {workspace.join_code ? ` · join code ${workspace.join_code}` : ""}
            </p>
          </div>
          <button
            className="btn btn--small"
            onClick={() => navigate(`/workspaces/${id}/projects`)}
          >
            View all projects
          </button>
        </div>
      </header>

      <div className="stat-grid">
        <Stat value={stats.active_projects} label="Active projects" tone="accent" />
        <Stat value={stats.on_track} label="On track" tone="ok" />
        <Stat value={stats.needs_attention} label="Need attention" tone="attention" />
        <Stat value={stats.at_risk} label="At risk" tone="risk" />
        <Stat value={stats.blocked} label="Blocked" tone="risk" />
        <Stat
          value={stats.average_readiness ?? "—"}
          label="Average readiness"
          hint={stats.average_readiness === null ? "no evaluations yet" : "out of 100"}
        />
      </div>

      <div className="split">
        <div className="stack">
          {oversight && (
            <section>
              <div className="section-head">
                <h2>Needs attention</h2>
                <span className="faint">
                  {attention.reduce((n, g) => n + g.projects.length, 0)} items
                </span>
              </div>
              <AttentionQueue groups={attention} onOpenProject={openProject} />
            </section>
          )}

          <Card title="Upcoming deadlines">
            {upcoming_deadlines.length === 0 ? (
              <p className="muted">No scheduled milestones yet.</p>
            ) : (
              <table className="table">
                <tbody>
                  {upcoming_deadlines.map((deadline) => (
                    <tr
                      key={`${deadline.project_id}-${deadline.due}`}
                      onClick={() => openProject(deadline.project_id)}
                      style={{ cursor: "pointer" }}
                    >
                      <td>
                        <div className="dt__primary">{deadline.label}</div>
                        <div className="dt__sub">
                          {deadline.owner_name} · {deadline.title}
                        </div>
                      </td>
                      <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                        <div className="num">{formatDate(deadline.due)}</div>
                        <div
                          className="dt__sub"
                          style={{
                            color: deadline.days_away < 0 ? "var(--status-risk)" : undefined,
                          }}
                        >
                          {deadline.days_away < 0
                            ? `${Math.abs(deadline.days_away)}d overdue`
                            : `in ${deadline.days_away}d`}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>

          <Card title="Where projects are">
            <div className="stack gap-2">
              {Object.entries(stats.by_stage)
                .sort((a, b) => b[1] - a[1])
                .map(([stage, count]) => (
                  <div key={stage} className="row gap-3">
                    <span style={{ minWidth: 170, fontSize: "0.86rem" }}>
                      {humanStage(stage)}
                    </span>
                    <div style={{ flex: 1 }}>
                      <Meter
                        percent={Math.round((count / Math.max(1, stats.total_projects)) * 100)}
                        showValue={false}
                      />
                    </div>
                    <span className="num" style={{ minWidth: 24, textAlign: "right" }}>
                      {count}
                    </span>
                  </div>
                ))}
            </div>
          </Card>
        </div>

        <div className="stack">
          <Card title="Mentors">
            {mentors.length === 0 ? (
              <p className="muted">Nobody has the mentor role here yet.</p>
            ) : (
              <table className="table">
                <tbody>
                  {mentors.map((mentor) => (
                    <tr key={mentor.user_id}>
                      <td>
                        <div className="dt__primary">{mentor.name}</div>
                        <div className="dt__sub">
                          {mentor.assigned_projects} project
                          {mentor.assigned_projects === 1 ? "" : "s"}
                          {mentor.needing_review > 0
                            ? ` · ${mentor.needing_review} awaiting reply`
                            : ""}
                        </div>
                      </td>
                      <td style={{ textAlign: "right" }}>
                        {mentor.at_risk > 0 && (
                          <span className="pill pill--warn">{mentor.at_risk} at risk</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>

          <Card title="Poster & interview readiness">
            <div className="stack gap-3">
              <div>
                <div className="faint">Poster progress (average)</div>
                <Meter percent={stats.average_poster} />
              </div>
              <div>
                <div className="faint">Interview prep (average)</div>
                <Meter percent={stats.average_interview} />
              </div>
              <div className="row faint gap-2">
                <span>{stats.awaiting_approval} awaiting approval</span>
                <span>·</span>
                <span>{stats.without_mentor} without a mentor</span>
              </div>
            </div>
          </Card>

          <Card
            title="Recent activity"
            aside={
              <a
                href={`/workspaces/${id}/activity`}
                onClick={(e) => {
                  e.preventDefault();
                  navigate(`/workspaces/${id}/activity`);
                }}
                className="faint"
              >
                See all
              </a>
            }
          >
            <ActivityFeed entries={recent_activity} />
          </Card>
        </div>
      </div>
    </div>
  );
}
