import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../api/useAsync";
import { useAuth } from "../state/auth";
import { isOversight, useWorkspace } from "../state/workspace";
import WorkspaceSwitcher from "../components/WorkspaceSwitcher";
import { Card, ErrorNote, Loading, Pill, formatDate, humanise } from "../components/ui";
import { StatusPill } from "../components/workspace-ui";

/**
 * The student's home. Scoped to the selected workspace so "my projects" means
 * the same thing as everything else in the sidebar.
 */
export default function Projects() {
  const { user, signOut } = useAuth();
  const { current, loading: wsLoading } = useWorkspace();
  const navigate = useNavigate();
  const { data, error, loading } = useAsync(
    () => (current ? api.listProjects(current.id) : Promise.resolve([])),
    [current?.id],
  );

  const oversight = isOversight(current?.my_role);

  return (
    <div className="shell">
      <nav className="rail">
        <div className="rail__brand">
          Research Coach
          <span>Turn an idea into a question you can defend</span>
        </div>

        <WorkspaceSwitcher />

        {current && (
          <div className="rail__group">
            <NavLinks workspaceId={current.id} oversight={oversight} />
          </div>
        )}

        <div className="rail__foot">
          <div>{user?.name}</div>
          <button className="btn btn--quiet btn--small" style={{ marginTop: "0.4rem" }} onClick={signOut}>
            Sign out
          </button>
        </div>
      </nav>

      <main className="main">
        <div className="main__inner stack">
          <header className="page-head">
            <div className="row" style={{ justifyContent: "space-between" }}>
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
            <Link
              key={project.id}
              to={`/projects/${project.id}`}
              style={{ textDecoration: "none", color: "inherit" }}
            >
              <Card
                title={project.title}
                aside={
                  <div className="row" style={{ gap: "0.4rem" }}>
                    <StatusPill status={project.status} />
                    <Pill>{humanise(project.stage)}</Pill>
                  </div>
                }
              >
                <div className="question-hero" style={{ marginBottom: "0.7rem" }}>
                  <q style={{ fontSize: "1.1rem" }}>{project.current_question}</q>
                </div>
                <div className="row faint">
                  <span>{humanise(project.category)}</span>
                  <span>·</span>
                  <span>Grade {project.grade_level}</span>
                  <span>·</span>
                  <span>{humanise(project.project_type)}</span>
                  <span>·</span>
                  <span>Updated {formatDate(project.updated_at)}</span>
                  {project.owner_id !== user?.id && (
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

function NavLinks({ workspaceId, oversight }: { workspaceId: number; oversight: boolean }) {
  return (
    <>
      <div className="rail__heading">Workspace</div>
      <Link className="rail__link" to={`/workspaces/${workspaceId}`}>
        Dashboard
      </Link>
      <Link className="rail__link" to={`/workspaces/${workspaceId}/projects`}>
        {oversight ? "All projects" : "Shared projects"}
      </Link>
      <Link className="rail__link" to={`/workspaces/${workspaceId}/members`}>
        Members
      </Link>
      <Link className="rail__link" to={`/workspaces/${workspaceId}/activity`}>
        Activity
      </Link>
    </>
  );
}
