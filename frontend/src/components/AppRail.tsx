import { NavLink, useNavigate } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "../state/auth";
import { isOversight, useWorkspace } from "../state/workspace";
import WorkspaceSwitcher from "./WorkspaceSwitcher";

/**
 * The one navigation rail, used by every authenticated shell.
 *
 * Context sensitivity is the whole job here. Workspace links resolve against
 * the currently selected workspace, and the Prepare group resolves against the
 * project you are currently inside — when there is no project open those links
 * would go nowhere, so they render as disabled hints rather than dead ends.
 *
 * The rail is a convenience, not a security boundary: every link it hides is
 * also refused by the backend.
 */

interface Props {
  /** Set when the shell is rendered inside a project, so Prepare can resolve. */
  projectId?: number;
  /** Sub-line under the wordmark. */
  subtitle?: string;
  /** Extra group rendered first, e.g. the per-project section list. */
  children?: ReactNode;
}

function Group({ heading, children }: { heading: string; children: ReactNode }) {
  return (
    <div className="rail__group">
      <div className="rail__heading">{heading}</div>
      {children}
    </div>
  );
}

function Link({ to, label, end }: { to: string; label: string; end?: boolean }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) => `rail__link${isActive ? " is-active" : ""}`}
    >
      {label}
    </NavLink>
  );
}

/** A Prepare link with no project to point at. Explains itself on hover. */
function Unavailable({ label }: { label: string }) {
  return (
    <span className="rail__link is-disabled" title="Open a project to use this">
      {label}
    </span>
  );
}

export default function AppRail({ projectId, subtitle, children }: Props) {
  const { user, signOut } = useAuth();
  const { current } = useWorkspace();
  const navigate = useNavigate();
  const oversight = isOversight(current?.my_role);
  const ws = current?.id;

  return (
    <nav className="rail">
      <NavLink
        to="/projects"
        className="rail__brand"
        style={{ textDecoration: "none", color: "inherit" }}
      >
        Research Coach
        <span>{subtitle ?? (oversight ? "Workspace overview" : "Your research")}</span>
      </NavLink>

      <WorkspaceSwitcher />

      {children}

      <Group heading="Research">
        <Link to="/projects" label="Home" end />
        <Link to="/projects" label="My projects" />
        {projectId ? (
          <Link to={`/projects/${projectId}/analysis`} label="Research Coach" />
        ) : (
          <Unavailable label="Research Coach" />
        )}
        <Link
          to={projectId ? `/projects/${projectId}/assistant` : "/assistant"}
          label="AI Research Assistant"
        />
      </Group>

      {ws && !current?.is_personal && (
        <Group heading="Workspace">
          <Link to={`/workspaces/${ws}`} label="Workspace dashboard" end />
          <Link to={`/workspaces/${ws}/projects`} label="Projects" />
          <Link to={`/workspaces/${ws}/teams`} label="Teams" />
          <Link to={`/workspaces/${ws}/members`} label="Members" />
          <Link to={`/workspaces/${ws}/activity`} label="Activity" />
          {current?.my_role === "owner" && (
            <Link to={`/workspaces/${ws}/settings`} label="Settings" />
          )}
        </Group>
      )}

      <Group heading="Learn">
        <Link to="/library" label="Research Library" />
        <Link to="/winning-projects" label="Winning Projects" />
        <Link to="/isef" label="ISEF Project Explorer" />
      </Group>

      <Group heading="Prepare">
        {projectId ? (
          <>
            <Link to={`/projects/${projectId}/timeline`} label="Timeline" />
            <Link to={`/projects/${projectId}/poster`} label="Poster Coach" />
            <Link to={`/projects/${projectId}/judging`} label="Judge Practice" />
          </>
        ) : (
          <>
            <Unavailable label="Timeline" />
            <Unavailable label="Poster Coach" />
            <Unavailable label="Judge Practice" />
          </>
        )}
      </Group>

      <Group heading="Connect">
        <Link to="/outreach" label="Research Outreach" />
      </Group>

      <div className="rail__foot">
        <div>{user?.name}</div>
        <button
          className="btn btn--quiet btn--small"
          style={{ marginTop: "0.4rem" }}
          onClick={() => {
            signOut();
            navigate("/");
          }}
        >
          Sign out
        </button>
      </div>
    </nav>
  );
}
