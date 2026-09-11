/*
  The outreach template library (sections 39-41).

  A student does not think "I need the technical-feedback template" — they
  think "I want someone to tell me if my stats are wrong". So the library is
  grouped by what they want, and each template's preview leads with when to use
  it and, just as importantly, when not to.

  The preview exists to be read before writing, which is why "common mistakes"
  sits next to the template rather than appearing as a warning afterwards.
*/

import { useMemo, useState } from "react";
import { Callout, Card, Pill } from "./ui";
import type { OutreachTemplate } from "../api/types";

interface Props {
  templates: OutreachTemplate[];
  categories: { key: string; label: string }[];
  selected: string;
  onSelect: (key: string) => void;
  sources?: { name: string; url: string }[];
  sourcesNote?: string;
}

export default function OutreachTemplateLibrary({
  templates,
  categories,
  selected,
  onSelect,
  sources,
  sourcesNote,
}: Props) {
  const [open, setOpen] = useState<string | null>(selected);

  const grouped = useMemo(() => {
    return categories
      .map((category) => ({
        ...category,
        items: templates.filter((t) => t.category === category.key),
      }))
      .filter((group) => group.items.length > 0);
  }, [templates, categories]);

  return (
    <Card title="Template library">
      <p className="muted">
        Pick the one that matches what you actually want. A message asking for a lab place is a
        different email from one asking a question about a paper, and sending the wrong shape is
        the most common reason a student gets no reply.
      </p>

      <div className="outreach-lib">
        {grouped.map((group) => (
          <section key={group.key}>
            <h3 className="outreach-lib__heading">{group.label}</h3>
            <ul className="outreach-lib__list">
              {group.items.map((template) => {
                const isOpen = open === template.key;
                const isSelected = selected === template.key;
                return (
                  <li key={template.key}>
                    <button
                      type="button"
                      className={`outreach-lib__item${isSelected ? " is-selected" : ""}`}
                      onClick={() => setOpen(isOpen ? null : template.key)}
                      aria-expanded={isOpen}
                    >
                      <span>{template.name}</span>
                      {isSelected ? <Pill tone="ok">In the builder</Pill> : null}
                    </button>

                    {isOpen ? (
                      <div className="outreach-lib__preview">
                        <Detail label="Best used when" body={template.when_to_use} />
                        {template.avoid_when ? (
                          <Detail label="Avoid using when" body={template.avoid_when} />
                        ) : null}

                        {template.required_personalisation.length > 0 ? (
                          <>
                            <h4>You must supply</h4>
                            <ul className="tight-list">
                              {template.required_personalisation.map((item) => (
                                <li key={item}>{item}</li>
                              ))}
                            </ul>
                          </>
                        ) : null}

                        {template.example_subjects.length > 0 ? (
                          <>
                            <h4>Example subject lines</h4>
                            <ul className="tight-list">
                              {template.example_subjects.map((item) => (
                                <li key={item}>
                                  <code className="code">{item}</code>
                                </li>
                              ))}
                            </ul>
                          </>
                        ) : null}

                        <h4>Structure</h4>
                        <ol className="tight-list">
                          {template.structure.map((row) => (
                            <li key={row.section}>
                              <strong>{row.section}.</strong> {row.guidance}
                            </li>
                          ))}
                        </ol>

                        {template.why_it_works ? (
                          <Detail label="Why this works" body={template.why_it_works} />
                        ) : null}

                        {template.common_mistakes.length > 0 ? (
                          <>
                            <h4>Common mistakes</h4>
                            <ul className="tick-list tick-list--minus">
                              {template.common_mistakes.map((item) => (
                                <li key={item}>{item}</li>
                              ))}
                            </ul>
                          </>
                        ) : null}

                        <button
                          type="button"
                          className="btn btn--small"
                          onClick={() => onSelect(template.key)}
                        >
                          Use this template
                        </button>
                      </div>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>

      {sources && sources.length > 0 ? (
        <Callout tone="note" title="Where these came from">
          <p>{sourcesNote}</p>
          <ul className="tight-list">
            {sources.map((source) => (
              <li key={source.url}>
                <a href={source.url} target="_blank" rel="noreferrer">
                  {source.name}
                </a>
              </li>
            ))}
          </ul>
        </Callout>
      ) : null}
    </Card>
  );
}

function Detail({ label, body }: { label: string; body: string }) {
  return (
    <p className="outreach-lib__detail">
      <span className="faint">{label}: </span>
      {body}
    </p>
  );
}
