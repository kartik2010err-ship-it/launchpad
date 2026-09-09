import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useProject } from "./ProjectLayout";
import type { AnswerCritique, InterviewQuestion } from "../api/types";
import { Callout, Card, Gauge, Pill, humanise } from "../components/ui";
import QuestionHero from "../components/QuestionHero";

/**
 * The interview is the heart of the app, so it behaves like a conversation and
 * not a form: you answer the questions you were asked, the engine reacts to
 * each answer, and the next batch depends on what you said. Rejected answers
 * come back — that is the point, not a bug.
 */
export default function Interview() {
  const { project, reload } = useProject();
  const navigate = useNavigate();

  const initialQuestions: InterviewQuestion[] = project.interview_turns
    .filter((turn) => !turn.answer_text)
    .map((turn) => ({
      key: turn.question_key,
      dimension: turn.dimension,
      text: turn.question_text,
      why_asked: turn.why_asked ?? "",
      hint: null,
    }));

  const [questions, setQuestions] = useState<InterviewQuestion[]>(initialQuestions);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [critiques, setCritiques] = useState<AnswerCritique[]>([]);
  const [completeness, setCompleteness] = useState<number | null>(null);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const answered = project.interview_turns.filter((turn) => turn.answer_text);

  async function submit() {
    const answers = questions
      .map((question) => ({ question_key: question.key, answer: (drafts[question.key] ?? "").trim() }))
      .filter((entry) => entry.answer.length > 0);
    if (answers.length === 0) return;

    setBusy(true);
    setError(null);
    try {
      const step = await api.interview(project.id, answers, 3);
      setCritiques(step.critiques);
      setQuestions(step.questions);
      setCompleteness(step.completeness);
      setReady(step.ready_to_evaluate);
      setDrafts({});
      reload();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function evaluate() {
    setBusy(true);
    try {
      await api.evaluate(project.id);
      navigate(`/projects/${project.id}/analysis`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      <header className="page-head">
        <h1>Research interview</h1>
        <p>
          These questions are chosen from what you have already said. Short or vague answers get handed back with a
          reason — that is the tool working, not you failing.
        </p>
      </header>

      <QuestionHero project={project} showLineage={false} />

      {completeness !== null && (
        <Card>
          <Gauge label="How much the engine knows about your project" value={completeness} suffix="%" />
          <p className="faint" style={{ marginTop: "0.5rem", marginBottom: 0 }}>
            Scores stay capped until this is high. An evaluation from thin information would be a guess dressed up as a
            number.
          </p>
        </Card>
      )}

      {critiques.length > 0 && (
        <div className="stack" style={{ gap: "0.6rem" }}>
          {critiques.map((critique) => (
            <Callout
              key={critique.question_key}
              tone={critique.accepted ? "note" : "warn"}
              title={humanise(critique.question_key)}
            >
              <p>{critique.note}</p>
              {critique.follow_up && (
                <p className="muted" style={{ marginBottom: 0 }}>
                  {critique.follow_up}
                </p>
              )}
            </Callout>
          ))}
        </div>
      )}

      {questions.length > 0 ? (
        <Card title="Answer these">
          {questions.map((question) => (
            <label key={question.key} className="field">
              <span className="field__label">
                {question.text} <Pill>{humanise(question.dimension)}</Pill>
              </span>
              {question.why_asked && <span className="field__hint">Why this matters: {question.why_asked}</span>}
              {question.hint && <span className="field__hint">{question.hint}</span>}
              <textarea
                value={drafts[question.key] ?? ""}
                onChange={(e) => setDrafts({ ...drafts, [question.key]: e.target.value })}
                placeholder="Write as much detail as you actually have. Say so if you do not know yet."
              />
            </label>
          ))}
          <div className="row">
            <button className="btn" onClick={submit} disabled={busy}>
              {busy ? "Thinking…" : "Submit answers"}
            </button>
            {answered.length > 0 && (
              <button className="btn btn--quiet" onClick={evaluate} disabled={busy}>
                Evaluate anyway
              </button>
            )}
          </div>
        </Card>
      ) : (
        <Card title={ready ? "Interview complete" : "Nothing left to ask right now"}>
          <p className="muted">
            The engine has enough to evaluate the project. You can come back and revise answers at any point; every
            evaluation is stored so you can see the score move.
          </p>
          <button className="btn" onClick={evaluate} disabled={busy}>
            {busy ? "Evaluating…" : "Evaluate my project"}
          </button>
        </Card>
      )}

      {error && <Callout tone="flag">{error}</Callout>}

      {answered.length > 0 && (
        <Card title={`What you have told the engine (${answered.length})`}>
          <table className="table">
            <tbody>
              {answered.map((turn) => (
                <tr key={turn.id}>
                  <th style={{ width: "30%", borderBottom: "1px solid var(--rule)" }}>{turn.question_text}</th>
                  <td>
                    {turn.answer_text}
                    {turn.followup_note && <div className="faint">{turn.followup_note}</div>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
