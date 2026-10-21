import axios from "axios";

// All calls go through the gateway; in dev Vite proxies /api to it.
export const api = axios.create({ baseURL: "/api" });

export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};
