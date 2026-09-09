import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useWorkspace } from "../state/workspace";
import { RoleLabel } from "./workspace-ui";

function initials(name: string): string {
  const words = name.split(/\s+/).filter(Boolean);
  return ((words[0]?.[0] ?? "") + (words[1]?.[0] ?? "")).toUpperCase() || "W";
}

/**
 * The workspace selector. Deliberately the first thing in the sidebar: which
 * workspace you are in changes what every screen below it means.
 */
export default function WorkspaceSwitcher() {
  const { workspaces, current, select } = useWorkspace();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  if (!current) return null;

  const shared = workspaces.filter((w) => !w.is_personal);
  const personal = workspaces.filter((w) => w.is_personal);

  return (
    <div className="switcher" ref={ref}>
      <button className="switcher__button" onClick={() => setOpen((v) => !v)}>
        <span className="switcher__mark">{initials(current.name)}</span>
        <span className="switcher__text">
          <span className="switcher__name">{current.name}</span>
          <span className="switcher__meta">
            {current.member_count} member{current.member_count === 1 ? "" : "s"} ·{" "}
            {current.my_role}
          </span>
        </span>
        <span className="faint">▾</span>
      </button>

      {open && (
        <div className="switcher__menu">
          {shared.length > 0 && <div className="switcher__group">Shared workspaces</div>}
          {shared.map((workspace) => (
            <button
              key={workspace.id}
              className={`switcher__item${workspace.id === current.id ? " is-current" : ""}`}
              onClick={() => {
                select(workspace.id);
                setOpen(false);
                navigate(`/workspaces/${workspace.id}`);
              }}
            >
              <span className="switcher__name">{workspace.name}</span>
              <RoleLabel role={workspace.my_role} />
            </button>
          ))}

          {personal.length > 0 && <div className="switcher__group">Personal</div>}
          {personal.map((workspace) => (
            <button
              key={workspace.id}
              className={`switcher__item${workspace.id === current.id ? " is-current" : ""}`}
              onClick={() => {
                select(workspace.id);
                setOpen(false);
                navigate(`/workspaces/${workspace.id}`);
              }}
            >
              <span className="switcher__name">{workspace.name}</span>
              <RoleLabel role={workspace.my_role} />
            </button>
          ))}

          <div className="switcher__group">Add</div>
          <button
            className="switcher__item"
            onClick={() => {
              setOpen(false);
              navigate("/workspaces/new");
            }}
          >
            <span>Create a workspace</span>
          </button>
          <button
            className="switcher__item"
            onClick={() => {
              setOpen(false);
              navigate("/workspaces/join");
            }}
          >
            <span>Join with a code</span>
          </button>
        </div>
      )}
    </div>
  );
}
