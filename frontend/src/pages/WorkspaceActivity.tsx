import { useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../api/useAsync";
import { Card, ErrorNote, Loading } from "../components/ui";
import { ActivityFeed } from "../components/workspace-ui";

const FILTERS: [string, string][] = [
  ["", "All activity"],
  ["milestone", "Milestones"],
  ["comment", "Comments"],
  ["project_change", "Project changes"],
  ["overdue", "Overdue"],
];

export default function WorkspaceActivity() {
  const { workspaceId } = useParams();
  const id = Number(workspaceId);
  const [kind, setKind] = useState("");
  const { data, error, loading } = useAsync(
    () => api.workspaceActivity(id, kind || undefined),
    [id, kind],
  );

  return (
    <div className="stack">
      <header className="page-head">
        <h1>Activity</h1>
        <p>Everything happening in this workspace, newest first.</p>
      </header>

      <div className="filters">
        {FILTERS.map(([value, label]) => (
          <button
            key={value}
            className={`btn btn--small ${kind === value ? "" : "btn--quiet"}`}
            onClick={() => setKind(value)}
          >
            {label}
          </button>
        ))}
      </div>

      {loading && <Loading />}
      {error && <ErrorNote message={error} />}
      {data && (
        <Card>
          <ActivityFeed entries={data} />
        </Card>
      )}
    </div>
  );
}
