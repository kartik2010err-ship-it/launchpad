import { useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../state/auth";
import { useAsync } from "../api/useAsync";
import { Card, Pill, formatDate, humanise } from "./ui";

const SECTIONS = ["question", "methodology", "novelty", "timeline", "poster", "interview", "general"];

/** Shown to both sides: students see what was asked of them, mentors can add. */
export default function MentorThread({ projectId }: { projectId: number }) {
  const { user } = useAuth();
  const { data, reload } = useAsync(() => api.comments(projectId), [projectId]);
  const [body, setBody] = useState("");
  const [section, setSection] = useState("general");
  const [requiresAction, setRequiresAction] = useState(true);
  const [busy, setBusy] = useState(false);

  async function add() {
    setBusy(true);
    try {
      await api.addComment(projectId, { section, body: body.trim(), requires_action: requiresAction });
      setBody("");
      reload();
    } finally {
      setBusy(false);
    }
  }

  async function resolve(commentId: number) {
    await api.resolveComment(projectId, commentId);
    reload();
  }

  const comments = data ?? [];

  return (
    <Card title="Mentor comments">
      {comments.length === 0 && <p className="muted">No comments yet.</p>}

      {comments.map((comment) => (
        <div key={comment.id} className="task">
          <div className="task__body">
            <div style={{ color: comment.resolved ? "var(--ink-faint)" : undefined }}>{comment.body}</div>
            <div className="task__meta">
              <Pill>{humanise(comment.section)}</Pill>
              {comment.requires_action && !comment.resolved && <Pill tone="warn">Action needed</Pill>}
              {comment.resolved && <Pill tone="ok">Resolved</Pill>}
              <span className="faint">
                {comment.author_name} · {formatDate(comment.created_at)}
              </span>
            </div>
          </div>
          {!comment.resolved && (
            <button className="btn btn--quiet btn--small" onClick={() => resolve(comment.id)}>
              Mark done
            </button>
          )}
        </div>
      ))}

      {user?.role === "mentor" && (
        <div style={{ marginTop: "1rem", borderTop: "1px solid var(--rule)", paddingTop: "0.9rem" }}>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Be specific about what to change and why."
            style={{ minHeight: "4rem" }}
          />
          <div className="row" style={{ marginTop: "0.6rem" }}>
            <select value={section} onChange={(e) => setSection(e.target.value)} style={{ width: "auto" }}>
              {SECTIONS.map((value) => (
                <option key={value} value={value}>
                  {humanise(value)}
                </option>
              ))}
            </select>
            <label className="row" style={{ gap: "0.3rem" }}>
              <input
                type="checkbox"
                checked={requiresAction}
                onChange={(e) => setRequiresAction(e.target.checked)}
                style={{ width: "auto" }}
              />
              <span className="faint">Needs a response</span>
            </label>
            <button className="btn btn--small" onClick={add} disabled={busy || body.trim().length < 3}>
              Post comment
            </button>
          </div>
        </div>
      )}
    </Card>
  );
}
