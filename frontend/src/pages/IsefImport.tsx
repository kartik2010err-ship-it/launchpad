/*
  Adding projects to the historical catalogue (sections 19-21).

  This page exists because the obvious import path is closed. Society for
  Science's terms forbid robots and forbid reproducing their material without
  written permission, so the app has no scraper and will not grow one. What it
  has instead is a door for data somebody is actually allowed to store.

  The permission note is required, not optional, and it is stored on every row.
  Asking a person to write one sentence about where the data came from is the
  cheapest possible check against importing something the club has no right to.
*/

import { useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import AppRail from "../components/AppRail";
import { Callout, Card, ErrorNote } from "../components/ui";
import type { HistoricalImportReport } from "../api/types";

const EXAMPLE = `title,year,category,abstract,awards,team,url
Reef Bleaching Prediction,2024,Environmental Engineering,"We trained a model on...",First Award,true,https://example.org/1`;

export default function IsefImport() {
  const [csv, setCsv] = useState("");
  const [source, setSource] = useState("club-archive");
  const [permission, setPermission] = useState("");
  const [report, setReport] = useState<HistoricalImportReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setReport(null);
    try {
      setReport(
        await api.importHistoricalCsv({
          csv_text: csv,
          source: source.trim() || "csv",
          permission_note: permission.trim(),
        }),
      );
      setCsv("");
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
              the existing records rather than duplicating them, so a corrected spreadsheet can
              simply be uploaded again.
            </p>
          </header>

          <Callout tone="warn" title="Where this data may come from">
            <p>
              Research Coach does not download projects from the ISEF abstract database.
              Society for Science's terms forbid automated access and forbid reproducing their
              material without written permission, so importing from there needs that
              permission in writing first.
            </p>
            <p>
              Data you can import today: your own fair's records, an openly-licensed dataset,
              or projects you have written permission to store.
            </p>
          </Callout>

          <Card title="Import a CSV">
            <form onSubmit={submit}>
              <label className="field">
                <span>Where did this data come from?</span>
                <input
                  className="input"
                  value={source}
                  onChange={(e) => setSource(e.target.value)}
                  placeholder="club-archive"
                />
                <span className="faint">
                  A short label stored on every row, so records can be traced or re-imported
                  later.
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

              <label className="field">
                <span>CSV</span>
                <textarea
                  className="input"
                  rows={10}
                  style={{ fontFamily: "var(--mono)", fontSize: "var(--text-sm)" }}
                  value={csv}
                  onChange={(e) => setCsv(e.target.value)}
                  placeholder={EXAMPLE}
                />
                <span className="faint">
                  A <code className="code">title</code> column is required. Also recognised:
                  year, category, subcategory, project_type, team, abstract, awards, student,
                  school, country, state, url, id. Unknown columns are kept as metadata rather
                  than discarded.
                </span>
              </label>

              {error && <ErrorNote message={error} />}

              <button
                className="btn"
                disabled={busy || csv.trim().length < 10 || permission.trim().length < 3}
              >
                {busy ? "Importing…" : "Import"}
              </button>
            </form>

            {report ? (
              <div style={{ marginTop: "var(--space-4)" }}>
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
