/*
  The Research Assistant (sections 11-15).

  Three things this screen is built around:

  * The student can see what the assistant was told. The context strip is not
    decoration — it is the answer to "does it already know about my project?",
    and it lists what is missing as plainly as what is known.
  * Guides are rendered from ids the server returned, never from links inside
    the prose. Renaming a guide cannot break a recommendation.
  * Conversations are private. The sharing control says so in words, because a
    student who is unsure whether their teacher can read this will not ask the
    question they actually needed to ask.
*/

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import AppRail from "../components/AppRail";
import { api } from "../api/client";
import type {
  AssistantConversation,
  AssistantConversationSummary,
  AssistantMessage,
} from "../api/types";

/** Markdown-light: **bold**, `code`, - bullets, blank-line paragraphs. */
function renderBody(text: string) {
  const blocks = text.split(/\n{2,}/);
  return blocks.map((block, blockIndex) => {
    const lines = block.split("\n");
    if (lines.every((line) => /^\s*[-*]\s+/.test(line))) {
      return (
        <ul className="tight-list" key={blockIndex}>
          {lines.map((line, i) => (
            <li key={i}>{inline(line.replace(/^\s*[-*]\s+/, ""))}</li>
          ))}
        </ul>
      );
    }
    if (lines.every((line) => /^\s*\d+\.\s+/.test(line))) {
      return (
        <ol className="tight-list" key={blockIndex}>
          {lines.map((line, i) => (
            <li key={i}>{inline(line.replace(/^\s*\d+\.\s+/, ""))}</li>
          ))}
        </ol>
      );
    }
    return <p key={blockIndex}>{inline(block)}</p>;
  });
}

