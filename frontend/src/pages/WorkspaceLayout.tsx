import { NavLink, Outlet, useParams } from "react-router-dom";
import { useEffect } from "react";
import { useAuth } from "../state/auth";
import { isOversight, useWorkspace } from "../state/workspace";
import WorkspaceSwitcher from "../components/WorkspaceSwitcher";
import { Loading } from "../components/ui";

/**
 * Everything under /workspaces/:id renders inside this shell.
 *
 * The nav is filtered by the caller's role *in this workspace* — but that is a
 * convenience, not a security boundary. The backend rejects the requests too.
 */
export default function WorkspaceLayout() {
  const { workspaceId } = useParams();
  const id = Number(workspaceId);
  const { user, signOut } = useAuth();
  const { current, workspaces, select, loading } = useWorkspace();

  useEffect(() => {
    if (id && current?.id !== id && workspaces.some((w) => w.id === id)) {
      select(id);
    }
  }, [id, current?.id, workspaces, select]);

  if (loading && !current) return <Loading what="Loading workspace" />;
  if (!current) {
    return (
      <div className="main">
        <div className="main__inner">
          <div className="empty">
            <h3>Workspace not available</h3>
            <p>You are not a member of this workspace, or it has been archived.</p>
            <NavLink className="btn" to="/projects">
              Back to your projects
            </NavLink>
          </div>
        </div>
      </div>
    );
  }

  const oversight = isOversight(current.my_role);
  const links: [string, string][] = [
    ["", "Dashboard"],
    ["projects", "Projects"],
    ["members", "Members"],
    ["activity", "Activity"],
  ];
  if (current.my_role === "owner") links.push(["settings", "Settings"]);

  return (
    <div className="shell">
      <nav className="rail">
        <NavLink to="/projects" className="rail__brand" style={{ textDecoration: "none", color: "inherit" }}>
          Research Coach
          <span>{oversight ? "Workspace overview" : "Your workspace"}</span>
        </NavLink>

        <WorkspaceSwitcher />

        <div className="rail__group">
          {links.map(([path, label]) => (
            <NavLink
              key={path}
              end={path === ""}
              to={path ? `/workspaces/${current.id}/${path}` : `/workspaces/${current.id}`}
              className={({ isActive }) => `rail__link${isActive ? " is-active" : ""}`}
            >
              {label}
            </NavLink>
          ))}
        </div>

        <div className="rail__group">
          <div className="rail__heading">Mine</div>
          <NavLink to="/projects" className="rail__link">
            My projects
          </NavLink>
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
          <Outlet />
        </div>
      </main>
    </div>
  );
}
