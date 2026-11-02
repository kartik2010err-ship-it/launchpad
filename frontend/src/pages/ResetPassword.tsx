import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { Callout } from "../components/ui";
import { useAuth } from "../state/auth";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const { adoptToken } = useAuth();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    document.title = "Choose a new password · Research Coach";
  }, []);

  const mismatch = confirm.length > 0 && confirm !== password;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (password !== confirm) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.resetPassword(token, password);
      await adoptToken(result.access_token);
      navigate("/home", { replace: true });
    } catch (err) {
      setError((err as Error).message);
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
          Choose a new password
        </h1>

        {!token ? (
          <>
            <Callout tone="flag">
              This link is missing its code. Open the link from the email again, or request a new one.
            </Callout>
            <Link to="/forgot-password" className="btn">
              Request a new link
            </Link>
          </>
        ) : (
          <>
            <label className="field">
              <span className="field__label">New password</span>
              <input
                type="password"
                name="new-password"
                autoComplete="new-password"
                required
                minLength={8}
                autoFocus
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <span className="faint">At least 8 characters.</span>
            </label>
            <label className="field">
              <span className="field__label">Type it again</span>
              <input
                type="password"
                name="confirm-password"
                autoComplete="new-password"
                required
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                aria-invalid={mismatch}
              />
              {mismatch && <span className="faint">The two passwords don't match yet.</span>}
            </label>
            {error && (
              <Callout tone="flag">
                {error}{" "}
                {/expired|invalid|used/i.test(error) && <Link to="/forgot-password">Request a new link.</Link>}
              </Callout>
            )}
            <button
              type="submit"
              className="btn"
              disabled={busy || password.length < 8 || password !== confirm}
            >
              {busy ? "Saving…" : "Save new password"}
            </button>
            <p className="faint m-0">This signs you out on every other device.</p>
          </>
        )}
      </form>
    </main>
  );
}
