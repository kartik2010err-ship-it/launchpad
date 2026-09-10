import { useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../api/useAsync";
import type { WorkspaceMember, WorkspaceRole } from "../api/types";
import { Callout, Card, ErrorNote, Loading, formatDate } from "../components/ui";
import { Column, DataTable, RoleLabel } from "../components/workspace-ui";
import { useWorkspace } from "../state/workspace";

const ROLES: WorkspaceRole[] = ["owner", "lead", "mentor", "member"];

const ROLE_HELP: Record<WorkspaceRole, string> = {
  owner: "Manages settings, members and roles.",
  lead: "Sees every project, leaves feedback, assigns mentors.",
  mentor: "Sees assigned projects and reviews them.",
  member: "Works on their own projects.",
};

export default function WorkspaceMembers() {
  const { workspaceId } = useParams();
  const id = Number(workspaceId);
  const { current, reload: reloadWorkspaces } = useWorkspace();
  const detail = useAsync(() => api.workspace(id), [id]);
  const { data, error, loading, reload } = useAsync(() => api.members(id), [id]);
  const [busy, setBusy] = useState<number | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [invite, setInvite] = useState({ email: "", role: "member" as WorkspaceRole });
  const [inviteLink, setInviteLink] = useState<string | null>(null);

  const isOwner = current?.my_role === "owner";

  async function setRole(member: WorkspaceMember, role: WorkspaceRole) {
    setBusy(member.user_id);
    setProblem(null);
    try {
      await api.changeMemberRole(id, member.user_id, role);
      reload();
      reloadWorkspaces();
    } catch (err) {
      setProblem((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function remove(member: WorkspaceMember) {
    setBusy(member.user_id);
    setProblem(null);
    try {
      await api.removeMember(id, member.user_id);
      reload();
    } catch (err) {
      setProblem((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function sendInvite() {
    setProblem(null);
    try {
      const created = await api.invite(id, {
        email: invite.email || null,
        role: invite.role,
      });
      setInviteLink(`${window.location.origin}/invite/${created.token}`);
      setInvite({ email: "", role: "member" });
    } catch (err) {
      setProblem((err as Error).message);
    }
  }

  const columns: Column<WorkspaceMember>[] = [
    {
      key: "name",
      header: "Name",
      sortValue: (m) => m.name,
      render: (m) => (
        <>
          <div className="dt__primary">{m.name}</div>
          <div className="dt__sub">{m.email}</div>
        </>
      ),
    },
    {
      key: "role",
      header: "Role",
      sortValue: (m) => m.role,
      render: (m) =>
        isOwner ? (
          <select
            value={m.role}
            disabled={busy === m.user_id}
            onChange={(e) => setRole(m, e.target.value as WorkspaceRole)}
            style={{ width: "auto", fontSize: "0.82rem", padding: "0.2rem 0.4rem" }}
          >
            {ROLES.map((role) => (
              <option key={role} value={role}>
                {role}
              </option>
            ))}
          </select>
        ) : (
          <RoleLabel role={m.role} />
        ),
    },
    {
      key: "projects",
      header: "Projects",
      sortValue: (m) => m.project_count,
      render: (m) => <span className="num">{m.project_count}</span>,
    },
    {
      key: "mentoring",
      header: "Mentoring",
      sortValue: (m) => m.mentoring_count,
      render: (m) =>
        m.mentoring_count > 0 ? (
          <span className="num">{m.mentoring_count}</span>
        ) : (
          <span className="dt__sub">—</span>
        ),
    },
    {
      key: "activity",
      header: "Last activity",
      sortValue: (m) => m.last_activity,
      render: (m) =>
        m.last_activity ? (
          <span className="dt__sub">{formatDate(m.last_activity)}</span>
        ) : (
          <span className="dt__sub">—</span>
        ),
    },
    {
      key: "actions",
      header: "",
      render: (m) =>
        isOwner ? (
          <button
            className="btn btn--quiet btn--small"
            disabled={busy === m.user_id}
            onClick={(e) => {
              e.stopPropagation();
              remove(m);
            }}
          >
            Remove
          </button>
        ) : null,
    },
  ];

  if (loading) return <Loading what="Loading members" />;
  if (error) return <ErrorNote message={error} />;

  return (
    <div className="stack">
      <header className="page-head">
        <h1>Members</h1>
        <p>
          {data?.length ?? 0} people. Roles apply to this workspace only — the same person can
          hold a different role somewhere else.
        </p>
      </header>

      {problem && <Callout tone="flag">{problem}</Callout>}

      <DataTable rows={data ?? []} columns={columns} rowKey={(m) => m.user_id} />

      {isOwner && (
        <Card title="Invite someone">
          <div className="filters mb-3">
            <input
              type="text"
              placeholder="Email (optional — leave blank for a shareable link)"
              value={invite.email}
              onChange={(e) => setInvite({ ...invite, email: e.target.value })}
              style={{ minWidth: 280 }}
            />
            <select
              value={invite.role}
              onChange={(e) => setInvite({ ...invite, role: e.target.value as WorkspaceRole })}
            >
              {ROLES.filter((r) => r !== "owner").map((role) => (
                <option key={role} value={role}>
                  Join as {role}
                </option>
              ))}
            </select>
            <button className="btn btn--small" onClick={sendInvite}>
              Create invitation
            </button>
          </div>
          <p className="faint mb-2">
            {ROLE_HELP[invite.role]}
          </p>
          {detail.data?.join_code && (
            <p className="faint">
              Anyone can also join as a member with the code <code>{detail.data.join_code}</code>.
            </p>
          )}
          {inviteLink && (
            <Callout tone="note" title="Invitation link">
              <p style={{ marginBottom: 0, wordBreak: "break-all" }}>{inviteLink}</p>
            </Callout>
          )}
        </Card>
      )}
    </div>
  );
}
