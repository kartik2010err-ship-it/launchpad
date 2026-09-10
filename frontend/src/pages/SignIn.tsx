import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../state/auth";
import { Callout } from "../components/ui";

export default function SignIn() {
  const { signIn, signUp } = useAuth();
  const [params] = useSearchParams();
  const [mode, setMode] = useState<"in" | "up">(params.get("mode") === "up" ? "up" : "in");
  const intent = params.get("intent"); // "project" | "workspace" | null — informs post-signup copy only
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "student", grade_level: 10 });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (params.get("mode") === "up") setMode("up");
  }, [params]);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      if (mode === "in") await signIn(form.email, form.password);
      else
        await signUp({
          name: form.name,
          email: form.email,
          password: form.password,
          role: form.role,
          grade_level: Number(form.grade_level),
        });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ maxWidth: 400, margin: "10vh auto", padding: "0 1rem" }}>
      <Link
        to="/"
        className="rail__brand"
        style={{ padding: 0, marginBottom: "1.5rem", textDecoration: "none", color: "inherit", display: "block" }}
      >
        Research Coach
        <span>Turn an idea into a research question you can defend</span>
      </Link>

      <div className="card stack">
        <div className="row">
          <button className={`btn btn--small ${mode === "in" ? "" : "btn--quiet"}`} onClick={() => setMode("in")}>
            Sign in
          </button>
          <button className={`btn btn--small ${mode === "up" ? "" : "btn--quiet"}`} onClick={() => setMode("up")}>
            Create an account
          </button>
        </div>

        {mode === "up" && intent === "workspace" && (
          <p className="faint m-0">
            Create an account first, then set up your workspace on the next screen.
          </p>
        )}
        {mode === "up" && intent === "project" && (
          <p className="faint m-0">
            Create an account first, then start your project on the next screen.
          </p>
        )}

        {mode === "up" && (
          <label className="field">
            <span className="field__label">Your name</span>
            <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </label>
        )}

        <label className="field">
          <span className="field__label">Email</span>
          <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </label>

        <label className="field">
          <span className="field__label">Password</span>
          <input
            type="password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            onKeyDown={(e) => e.key === "Enter" && submit()}
          />
        </label>

        {mode === "up" && (
          <div className="grid-2">
            <label className="field">
              <span className="field__label">I am a</span>
              <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                <option value="student">Student</option>
                <option value="mentor">Mentor or advisor</option>
              </select>
            </label>
            <label className="field">
              <span className="field__label">Grade</span>
              <input
                type="number"
                min={5}
                max={12}
                value={form.grade_level}
                onChange={(e) => setForm({ ...form, grade_level: Number(e.target.value) })}
              />
            </label>
          </div>
        )}

        {error && <Callout tone="flag">{error}</Callout>}

        <button className="btn" onClick={submit} disabled={busy || !form.email || !form.password}>
          {busy ? "Working…" : mode === "in" ? "Sign in" : "Create account"}
        </button>

        <p className="faint m-0">
          Demo accounts use the password <code>coach1234</code> — try <code>ava@example.edu</code> for a weak project,{" "}
          <code>priya@example.edu</code> for a strong one, or <code>mentor@example.edu</code> for the advisor view.
        </p>
      </div>
    </div>
  );
}
