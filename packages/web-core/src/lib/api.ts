import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";

// Every app talks to the gateway; in dev Vite proxies /api and /media to it.
export const api = axios.create({ baseURL: "/api" });

export type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };
export type Tokens = { access: string; refresh: string };

const KEY = "shohor.tokens";
const listeners = new Set<(t: Tokens | null) => void>();

export function getTokens(): Tokens | null {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Tokens) : null;
  } catch {
    return null;
  }
}

export function setTokens(tokens: Tokens | null) {
  try {
    if (tokens) localStorage.setItem(KEY, JSON.stringify(tokens));
    else localStorage.removeItem(KEY);
  } catch {
    // storage unavailable (private mode): the session lasts for this tab only
  }
  listeners.forEach((fn) => fn(tokens));
}

export function onTokensChange(fn: (t: Tokens | null) => void) {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

api.interceptors.request.use((config) => {
  const tokens = getTokens();
  if (tokens) config.headers.Authorization = `Bearer ${tokens.access}`;
  return config;
});

let refreshing: Promise<Tokens | null> | null = null;

async function refresh(): Promise<Tokens | null> {
  const tokens = getTokens();
  if (!tokens) return null;
  try {
    const { data } = await axios.post<Tokens>("/api/auth/token/refresh/", { refresh: tokens.refresh });
    setTokens(data);
    return data;
  } catch {
    setTokens(null);
    return null;
  }
}

/** Refresh now, e.g. after a role change, so the new claims are in the access token. */
export function refreshTokens() {
  refreshing ??= refresh().finally(() => (refreshing = null));
  return refreshing;
}

api.interceptors.response.use(undefined, async (error: AxiosError) => {
  const original = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined;
  if (error.response?.status !== 401 || !original || original._retried || !getTokens()) throw error;
  original._retried = true;
  const tokens = await refreshTokens();
  if (!tokens) throw error;
  original.headers.Authorization = `Bearer ${tokens.access}`;
  return api(original);
});

/** Turns a DRF error response into one readable line. */
export function errorMessage(error: unknown, fallback = "কিছু একটা সমস্যা হয়েছে। আবার চেষ্টা করুন।"): string {
  const data = (error as AxiosError)?.response?.data as unknown;
  if (!data) return fallback;
  if (typeof data === "string") return fallback;
  const first = (value: unknown): string | null => {
    if (typeof value === "string") return value;
    if (Array.isArray(value)) return value.length ? first(value[0]) : null;
    if (value && typeof value === "object") {
      for (const v of Object.values(value)) {
        const found = first(v);
        if (found) return found;
      }
    }
    return null;
  };
  return first(data) ?? fallback;
}

export async function upload(file: File, purpose: string, visibility: "public" | "private" = "public") {
  const form = new FormData();
  form.append("file", file);
  form.append("purpose", purpose);
  form.append("visibility", visibility);
  const { data } = await api.post<{ id: number; url: string }>("/media/", form);
  return data.url;
}
