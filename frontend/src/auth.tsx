import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";

import { api, setUnauthorizedHandler, TOKEN_KEY, User } from "@/src/api";
import { queryClient } from "@/src/query-client";
import { registerForPush } from "@/src/push";
import { storage } from "@/src/utils/storage";

type RegisterData = {
  name: string;
  email: string;
  password: string;
  phone: string;
  company: string;
  org_number?: string;
  city_id?: string | null;
};

type AuthCtx = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (d: RegisterData) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(async () => {
    await storage.secureRemove(TOKEN_KEY);
    queryClient.clear();
    setUser(null);
  }, []);

  const refresh = useCallback(async () => {
    try {
      setUser(await api<User>("/auth/me"));
    } catch {
      /* keep current state; 401 handler logs out */
    }
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      logout();
    });
    (async () => {
      const token = await storage.secureGet(TOKEN_KEY, null);
      if (token) {
        try {
          setUser(await api<User>("/auth/me"));
        } catch {
          await storage.secureRemove(TOKEN_KEY);
        }
      }
      setLoading(false);
    })();
  }, [logout]);

  // Register this device for push on login and on every app open (tokens rotate).
  useEffect(() => {
    if (user?.id) registerForPush(user.id);
  }, [user?.id]);

  const handleAuth = async (res: { access_token: string; user: User }) => {
    await storage.secureSet(TOKEN_KEY, res.access_token);
    setUser(res.user);
  };

  const login = async (email: string, password: string) => {
    await handleAuth(await api("/auth/login", { method: "POST", body: { email: email.trim(), password } }));
  };

  const register = async (d: RegisterData) => {
    await handleAuth(await api("/auth/register", { method: "POST", body: d }));
  };

  return <Ctx.Provider value={{ user, loading, login, register, logout, refresh }}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth outside provider");
  return c;
}
