import { useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { Callout } from "../components/ui";

export default function ForgotPassword() {
  const [params] = useSearchParams();
  const [email, setEmail] = useState(params.get("email") ?? "");
  const [sent, setSent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    document.title = "Reset your password · Research Coach";
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setSent((await api.forgotPassword(email)).detail);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-page">
      <Link to="/" className="rail__brand auth-page__brand">
        Research Coach
        <span>Turn an idea into a research question you can defend</span>
      </Link>

      <form className="card stack" onSubmit={submit}>
        <h1 className="m-0" style={{ fontSize: "1.15rem" }}>
          Reset your password
        </h1>

        {sent ? (
          <>
            <Callout tone="note">{sent}</Callout>
            <p className="faint m-0">
              Didn't get it after a few minutes? Check that the address is the one you signed up with, then{" "}
              <button type="button" className="link-button" onClick={() => setSent(null)}>
                try again
              </button>
              .
            </p>
          </>
        ) : (
          <>
            <p className="muted m-0">
              Enter the email you signed up with. We'll send you a link to choose a new password.
            </p>
            <label className="field">
              <span className="field__label">Email</span>
              <input
                type="email"
                name="email"
                autoComplete="email"
                inputMode="email"
                required
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            {error && <Callout tone="flag">{error}</Callout>}
            <button type="submit" className="btn" disabled={busy || !email}>
              {busy ? "Sending…" : "Send reset link"}
            </button>
          </>
        )}

        <Link to="/sign-in" className="faint">
          ← Back to sign in
        </Link>
      </form>
    </main>
  );
}
