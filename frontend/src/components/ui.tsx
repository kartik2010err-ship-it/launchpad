import { useEffect, useState, type ReactNode } from "react";
import type { EvidenceBasis, NoveltyStatus, RequirementSource, TaskStatus } from "../api/types";

/* ------------------------------------------------------------------ card -- */

export function Card({
  title,
  aside,
  children,
  sunk,
}: {
  title?: ReactNode;
  aside?: ReactNode;
  children: ReactNode;
  sunk?: boolean;
}) {
  return (
    <section className={sunk ? "card card--sunk" : "card"}>
      {(title || aside) && (
        <header className="card__title">
          {typeof title === "string" ? <h3>{title}</h3> : title}
          {aside}
        </header>
      )}
      {children}
    </section>
  );
}

/* --------------------------------------------------------------- callout -- */

export function Callout({
  tone = "note",
  title,
  children,
}: {
  tone?: "note" | "warn" | "flag";
  title?: string;
  children: ReactNode;
}) {
  return (
    <div className={`callout callout--${tone}`} role={tone === "flag" ? "alert" : undefined}>
      {title && <div className="callout__title">{title}</div>}
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ pill -- */

export function Pill({
  tone = "neutral",
  children,
}: {
  tone?: "neutral" | "ok" | "warn" | "flag" | "inert";
  children: ReactNode;
}) {
  return <span className={tone === "neutral" ? "pill" : `pill pill--${tone}`}>{children}</span>;
}

/* ----------------------------------------------------------------- gauge -- */

function toneForScore(score: number): "flag" | "warn" | "ok" | "" {
  if (score < 45) return "flag";
  if (score < 68) return "warn";
  return "ok";
}

/**
 * A panel meter rather than a progress bar: the ticks mark the 40/68 score
 * bands, so the position of the fill carries meaning on its own.
 */
export function Gauge({
  label,
  value,
  basis,
  suffix = "/100",
  animate = true,
}: {
  label: ReactNode;
  value: number;
  basis?: EvidenceBasis;
  suffix?: string;
  animate?: boolean;
}) {
  const unassessable = basis === "not_yet_assessable";
  const [shown, setShown] = useState(animate ? 0 : value);

  useEffect(() => {
    if (!animate) {
      setShown(value);
      return;
    }
    const id = window.requestAnimationFrame(() => setShown(value));
    return () => window.cancelAnimationFrame(id);
  }, [value, animate]);

  const tone = unassessable ? "inert" : toneForScore(value);

  return (
    <div className={`gauge${tone ? ` gauge--${tone}` : ""}`}>
      <div className="gauge__head">
        <span className="gauge__label">{label}</span>
        <span className="gauge__value">{unassessable ? "not yet assessable" : `${value}${suffix}`}</span>
      </div>
      <div
        className="gauge__track"
        role="meter"
        aria-valuenow={unassessable ? undefined : value}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={typeof label === "string" ? label : undefined}
      >
        {!unassessable && <div className="gauge__fill" style={{ width: `${Math.max(0, Math.min(100, shown))}%` }} />}
        <div className="gauge__tick" style={{ left: "45%" }} />
        <div className="gauge__tick" style={{ left: "68%" }} />
      </div>
    </div>
  );
}

/* -------------------------------------------------------- vocabulary UI -- */

const BASIS_COPY: Record<EvidenceBasis, { label: string; tone: "ok" | "warn" | "inert"; help: string }> = {
  current_evidence: {
    label: "current evidence",
    tone: "ok",
    help: "Scored from work you have actually produced.",
  },
  projected_potential: {
    label: "projected potential",
    tone: "warn",
    help: "An estimate of where this could land, not what it is now.",
  },
  not_yet_assessable: {
    label: "not yet assessable",
    tone: "inert",
    help: "You have not made the thing this category judges, so it is left unscored rather than guessed.",
  },
};

export function BasisChip({ basis }: { basis: EvidenceBasis }) {
  const copy = BASIS_COPY[basis];
  return (
    <span title={copy.help}>
      <Pill tone={copy.tone}>{copy.label}</Pill>
    </span>
  );
}

export const NOVELTY_COPY: Record<NoveltyStatus, { label: string; tone: "flag" | "warn" | "neutral" | "ok" }> = {
  likely_common: { label: "Likely common", tone: "flag" },
  incremental: { label: "Incremental", tone: "warn" },
  moderately_differentiated: { label: "Moderately differentiated", tone: "neutral" },
  potentially_novel: { label: "Potentially novel", tone: "ok" },
  strong_research_gap_potential: { label: "Strong research-gap potential", tone: "ok" },
  insufficient_evidence: { label: "Insufficient evidence", tone: "inert" as "neutral" },
};

export const SOURCE_COPY: Record<RequirementSource, { label: string; tone: "warn" | "neutral" | "ok" }> = {
  verified_competition_requirement: { label: "Verified requirement", tone: "ok" },
  unverified_competition_item: { label: "Unverified — confirm officially", tone: "warn" },
  recommended_club_milestone: { label: "Club milestone", tone: "neutral" },
};

export const STATUS_COPY: Record<TaskStatus, string> = {
  not_started: "Not started",
  in_progress: "In progress",
  blocked: "Blocked",
  needs_mentor_review: "Needs mentor review",
  complete: "Complete",
};

export function humanise(value: string): string {
  return value.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

/* ----------------------------------------------------------- list blocks -- */

export function Findings({
  strengths,
  weaknesses,
  improvements,
}: {
  strengths?: string[];
  weaknesses?: string[];
  improvements?: string[];
}) {
  return (
    <div className="stack gap-3">
      {strengths && strengths.length > 0 && (
        <div>
          <div className="faint">Strengths</div>
          <ul className="tick-list tick-list--plus">
            {strengths.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </div>
      )}
      {weaknesses && weaknesses.length > 0 && (
        <div>
          <div className="faint">Weaknesses</div>
          <ul className="tick-list tick-list--minus">
            {weaknesses.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </div>
      )}
      {improvements && improvements.length > 0 && (
        <div>
          <div className="faint">To improve</div>
          <ul className="tick-list tick-list--arrow">
            {improvements.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/* --------------------------------------------------------- async states -- */

export function Loading({ what = "Loading" }: { what?: string }) {
  return <p className="muted">{what}…</p>;
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <Callout tone="flag" title="That did not load">
      <p>{message}</p>
    </Callout>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <Card sunk>
      <h3>{title}</h3>
      {children}
    </Card>
  );
}
