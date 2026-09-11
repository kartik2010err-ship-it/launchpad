import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { useAsync } from "../api/useAsync";
import { isOversight, useWorkspace } from "../state/workspace";
import { Card, Callout, ErrorNote, Loading, Pill, humanise } from "../components/ui";
import { StatusPill } from "../components/workspace-ui";

/**
 * Teams in a workspace: browse what exists, join with a team code.
 *
 * The distinction this page has to make unmistakable is that a team code is a
 * *second* door — you are already in the workspace — and that entering one puts
 * you on an existing shared project rather than creating anything.
 */
export default function WorkspaceTeams() {
  const { workspaceId } = useParams();
  const wsId = Number(workspaceId);
  const { current } = useWorkspace();
  const oversight = isOversight(current?.my_role);

  const { data, error, loading, reload } = useAsync(() => api.teams(wsId), [wsId]);
  // The create-team setting lives on the workspace detail, not the summary the
  // switcher holds, so it is fetched here rather than guessed from a role.
  const { data: workspace } = useAsync(() => api.workspace(wsId), [wsId]);
  const canCreate = oversight || workspace?.members_can_create_teams !== false;

  const [code, setCode] = useState("");
  const [joinError, setJoinError] = useState<string | null>(null);
  const [joined, setJoined] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function join(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setJoinError(null);
    setJoined(null);
    try {
      const team = await api.joinTeam(wsId, code.trim().toUpperCase());
      setJoined(team.name);
      setCode("");
      reload();
    } catch (err) {
      setJoinError(err instanceof ApiError ? err.message : "Could not join that team.");
    } finally {
      setBusy(false);
    }
  }

  const mine = data?.filter((t) => t.i_am_member) ?? [];
  const others = data?.filter((t) => !t.i_am_member) ?? [];

  return (
    <div className="stack">
      <header className="page-head">
        <div className="row row--between">
          <div>
            <h1>Teams</h1>
            <p>
              A team shares one research project. Everyone on it opens the same research
              question, timeline, notebook and poster — nothing is copied per person.
            </p>
          </div>
          {canCreate && (
            <NewTeam wsId={wsId} onCreated={reload} oversight={oversight} />
          )}
        </div>
      </header>

      <Card title="Join a team">
        <p className="muted">
          Team codes are separate from the workspace code. You are already in{" "}
          <strong>{current?.name}</strong>; a team code puts you onto that team's existing
          project.
        </p>
        <form className="row gap-2 mt-3" onSubmit={join}>
          <input
            className="input"
            style={{ maxWidth: "240px", fontFamily: "var(--mono)" }}
            placeholder="CORAL-8K2P"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            aria-label="Team join code"
          />
          <button className="btn btn--small" disabled={busy || code.trim().length < 3}>
            {busy ? "Joining…" : "Join team"}
          </button>
        </form>
        {joinError && (
          <div className="mt-3">
            <Callout tone="flag">
              <p>{joinError}</p>
            </Callout>
          </div>
        )}
        {joined && (
          <div className="mt-3">
            <Callout tone="note" title={`You are on ${joined}`}>
              <p>
                You now share that team's project. Any change you make is a change everyone on
                the team sees.
              </p>
            </Callout>
          </div>
        )}
      </Card>

      {loading && <Loading what="Loading teams" />}
      {error && <ErrorNote message={error} />}

      {data && data.length === 0 && (
        <Card sunk>
          <h3>No teams here yet</h3>
          <p className="muted">
            {canCreate
              ? "Create one to group students around a shared project — you will be on the team you make."
              : "Ask a workspace lead to create a team, or use a team code if you were given one."}
          </p>
        </Card>
      )}

      {data && data.length > 0 && mine.length === 0 && (
        <Callout tone="note" title="You are not on a team yet">
          <p>
            {oversight
              ? "You oversee every team below without being a member of any of them. If you are entering your own project, create a team for yourself — it is an ordinary team, with an ordinary code."
              : "Use a team code above to join one, or create your own."}
          </p>
        </Callout>
      )}

      {mine.length > 0 && (
        <section className="stack gap-3">
          <div className="section-head">
            <h2>My teams</h2>
            <span className="faint">Teams you are actually on</span>
          </div>
          {mine.map((team) => (
            <TeamCard key={team.id} wsId={wsId} team={team} />
          ))}
        </section>
      )}

      {others.length > 0 && (
        <section className="stack gap-3">
          <div className="section-head">
            <h2>All teams</h2>
            <span className="faint">
              {oversight
                ? "You oversee these as workspace lead — you are not a member of them"
                : "Other teams in this workspace"}
            </span>
          </div>
          {others.map((team) => (
            <TeamCard key={team.id} wsId={wsId} team={team} />
          ))}
        </section>
      )}
    </div>
  );
}

