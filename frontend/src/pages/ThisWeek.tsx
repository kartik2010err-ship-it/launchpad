import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../api/useAsync";
import { useProject } from "./ProjectLayout";
import QuestionHero from "../components/QuestionHero";
import MentorThread from "../components/MentorThread";
import {
  Callout,
  Card,
  ErrorNote,
  Gauge,
  Loading,
  Pill,
  SOURCE_COPY,
  formatDate,
  humanise,
} from "../components/ui";

export default function ThisWeek() {
  const { project } = useProject();
  const week = useAsync(() => api.thisWeek(project.id), [project.id]);
  const readiness = useAsync(() => api.readiness(project.id), [project.id]);

  return (
    <div className="stack">
      <header className="page-head">
        <h1>{project.title}</h1>
      </header>

      <QuestionHero project={project} />

      {readiness.data && (
        <Card title="Readiness by area" aside={<span className="num muted">{readiness.data.overall}% overall</span>}>
          <div className="stack" style={{ gap: "0.8rem" }}>
            {readiness.data.areas.map((area) => (
              <div key={area.key}>
                <Gauge label={area.label} value={area.percent} suffix="%" />
                <div className="faint">{area.note}</div>
              </div>
            ))}
          </div>
          <p className="faint" style={{ marginTop: "0.9rem", marginBottom: 0 }}>
            {readiness.data.disclaimer}
          </p>
        </Card>
      )}

      {week.loading && <Loading what="Working out this week" />}
      {week.error && <ErrorNote message={week.error} />}

      {week.data && (
        <>
          {week.data.upcoming_deadline && (
            <Card sunk>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <span>
                  Next deadline <strong>{formatDate(week.data.upcoming_deadline)}</strong>
                </span>
                <span className="num">
                  {week.data.days_remaining} days left · {week.data.completion_percent}% of tasks done
                </span>
              </div>
            </Card>
          )}

          {week.data.risk_notes.map((note, i) => (
            <Callout key={i} tone="warn" title="Worth acting on now">
              <p>{note}</p>
            </Callout>
          ))}

          {week.data.blockers.length > 0 && (
            <Callout tone="flag" title="Blocked">
              <ul className="tight-list">
                {week.data.blockers.map((task) => (
                  <li key={task.id}>
                    {task.title} — {task.ai_note ?? "waiting on something upstream"}
                  </li>
                ))}
              </ul>
            </Callout>
          )}

          <Card
            title="Do these this week"
            aside={
              <Link className="btn btn--quiet btn--small" to={`/projects/${project.id}/timeline`}>
                Full timeline
              </Link>
            }
          >
            {week.data.priorities.length === 0 ? (
              <p className="muted">
                No schedule yet. Generate a timeline and this turns into a week-by-week list.
              </p>
            ) : (
              <div>
                {week.data.priorities.map((task) => (
                  <div key={task.id} className="task">
                    <div className="task__body">
                      <div className="task__title">{task.title}</div>
                      {task.description && <div className="faint">{task.description}</div>}
                      <div className="task__meta">
                        <Pill tone={task.priority === "critical" ? "flag" : task.priority === "high" ? "warn" : "neutral"}>
                          {humanise(task.priority)}
                        </Pill>
                        <Pill tone={SOURCE_COPY[task.requirement_source].tone}>
                          {SOURCE_COPY[task.requirement_source].label}
                        </Pill>
                        <span className="faint num">
                          due {formatDate(task.due_date)} · {task.estimated_hours}h
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <MentorThread projectId={project.id} />
        </>
      )}
    </div>
  );
}
