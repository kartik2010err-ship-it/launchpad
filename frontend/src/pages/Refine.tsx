import { useState } from "react";
import { api } from "../api/client";
import { useProject } from "./ProjectLayout";
import type { QuestionVariant, RefinementResult } from "../api/types";
import { Callout, Card, Pill } from "../components/ui";
import QuestionHero from "../components/QuestionHero";

const TONE: Record<string, "ok" | "warn" | "flag"> = {
  safe: "ok",
  competitive: "warn",
  ambitious: "flag",
};

function VariantCard({
  variant,
  onSelect,
  busy,
}: {
  variant: QuestionVariant;
  onSelect: (variant: QuestionVariant) => void;
  busy: boolean;
}) {
  return (
    <Card
      title={variant.label}
      aside={<Pill tone={TONE[variant.variant] ?? "neutral"}>{variant.variant}</Pill>}
    >
      <div className="question-hero mb-4">
        <q className="text-lg">{variant.question}</q>
      </div>

      <table className="table">
        <tbody>
          <tr>
            <th style={{ width: "38%" }}>Independent variable</th>
            <td>{variant.independent_variable}</td>
          </tr>
          <tr>
            <th>Dependent variable</th>
            <td>{variant.dependent_variable}</td>
          </tr>
          <tr>
            <th>Controls</th>
            <td>{variant.controls.join("; ")}</td>
          </tr>
          <tr>
            <th>Population or sample</th>
            <td>{variant.population}</td>
          </tr>
          <tr>
            <th>Hypothesis</th>
            <td>{variant.hypothesis}</td>
          </tr>
          <tr>
            <th>Primary measurement</th>
            <td>{variant.primary_measurement}</td>
          </tr>
          <tr>
            <th>Experiment type</th>
            <td>{variant.experiment_type}</td>
          </tr>
        </tbody>
      </table>

      <div className="grid-2 mt-4">
        <div>
          <div className="faint">What changed</div>
          <ul className="tick-list tick-list--plus">
            {variant.what_changed.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </div>
        <div>
          <div className="faint">What it costs you</div>
          <ul className="tick-list tick-list--minus">
            {variant.trade_offs.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </div>
      </div>

      <button className="btn mt-4" onClick={() => onSelect(variant)} disabled={busy}>
        Adopt this as my question
      </button>
    </Card>
  );
}

export default function Refine() {
  const { project, reload } = useProject();
  const [result, setResult] = useState<RefinementResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [custom, setCustom] = useState("");

  async function generate() {
    setBusy(true);
    setError(null);
    try {
      setResult(await api.refine(project.id));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function adopt(payload: Record<string, unknown>) {
    setBusy(true);
    try {
      await api.selectQuestion(project.id, payload);
      reload();
      setCustom("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      <header className="page-head">
        <h1>Question rewrite</h1>
        <p>
          Three rewrites at different levels of risk. Your original is never overwritten — every version is kept, so you
          can show a judge how the question developed.
        </p>
      </header>

      <QuestionHero project={project} />

      {!result && (
        <Card>
          <p className="muted">
            The rewrites are built from your interview answers, so answer more of them first if the variants come back
            thin.
          </p>
          <button className="btn" onClick={generate} disabled={busy}>
            {busy ? "Rewriting…" : "Generate three rewrites"}
          </button>
        </Card>
      )}

      {error && <Callout tone="flag">{error}</Callout>}

      {result && (
        <>
          <Card title="What is wrong with the current question">
            <ul className="tick-list tick-list--minus">
              {result.diagnosis.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </Card>

          {result.variants.map((variant) => (
            <VariantCard
              key={variant.variant}
              variant={variant}
              busy={busy}
              onSelect={(v) =>
                adopt({
                  text: v.question,
                  variant: v.variant,
                  rationale: v.what_changed.join(" "),
                  improvements: v.what_changed,
                  source: "ai_variant",
                })
              }
            />
          ))}

          <Card title="Or write your own">
            <p className="muted">
              Often the best question is a mix of two of these. Write it here and it gets saved as the next version.
            </p>
            <textarea value={custom} onChange={(e) => setCustom(e.target.value)} />
            <button
              className="btn mt-3"
              disabled={busy || custom.trim().length < 10}
              onClick={() => adopt({ text: custom.trim(), source: "student_edit" })}
            >
              Save my version
            </button>
          </Card>

          <p className="faint">{result.note}</p>

          <button className="btn btn--quiet btn--small" onClick={generate} disabled={busy}>
            Regenerate from my latest answers
          </button>
        </>
      )}
    </div>
  );
}
