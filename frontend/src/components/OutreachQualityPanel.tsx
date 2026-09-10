/*
  Outreach quality score (section 37).

  The score is not a grade — it is a checklist the student can act on, so the
  improvements are the point and the number is the summary. Strengths are shown
  too, because a student who is told only what is wrong learns nothing about
  what to keep.
*/

import { Pill } from "./ui";
import type { OutreachQuality } from "../api/types";

export default function OutreachQualityPanel({ quality }: { quality: OutreachQuality }) {
  const tone = quality.score >= 80 ? "ok" : quality.score >= 60 ? "warn" : "flag";

  return (
    <div className={`outreach-score outreach-score--${tone}`}>
      <div className="outreach-score__head">
        <div className="outreach-score__number">
          <strong>{quality.score}</strong>
          <span className="faint">/100</span>
        </div>
        <div>
          <p className="outreach-score__verdict">{quality.verdict}</p>
          <span className="faint">{quality.word_count} words</span>
        </div>
        <Pill tone={tone}>
          {quality.personalisation.is_specific ? "Personalised" : "Too generic"}
        </Pill>
      </div>

      {quality.strengths.length > 0 ? (
        <>
          <h4>Strong</h4>
          <ul className="tick-list tick-list--plus">
            {quality.strengths.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </>
      ) : null}

      {quality.improvements.length > 0 ? (
        <>
          <h4>Improve before sending</h4>
          <ul className="tick-list tick-list--arrow">
            {quality.improvements.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  );
}
