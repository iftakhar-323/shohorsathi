import { useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { api, getTokens, onTokensChange, setTokens, type Tokens } from "./api";
import { t } from "./i18n";

export type Role = "customer" | "provider" | "admin";
export type SessionUser = { id: number; role: Role; name: string; phone: string };

function decode(access: string): SessionUser | null {
  try {
    const payload = JSON.parse(atob(access.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return { id: Number(payload.user_id), role: payload.role, name: payload.name, phone: payload.phone };
  } catch {
    return null;
  }
}

type AuthValue = {
  user: SessionUser | null;
  login: (phone: string, password: string) => Promise<SessionUser | null>;
  requestOtp: (phone: string, purpose?: "register" | "reset_password", channel?: "sms" | "whatsapp") => Promise<void>;
  register: (data: { phone: string; full_name: string; password: string; otp: string; email?: string; accept_terms: boolean; marketing_opt_in?: boolean }) => Promise<void>;
  resetPassword: (data: { phone: string; otp: string; new_password: string }) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [tokens, setState] = useState<Tokens | null>(getTokens);
  const queryClient = useQueryClient();

  useEffect(() => onTokensChange(setState), []);

  const value = useMemo<AuthValue>(
    () => ({
      user: tokens ? decode(tokens.access) : null,
      async login(phone, password) {
        const { data } = await api.post<Tokens>("/auth/login/", { phone, password });
        setTokens(data);
        return decode(data.access);
      },
      async requestOtp(phone, purpose = "register", channel = "sms") {
        await api.post("/auth/otp/request/", { phone, purpose, channel });
      },
      async register(body) {
        const { data } = await api.post<Tokens>("/auth/register/", body);
        setTokens({ access: data.access, refresh: data.refresh });
      },
      async resetPassword(body) {
        await api.post("/auth/password/reset/", body);
      },
      logout() {
        setTokens(null);
        queryClient.clear();
      },
    }),
    [tokens, queryClient],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

/** Sends visitors to /login (and back afterwards); optionally limits to some roles. */
export function RequireAuth({ children, roles }: { children: ReactNode; roles?: Role[] }) {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />;
  if (roles && !roles.includes(user.role)) return <Forbidden />;
  return <>{children}</>;
}

function Forbidden() {
  const { user, logout } = useAuth();
  return (
    <section className="mx-auto flex max-w-[560px] flex-col items-start gap-3 px-6 py-20">
      <h1 className="m-0 text-2xl font-bold">{t("এই অ্যাকাউন্ট দিয়ে এই পেজ খোলা যাবে না")}</h1>
      <p className="m-0 text-muted">{t("{name} হিসেবে লগইন আছেন। অন্য অ্যাকাউন্টে লগইন করতে লগআউট করুন।", { name: user?.name ?? "" })}</p>
      <button type="button" onClick={logout} className="h-11 rounded-xl bg-brand px-4 font-semibold text-white">{t("লগআউট")}</button>
    </section>
  );
}
