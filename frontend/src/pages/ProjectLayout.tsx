import { NavLink, Outlet, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../api/useAsync";
import AppRail from "../components/AppRail";
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

/**
 * Section 2. Twelve links in one flat list is a menu, not a workspace — the
 * student cannot tell what they have finished or what comes next. Grouped by
 * the phase of the project each tool belongs to, the same twelve links answer
 * "where am I" without anyone reading a label twice.
 *
 * Routes are unchanged. This is organisation, not a migration.
 */
const SECTION_GROUPS: { heading: string; links: [string, string][] }[] = [
  {
    heading: "Overview",
    links: [
      ["", "This week"],
      ["assistant", "Ask the Assistant"],
    ],
  },
  {
    heading: "Research",
    links: [
      ["interview", "Interview"],
      ["analysis", "Question evaluation"],
      ["novelty", "Novelty check"],
      ["refine", "Question rewrite"],
      ["plan", "Research plan"],
    ],
  },
  {
    heading: "Experiment",
    links: [["notebook", "Research notebook"]],
  },
  {
    heading: "Competition",
    links: [
      ["timeline", "Timeline"],
      ["rubric", "AzSEF rubric"],
      ["poster", "Poster"],
      ["judging", "Judge prep"],
    ],
  },
];

export default function ProjectLayout() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const { data: project, error, loading, reload } = useAsync(() => api.getProject(id), [id]);

  return (
    <div className="shell">
      <AppRail projectId={id} subtitle={project ? project.title : "Loading project"}>
        {SECTION_GROUPS.map((group) => (
          <div className="rail__group" key={group.heading}>
            <div className="rail__heading">{group.heading}</div>
            {group.links.map(([path, label]) => (
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
        ))}

        {/* A team project's roster and contribution log live on the team page,
            which is workspace-scoped — linking out beats duplicating it here. */}
        {project?.owner_team_id ? (
          <div className="rail__group">
            <div className="rail__heading">Team</div>
            <NavLink
              to={`/workspaces/${project.workspace_id}/teams/${project.owner_team_id}`}
              className={({ isActive }) => `rail__link${isActive ? " is-active" : ""}`}
            >
              Members &amp; contributions
            </NavLink>
          </div>
        ) : null}
      </AppRail>

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
