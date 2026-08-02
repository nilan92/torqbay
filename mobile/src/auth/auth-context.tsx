import React, { createContext, use, useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, apiFetch } from "@/api/client";
import { clearTokens, loadTokens, saveTokens } from "@/auth/token-storage";

export type UserRole = "owner" | "manager" | "technician" | "frontdesk";

export type AuthUser = {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  tenant_id: string;
};

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

type AuthValue = {
  status: AuthStatus;
  user: AuthUser | null;
  accessToken: string | null;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);

  // Restore a stored session once, at launch.
  useEffect(() => {
    let cancelled = false;

    (async () => {
      const tokens = await loadTokens();
      if (!tokens) {
        if (!cancelled) setStatus("unauthenticated");
        return;
      }
      try {
        const me = await apiFetch<AuthUser>("/api/v1/users/me", {
          token: tokens.accessToken,
        });
        if (cancelled) return;
        setAccessToken(tokens.accessToken);
        setUser(me);
        setStatus("authenticated");
      } catch {
        // A stored token the server rejects is worse than no token: clear it
        // so the next launch doesn't repeat the failed round trip.
        await clearTokens();
        if (!cancelled) setStatus("unauthenticated");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const tokens = await apiFetch<{ access_token: string; refresh_token: string }>(
      "/api/v1/auth/login",
      { method: "POST", body: { email, password } }
    );

    await saveTokens({
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
    });

    const me = await apiFetch<AuthUser>("/api/v1/users/me", {
      token: tokens.access_token,
    });

    setAccessToken(tokens.access_token);
    setUser(me);
    setStatus("authenticated");
  }, []);

  const signOut = useCallback(async () => {
    await clearTokens();
    setAccessToken(null);
    setUser(null);
    setStatus("unauthenticated");
  }, []);

  const value = useMemo<AuthValue>(
    () => ({ status, user, accessToken, signIn, signOut }),
    [status, user, accessToken, signIn, signOut]
  );

  return <AuthContext value={value}>{children}</AuthContext>;
}

export function useAuth(): AuthValue {
  const value = use(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}

export { ApiError };
