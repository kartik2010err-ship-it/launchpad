import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../api/useAsync";
import type { WorkspaceProjectRow } from "../api/types";
import { ErrorNote, Loading, formatDate, humanise } from "../components/ui";
import {
  Column,
  DataTable,
  Meter,
  StatusPill,
  humanStage,
} from "../components/workspace-ui";
import { NOVELTY_COPY, Pill } from "../components/ui";

const STATUSES = ["on_track", "needs_attention", "at_risk", "blocked", "complete"];
const APPROVALS = ["not_started", "required", "cleared", "complete"];

export default function WorkspaceProjects() {
  const { workspaceId } = useParams();
  const id = Number(workspaceId);
  const navigate = useNavigate();
  const { data, error, loading } = useAsync(() => api.workspaceProjects(id), [id]);

  const [search, setSearch] = useState("");
  const [stage, setStage] = useState("");
  const [status, setStatus] = useState("");
  const [mentor, setMentor] = useState("");
  const [category, setCategory] = useState("");
  const [competition, setCompetition] = useState("");
  const [approval, setApproval] = useState("");

  const rows = data ?? [];

  // Filtering runs client-side: the table is a few dozen rows and instant
  // feedback beats a round trip per keystroke.
  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return rows.filter(
      (r) =>
        (!needle ||
          r.title.toLowerCase().includes(needle) ||
          r.owner_name.toLowerCase().includes(needle) ||
          r.member_names.some((n) => n.toLowerCase().includes(needle)) ||
          r.current_question.toLowerCase().includes(needle)) &&
        (!stage || r.stage === stage) &&
        (!status || r.status === status) &&
        (!mentor || String(r.mentor_id ?? "none") === mentor) &&
        (!category || r.category === category) &&
        (!competition || (r.competition_name ?? "") === competition) &&
        (!approval || r.approval_status === approval),
    );
  }, [rows, search, stage, status, mentor, category, competition, approval]);

  const unique = <K extends keyof WorkspaceProjectRow>(key: K) =>
    Array.from(new Set(rows.map((r) => r[key]).filter(Boolean))) as string[];

  const mentors = useMemo(() => {
    const map = new Map<string, string>();
    rows.forEach((r) => {
      if (r.mentor_id) map.set(String(r.mentor_id), r.mentor_name ?? "Mentor");
    });
    return Array.from(map.entries());
  }, [rows]);

  const columns: Column<WorkspaceProjectRow>[] = [
    {
      key: "type",
      header: "Type",
      sortValue: (r) => r.owner_kind,
      render: (r) => (
        <Pill tone={r.owner_kind === "team" ? "ok" : "neutral"}>
          {r.owner_kind === "team" ? "Team" : "Individual"}
        </Pill>
      ),
    },
    {
      key: "members",
      header: "Members",
      // Team projects sort under the team name; individual ones under the
      // student. Same column, because to a workspace lead they are the same
      // question: whose project is this?
      sortValue: (r) => r.owner_name,
      render: (r) => (
        <>
          <div className="dt__primary">{r.owner_name}</div>
          <div className="dt__sub">
            {r.owner_kind === "team" && r.member_names.length > 0
              ? r.member_names.join(", ")
              : humanise(r.category)}
          </div>
        </>
      ),
    },
    {
      key: "project",
      header: "Project",
      sortValue: (r) => r.title,
      render: (r) => (
        <>
          <div className="dt__primary">{r.title}</div>
          <div className="dt__sub">
            {r.competition_name
              ? `${r.competition_name.split("(")[0].trim()}`
              : "No competition set"}
            {r.days_to_competition !== null ? ` · ${r.days_to_competition}d out` : ""}
          </div>
        </>
      ),
    },
    {
      key: "stage",
      header: "Stage",
      sortValue: (r) => r.stage,
      render: (r) => <span style={{ fontSize: "0.82rem" }}>{humanStage(r.stage)}</span>,
    },
    {
      key: "readiness",
      header: "Readiness",
      width: "150px",
      sortValue: (r) => r.readiness,
      render: (r) => <Meter percent={r.readiness} />,
    },
    {
      key: "novelty",
      header: "Novelty",
      sortValue: (r) => r.novelty_status,
      render: (r) =>
        r.novelty_status ? (
          <Pill tone={NOVELTY_COPY[r.novelty_status].tone}>
            {NOVELTY_COPY[r.novelty_status].label}
          </Pill>
        ) : (
          <span className="dt__sub">—</span>
        ),
    },
    {
      key: "mentor",
      header: "Mentor",
      sortValue: (r) => r.mentor_name ?? "zzz",
      render: (r) =>
        r.mentor_name ? (
          <span style={{ fontSize: "0.82rem" }}>{r.mentor_name}</span>
        ) : (
          <span className="pill pill--warn">Unassigned</span>
        ),
    },
    {
      key: "deadline",
      header: "Next deadline",
      sortValue: (r) => r.next_deadline,
      render: (r) =>
        r.next_deadline ? (
          <>
            <div className="num" style={{ fontSize: "0.8rem" }}>
              {formatDate(r.next_deadline)}
            </div>
            <div className="dt__sub">{r.next_task}</div>
          </>
        ) : (
          <span className="dt__sub">—</span>
        ),
    },
    {
      key: "status",
      header: "Status",
      sortValue: (r) => r.status,
      render: (r) => (
        <>
          <StatusPill status={r.status} />
          {(r.blockers[0] ?? r.reasons[0]) && (
            <div className="dt__sub" style={{ marginTop: 2 }}>
              {r.blockers[0] ?? r.reasons[0]}
            </div>
          )}
        </>
      ),
    },
  ];

  if (loading) return <Loading what="Loading projects" />;
  if (error) return <ErrorNote message={error} />;

  return (
    <div className="stack">
      <header className="page-head">
        <h1>Projects</h1>
        <p>
          {filtered.length} of {rows.length} project{rows.length === 1 ? "" : "s"} in this
          workspace.
        </p>
      </header>

      <div className="filters">
        <input
          type="search"
          placeholder="Search student, title or question"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Any status</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {humanise(s)}
            </option>
          ))}
        </select>
        <select value={stage} onChange={(e) => setStage(e.target.value)}>
          <option value="">Any stage</option>
          {unique("stage").map((s) => (
            <option key={s} value={s}>
              {humanStage(s)}
            </option>
          ))}
        </select>
        <select value={mentor} onChange={(e) => setMentor(e.target.value)}>
          <option value="">Any mentor</option>
          <option value="none">Unassigned</option>
          {mentors.map(([mid, name]) => (
            <option key={mid} value={mid}>
              {name}
            </option>
          ))}
        </select>
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">Any category</option>
          {unique("category").map((c) => (
            <option key={c} value={c}>
              {humanise(c)}
            </option>
          ))}
        </select>
        <select value={competition} onChange={(e) => setCompetition(e.target.value)}>
          <option value="">Any competition</option>
          {unique("competition_name").map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <select value={approval} onChange={(e) => setApproval(e.target.value)}>
          <option value="">Any approval state</option>
          {APPROVALS.map((a) => (
            <option key={a} value={a}>
              {humanise(a)}
            </option>
          ))}
        </select>
      </div>

      <DataTable
        rows={filtered}
        columns={columns}
        rowKey={(r) => r.project_id}
        onRowClick={(r) => navigate(`/workspaces/${id}/projects/${r.project_id}`)}
        isFlagged={(r) => r.status === "at_risk" || r.status === "blocked"}
        empty={
          <div className="empty">
            <h3>No projects match</h3>
            <p>
              {rows.length === 0
                ? "Nobody has started a project in this workspace yet."
                : "Try clearing a filter."}
            </p>
          </div>
        }
      />
    </div>
  );
}
