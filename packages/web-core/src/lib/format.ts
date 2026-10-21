import { locale, t } from "./i18n";

// Formatters follow the current language (Bangla digits in Bangla mode).
const taka = () => new Intl.NumberFormat(locale(), { maximumFractionDigits: 0 });
const number = () => new Intl.NumberFormat(locale());
const day = () => new Intl.DateTimeFormat(locale(), { day: "numeric", month: "short", year: "numeric" });
const dayTime = () => new Intl.DateTimeFormat(locale(), { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });

export function formatTaka(amount: string | number | null | undefined) {
  return `৳ ${taka().format(Number(amount ?? 0))}`;
}

export function formatNumber(n: number | string) {
  return number().format(Number(n));
}

export function formatDate(value: string | Date) {
  return day().format(typeof value === "string" ? new Date(value) : value);
}

export function formatDateTime(value: string | Date) {
  return dayTime().format(typeof value === "string" ? new Date(value) : value);
}

export function todayISO(offsetDays = 0) {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export const SLOTS = [
  { value: "09-11", label: "সকাল ৯–১১" },
  { value: "11-13", label: "১১–১" },
  { value: "14-16", label: "দুপুর ২–৪" },
  { value: "16-18", label: "বিকাল ৪–৬" },
  { value: "18-20", label: "সন্ধ্যা ৬–৮" },
  { value: "20-22", label: "রাত ৮–১০" },
];

export function slotOptions() {
  return SLOTS.map((s) => ({ value: s.value, label: t(s.label) }));
}

export function slotLabel(value: string) {
  const slot = SLOTS.find((s) => s.value === value);
  return slot ? t(slot.label) : value;
}

const STATUS: Record<string, { label: string; tone: Tone }> = {
  pending: { label: "অপেক্ষমাণ", tone: "warn" },
  confirmed: { label: "কনফার্মড", tone: "info" },
  on_the_way: { label: "পথে আছে", tone: "info" },
  working: { label: "কাজ চলছে", tone: "info" },
  delivered: { label: "ডেলিভারি হয়েছে", tone: "ok" },
  completed: { label: "সম্পন্ন", tone: "ok" },
  cancelled: { label: "বাতিল", tone: "muted" },
  open: { label: "খোলা", tone: "warn" },
  assigned: { label: "অ্যাসাইন করা", tone: "info" },
  accepted: { label: "গ্রহণ করা", tone: "info" },
  approved: { label: "অনুমোদিত", tone: "ok" },
  rejected: { label: "বাতিল/প্রত্যাখ্যাত", tone: "bad" },
  suspended: { label: "স্থগিত", tone: "bad" },
  submitted: { label: "জমা হয়েছে", tone: "warn" },
  under_review: { label: "রিভিউ চলছে", tone: "info" },
  quote_sent: { label: "কোট পাঠানো হয়েছে", tone: "info" },
  countered: { label: "পাল্টা প্রস্তাব", tone: "warn" },
  provider_assigned: { label: "প্রোভাইডার নির্ধারিত", tone: "info" },
  in_progress: { label: "কাজ চলছে", tone: "info" },
  requested: { label: "অনুরোধ করা", tone: "warn" },
  paid: { label: "পরিশোধিত", tone: "ok" },
  unpaid: { label: "বাকি", tone: "warn" },
  in_payout: { label: "পেআউটে", tone: "info" },
  refunded: { label: "রিফান্ড হয়েছে", tone: "muted" },
  rescheduled: { label: "সময় বদলানো", tone: "info" },
  resolved: { label: "সমাধান হয়েছে", tone: "ok" },
  active: { label: "চালু", tone: "ok" },
  paused: { label: "বিরতিতে", tone: "warn" },
  expired: { label: "মেয়াদ শেষ", tone: "muted" },
  reported: { label: "রিপোর্ট হয়েছে", tone: "warn" },
  forwarded: { label: "পাঠানো হয়েছে", tone: "info" },
  scheduled: { label: "নির্ধারিত", tone: "info" },
  skipped: { label: "বাদ দেওয়া", tone: "muted" },
  failed: { label: "ব্যর্থ", tone: "bad" },
  held: { label: "জমা রাখা", tone: "info" },
  released: { label: "ছাড় করা", tone: "ok" },
  initiated: { label: "শুরু হয়েছে", tone: "warn" },
};

export type Tone = "ok" | "info" | "warn" | "bad" | "muted";

export function statusInfo(status: string) {
  const info = STATUS[status];
  return info ? { label: t(info.label), tone: info.tone } : { label: status, tone: "muted" as Tone };
}
