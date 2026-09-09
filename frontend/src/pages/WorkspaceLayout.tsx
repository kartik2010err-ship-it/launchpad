import { NavLink, Outlet, useParams } from "react-router-dom";
import { useEffect } from "react";
import { useWorkspace } from "../state/workspace";
import AppRail from "../components/AppRail";
import { Loading } from "../components/ui";

/**
 * Everything under /workspaces/:id renders inside this shell.
 *
 * Navigation lives in AppRail so the workspace, project and library shells all
 * present the same map of the product.
 */
export default function WorkspaceLayout() {
  const { workspaceId } = useParams();
  const id = Number(workspaceId);
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

  return (
    <div className="shell">
      <AppRail subtitle={current.name} />
      <main className="main">
        <div className="main__inner">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
