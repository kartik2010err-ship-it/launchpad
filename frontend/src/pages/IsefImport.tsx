/*
  Adding projects to the historical catalogue (sections 19-21).

  This page exists because the obvious import path is closed. Society for
  Science's terms forbid robots and forbid reproducing their materials without
  written permission, so the app has no scraper and will not grow one. What it
  has instead is three doors for data somebody is actually allowed to store:
  a CSV, a JSON document, or one project typed in by hand.

  The permission note is required on all three, and is stored on every row it
  creates. Asking a person to write one sentence about where the data came from
  is the cheapest possible check against importing something the club has no
  right to — and it means that six months later, someone can tell.
*/

import { useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import AppRail from "../components/AppRail";
import { Callout, Card, ErrorNote } from "../components/ui";
import type { HistoricalImportReport } from "../api/types";

type Mode = "csv" | "json" | "single";

const CSV_EXAMPLE = `title,year,category,abstract,awards,team,url
Reef Bleaching Prediction,2024,Environmental Engineering,"We trained a model on...",First Award,true,https://example.org/1`;

const JSON_EXAMPLE = `[
  {
    "title": "Reef Bleaching Prediction",
    "year": 2024,
    "category": "Environmental Engineering",
    "abstract": "We trained a model on...",
    "awards": "First Award",
    "team": true,
    "url": "https://example.org/1"
  }
]`;

const RECOGNISED =
  "title (required), id, year, category, subcategory, project_type, team, abstract, " +
  "awards, student, school, country, state, url";

export default function IsefImport() {
  const [mode, setMode] = useState<Mode>("csv");
  const [source, setSource] = useState("club-archive");
  const [permission, setPermission] = useState("");
  const [report, setReport] = useState<HistoricalImportReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [text, setText] = useState("");
  const [single, setSingle] = useState({
    title: "",
    year: "",
    category: "",
    abstract: "",
    awards: "",
    student_display: "",
    school_display: "",
    source_url: "",
    team_project: "",
  });

  const permissionOk = permission.trim().length >= 3;
  const canSubmit =
    permissionOk &&
    !busy &&
    (mode === "single" ? single.title.trim().length >= 3 : text.trim().length >= 10);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setReport(null);
    try {
      if (mode === "csv") {
        setReport(
          await api.importHistoricalCsv({
            csv_text: text,
            source: source.trim() || "csv",
            permission_note: permission.trim(),
          }),
        );
        setText("");
      } else if (mode === "json") {
        setReport(
          await api.importHistoricalJson({
            json_text: text,
            source: source.trim() || "json",
            permission_note: permission.trim(),
          }),
        );
        setText("");
      } else {
        setReport(
          await api.importHistoricalProject({
            title: single.title,
            year: single.year ? Number(single.year) : null,
            category: single.category || null,
            abstract: single.abstract || null,
            awards: single.awards || null,
            student_display: single.student_display || null,
            school_display: single.school_display || null,
            source_url: single.source_url || null,
            team_project:
              single.team_project === "" ? null : single.team_project === "true",
            source: source.trim() || "manual",
            permission_note: permission.trim(),
          }),
        );
        setSingle({
          title: "",
          year: "",
          category: "",
          abstract: "",
          awards: "",
          student_display: "",
          school_display: "",
          source_url: "",
          team_project: "",
        });
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "That import did not go through.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="shell">
      <AppRail subtitle="ISEF Project Explorer" />
      <main className="main">
        <div className="main__inner stack">
          <Link className="faint" to="/isef">
            ← Back to the explorer
          </Link>

          <header className="page-head">
            <h1>Import previous projects</h1>
            <p>
              Add projects your club is permitted to store. Re-importing the same file updates
              the existing records rather than duplicating them, so a corrected file can simply
              be uploaded again.
            </p>
          </header>

          <Callout tone="warn" title="What may be imported here">
            <p>
              Research Coach does not download projects from the ISEF abstract database.
              Society for Science's terms forbid automated access and forbid reproducing their
              materials without written permission, so importing from there requires that
              permission in writing first.
            </p>
            <p>Data you can import today:</p>
            <ul className="tight-list">
              <li>Your own fair's or school's records.</li>
              <li>An openly-licensed dataset whose licence permits storage and display.</li>
              <li>Anything you hold written permission to store.</li>
            </ul>
          </Callout>

          <Card title="Import">
            <div className="row gap-2 row--wrap mb-4">
              {(
                [
                  ["csv", "CSV"],
                  ["json", "JSON"],
                  ["single", "One project"],
                ] as [Mode, string][]
              ).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  className={`btn btn--small ${mode === key ? "" : "btn--quiet"}`}
                  onClick={() => {
                    setMode(key);
                    setReport(null);
                    setError(null);
                  }}
                >
                  {label}
                </button>
              ))}
            </div>

            <form onSubmit={submit}>
              <div className="grid-2">
                <label className="field">
                  <span>Where did this data come from?</span>
                  <input
                    className="input"
                    value={source}
                    onChange={(e) => setSource(e.target.value)}
                    placeholder="club-archive"
                  />
                  <span className="faint">
                    A short label stored on every row, so records can be traced or re-imported.
                  </span>
                </label>

                <label className="field">
                  <span>Why may these be stored?</span>
                  <input
                    className="input"
                    value={permission}
                    onChange={(e) => setPermission(e.target.value)}
                    placeholder="Our school's own fair records, collected by the club."
                    required
                  />
                  <span className="faint">Required. Recorded against every imported project.</span>
                </label>
              </div>

              {mode === "single" ? (
                <>
                  <label className="field">
                    <span>Project title</span>
                    <input
                      className="input"
                      value={single.title}
                      onChange={(e) => setSingle({ ...single, title: e.target.value })}
                    />
                  </label>

                  <div className="grid-2">
                    <label className="field">
                      <span>Year</span>
                      <input
                        className="input"
                        value={single.year}
                        onChange={(e) => setSingle({ ...single, year: e.target.value })}
                        placeholder="2024"
                      />
                    </label>
                    <label className="field">
                      <span>Category as the fair published it</span>
                      <input
                        className="input"
                        value={single.category}
                        onChange={(e) => setSingle({ ...single, category: e.target.value })}
                        placeholder="Environmental Engineering"
                      />
                    </label>
                  </div>

                  <label className="field">
                    <span>Abstract</span>
                    <textarea
                      className="input"
                      rows={6}
                      value={single.abstract}
                      onChange={(e) => setSingle({ ...single, abstract: e.target.value })}
                    />
                    <span className="faint">
                      Leave blank if you do not have it. The app will show no AI breakdown
                      rather than guessing from the title.
                    </span>
                  </label>

                  <div className="grid-2">
                    <label className="field">
                      <span>Awards</span>
                      <input
                        className="input"
                        value={single.awards}
                        onChange={(e) => setSingle({ ...single, awards: e.target.value })}
                      />
                    </label>
                    <label className="field">
                      <span>Team or individual</span>
                      <select
                        value={single.team_project}
                        onChange={(e) => setSingle({ ...single, team_project: e.target.value })}
                      >
                        <option value="">Not recorded</option>
                        <option value="true">Team</option>
                        <option value="false">Individual</option>
                      </select>
                    </label>
                  </div>

                  <div className="grid-2">
                    <label className="field">
                      <span>Student(s)</span>
                      <input
                        className="input"
                        value={single.student_display}
                        onChange={(e) =>
                          setSingle({ ...single, student_display: e.target.value })
                        }
                      />
                    </label>
                    <label className="field">
                      <span>School</span>
                      <input
                        className="input"
                        value={single.school_display}
                        onChange={(e) =>
                          setSingle({ ...single, school_display: e.target.value })
                        }
                      />
                    </label>
                  </div>

                  <label className="field">
                    <span>Original record URL</span>
                    <input
                      className="input"
                      value={single.source_url}
                      onChange={(e) => setSingle({ ...single, source_url: e.target.value })}
                      placeholder="https://…"
                    />
                  </label>

                  <p className="faint">
                    Leave anything you do not have blank. A field left empty is stored as
                    "not provided by the source" — it is never filled in for you.
                  </p>
                </>
              ) : (
                <label className="field">
                  <span>{mode === "csv" ? "CSV" : "JSON"}</span>
                  <textarea
                    className="input outreach-draft__body"
                    rows={12}
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder={mode === "csv" ? CSV_EXAMPLE : JSON_EXAMPLE}
                  />
                  <span className="faint">
                    Recognised fields: {RECOGNISED}. Unknown columns are kept as metadata
                    rather than discarded.
                    {mode === "json"
                      ? " A bare list, an object with a projects list, or an object keyed by project id are all accepted."
                      : ""}
                  </span>
                </label>
              )}

              {error && <ErrorNote message={error} />}

              <button className="btn" disabled={!canSubmit}>
                {busy ? "Importing…" : "Import"}
              </button>
              {!permissionOk && (
                <span className="faint"> Add the permission note to enable importing.</span>
              )}
            </form>

            {report ? (
              <div className="mt-4">
                <Callout tone={report.errors.length ? "warn" : "note"} title="Import finished">
                  <p>
                    {report.created} added, {report.updated} updated, {report.skipped} skipped.
                  </p>
                  {report.errors.length > 0 ? (
                    <ul className="tight-list">
                      {report.errors.slice(0, 8).map((row) => (
                        <li key={row}>{row}</li>
                      ))}
                    </ul>
                  ) : null}
                  <p>
                    <Link to="/isef">Open the explorer →</Link>
                  </p>
                </Callout>
              </div>
            ) : null}
          </Card>
        </div>
      </main>
    </div>
  );
}
