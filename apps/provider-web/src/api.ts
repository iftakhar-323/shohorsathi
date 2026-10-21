import { api, type Paginated } from "@shohor/web-core";
import { useQuery } from "@tanstack/react-query";
import { isAxiosError } from "axios";

export type Provider = {
  id: number;
  user_id: number;
  full_name: string;
  phone: string;
  gender: string;
  provider_type: string;
  skills: string[];
  area_ids: number[];
  bio: string;
  experience_years: number;
  nid_number: string;
  photo_url: string;
  nid_front_url: string;
  nid_back_url: string;
  kitchen_photo_urls: string[];
  status: "pending" | "approved" | "rejected" | "suspended";
  rejection_reason: string;
  is_online: boolean;
  working_days: number[];
  work_start: string;
  work_end: string;
  payout_method: string;
  payout_account: string;
  rating_avg: string;
  rating_count: number;
  jobs_completed: number;
  badges: string[];
  trust_score: number;
};

export type Job = {
  id: number;
  source: string;
  source_id: number;
  title: string;
  category_slug: string;
  area_name: string;
  address_line?: string;
  latitude: string | null;
  longitude: string | null;
  customer_name: string;
  customer_phone?: string;
  scheduled_date: string;
  slot: string;
  amount: string;
  is_emergency: boolean;
  description: string;
  photo_urls: string[];
  checklist: { label: string; done: boolean }[];
  before_photos: string[];
  after_photos: string[];
  status: string;
  provider: number | null;
  logs?: { status: string; note: string; created_at: string }[];
};

export const PROVIDER_TYPES = [
  { value: "electrician", label: "ইলেকট্রিশিয়ান" },
  { value: "plumber", label: "প্লাম্বার" },
  { value: "cleaner", label: "ক্লিনার" },
  { value: "ac_technician", label: "এসি টেকনিশিয়ান" },
  { value: "painter", label: "পেইন্টার" },
  { value: "pest_control", label: "পেস্ট কন্ট্রোল" },
  { value: "home_chef", label: "হোম শেফ" },
  { value: "rider", label: "রাইডার" },
  { value: "helper", label: "হেল্পার" },
  { value: "other", label: "অন্যান্য" },
];

export const DAYS = ["সোম", "মঙ্গল", "বুধ", "বৃহঃ", "শুক্র", "শনি", "রবি"];

export function useProvider() {
  return useQuery({
    queryKey: ["provider-me"],
    queryFn: async () => {
      try {
        return (await api.get<Provider>("/providers/me/")).data;
      } catch (e) {
        if (isAxiosError(e) && e.response?.status === 404) return null;
        throw e;
      }
    },
  });
}

export function useJobs(tab: string, enabled = true) {
  return useQuery({
    queryKey: ["jobs", tab],
    queryFn: async () => (await api.get<Paginated<Job>>("/providers/jobs/", { params: { tab } })).data,
    enabled,
    refetchInterval: 20_000,
  });
}