function TeamCard({
  wsId,
  team,
}: {
  wsId: number;
  team: import("../api/types").TeamSummary;
}) {
  return (
    <Link className="plain-link"
      to={`/workspaces/${wsId}/teams/${team.id}`}
    >
      <Card
        title={team.name}
        aside={
          <div className="row gap-2">
            {team.status && <StatusPill status={team.status} />}
            <Pill tone={team.seats_left === 0 ? "inert" : "neutral"}>
              {team.member_count}/{team.max_team_size}
            </Pill>
            {team.membership_locked && <Pill tone="warn">Roster locked</Pill>}
            {team.is_archived && <Pill tone="inert">Archived</Pill>}
          </div>
        }
      >
        {team.description && <p className="muted">{team.description}</p>}

        {team.project_title ? (
          <div className="question-hero mb-3">
            <q className="text-base">{team.project_title}</q>
          </div>
        ) : (
          <p className="faint">No shared project started yet.</p>
        )}

        <div className="row faint">
          <span>{team.member_names.join(", ") || "No members yet"}</span>
          {team.mentor_name && (
            <>
              <span>·</span>
              <span>Mentor: {team.mentor_name}</span>
            </>
          )}
          {team.stage && (
            <>
              <span>·</span>
              <span>{humanise(team.stage)}</span>
            </>
          )}
          {team.readiness !== null && (
            <>
              <span>·</span>
              <span>{team.readiness}% ready</span>
            </>
          )}
        </div>

        {team.join_code && (
          <div className="faint mt-2">
            Team code <code className="code">{team.join_code}</code>
          </div>
        )}
      </Card>
    </Link>
  );
}

/**
 * Section 5. A member creating a team always joins it — the API enforces that,
 * and offering a checkbox that does nothing would be a lie. Oversight gets the
 * choice, because a coach setting up the season is not entering the fair.
 */
function NewTeam({
  wsId,
  onCreated,
  oversight,
}: {
  wsId: number;
  onCreated: () => void;
  oversight: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [discoverable, setDiscoverable] = useState(true);
  const [joinAsMember, setJoinAsMember] = useState(!oversight);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.createTeam(wsId, {
        name,
        description: description || null,
        competition_key: "azsef",
        is_discoverable: discoverable,
        join_as_member: oversight ? joinAsMember : true,
      });
      setName("");
      setDescription("");
      setOpen(false);
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create that team.");
    } finally {
      setBusy(false);
    }
  }

  if (!open)
    return (
      <button className="btn btn--small" onClick={() => setOpen(true)}>
        Create a team
      </button>
    );

  return (
    <form className="card" onSubmit={submit} style={{ minWidth: "320px" }}>
      <label className="field">
        <span>Team name</span>
        <input
          className="input"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Team Coral"
          autoFocus
        />
      </label>
      <label className="field">
        <span>What they are working on</span>
        <input
          className="input"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Reef imagery and bleaching signatures"
        />
      </label>
      <label className="row gap-2 mt-1">
        <input
          type="checkbox"
          checked={discoverable}
          onChange={(e) => setDiscoverable(e.target.checked)}
        />
        <span className="faint">
          Other people in this workspace can see this team exists. Uncheck to make the join
          code the only way in.
        </span>
      </label>

      {oversight ? (
        <label className="row gap-2 mt-1">
          <input
            type="checkbox"
            checked={joinAsMember}
            onChange={(e) => setJoinAsMember(e.target.checked)}
          />
          <span className="faint">
            Put me on this team. Leave it off when you are setting a team up for students —
            overseeing a team does not make you a member of it.
          </span>
        </label>
      ) : (
        <p className="faint mt-1">
          You will be on this team, as its team lead.
        </p>
      )}

      {error && <ErrorNote message={error} />}
      <div className="row gap-2 mt-3">
        <button className="btn btn--small" disabled={busy || name.trim().length < 2}>
          {busy ? "Creating…" : "Create"}
        </button>
        <button
          type="button"
          className="btn btn--quiet btn--small"
          onClick={() => setOpen(false)}
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
