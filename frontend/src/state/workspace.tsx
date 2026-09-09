import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api } from "../api/client";
import type { WorkspaceSummary } from "../api/types";
import { useAuth } from "./auth";

const LAST_WORKSPACE = "research-coach-workspace";

interface WorkspaceValue {
  workspaces: WorkspaceSummary[];
  current: WorkspaceSummary | null;
  loading: boolean;
  select: (id: number) => void;
  reload: () => Promise<void>;
}

const Ctx = createContext<WorkspaceValue | null>(null);

/**
 * Which workspace the user is looking at right now.
 *
 * Everything role-dependent in the UI reads `current.my_role` — the same person
 * is a member in one space and an owner in another, so there is no such thing
 * as "the user's role" without a workspace attached.
 */
export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [currentId, setCurrentId] = useState<number | null>(() => {
    const stored = localStorage.getItem(LAST_WORKSPACE);
    return stored ? Number(stored) : null;
  });
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!user) {
      setWorkspaces([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const list = await api.myWorkspaces();
      setWorkspaces(list);
      setCurrentId((existing) => {
        if (existing && list.some((w) => w.id === existing)) return existing;
        // Prefer a shared space over the personal one: someone in a club
        // almost always wants the club on open.
        const shared = list.find((w) => !w.is_personal);
        return (shared ?? list[0])?.id ?? null;
      });
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (currentId) localStorage.setItem(LAST_WORKSPACE, String(currentId));
  }, [currentId]);

  const value = useMemo<WorkspaceValue>(
    () => ({
      workspaces,
      current: workspaces.find((w) => w.id === currentId) ?? null,
      loading,
      select: setCurrentId,
      reload: load,
    }),
    [workspaces, currentId, loading, load],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useWorkspace(): WorkspaceValue {
  const value = useContext(Ctx);
  if (!value) throw new Error("useWorkspace must be used inside WorkspaceProvider");
  return value;
}

/** Owner or lead: may see the whole workspace. */
export function isOversight(role: string | undefined): boolean {
  return role === "owner" || role === "lead";
}
