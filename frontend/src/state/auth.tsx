import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiError, SESSION_EXPIRED_EVENT, api, getToken, setToken } from "../api/client";
import type { User } from "../api/types";

interface AuthValue {
  user: User | null;
  ready: boolean;
  /** Set when a saved session could not be checked because the server was unreachable. */
  bootError: string | null;
  retryBoot: () => void;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (payload: Record<string, unknown>) => Promise<void>;
  signOut: () => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const [bootError, setBootError] = useState<string | null>(null);

  const boot = useCallback(() => {
    if (!getToken()) {
      setReady(true);
      return;
    }
    setReady(false);
    setBootError(null);
    api
      .me()
      .then(setUser)
      .catch((err: ApiError) => {
        // Only a rejected token ends the session. A network failure or a
        // server error says nothing about the token, and signing the student
        // out for it would make them retype their password for our outage.
        if (err.status === 401) setToken(null);
        else setBootError(err.message);
      })
      .finally(() => setReady(true));
  }, []);

  useEffect(boot, [boot]);

  useEffect(() => {
    const expire = () => {
      setToken(null);
      setUser(null);
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, expire);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, expire);
  }, []);

  const value = useMemo<AuthValue>(
    () => ({
      user,
      ready,
      bootError,
      retryBoot: boot,
      signIn: async (email, password) => {
        const result = await api.login(email, password);
        setToken(result.access_token);
        setUser(await api.me());
      },
      signUp: async (payload) => {
        const result = await api.register(payload);
        setToken(result.access_token);
        setUser(await api.me());
      },
      signOut: () => {
        setToken(null);
        setUser(null);
      },
    }),
    [user, ready, bootError, boot],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
