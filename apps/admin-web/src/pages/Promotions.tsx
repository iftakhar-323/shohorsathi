import { api, Badge, Button, errorMessage, ErrorNote, Field, formatDate, formatTaka, PageHeader, Select, t, Tabs, useServices, type Paginated } from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { DataTable } from "../components";

type GroupDeal = {
  id: number;
  title_bn: string;
  service_name_bn: string;
  base_price: string;
  discounted_price: string;
  discount_percent: number;
  current_participants: number;
  target_participants: number;
  is_locked_in: boolean;
  expires_at: string;
};

type SeasonalPackage = {
  id: number;
  title_bn: string;
  season: string;
  service_slugs: string[];
  discount_percent: number;
  active_from: string;
  active_until: string;
};

const SEASONS = [
  { value: "eid", label: "ঈদ" },
  { value: "summer", label: "গ্রীষ্ম" },
  { value: "monsoon", label: "বর্ষা" },
  { value: "winter", label: "শীত" },
  { value: "puja", label: "পূজা" },
];

export default function Promotions() {
  const [tab, setTab] = useState<"deals" | "seasonal" | "sponsored">("deals");
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("গ্রুপ ডিল ও মৌসুমি প্যাকেজ")} subtitle={t("প্রতিবেশীদের একসাথে বুকিং ছাড় এবং উৎসব/মৌসুমের অফার")} />
      <Tabs value={tab} onChange={setTab} tabs={[{ value: "deals", label: t("গ্রুপ ডিল") }, { value: "seasonal", label: t("মৌসুমি প্যাকেজ") }, { value: "sponsored", label: t("স্পন্সরড লিস্টিং") }]} />
      {tab === "deals" && <Deals />}
      {tab === "seasonal" && <Seasonal />}
      {tab === "sponsored" && <Sponsored />}
    </div>
  );
}

function useEnd(qc: ReturnType<typeof useQueryClient>, path: string, key: string) {
  return async (id: number) => {
    await api.patch(`${path}${id}/`, { is_active: false });
    qc.invalidateQueries({ queryKey: [key] });
  };
}

function Deals() {
  const qc = useQueryClient();
  const { data: services } = useServices();
  const { data: deals, isPending } = useQuery({
    queryKey: ["admin-group-deals"],
    queryFn: async () => (await api.get<Paginated<GroupDeal>>("/group-deals/")).data.results,
  });
  const [form, setForm] = useState({ title_bn: "", title_en: "", service: "", target_participants: "3", discount_percent: "15", expires_at: "" });
  const [error, setError] = useState("");
  const end = useEnd(qc, "/group-deals/", "admin-group-deals");

  async function create(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.post("/group-deals/", { ...form, service: Number(form.service), expires_at: new Date(form.expires_at).toISOString() });
      setForm({ ...form, title_bn: "", title_en: "" });
      qc.invalidateQueries({ queryKey: ["admin-group-deals"] });
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={create} className="grid gap-3 rounded-[20px] border border-line bg-surface p-5 sm:grid-cols-3">
        <Field label={t("শিরোনাম (বাংলা)")} required value={form.title_bn} onChange={(e) => setForm({ ...form, title_bn: e.target.value })} />
        <Field label={t("শিরোনাম (ইংরেজি)")} required value={form.title_en} onChange={(e) => setForm({ ...form, title_en: e.target.value })} />
        <Select label={t("সার্ভিস")} required value={form.service} onChange={(e) => setForm({ ...form, service: e.target.value })}
          options={[{ value: "", label: t("বাছাই করুন") }, ...(services?.results ?? []).map((s) => ({ value: String(s.id), label: s.name_bn }))]} />
        <Field label={t("কত ফ্ল্যাট লাগবে")} type="number" min={2} value={form.target_participants} onChange={(e) => setForm({ ...form, target_participants: e.target.value })} />
        <Field label={t("ছাড় (%)")} type="number" min={1} max={60} value={form.discount_percent} onChange={(e) => setForm({ ...form, discount_percent: e.target.value })} />
        <Field label={t("শেষ সময়")} type="datetime-local" required value={form.expires_at} onChange={(e) => setForm({ ...form, expires_at: e.target.value })} />
        <ErrorNote>{error}</ErrorNote>
        <Button type="submit" icon="plus" className="self-end">{t("ডিল চালু করুন")}</Button>
      </form>
      <DataTable
        loading={isPending}
        rows={deals}
        columns={[
          { label: t("ডিল"), render: (d) => <span className="font-semibold">{d.title_bn}</span> },
          { label: t("সার্ভিস"), render: (d) => d.service_name_bn },
          { label: t("দাম"), render: (d) => `${formatTaka(d.discounted_price)} (−${d.discount_percent}%)` },
          { label: t("যোগ দিয়েছে"), render: (d) => <Badge tone={d.is_locked_in ? "ok" : "warn"}>{`${d.current_participants}/${d.target_participants}`}</Badge> },
          { label: t("শেষ"), render: (d) => formatDate(d.expires_at) },
          { label: "", render: (d) => <Button variant="ghost" onClick={() => end(d.id)}>{t("বন্ধ করুন")}</Button> },
        ]}
      />
    </div>
  );
}

