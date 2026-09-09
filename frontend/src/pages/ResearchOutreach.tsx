import { useState } from "react";
import { api, ApiError } from "../api/client";
import { useAsync } from "../api/useAsync";
import { Callout, Card, ErrorNote, Loading, Pill, formatDate } from "../components/ui";
import { GlobalShell } from "./ResearchLibrary";
import type { OutreachContact, OutreachDraft, OutreachStatus } from "../api/types";

/**
 * Research Outreach: templates, a builder that refuses to write spam, and a
 * tracker.
 *
 * The builder deliberately will not produce a draft until the student has
 * written something specific about the recipient's work and named one concrete
 * ask. That refusal is the feature — a generic email sent to forty professors
 * costs the student far more than it gains.
 */

const STATUSES: OutreachStatus[] = [
  "draft",
  "sent",
  "replied",
  "meeting_scheduled",
  "no_response",
  "declined",
];

function statusTone(status: OutreachStatus): "ok" | "warn" | "flag" | "neutral" | "inert" {
  if (status === "replied" || status === "meeting_scheduled") return "ok";
  if (status === "sent") return "neutral";
  if (status === "no_response") return "warn";
  if (status === "declined") return "flag";
  return "inert";
}

export default function ResearchOutreach() {
  const templates = useAsync(() => api.outreachTemplates(), []);
  const contacts = useAsync(() => api.outreachContacts(), []);
  const summary = useAsync(() => api.outreachSummary(), []);

  const reloadAll = () => {
    contacts.reload();
    summary.reload();
  };

  return (
    <GlobalShell subtitle="Research Outreach">
      <div className="stack">
        <header className="page-head">
          <h1>Research Outreach</h1>
          <p>
            Contacting professors, graduate students and labs — professionally, one at a time,
            about work you have actually read.
          </p>
        </header>

        {templates.data && (
          <Callout tone="warn" title="Do not mass-email">
            <p>{templates.data.spam_warning}</p>
          </Callout>
        )}

        {summary.data && summary.data.follow_ups_due.length > 0 && (
          <Card title="Follow-ups due">
            <p className="muted">
              These were sent over ten days ago with no reply logged. Send one follow-up — not
              three.
            </p>
            {summary.data.follow_ups_due.map((row) => (
              <div key={row.id} className="row" style={{ justifyContent: "space-between" }}>
                <span>
                  <strong>{row.researcher_name}</strong>
                  {row.institution && <span className="faint"> · {row.institution}</span>}
                </span>
                <span className="faint">sent {formatDate(row.sent_on)}</span>
              </div>
            ))}
          </Card>
        )}

        <Builder templates={templates.data?.templates ?? []} onSaved={reloadAll} />

        <Card title="Outreach tracker">
          {contacts.loading && <Loading what="Loading contacts" />}
          {contacts.error && <ErrorNote message={contacts.error} />}
          {contacts.data?.length === 0 && (
            <p className="muted">
              Nothing tracked yet. Build a draft above and save it to start the log.
            </p>
          )}
          {contacts.data?.map((row) => (
            <TrackerRow key={row.id} row={row} onChange={reloadAll} />
          ))}
        </Card>

        {templates.data && (
          <Card title="How to write one that gets a reply">
            <ul className="tick-list tick-list--arrow">
              {templates.data.etiquette.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </Card>
        )}
      </div>
    </GlobalShell>
  );
}

function TrackerRow({ row, onChange }: { row: OutreachContact; onChange: () => void }) {
  async function setStatus(status: OutreachStatus) {
    await api.updateOutreachContact(row.id, { status });
    onChange();
  }

  async function remove() {
    await api.deleteOutreachContact(row.id);
    onChange();
  }

  return (
    <div className="outreach-row">
      <div>
        <strong>{row.researcher_name}</strong>
        {row.subject && <div className="faint">{row.subject}</div>}
      </div>
      <div className="faint">{row.institution ?? "—"}</div>
      <div className="faint">{formatDate(row.sent_on)}</div>
      <div>
        <select
          value={row.status}
          onChange={(e) => setStatus(e.target.value as OutreachStatus)}
          aria-label={`Status for ${row.researcher_name}`}
        >
          {STATUSES.map((status) => (
            <option key={status} value={status}>
              {status.replace(/_/g, " ")}
            </option>
          ))}
        </select>
      </div>
      <div className="row" style={{ gap: "0.4rem" }}>
        {row.follow_up_due && <Pill tone="warn">Follow up</Pill>}
        {!row.follow_up_due && row.follow_up_on && (
          <span className="faint">follow up {formatDate(row.follow_up_on)}</span>
        )}
        <Pill tone={statusTone(row.status)}>{row.status_label}</Pill>
        <button className="btn btn--quiet btn--small" onClick={remove}>
          Delete
        </button>
      </div>
    </div>
  );
}

function Builder({
  templates,
  onSaved,
}: {
  templates: import("../api/types").OutreachTemplate[];
  onSaved: () => void;
}) {
  const [templateKey, setTemplateKey] = useState("research_guidance");
  const [researcher, setResearcher] = useState("");
  const [institution, setInstitution] = useState("");
  const [email, setEmail] = useState("");
  const [topic, setTopic] = useState("");
  const [question, setQuestion] = useState("");
  const [theirWork, setTheirWork] = useState("");
  const [request, setRequest] = useState("");
  const [timeline, setTimeline] = useState("");
  const [draft, setDraft] = useState<OutreachDraft | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const template = templates.find((t) => t.key === templateKey);

  async function build(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setDraft(null);
    try {
      setDraft(
        await api.buildOutreachDraft({
          template_key: templateKey,
          researcher_name: researcher,
          their_work: theirWork,
          specific_request: request,
          research_topic: topic,
          research_question: question || null,
          timeline: timeline || null,
        }),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not build that draft.");
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    if (!draft) return;
    await api.createOutreachContact({
      researcher_name: researcher,
      institution: institution || null,
      email: email || null,
      their_work: theirWork,
      template_key: templateKey,
      subject: draft.subject,
      body: draft.body,
      status: "draft",
    });
    onSaved();
  }

  return (
    <Card title="Cold email builder">
      <p className="muted">
        Answer these and Research Coach will compose a draft. It will not write one without a
        specific reference to their work and one concrete ask — those are the two things that
        separate a message worth reading from spam.
      </p>

      <form onSubmit={build} style={{ marginTop: "0.9rem" }}>
        <label className="field">
          <span>What are you asking for?</span>
          <select value={templateKey} onChange={(e) => setTemplateKey(e.target.value)}>
            {templates.map((t) => (
              <option key={t.key} value={t.key}>
                {t.name}
              </option>
            ))}
          </select>
        </label>
        {template && <p className="faint">{template.when_to_use}</p>}

        <div className="grid-2">
          <label className="field">
            <span>Researcher's name</span>
            <input
              className="input"
              value={researcher}
              onChange={(e) => setResearcher(e.target.value)}
              placeholder="Dr. Elena Marsh"
            />
          </label>
          <label className="field">
            <span>Institution</span>
            <input
              className="input"
              value={institution}
              onChange={(e) => setInstitution(e.target.value)}
              placeholder="Arizona State University"
            />
          </label>
          <label className="field">
            <span>Their email (for your records)</span>
            <input
              className="input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="e.marsh@example.edu"
            />
          </label>
          <label className="field">
            <span>Your research topic</span>
            <input
              className="input"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="early bleaching detection"
            />
          </label>
        </div>

        <label className="field">
          <span>Your research question</span>
          <input
            className="input"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Can autoencoder features predict stress before visible bleaching?"
          />
        </label>

        <label className="field">
          <span>What of theirs did you read, and what struck you?</span>
          <textarea
            rows={3}
            value={theirWork}
            onChange={(e) => setTheirWork(e.target.value)}
            placeholder="your 2023 paper on thermal stress indices, particularly the finding that visible bleaching lags measurable stress by several days"
          />
          <span className="faint">
            Required. This is the sentence that proves the email was written for them.
          </span>
        </label>

        <label className="field">
          <span>What exactly are you asking for?</span>
          <textarea
            rows={2}
            value={request}
            onChange={(e) => setRequest(e.target.value)}
            placeholder="I wondered whether that lag also held at the lowest stress level in Figure 3"
          />
          {template && (
            <span className="faint">For example: {template.ask_examples.join("; ")}.</span>
          )}
        </label>

        <label className="field">
          <span>Your timeline (optional)</span>
          <input
            className="input"
            value={timeline}
            onChange={(e) => setTimeline(e.target.value)}
            placeholder="data collection through March, fair in April"
          />
        </label>

        {/* Not a failure: the builder refused on purpose, and the reason is the
            lesson. Framing it as an error would teach the wrong thing. */}
        {error && (
          <Callout tone="warn" title="Make it specific first">
            <p>{error}</p>
          </Callout>
        )}

        <button className="btn btn--small" disabled={busy || !researcher || !topic}>
          {busy ? "Composing…" : "Build draft"}
        </button>
      </form>

      {draft && (
        <div style={{ marginTop: "1.2rem" }}>
          <div className="card__title">
            <h3>Draft — {draft.word_count} words</h3>
            <button className="btn btn--small" onClick={save}>
              Save to tracker
            </button>
          </div>
          <p className="faint">Subject: {draft.subject}</p>
          <div className="draft">{draft.body}</div>

          <div style={{ marginTop: "0.9rem" }}>
            <Callout tone="note" title="Before you send">
              <ul className="tick-list tick-list--arrow">
                {draft.before_you_send.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </Callout>
          </div>
        </div>
      )}
    </Card>
  );
}
