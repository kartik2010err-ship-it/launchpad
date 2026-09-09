import { useState } from "react";
import { api } from "../api/client";
import { useAsync } from "../api/useAsync";
import { useProject } from "./ProjectLayout";
import type { MockJudgeReport } from "../api/types";
import { Callout, Card, ErrorNote, Gauge, Loading, Pill } from "../components/ui";

interface Turn {
  who: "judge" | "student";
  text: string;
  reaction?: string | null;
  probing?: string;
}

const DIFFICULTY_TONE: Record<string, "ok" | "warn" | "flag" | "neutral"> = {
  "warm-up": "ok",
  standard: "neutral",
  hard: "warn",
  brutal: "flag",
};

export default function JudgePrep() {
  const { project } = useProject();
  const prep = useAsync(() => api.interviewPrep(project.id), [project.id]);

  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [report, setReport] = useState<MockJudgeReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  async function start() {
    setBusy(true);
    setError(null);
    setReport(null);
    try {
      const reply = await api.mockJudge(project.id, {});
      setTurns([{ who: "judge", text: reply.judge_question }]);
      setRunning(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function answer() {
    const text = draft.trim();
    if (!text) return;
    setBusy(true);
    setDraft("");
    setTurns((current) => [...current, { who: "student", text }]);
    try {
      const reply = await api.mockJudge(project.id, { answer: text });
      setTurns((current) => [
        ...current,
        { who: "judge", text: reply.judge_question, reaction: reply.reaction, probing: reply.probing },
      ]);
      if (reply.finished) {
        setRunning(false);
        setReport(await api.mockReport(project.id));
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function finish() {
    setBusy(true);
    try {
      await api.mockJudge(project.id, { finish: true });
      setReport(await api.mockReport(project.id));
      setRunning(false);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      <header className="page-head">
        <h1>Judge preparation</h1>
        <p>
          Interviews are worth more points than the poster at most fairs. This is the part students skip and judges
          notice.
        </p>
      </header>

      <Card title="Mock judge" aside={running ? <Pill tone="warn">In progress</Pill> : undefined}>
        <p className="muted">
          The judge asks follow-ups based on what you actually say, and gets harder if you answer well. Type the way you
          would speak at the board, not the way you would write.
        </p>

        {turns.length > 0 && (
          <div className="chat" style={{ margin: "1rem 0" }}>
            {turns.map((turn, i) => (
              <div key={i} className={`turn turn--${turn.who}`}>
                <div className="turn__who">{turn.who === "judge" ? "Judge" : "You"}</div>
                {turn.reaction && (
                  <p className="muted" style={{ marginBottom: "0.5rem" }}>
                    {turn.reaction}
                  </p>
                )}
                <div>{turn.text}</div>
                {turn.probing && <div className="faint" style={{ marginTop: "0.3rem" }}>Probing: {turn.probing}</div>}
              </div>
            ))}
          </div>
        )}

        {running ? (
          <>
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Answer out loud, then type roughly what you said."
            />
            <div className="row" style={{ marginTop: "0.6rem" }}>
              <button className="btn" onClick={answer} disabled={busy || !draft.trim()}>
                {busy ? "…" : "Answer"}
              </button>
              <button className="btn btn--quiet" onClick={finish} disabled={busy}>
                End and get feedback
              </button>
            </div>
          </>
        ) : (
          <button className="btn" onClick={start} disabled={busy}>
            {turns.length > 0 ? "Run it again" : "Start a mock interview"}
          </button>
        )}

        {error && <Callout tone="flag">{error}</Callout>}
      </Card>

      {report && (
        <Card title="How that went">
          <Gauge label="Interview readiness" value={report.readiness} />
          <div className="grid-2" style={{ marginTop: "1rem" }}>
            {report.strong_answers.length > 0 && (
              <div>
                <div className="faint">Answered well</div>
                <ul className="tick-list tick-list--plus">
                  {report.strong_answers.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
            {report.weak_answers.length > 0 && (
              <div>
                <div className="faint">Answered poorly</div>
                <ul className="tick-list tick-list--minus">
                  {report.weak_answers.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
            {report.concepts_to_review.length > 0 && (
              <div>
                <div className="faint">Review these before the fair</div>
                <ul className="tick-list tick-list--arrow">
                  {report.concepts_to_review.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
            {report.communication_problems.length > 0 && (
              <div>
                <div className="faint">How you said it</div>
                <ul className="tick-list tick-list--arrow">
                  {report.communication_problems.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
          {report.better_explanations.length > 0 && (
            <div style={{ marginTop: "1rem" }}>
              <div className="faint">Ways to say it better</div>
              <ul className="tight-list">
                {report.better_explanations.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      )}

      {prep.loading && <Loading />}
      {prep.error && <ErrorNote message={prep.error} />}

      {prep.data && (
        <>
          <Card title="Your elevator pitch">
            <p className="muted">
              Judges decide what kind of conversation to have in the first thirty seconds. Draft these, then say them
              until they are not memorised.
            </p>
            <ul className="tight-list">
              {prep.data.pitch_prompts.map((prompt, i) => (
                <li key={i}>{prompt}</li>
              ))}
            </ul>
          </Card>

          <Card title={`Questions you are likely to be asked (${prep.data.questions.length})`}>
            <table className="table">
              <thead>
                <tr>
                  <th style={{ width: "42%" }}>Question</th>
                  <th>What they are actually testing</th>
                  <th style={{ width: "14%" }}>Level</th>
                </tr>
              </thead>
              <tbody>
                {prep.data.questions.map((question, i) => (
                  <tr key={i}>
                    <td>
                      {question.text}
                      <div className="faint">{question.category}</div>
                    </td>
                    <td className="muted">{question.what_theyre_probing}</td>
                    <td>
                      <Pill tone={DIFFICULTY_TONE[question.difficulty] ?? "neutral"}>{question.difficulty}</Pill>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </div>
  );
}
