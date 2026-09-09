import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { Callout, Card } from "../components/ui";
import { useWorkspace } from "../state/workspace";

export default function WorkspaceJoin() {
  const navigate = useNavigate();
  const { reload, select } = useWorkspace();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const workspace = await api.joinWorkspace(code.trim().toUpperCase());
      await reload();
      select(workspace.id);
      navigate(`/workspaces/${workspace.id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="main">
      <div className="main__inner stack" style={{ maxWidth: 480 }}>
        <header className="page-head">
          <h1>Join a workspace</h1>
          <p>Enter the code your teacher or club lead gave you.</p>
        </header>
        <Card>
          <label className="field">
            <span className="field__label">Join code</span>
            <input
              type="text"
              placeholder="HAMILTON-SCIENCE-27"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submit()}
              style={{ fontFamily: "var(--mono)", textTransform: "uppercase" }}
            />
            <span className="field__hint">You join as a member. Roles are set by the owner.</span>
          </label>
          {error && <Callout tone="flag">{error}</Callout>}
          <button className="btn" onClick={submit} disabled={busy || code.trim().length < 3}>
            {busy ? "Joining…" : "Join"}
          </button>
        </Card>
      </div>
    </div>
  );
}
