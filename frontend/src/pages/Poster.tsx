import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAsync } from "../api/useAsync";
import { useProject } from "./ProjectLayout";
import type { PosterCritique, PosterLayout } from "../api/types";
import { BasisChip, Callout, Card, ErrorNote, Gauge, Loading, Pill } from "../components/ui";

function LayoutPreview({ layout, selected, onSelect }: { layout: PosterLayout; selected: boolean; onSelect: () => void }) {
  const columns = Object.entries(layout.columns);
  return (
    <div
      className="card"
      style={{
        borderColor: selected ? "var(--accent)" : undefined,
        boxShadow: selected ? "0 0 0 1px var(--accent)" : undefined,
        cursor: "pointer",
      }}
      onClick={onSelect}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && onSelect()}
    >
      <div className="card__title">
        <h3>{layout.name}</h3>
        <Pill tone={selected ? "ok" : "neutral"}>fit {layout.fit_score}</Pill>
      </div>

      {/* A miniature of the board itself: the fastest way to judge a layout. */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: `repeat(${columns.length}, 1fr)`,
          gap: "4px",
          background: "var(--surface-sunk)",
          padding: "4px",
          borderRadius: "2px",
          marginBottom: "0.7rem",
        }}
      >
        {columns.map(([name, sections]) => (
          <div key={name} style={{ display: "flex", flexDirection: "column", gap: "3px" }}>
            {sections.map((section) => (
              <div
                key={section}
                style={{
                  background: "var(--surface)",
                  border: "1px solid var(--rule)",
                  fontSize: "0.62rem",
                  padding: "3px 4px",
                  color: "var(--ink-soft)",
                  overflow: "hidden",
                  whiteSpace: "nowrap",
                  textOverflow: "ellipsis",
                }}
              >
                {section.replace(/_/g, " ")}
              </div>
            ))}
          </div>
        ))}
      </div>

      <p className="muted" style={{ marginBottom: 0 }}>
        {layout.why_it_fits}
      </p>
    </div>
  );
}

export default function Poster() {
  const { project } = useProject();
  const plan = useAsync(() => api.posterPlan(project.id), [project.id]);
  const saved = useAsync(() => api.getPoster(project.id), [project.id]);

  const [sections, setSections] = useState<Record<string, string>>({});
  const [layoutKey, setLayoutKey] = useState<string | null>(null);
  const [critique, setCritique] = useState<PosterCritique | null>(null);
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (saved.data) {
      setSections(saved.data.sections ?? {});
      setLayoutKey(saved.data.layout_key ?? null);
    }
  }, [saved.data]);

  async function save() {
    setBusy(true);
    try {
      await api.savePoster(project.id, { layout_key: layoutKey, sections });
      setDirty(false);
    } finally {
      setBusy(false);
    }
  }

  async function runCritique() {
    setBusy(true);
    try {
      await api.savePoster(project.id, { layout_key: layoutKey, sections });
      setDirty(false);
      setCritique(await api.critiquePoster(project.id));
    } finally {
      setBusy(false);
    }
  }

  if (plan.loading) return <Loading what="Building the poster plan" />;
  if (plan.error) return <ErrorNote message={plan.error} />;
  if (!plan.data) return null;

  const wordCount = (text: string) => (text.trim() ? text.trim().split(/\s+/).length : 0);

  return (
    <div className="stack">
      <header className="page-head">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div>
            <h1>Poster</h1>
            <p>
              Section-by-section coaching against what judges read first. Word counts are guides, and the flags below
              only fire when a section is far off.
            </p>
          </div>
          <div className="row">
            <button className="btn btn--quiet btn--small" onClick={save} disabled={busy || !dirty}>
              {dirty ? "Save draft" : "Saved"}
            </button>
            <button className="btn btn--small" onClick={runCritique} disabled={busy}>
              Critique my draft
            </button>
          </div>
        </div>
      </header>

      {critique && (
        <Card
          title={
            <h3>
              Poster quality <BasisChip basis={critique.basis} />
            </h3>
          }
        >
          <Gauge label="Draft quality" value={critique.score} basis={critique.basis} />
          <div className="grid-2" style={{ marginTop: "0.9rem" }}>
            {critique.main_problems.length > 0 && (
              <div>
                <div className="faint">Main problems</div>
                <ul className="tick-list tick-list--minus">
                  {critique.main_problems.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
            {critique.text_length_flags.length > 0 && (
              <div>
                <div className="faint">Length flags</div>
                <ul className="tick-list tick-list--arrow">
                  {critique.text_length_flags.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
            {critique.strengths.length > 0 && (
              <div>
                <div className="faint">Working well</div>
                <ul className="tick-list tick-list--plus">
                  {critique.strengths.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
          <p className="faint" style={{ marginTop: "0.8rem", marginBottom: 0 }}>
            {critique.disclaimer}
          </p>
        </Card>
      )}

      <h2>Layout</h2>
      <div className="grid-2">
        {plan.data.layouts.map((layout) => (
          <LayoutPreview
            key={layout.key}
            layout={layout}
            selected={layoutKey === layout.key}
            onSelect={() => {
              setLayoutKey(layout.key);
              setDirty(true);
            }}
          />
        ))}
      </div>

      <h2>Sections</h2>
      {plan.data.sections.map((section) => {
        const text = sections[section.key] ?? "";
        const words = wordCount(text);
        const over = words > section.target_words * 1.6;
        const under = words > 0 && words < section.target_words * 0.4;
        return (
          <Card
            key={section.key}
            title={section.title}
            aside={
              <span className={`num ${over || under ? "" : "faint"}`} style={{ color: over || under ? "var(--warn)" : undefined }}>
                {words} / ~{section.target_words} words
              </span>
            }
          >
            <p className="muted">{section.purpose}</p>

            <textarea
              value={text}
              onChange={(e) => {
                setSections({ ...sections, [section.key]: e.target.value });
                setDirty(true);
              }}
              placeholder="Draft this section here."
            />

            <div className="grid-2" style={{ marginTop: "0.8rem" }}>
              {section.should_add.length > 0 && (
                <div>
                  <div className="faint">Should contain</div>
                  <ul className="tick-list tick-list--arrow">
                    {section.should_add.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
              {section.should_remove.length > 0 && (
                <div>
                  <div className="faint">Cut from here</div>
                  <ul className="tick-list tick-list--minus">
                    {section.should_remove.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
              {section.judge_questions.length > 0 && (
                <div>
                  <div className="faint">A judge reading this will ask</div>
                  <ul className="tick-list tick-list--arrow">
                    {section.judge_questions.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </Card>
        );
      })}

      <h2>Figures</h2>
      {plan.data.figures.length === 0 ? (
        <Callout tone="note">
          <p style={{ marginBottom: 0 }}>
            Figure suggestions appear once the engine knows what you are measuring. Answer the measurement questions in
            the interview.
          </p>
        </Callout>
      ) : (
        <div className="grid-2">
          {[...plan.data.figures, ...plan.data.visual_assets].map((figure, i) => (
            <Card key={i} title={figure.name} aside={<Pill>{figure.kind}</Pill>}>
              <p className="muted">{figure.why}</p>
              <p className="faint" style={{ marginBottom: 0 }}>
                Place it: {figure.where_on_poster}
              </p>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
