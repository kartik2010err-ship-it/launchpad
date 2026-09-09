import { useMemo, useState, type ReactNode } from "react";
import type {
  ActivityEntry,
  AttentionGroup,
  ProjectStatus,
  WorkspaceRole,
} from "../api/types";

/* ------------------------------------------------------------- statuses -- */

const STATUS_COPY: Record<ProjectStatus, string> = {
  on_track: "On track",
  needs_attention: "Needs attention",
  at_risk: "At risk",
  blocked: "Blocked",
  complete: "Complete",
};

export function StatusPill({ status }: { status: ProjectStatus }) {
  return <span className={`status status--${status}`}>{STATUS_COPY[status]}</span>;
}

const ROLE_COPY: Record<WorkspaceRole, string> = {
  owner: "Owner",
  lead: "Lead",
  mentor: "Mentor",
  member: "Member",
};

export function RoleLabel({ role }: { role: WorkspaceRole }) {
  return <span className="role-chip">{ROLE_COPY[role]}</span>;
}

/* ------------------------------------------------------------ stat card -- */

export function Stat({
  value,
  label,
  hint,
  tone,
  onClick,
}: {
  value: ReactNode;
  label: string;
  hint?: string;
  tone?: "accent" | "ok" | "attention" | "risk";
  onClick?: () => void;
}) {
  return (
    <div
      className={`stat${tone ? ` stat--${tone}` : ""}`}
      onClick={onClick}
      style={onClick ? { cursor: "pointer" } : undefined}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={(e) => onClick && e.key === "Enter" && onClick()}
    >
      <span className="stat__value">{value}</span>
      <span className="stat__label">{label}</span>
      {hint && <span className="stat__hint">{hint}</span>}
    </div>
  );
}

/* ---------------------------------------------------------------- meter -- */

export function Meter({
  percent,
  suffix = "%",
  showValue = true,
}: {
  percent: number | null;
  suffix?: string;
  showValue?: boolean;
}) {
  if (percent === null) {
    return <span className="dt__sub">not scored</span>;
  }
  const tone =
    percent >= 68 ? "ok" : percent >= 45 ? "attention" : "risk";
  return (
    <div className="meter">
      <div className="meter__track">
        <div
          className={`meter__fill meter__fill--${tone}`}
          style={{ width: `${Math.max(2, Math.min(100, percent))}%` }}
        />
      </div>
      {showValue && (
        <span className="meter__value">
          {percent}
          {suffix}
        </span>
      )}
    </div>
  );
}

/* ------------------------------------------------------------ data table -- */

export interface Column<T> {
  key: string;
  header: string;
  /** Value used for sorting; falls back to the rendered string. */
  sortValue?: (row: T) => string | number | null;
  render: (row: T) => ReactNode;
  width?: string;
}

export function DataTable<T>({
  rows,
  columns,
  rowKey,
  onRowClick,
  isFlagged,
  empty,
}: {
  rows: T[];
  columns: Column<T>[];
  rowKey: (row: T) => string | number;
  onRowClick?: (row: T) => void;
  isFlagged?: (row: T) => boolean;
  empty?: ReactNode;
}) {
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 } | null>(null);

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const column = columns.find((c) => c.key === sort.key);
    if (!column?.sortValue) return rows;
    return [...rows].sort((a, b) => {
      const av = column.sortValue!(a);
      const bv = column.sortValue!(b);
      // Nulls always sink, whichever direction is active.
      if (av === null && bv === null) return 0;
      if (av === null) return 1;
      if (bv === null) return -1;
      if (av === bv) return 0;
      return (av > bv ? 1 : -1) * sort.dir;
    });
  }, [rows, sort, columns]);

  if (rows.length === 0 && empty) return <>{empty}</>;

  return (
    <div className="table-wrap">
      <table className="dt">
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                style={column.width ? { width: column.width } : undefined}
                className={sort?.key === column.key ? "is-sorted" : undefined}
                onClick={() =>
                  column.sortValue &&
                  setSort((prev) =>
                    prev?.key === column.key
                      ? { key: column.key, dir: prev.dir === 1 ? -1 : 1 }
                      : { key: column.key, dir: 1 },
                  )
                }
              >
                {column.header}
                {sort?.key === column.key ? (sort.dir === 1 ? " ↑" : " ↓") : ""}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr
              key={rowKey(row)}
              onClick={() => onRowClick?.(row)}
              className={isFlagged?.(row) ? "is-flagged" : undefined}
            >
              {columns.map((column) => (
                <td key={column.key}>{column.render(row)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ----------------------------------------------------------- attention -- */

export function AttentionQueue({
  groups,
  onOpenProject,
}: {
  groups: AttentionGroup[];
  onOpenProject?: (projectId: number) => void;
}) {
  if (groups.length === 0) {
    return (
      <div className="empty">
        <h3>Nothing needs you right now</h3>
        <p>No overdue work, no unresolved flags, nobody has gone quiet.</p>
      </div>
    );
  }
  return (
    <div className="attention">
      {groups.map((group) => (
        <div key={group.key} className={`attention__group attention__group--${group.severity}`}>
          <div className="attention__label">{group.label}</div>
          <ul className="attention__items">
            {group.projects.slice(0, 5).map((project) => (
              <li key={project.project_id}>
                <a
                  href="#"
                  onClick={(e) => {
                    e.preventDefault();
                    onOpenProject?.(project.project_id);
                  }}
                >
                  {project.owner_name}
                </a>
                <span>— {project.detail}</span>
              </li>
            ))}
            {group.projects.length > 5 && (
              <li className="faint">and {group.projects.length - 5} more</li>
            )}
          </ul>
        </div>
      ))}
    </div>
  );
}

/* ---------------------------------------------------------------- feed -- */

export function ActivityFeed({ entries }: { entries: ActivityEntry[] }) {
  if (entries.length === 0) {
    return <p className="muted">No activity yet.</p>;
  }
  return (
    <div className="feed">
      {entries.map((entry) => (
        <div key={entry.id} className="feed__item">
          <span className={`feed__dot feed__dot--${entry.kind}`} />
          <div className="feed__body">
            <div className="feed__text">{entry.summary}</div>
            <div className="feed__meta">
              {entry.project_title ? `${entry.project_title} · ` : ""}
              {relativeTime(entry.created_at)}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  const minutes = Math.round((Date.now() - then) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function humanStage(stage: string): string {
  return stage.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}
