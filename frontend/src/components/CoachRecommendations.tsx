import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../api/useAsync";
import { Callout, Card, Pill } from "./ui";

/**
 * The bridge between the coach's findings and the two reference libraries.
 *
 * Guides are resolved by id on the backend from the `(dimension, criterion)`
 * pairs that actually scored badly — no component here decides which guide a
 * weakness maps to, so rewording a weakness never breaks a link.
 *
 * Winning-project examples come with the do-not-copy warning attached, because
 * the failure mode of showing a student strong work is that they copy it.
 */
export default function CoachRecommendations({ projectId }: { projectId: number }) {
  const guides = useAsync(() => api.recommendedGuides(projectId), [projectId]);
  const examples = useAsync(() => api.similarWinningProjects(projectId), [projectId]);

  const recommended = guides.data?.guides ?? [];
  const projects = examples.data?.projects ?? [];

  if (recommended.length === 0 && projects.length === 0) return null;

  return (
    <>
      {recommended.length > 0 && (
        <Card title="Learn how to fix these">
          <p className="muted">
            Each weakness the engine found is linked to the guide that explains that specific
            thing.
          </p>
          <div className="stack gap-3 mt-4">
            {recommended.map((guide) => (
              <div className="divided-top"
                key={guide.guide_id}
              >
                <div className="faint">{guide.reason}</div>
                <Link to={`/library/${guide.guide_id}`}>{guide.title} →</Link>
                <div className="faint">
                  {guide.summary} · {guide.read_minutes} min
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {projects.length > 0 && (
        <Card title="Examples in your category">
          <div className="stack gap-2">
            {projects.map((project) => (
              <div key={project.id} className="row row--between">
                <Link to={`/winning-projects/${project.id}`}>{project.title}</Link>
                {project.is_illustrative ? (
                  <Pill tone="warn">Teaching example</Pill>
                ) : (
                  <Pill tone="ok">Verified source</Pill>
                )}
              </div>
            ))}
          </div>
          <div className="mt-4">
            <Callout tone="warn" title="Inspiration, not a template">
              <p className="mb-0">{examples.data?.warning}</p>
            </Callout>
          </div>
        </Card>
      )}
    </>
  );
}
