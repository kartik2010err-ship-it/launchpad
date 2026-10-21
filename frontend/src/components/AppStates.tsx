import { Component, type ErrorInfo, type ReactNode } from "react";

export function FullPageLoading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="app-state" role="status" aria-live="polite">
      <div className="spinner" aria-hidden="true" />
      <p className="muted">{label}</p>
    </div>
  );
}

export function FullPageMessage({
  title,
  children,
  actions,
}: {
  title: string;
  children?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="app-state" role="alert">
      <h1>{title}</h1>
      {children && <p className="muted">{children}</p>}
      {actions && <div className="row">{actions}</div>}
    </div>
  );
}

interface BoundaryState {
  error: Error | null;
}

/**
 * Catches a crash in one page so the rest of the app keeps working. Without it,
 * any render error unmounts the whole tree and the student sees a blank screen.
 * Keyed by route in App, so navigating away clears it.
 */
export class ErrorBoundary extends Component<{ children: ReactNode }, BoundaryState> {
  state: BoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): BoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Page crashed", error, info.componentStack);
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    // A deploy replaces the hashed chunk files; a tab opened before it then
    // fails to load the next page. A reload fetches the new ones.
    const staleChunk = /dynamically imported module|Importing a module script failed|Failed to fetch/i.test(
      error.message,
    );
    return (
      <FullPageMessage
        title={staleChunk ? "Research Coach was updated" : "This page hit a problem"}
        actions={
          <>
            <button className="btn" onClick={() => window.location.reload()}>
              Reload
            </button>
            <a className="btn btn--quiet" href="/home">
              Go home
            </a>
          </>
        }
      >
        {staleChunk
          ? "Reload to get the latest version. Your work is saved."
          : "Your work is saved. Reloading usually fixes this; if it keeps happening, let your advisor know."}
      </FullPageMessage>
    );
  }
}