function inline(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={i}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`")) return <code className="code" key={i}>{part.slice(1, -1)}</code>;
    return <span key={i}>{part}</span>;
  });
}

function AssistantPanel() {
  const params = useParams();
  const [search] = useSearchParams();
  const projectId = params.projectId
    ? Number(params.projectId)
    : search.get("project")
      ? Number(search.get("project"))
      : null;

  const [conversations, setConversations] = useState<AssistantConversationSummary[]>([]);
  const [active, setActive] = useState<AssistantConversation | null>(null);
  const [draft, setDraft] = useState("");
  const [thinking, setThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);

  const refreshList = useCallback(async () => {
    const rows = await api.assistantConversations(projectId ?? undefined);
    setConversations(rows);
    return rows;
  }, [projectId]);

  const openConversation = useCallback(async (id: number) => {
    setError(null);
    setActive(await api.assistantConversation(id));
  }, []);

  const newConversation = useCallback(async () => {
    setError(null);
    const created = await api.startAssistantConversation(projectId);
    setActive(created);
    await refreshList();
  }, [projectId, refreshList]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const rows = await refreshList();
        if (cancelled) return;
        if (rows.length > 0) await openConversation(rows[0].id);
        else await newConversation();
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Could not load the assistant.");
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [active?.messages.length, thinking]);

  const send = useCallback(
    async (text: string) => {
      const body = text.trim();
      if (!body || !active || thinking) return;
      setError(null);
      setDraft("");

      // Optimistic: the student's turn appears immediately.
      const pending: AssistantMessage = {
        id: -Date.now(),
        role: "user",
        content: body,
        follow_ups: [],
        provider: null,
        created_at: new Date().toISOString(),
        guides: [],
      };
      setActive({ ...active, messages: [...active.messages, pending] });
      setThinking(true);
      try {
        await api.sendAssistantMessage(active.id, body);
        setActive(await api.assistantConversation(active.id));
        await refreshList();
      } catch (e) {
        setError(e instanceof Error ? e.message : "The assistant could not reply.");
        setActive(await api.assistantConversation(active.id));
      } finally {
        setThinking(false);
      }
    },
    [active, thinking, refreshList],
  );

  const toggleShare = useCallback(async () => {
    if (!active) return;
    try {
      setActive(await api.shareAssistantConversation(active.id, !active.shared_with_team));
      await refreshList();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not change sharing.");
    }
  }, [active, refreshList]);

  const remove = useCallback(
    async (id: number) => {
      await api.deleteAssistantConversation(id);
      const rows = await refreshList();
      if (active?.id === id) {
        if (rows.length > 0) await openConversation(rows[0].id);
        else await newConversation();
      }
    },
    [active, refreshList, openConversation, newConversation],
  );

  const context = active?.context ?? null;
  const isEmpty = (active?.messages.length ?? 0) === 0;

  const starters = useMemo(
    () => (active?.suggested_actions ?? []).slice(0, isEmpty ? 8 : 4),
    [active?.suggested_actions, isEmpty],
  );

  return (
    <div className="assistant">
      <aside className="assistant__rail">
        <button className="btn btn--small" onClick={newConversation} type="button">
          + New conversation
        </button>
        <p className="assistant__privacy">
          Private to you. Your teacher and workspace owner cannot read these.
        </p>
        <ul className="assistant__list">
          {conversations.map((row) => (
            <li key={row.id}>
              <button
                type="button"
                className={`assistant__item${active?.id === row.id ? " is-active" : ""}`}
                onClick={() => openConversation(row.id)}
              >
                <span className="assistant__item-title">{row.title}</span>
                <span className="faint">
                  {row.project_title ? `${row.project_title} · ` : ""}
                  {row.message_count} message{row.message_count === 1 ? "" : "s"}
                  {row.shared_with_team ? " · shared" : ""}
                </span>
              </button>
              <button
                type="button"
                className="assistant__remove"
                aria-label={`Delete ${row.title}`}
                onClick={() => remove(row.id)}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <section className="assistant__main">
        <header className="page-head">
          <div>
            <h1>Research Assistant</h1>
            <p className="muted">
              A research mentor, not an answer key. It will explain, challenge and point you at
              the right guide — it will not write your project for you.
            </p>
          </div>
          {active?.project_id ? (
            <button className="btn btn--quiet btn--small" type="button" onClick={toggleShare}>
              {active.shared_with_team ? "Shared with team — make private" : "Share with team"}
            </button>
          ) : null}
        </header>

        {context ? (
          <div className="card card--sunk assistant__context">
            <div className="section-head">
              <h2>What it already knows</h2>
              <Link className="faint" to={`/projects/${context.project_id}`}>
                Open project
              </Link>
            </div>
            <p className="assistant__question">{context.question}</p>
            <div className="assistant__chips">
              <span className="pill">{context.stage.replace(/_/g, " ")}</span>
              <span className="pill">{context.category.replace(/_/g, " ")}</span>
              {context.competition ? <span className="pill">{context.competition}</span> : null}
              {context.readiness !== null ? (
                <span className="pill pill--ok">Readiness {context.readiness}</span>
              ) : null}
              <span className="pill">
                {context.answered_count}/{context.total_questions} interview answers
              </span>
              {context.next_deadline ? (
                <span className="pill pill--warn">Due {context.next_deadline}</span>
              ) : null}
              {context.safety_flags.map((flag) => (
                <span className="pill pill--flag" key={flag}>
                  {flag}
                </span>
              ))}
            </div>
            {context.missing_fields.length > 0 ? (
              <p className="faint assistant__missing">
                Not on record yet: {context.missing_fields.join(", ")}. The assistant will say so
                rather than guess.
              </p>
            ) : null}
          </div>
        ) : (
          <div className="callout callout--note">
            No project attached, so answers here are general. Open the assistant from inside a
            project to get advice grounded in your actual question, scores and deadlines.
          </div>
        )}

        <div className="chat assistant__chat">
          {isEmpty ? (
            <div className="empty">
              <p>Ask anything about your research — or start with one of these.</p>
            </div>
          ) : null}

          {(active?.messages ?? []).map((message) => (
            <article
              className={`turn ${message.role === "user" ? "turn--student" : "turn--judge"}`}
              key={message.id}
            >
              <div className="assistant__body">{renderBody(message.content)}</div>

              {message.guides.length > 0 ? (
                <div className="assistant__guides">
                  {message.guides.map((guide) => (
                    <Link
                      className="assistant__guide"
                      key={guide.guide_id}
                      to={`/library/${guide.guide_id}`}
                    >
                      <span className="faint">Read</span>
                      <strong>{guide.title}</strong>
                      <span className="faint">{guide.read_minutes} min</span>
                    </Link>
                  ))}
                </div>
              ) : null}

              {message.follow_ups.length > 0 ? (
                <div className="assistant__followups">
                  {message.follow_ups.map((question) => (
                    <button
                      className="btn btn--ghost btn--small"
                      key={question}
                      type="button"
                      onClick={() => send(question)}
                    >
                      {question}
                    </button>
                  ))}
                </div>
              ) : null}
            </article>
          ))}

          {thinking ? (
            <article className="turn turn--judge assistant__thinking">
              <span className="faint">Thinking…</span>
            </article>
          ) : null}
          <div ref={endRef} />
        </div>

        {error ? <div className="callout callout--flag">{error}</div> : null}

        {starters.length > 0 ? (
          <div className="assistant__starters">
            {starters.map((action) => (
              <button
                className="btn btn--ghost btn--small"
                key={action.key}
                type="button"
                disabled={thinking}
                onClick={() => send(action.prompt)}
              >
                {action.label}
              </button>
            ))}
          </div>
        ) : null}

        <form
          className="assistant__composer"
          onSubmit={(event) => {
            event.preventDefault();
            void send(draft);
          }}
        >
          <textarea
            className="input"
            rows={2}
            value={draft}
            placeholder="Ask about your project…"
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void send(draft);
              }
            }}
          />
          <button className="btn" type="submit" disabled={thinking || !draft.trim()}>
            Send
          </button>
        </form>
      </section>
    </div>
  );
}

/**
 * Inside a project the shell already exists (ProjectLayout renders it), so the
 * panel is dropped straight into the outlet. Opened standalone it has to bring
 * its own rail.
 */
export default function ResearchAssistant() {
  const params = useParams();
  if (params.projectId) return <AssistantPanel />;
  return (
    <div className="shell">
      <AppRail subtitle="Research Assistant" />
      <main className="main">
        <div className="main__inner">
          <AssistantPanel />
        </div>
      </main>
    </div>
  );
}
