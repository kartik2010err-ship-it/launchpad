import type { Project } from "../api/types";
import { formatDate, humanise } from "./ui";

/**
 * The student's question is the object under study, so it gets the one piece of
 * typographic weight in the app. Its revision history sits directly underneath
 * because "how did this question get better" is the thing we want them to see.
 */
export default function QuestionHero({ project, showLineage = true }: { project: Project; showLineage?: boolean }) {
  const revisions = [...project.revisions].sort((a, b) => b.version - a.version);
  const current = revisions[0];

  return (
    <div className="stack gap-4">
      <div className="question-hero">
        <q>{project.current_question}</q>
        <div className="row faint mt-2">
          <span>{humanise(project.stage)}</span>
          <span>·</span>
          <span>{humanise(project.category)}</span>
          <span>·</span>
          <span>{humanise(project.project_type)}</span>
          {current && (
            <>
              <span>·</span>
              <span>version {current.version}</span>
            </>
          )}
        </div>
      </div>

      {showLineage && revisions.length > 1 && (
        <details>
          <summary className="faint" style={{ cursor: "pointer" }}>
            How this question changed ({revisions.length} versions)
          </summary>
          <div className="lineage mt-4">
            {revisions.map((revision, index) => (
              <div key={revision.id} className={`lineage__item${index === 0 ? " is-current" : ""}`}>
                <div className="lineage__version">
                  v{revision.version} · {humanise(revision.source)} · {formatDate(revision.created_at)}
                </div>
                <div className="lineage__text">{revision.text}</div>
                {revision.rationale && <div className="faint">{revision.rationale}</div>}
                {revision.improvements.length > 0 && (
                  <ul className="tick-list tick-list--plus faint mt-1">
                    {revision.improvements.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
