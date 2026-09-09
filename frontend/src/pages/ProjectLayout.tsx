import { NavLink, Outlet, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../api/useAsync";
import { useAuth } from "../state/auth";
import { ErrorNote, Loading } from "../components/ui";
import { createContext, useContext } from "react";
import type { Project } from "../api/types";

interface ProjectContext {
  project: Project;
  reload: () => void;
}

const Ctx = createContext<ProjectContext | null>(null);

export function useProject(): ProjectContext {
  const value = useContext(Ctx);
  if (!value) throw new Error("useProject must be used inside ProjectLayout");
  return value;
}

const SECTIONS: [string, string][] = [
  ["", "This week"],
  ["interview", "Interview"],
  ["analysis", "Readiness"],
  ["rubric", "AzSEF rubric"],
  ["novelty", "Novelty check"],
  ["refine", "Question rewrite"],
  ["plan", "Research plan"],
  ["timeline", "Timeline"],
  ["poster", "Poster"],
  ["judging", "Judge prep"],
  ["notebook", "Notebook"],
];

export default function ProjectLayout() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const { user, signOut } = useAuth();
  const { data: project, error, loading, reload } = useAsync(() => api.getProject(id), [id]);

  return (
    <div className="shell">
      <nav className="rail">
        <NavLink to="/projects" className="rail__brand" style={{ textDecoration: "none", color: "inherit" }}>
          Research Coach
          <span>{project ? project.title : "Loading project"}</span>
        </NavLink>

        <div className="rail__group">
          <div className="rail__heading">Project</div>
          {SECTIONS.map(([path, label]) => (
            <NavLink
              key={path}
              end={path === ""}
              to={path ? `/projects/${id}/${path}` : `/projects/${id}`}
              className={({ isActive }) => `rail__link${isActive ? " is-active" : ""}`}
            >
              {label}
            </NavLink>
          ))}
        </div>

        <div className="rail__group">
          <div className="rail__heading">Elsewhere</div>
          <NavLink to="/projects" className="rail__link">
            All projects
          </NavLink>
          {user?.role === "mentor" && (
            <NavLink to="/mentor" className="rail__link">
              Mentor dashboard
            </NavLink>
          )}
        </div>

        <div className="rail__foot">
          <div>{user?.name}</div>
          <button className="btn btn--quiet btn--small" style={{ marginTop: "0.4rem" }} onClick={signOut}>
            Sign out
          </button>
        </div>
      </nav>

      <main className="main">
        <div className="main__inner">
          {loading && <Loading what="Loading project" />}
          {error && <ErrorNote message={error} />}
          {project && (
            <Ctx.Provider value={{ project, reload }}>
              <Outlet />
            </Ctx.Provider>
          )}
        </div>
      </main>
    </div>
  );
}