function Seasonal() {
  const qc = useQueryClient();
  const { data: packages, isPending } = useQuery({
    queryKey: ["admin-seasonal"],
    queryFn: async () => (await api.get<Paginated<SeasonalPackage>>("/seasonal-packages/")).data.results,
  });
  const [form, setForm] = useState({ title_bn: "", title_en: "", tagline_bn: "", tagline_en: "", season: "eid", service_slugs: "", discount_percent: "20", active_from: "", active_until: "" });
  const [error, setError] = useState("");
  const end = useEnd(qc, "/seasonal-packages/", "admin-seasonal");
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });

  async function create(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.post("/seasonal-packages/", { ...form, service_slugs: form.service_slugs.split(",").map((s) => s.trim()).filter(Boolean) });
      qc.invalidateQueries({ queryKey: ["admin-seasonal"] });
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={create} className="grid gap-3 rounded-[20px] border border-line bg-surface p-5 sm:grid-cols-3">
        <Field label={t("শিরোনাম (বাংলা)")} required value={form.title_bn} onChange={set("title_bn")} />
        <Field label={t("শিরোনাম (ইংরেজি)")} required value={form.title_en} onChange={set("title_en")} />
        <Select label={t("মৌসুম")} value={form.season} onChange={set("season")} options={SEASONS.map((s) => ({ ...s, label: t(s.label) }))} />
        <Field label={t("ট্যাগলাইন (বাংলা)")} value={form.tagline_bn} onChange={set("tagline_bn")} />
        <Field label={t("ট্যাগলাইন (ইংরেজি)")} value={form.tagline_en} onChange={set("tagline_en")} />
        <Field label={t("সার্ভিস স্লাগ (কমা দিয়ে)")} value={form.service_slugs} onChange={set("service_slugs")} placeholder="ac-cleaning, home-deep-clean" />
        <Field label={t("ছাড় (%)")} type="number" min={1} max={60} value={form.discount_percent} onChange={set("discount_percent")} />
        <Field label={t("শুরু")} type="date" required value={form.active_from} onChange={set("active_from")} />
        <Field label={t("শেষ")} type="date" required value={form.active_until} onChange={set("active_until")} />
        <ErrorNote>{error}</ErrorNote>
        <Button type="submit" icon="plus" className="self-end">{t("প্যাকেজ যোগ করুন")}</Button>
      </form>
      <DataTable
        loading={isPending}
        rows={packages}
        columns={[
          { label: t("প্যাকেজ"), render: (p) => <span className="font-semibold">{p.title_bn}</span> },
          { label: t("মৌসুম"), render: (p) => t(SEASONS.find((s) => s.value === p.season)?.label ?? p.season) },
          { label: t("সার্ভিস"), render: (p) => p.service_slugs.join(", ") },
          { label: t("ছাড় (%)"), render: (p) => `${p.discount_percent}%` },
          { label: t("সময়"), render: (p) => `${formatDate(p.active_from)} – ${formatDate(p.active_until)}` },
          { label: "", render: (p) => <Button variant="ghost" onClick={() => end(p.id)}>{t("বন্ধ করুন")}</Button> },
        ]}
      />
    </div>
  );
}

type Placement = { id: number; item_type: string; slug: string; name: string; sponsor_name: string; fee: string; starts_at: string; ends_at: string };

/** Paid placements: a shop or provider pays to have a service/product listed first for some days. */
function Sponsored() {
  const qc = useQueryClient();
  const { data: services } = useServices();
  const { data: placements, isPending } = useQuery({
    queryKey: ["admin-sponsored"],
    queryFn: async () => (await api.get<Paginated<Placement>>("/catalog/sponsored/")).data.results,
  });
  const [form, setForm] = useState({ slug: "", days: "7", fee: "1000", sponsor_name: "" });
  const [error, setError] = useState("");

  async function book(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.post(`/services/${form.slug}/sponsor/`, { days: Number(form.days), fee: form.fee, sponsor_name: form.sponsor_name });
      setForm({ ...form, sponsor_name: "" });
      qc.invalidateQueries({ queryKey: ["admin-sponsored"] });
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={book} className="grid gap-3 rounded-[20px] border border-line bg-surface p-5 sm:grid-cols-4">
        <Select label={t("সার্ভিস")} required value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })}
          options={[{ value: "", label: t("বাছাই করুন") }, ...(services?.results ?? []).map((s) => ({ value: s.slug, label: s.name_bn }))]} />
        <Field label={t("স্পন্সর (দোকান/প্রোভাইডার)")} required value={form.sponsor_name} onChange={(e) => setForm({ ...form, sponsor_name: e.target.value })} />
        <Field label={t("কত দিন")} type="number" min={1} max={90} value={form.days} onChange={(e) => setForm({ ...form, days: e.target.value })} />
        <Field label={t("ফি (৳)")} type="number" min={0} value={form.fee} onChange={(e) => setForm({ ...form, fee: e.target.value })} />
        <ErrorNote>{error}</ErrorNote>
        <Button type="submit" icon="plus" className="self-end">{t("স্পন্সর করুন")}</Button>
      </form>
      <DataTable
        loading={isPending}
        rows={placements}
        columns={[
          { label: t("সার্ভিস"), render: (p) => <span className="font-semibold">{p.name}</span> },
          { label: t("স্পন্সর"), render: (p) => p.sponsor_name },
          { label: t("ফি (৳)"), render: (p) => formatTaka(p.fee) },
          { label: t("সময়"), render: (p) => `${formatDate(p.starts_at)} – ${formatDate(p.ends_at)}` },
        ]}
      />
    </div>
  );
}
