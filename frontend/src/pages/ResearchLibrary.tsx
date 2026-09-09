import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../api/useAsync";
import AppRail from "../components/AppRail";
import { Card, ErrorNote, Loading, Pill } from "../components/ui";
import type { GuideCategory, GuideSummary } from "../api/types";

/** Shared shell for the pages that are not scoped to a workspace or project. */
export function GlobalShell({
  children,
  subtitle,
}: {
  children: React.ReactNode;
  subtitle?: string;
}) {
  return (
    <div className="shell">
      <AppRail subtitle={subtitle} />
      <main className="main">
        <div className="main__inner">{children}</div>
      </main>
    </div>
  );
}

function GuideCard({ guide }: { guide: GuideSummary }) {
  return (
    <Link className="guide-card" to={`/library/${guide.id}`}>
      <div className="guide-card__meta">
        <span>{guide.category_label}</span>
        <span>·</span>
        <span>{guide.read_minutes} min</span>
        {guide.has_comparisons && (
          <>
            <span>·</span>
            <span>weak vs strong</span>
          </>
        )}
      </div>
      <div className="guide-card__title">{guide.title}</div>
      <div className="guide-card__summary">{guide.summary}</div>
    </Link>
  );
}

export default function ResearchLibrary() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<GuideCategory | "">("");

  const categories = useAsync(() => api.libraryCategories(), []);
  const guides = useAsync(
    () => api.guides({ q: query, category }),
    [query, category],
  );

  return (
    <GlobalShell subtitle="Research Library">
      <div className="stack">
        <header className="page-head">
          <h1>Research Library</h1>
          <p>
            Short guides on how research is actually done — how to make a variable measurable,
            what a p-value does and does not say, how to write a limitation that helps you. The
            coach links here directly when it finds a weakness.
          </p>
        </header>

        <div className="row" style={{ gap: "0.5rem" }}>
          <input
            className="input"
            style={{ maxWidth: "320px" }}
            type="search"
            placeholder="Search guides"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search guides"
          />
          <button
            className={`btn btn--small${category === "" ? "" : " btn--quiet"}`}
            onClick={() => setCategory("")}
          >
            All
          </button>
          {categories.data?.map((row) => (
            <button
              key={row.key}
              className={`btn btn--small${category === row.key ? "" : " btn--quiet"}`}
              onClick={() => setCategory(row.key)}
            >
              {row.label} ({row.guide_count})
            </button>
          ))}
        </div>

        {guides.loading && <Loading what="Loading guides" />}
        {guides.error && <ErrorNote message={guides.error} />}

        {guides.data?.length === 0 && (
          <Card sunk>
            <h3>No guides match that</h3>
            <p className="muted">Try a broader search, or clear the category filter.</p>
          </Card>
        )}

        <div className="guide-grid">
          {guides.data?.map((guide) => (
            <GuideCard key={guide.id} guide={guide} />
          ))}
        </div>
      </div>
    </GlobalShell>
  );
}

/** One guide, including its weak/strong comparisons. */
export function GuideDetailPage() {
  const { guideId } = useParams();
  const { data, error, loading } = useAsync(() => api.guide(guideId!), [guideId]);

  return (
    <GlobalShell subtitle="Research Library">
      {loading && <Loading what="Loading guide" />}
      {error && <ErrorNote message={error} />}
      {data && (
        <div className="stack">
          <header className="page-head">
            <div className="faint">
              <Link to="/library">Research Library</Link> · {data.category_label}
            </div>
            <h1>{data.title}</h1>
            <p>{data.summary}</p>
            <div className="row faint">
              <span>{data.read_minutes} min read</span>
              {data.tags.slice(0, 5).map((tag) => (
                <Pill key={tag}>{tag.replace(/_/g, " ")}</Pill>
              ))}
            </div>
          </header>

          <Card>
            {data.sections.map((section) => (
              <section className="guide-section" key={section.heading}>
                <h3>{section.heading}</h3>
                <p>{section.body}</p>
                {section.points.length > 0 && (
                  <ul className="tick-list tick-list--arrow">
                    {section.points.map((point, i) => (
                      <li key={i}>{point}</li>
                    ))}
                  </ul>
                )}
              </section>
            ))}
          </Card>

          {data.comparisons.map((comparison) => (
            <Card key={comparison.label} title={`Weak vs strong: ${comparison.label}`}>
              <p className="muted">
                Read both, then read why. The lesson is the change between them — copying the
                stronger version teaches you nothing.
              </p>
              <div className="compare" style={{ marginTop: "0.8rem" }}>
                <div className="compare__side compare__side--weak">
                  <div className="compare__label">Weak</div>
                  <div>{comparison.weak}</div>
                </div>
                <div className="compare__side compare__side--strong">
                  <div className="compare__label">Stronger</div>
                  <div>{comparison.strong}</div>
                </div>
              </div>
              <div className="compare__why">
                <div className="compare__label">Why it is better</div>
                <p style={{ margin: 0 }}>{comparison.why}</p>
              </div>
            </Card>
          ))}

          {data.related.length > 0 && (
            <section className="stack" style={{ gap: "0.75rem" }}>
              <h2>Read next</h2>
              <div className="guide-grid">
                {data.related.map((guide) => (
                  <GuideCard key={guide.id} guide={guide} />
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </GlobalShell>
  );
}
