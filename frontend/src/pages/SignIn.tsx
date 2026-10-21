import { useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../state/auth";
import { Callout } from "../components/ui";

/** Only same-site paths, so a crafted link cannot bounce a student off-site. */
export function safeNext(value: string | null): string {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : "/home";
}

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

  useEffect(() => {
    document.title = mode === "in" ? "Sign in · Research Coach" : "Create an account · Research Coach";
  }, [mode]);

  async function submit(event: FormEvent) {
    event.preventDefault();
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
          grade_level: form.role === "student" ? Number(form.grade_level) : null,
        });
      // Signing in re-renders the app with its signed-in routes, where
      // /sign-in forwards to ?next= (see AfterSignIn in App).
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const switchMode = (value: "in" | "up") => {
    setMode(value);
    setError(null);
  };

  return (
    <main className="auth-page">
      <Link to="/" className="rail__brand auth-page__brand">
        Research Coach
        <span>Turn an idea into a research question you can defend</span>
      </Link>

      <form className="card stack" onSubmit={submit} noValidate={false}>
        <h1 className="sr-only">{mode === "in" ? "Sign in" : "Create an account"}</h1>
        <div className="row" role="tablist" aria-label="Sign in or create an account">
          <button
            type="button"
            role="tab"
            aria-selected={mode === "in"}
            className={`btn btn--small ${mode === "in" ? "" : "btn--quiet"}`}
            onClick={() => switchMode("in")}
          >
            Sign in
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "up"}
            className={`btn btn--small ${mode === "up" ? "" : "btn--quiet"}`}
            onClick={() => switchMode("up")}
          >
            Create an account
          </button>
        </div>

        {mode === "up" && intent === "workspace" && (
          <p className="faint m-0">Create an account first, then set up your workspace on the next screen.</p>
        )}
        {mode === "up" && intent === "project" && (
          <p className="faint m-0">Create an account first, then start your project on the next screen.</p>
        )}

        {mode === "up" && (
          <label className="field">
            <span className="field__label">Your name</span>
            <input
              type="text"
              name="name"
              autoComplete="name"
              required
              maxLength={120}
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </label>
        )}

        <label className="field">
          <span className="field__label">Email</span>
          <input
            type="email"
            name="email"
            autoComplete="email"
            inputMode="email"
            required
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
        </label>

        <label className="field">
          <span className="field__label">Password</span>
          <input
            type="password"
            name="password"
            autoComplete={mode === "in" ? "current-password" : "new-password"}
            required
            minLength={mode === "up" ? 8 : undefined}
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
          {mode === "up" && <span className="faint">At least 8 characters.</span>}
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
            {form.role === "student" && (
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
            )}
          </div>
        )}

        {error && <Callout tone="flag">{error}</Callout>}

        <button type="submit" className="btn" disabled={busy || !form.email || !form.password}>
          {busy ? "Working…" : mode === "in" ? "Sign in" : "Create account"}
        </button>

        <p className="faint m-0">
          Demo accounts use the password <code>coach1234</code> — try <code>ava@example.edu</code> for a weak project,{" "}
          <code>priya@example.edu</code> for a strong one, or <code>mentor@example.edu</code> for the advisor view.
        </p>
      </form>
    </main>
  );
}
