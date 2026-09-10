import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../api/useAsync";
import { useAuth } from "../state/auth";
import { useWorkspace } from "../state/workspace";
import AppRail from "../components/AppRail";
import { Card, ErrorNote, Loading, Pill, formatDate, humanise } from "../components/ui";
import { StatusPill } from "../components/workspace-ui";

/**
 * The student's home. Scoped to the selected workspace so "my projects" means
 * the same thing as everything else in the sidebar.
 */
export default function Projects() {
  const { user } = useAuth();
  const { current, loading: wsLoading } = useWorkspace();
  const navigate = useNavigate();
  const { data, error, loading } = useAsync(
    () => (current ? api.listProjects(current.id) : Promise.resolve([])),
    [current?.id],
  );

  return (
    <div className="shell">
      <AppRail />

      <main className="main">
        <div className="main__inner stack">
          <header className="page-head">
            <div className="row row--between">
              <div>
                <h1>Your projects</h1>
                <p>
                  {current
                    ? `In ${current.name}.`
                    : "Pick or create a workspace to get started."}
                </p>
              </div>
              <button className="btn btn--small" onClick={() => navigate("/projects/new")}>
                Start a project
              </button>
            </div>
          </header>

          {(loading || wsLoading) && <Loading />}
          {error && <ErrorNote message={error} />}

          {data?.length === 0 && !loading && (
            <div className="empty">
              <h3>No projects here yet</h3>
              <p>
                Start with whatever you have, even one vague sentence. The first thing this tool
                does is interview you about it.
              </p>
              <button className="btn" onClick={() => navigate("/projects/new")}>
                Start a project
              </button>
            </div>
          )}

          {data?.map((project) => (
            <Link className="plain-link"
              key={project.id}
              to={`/projects/${project.id}`}
            >
              <Card
                title={project.title}
                aside={
                  <div className="row gap-2">
                    <StatusPill status={project.status} />
                    <Pill>{humanise(project.stage)}</Pill>
                  </div>
                }
              >
                <div className="question-hero mb-3">
                  <q className="text-lg">{project.current_question}</q>
                </div>
                <div className="row faint">
                  <span>{humanise(project.category)}</span>
                  <span>·</span>
                  <span>Grade {project.grade_level}</span>
                  <span>·</span>
                  <span>{humanise(project.project_type)}</span>
                  <span>·</span>
                  <span>Updated {formatDate(project.updated_at)}</span>
                  {project.owner_kind === "team" && (
                    <>
                      <span>·</span>
                      <span>team project</span>
                    </>
                  )}
                  {project.owner_kind === "individual" && project.owner_id !== user?.id && (
                    <>
                      <span>·</span>
                      <span>shared with you</span>
                    </>
                  )}
                </div>
              </Card>
            </Link>
          ))}
        </div>
      </main>
    </div>
  );
}
