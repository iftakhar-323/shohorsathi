import { Button, Card, ErrorNote, Field, Modal, PageHeader, Select, Stat, StatusBadge, Tabs, api, errorMessage, formatDate, formatTaka, localName, slotLabel, t, todayISO } from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { DataTable, FilterChips, PrivateImage, usePaged } from "../components";

type Plan = { id: number; slug: string; category: string; name_bn: string; name_en: string; is_active: boolean; sizes_apply: boolean; prices: { id: number; duration_days: number; home_size: number; price: string }[] };
type Sub = { id: number; plan: Plan; customer_name: string; customer_phone: string; area_name: string; start_date: string; end_date: string; price: string; status: string; paid: boolean; preferred_provider_name: string; stats: Record<string, number> };
type Visit = { id: number; date: string; slot: string; kind: string; meal_type: string; status: string; provider_name: string; rating: number | null };
type Student = { id: number; user_id: number; institution: string; id_card_url: string; status: string; created_at: string };
type Menu = { id: number; date: string; meal_type: string; diet: string; items_bn: string; items_en: string };

type Tab = "subscriptions" | "plans" | "students" | "menu";

function SubscriptionList() {
  const [status, setStatus] = useState("active");
  const { data, isPending } = usePaged<Sub>(["admin-subs"], "/admin/subscriptions/", { status: status || undefined });
  const [open, setOpen] = useState<Sub | null>(null);
  const { data: visits } = useQuery({
    queryKey: ["admin-subs", open?.id, "visits"],
    queryFn: async () => (await api.get<Visit[]>(`/admin/subscriptions/${open!.id}/visits/`)).data,
    enabled: !!open,
  });
  return (
    <>
      <FilterChips value={status} onChange={setStatus} options={[{ value: "active", label: t("চালু") }, { value: "pending_payment", label: t("পেমেন্ট বাকি") }, { value: "paused", label: t("বিরতিতে") }, { value: "cancelled", label: t("বাতিল") }, { value: "", label: t("সব") }]} />
      <DataTable
        loading={isPending}
        rows={data?.results}
        onRowClick={setOpen}
        columns={[
          { label: t("প্ল্যান"), render: (s) => <span className="font-semibold">{localName(s.plan)}</span> },
          { label: t("গ্রাহক"), render: (s) => <>{s.customer_name}<span className="block text-[13px] text-muted">{s.customer_phone}</span></> },
          { label: t("এলাকা"), render: (s) => s.area_name },
          { label: t("মেয়াদ"), render: (s) => `${formatDate(s.start_date)} – ${formatDate(s.end_date)}` },
          { label: t("মূল্য"), render: (s) => formatTaka(s.price) },
          { label: t("প্রোভাইডার"), render: (s) => s.preferred_provider_name || "—" },
          { label: t("অবস্থা"), render: (s) => <StatusBadge status={s.status} /> },
        ]}
      />
      <Modal title={open ? localName(open.plan) : ""} open={!!open} onClose={() => setOpen(null)}>
        {visits?.map((v) => (
          <div key={v.id} className="flex items-center gap-3 border-b border-subtle pb-2 text-[15px]">
            <span className="w-28">{formatDate(v.date)}</span>
            <span className="flex-1">{v.meal_type || v.kind} · {slotLabel(v.slot)} {v.provider_name && `· ${v.provider_name}`} {v.rating && `· ${v.rating}★`}</span>
            <StatusBadge status={v.status} />
          </div>
        ))}
      </Modal>
    </>
  );
}

function PlanPrices() {
  const qc = useQueryClient();
  const { data: plans } = useQuery({ queryKey: ["admin-plans"], queryFn: async () => (await api.get<Plan[]>("/subscription-plans/")).data });
  const [error, setError] = useState("");

  async function save(id: number, price: string) {
    setError("");
    try {
      await api.patch(`/admin/plan-prices/${id}/`, { price });
      qc.invalidateQueries({ queryKey: ["admin-plans"] });
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function toggle(p: Plan) {
    await api.patch(`/subscription-plans/${p.slug}/`, { is_active: !p.is_active });
    qc.invalidateQueries({ queryKey: ["admin-plans"] });
  }

  return (
    <div className="flex flex-col gap-3">
      <ErrorNote>{error}</ErrorNote>
      {plans?.map((p) => (
        <Card key={p.id} className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <span className="flex-1 text-lg font-bold">{localName(p)} <span className="text-sm font-normal text-muted">({p.category})</span></span>
            <Button variant={p.is_active ? "ghost" : "secondary"} onClick={() => toggle(p)}>{p.is_active ? t("বন্ধ করুন") : t("চালু করুন")}</Button>
          </div>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(150px,1fr))] gap-2">
            {p.prices.map((row) => (
              <label key={row.id} className="flex flex-col gap-1 text-sm">
                <span className="text-muted">{row.duration_days} {t("দিন")}{row.home_size ? ` · ${row.home_size} BR` : ""}</span>
                <input type="number" min={0} defaultValue={row.price} onBlur={(e) => e.target.value !== row.price && save(row.id, e.target.value)} className="h-10 rounded-xl border border-line px-3" />
              </label>
            ))}
          </div>
        </Card>
      ))}
    </div>
  );
}

function Students() {
  const qc = useQueryClient();
  const { data, isPending } = usePaged<Student>(["admin-students"], "/admin/student-verifications/", { status: "pending" });
  async function decide(s: Student, status: "approved" | "rejected") {
    await api.post(`/admin/student-verifications/${s.id}/decide/`, { status });
    qc.invalidateQueries({ queryKey: ["admin-students"] });
  }
  return (
    <DataTable
      loading={isPending}
      rows={data?.results}
      empty={t("যাচাইয়ের অপেক্ষায় কেউ নেই")}
      columns={[
        { label: t("প্রতিষ্ঠান"), render: (s) => s.institution },
        { label: t("আইডি কার্ড"), render: (s) => <PrivateImage url={s.id_card_url} alt={t("স্টুডেন্ট আইডি কার্ড")} /> },
        { label: t("তারিখ"), render: (s) => formatDate(s.created_at) },
        { label: "", render: (s) => <div className="flex gap-2"><Button onClick={() => decide(s, "approved")}>{t("অনুমোদন")}</Button><Button variant="ghost" onClick={() => decide(s, "rejected")}>{t("প্রত্যাখ্যান")}</Button></div> },
      ]}
    />
  );
}

function MealMenu() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["admin-menu"], queryFn: async () => (await api.get<Menu[]>("/meal-menu/")).data });
  const [f, setF] = useState({ date: todayISO(1), meal_type: "lunch", diet: "bangla", items_bn: "", items_en: "" });
  const [error, setError] = useState("");

  async function add(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.post("/meal-menu/", f);
      setF({ ...f, items_bn: "", items_en: "" });
      qc.invalidateQueries({ queryKey: ["admin-menu"] });
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={add} className="grid items-end gap-3 rounded-[20px] border border-line bg-surface p-4 sm:grid-cols-3">
        <Field label={t("তারিখ")} type="date" value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} />
        <Select label={t("বেলা")} value={f.meal_type} onChange={(e) => setF({ ...f, meal_type: e.target.value })} options={[{ value: "breakfast", label: t("সকালের নাস্তা") }, { value: "lunch", label: t("দুপুরের খাবার") }, { value: "dinner", label: t("রাতের খাবার") }]} />
        <Select label={t("খাবারের ধরন")} value={f.diet} onChange={(e) => setF({ ...f, diet: e.target.value })} options={[{ value: "bangla", label: t("বাংলা ঘরোয়া খাবার") }, { value: "light", label: t("হালকা খাবার") }, { value: "protein", label: t("প্রোটিন-সমৃদ্ধ") }]} />
        <Field label={t("মেনু (বাংলা)")} required value={f.items_bn} onChange={(e) => setF({ ...f, items_bn: e.target.value })} placeholder="ভাত, ডাল, মুরগি" />
        <Field label={t("মেনু (English)")} required value={f.items_en} onChange={(e) => setF({ ...f, items_en: e.target.value })} placeholder="Rice, dal, chicken" />
        <Button type="submit" icon="plus">{t("যোগ করুন")}</Button>
      </form>
      <ErrorNote>{error}</ErrorNote>
      <DataTable rows={data} columns={[
        { label: t("তারিখ"), render: (m) => formatDate(m.date) },
        { label: t("বেলা"), render: (m) => m.meal_type },
        { label: t("খাবারের ধরন"), render: (m) => m.diet },
        { label: t("মেনু"), render: (m) => <>{m.items_bn}<span className="block text-[13px] text-muted">{m.items_en}</span></> },
      ]} />
    </div>
  );
}

export default function Subscriptions() {
  const [tab, setTab] = useState<Tab>("subscriptions");
  const { data: stats } = useQuery({
    queryKey: ["sub-stats"],
    queryFn: async () => (await api.get<{ active_total: number; recurring_value: string; visits_tomorrow: number; students_pending: number }>("/admin/subscription-stats/")).data,
  });
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t("সাবস্ক্রিপশন")} subtitle={t("ক্লিনিং, মিল ও পরিবারের ৭/১৫/৩০ দিনের প্ল্যান")} />
      <div className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-3">
        <Stat label={t("চালু সাবস্ক্রাইবার")} value={stats?.active_total ?? "–"} icon="repeat" />
        <Stat label={t("নিয়মিত আয় (চালু)")} value={formatTaka(stats?.recurring_value)} icon="money" />
        <Stat label={t("আগামীকালের ভিজিট/মিল")} value={stats?.visits_tomorrow ?? "–"} icon="calendar" />
        <Stat label={t("স্টুডেন্ট যাচাই বাকি")} value={stats?.students_pending ?? 0} icon="user" />
      </div>
      <Tabs value={tab} onChange={setTab} tabs={[{ value: "subscriptions", label: t("সাবস্ক্রিপশন") }, { value: "plans", label: t("প্ল্যান ও দাম") }, { value: "students", label: t("স্টুডেন্ট যাচাই") }, { value: "menu", label: t("মিল মেনু") }]} />
      {tab === "subscriptions" && <SubscriptionList />}
      {tab === "plans" && <PlanPrices />}
      {tab === "students" && <Students />}
      {tab === "menu" && <MealMenu />}
    </div>
  );
}
