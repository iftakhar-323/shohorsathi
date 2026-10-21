import { Badge, Button, Card, ErrorNote, MapView, PageHeader, Select, Stat, SuccessNote, Tabs, api, errorMessage, formatDate, formatNumber, formatTaka, t, useCities, type MapPoint } from "@shohor/web-core";
import { useQuery } from "@tanstack/react-query";

import { DataTable } from "../components";
import { useState } from "react";

type Summary = {
  gmv: string; revenue_completed: string; commission: string; orders: number; orders_completed: number; orders_cancelled: number;
  bookings: number; emergency_bookings: number; subscriptions_new: number; subscriptions_renewed: number; subscription_value: string;
  customers_new: number; customers_returning: number; issues_resolved: number;
  top_services: { title: string; n: number; value: string }[]; top_categories: { category: string; n: number }[];
  by_area: { area_id: number; area_name: string; n: number }[]; daily: { day: string; orders: number; value: string }[];
};

function Bars({ rows, label, value }: { rows: { key: string; label: string; n: number }[]; label: string; value?: (n: number) => string }) {
  const max = Math.max(1, ...rows.map((r) => r.n));
  return (
    <Card className="flex flex-col gap-2">
      <h2 className="m-0 text-lg font-bold">{label}</h2>
      {rows.length === 0 && <span className="text-muted">{t("এখনো ডেটা নেই")}</span>}
      {rows.map((r) => (
        <div key={r.key} className="grid grid-cols-[minmax(0,10rem)_1fr_auto] items-center gap-3 text-[15px]">
          <span className="truncate">{r.label}</span>
          <div className="h-3 rounded-full bg-subtle"><div className="h-3 rounded-full bg-brand" style={{ width: `${(r.n / max) * 100}%` }} /></div>
          <span className="font-semibold tabular-nums">{value ? value(r.n) : formatNumber(r.n)}</span>
        </div>
      ))}
    </Card>
  );
}

function Daily({ rows }: { rows: Summary["daily"] }) {
  const max = Math.max(1, ...rows.map((r) => Number(r.value)));
  return (
    <Card className="flex flex-col gap-3">
      <h2 className="m-0 text-lg font-bold">{t("দৈনিক অর্ডার মূল্য")}</h2>
      {rows.length === 0 ? <span className="text-muted">{t("এখনো ডেটা নেই")}</span> : (
        <div className="flex h-44 items-end gap-1" role="img" aria-label={t("দৈনিক অর্ডার মূল্য")}>
          {rows.map((r) => (
            <div key={r.day} className="group relative flex flex-1 flex-col items-center justify-end">
              <div className="w-full min-w-1 rounded-t bg-brand" style={{ height: `${(Number(r.value) / max) * 160}px` }} title={`${formatDate(r.day)}: ${formatTaka(r.value)} (${r.orders})`} />
            </div>
          ))}
        </div>
      )}
      {rows.length > 0 && <div className="flex justify-between text-[12px] text-muted"><span>{formatDate(rows[0].day)}</span><span>{formatDate(rows[rows.length - 1].day)}</span></div>}
    </Card>
  );
}

type Forecast = { category: string; trend: number; last_14_days: number; week_total: number; days: { date: string; expected: number; providers_needed: number }[] };
type Churn = { user_id: number; orders: number; value: string; last_order: string; days_since: number; usual_gap_days: number | null; score: number; risk: "high" | "medium" };
type Flag = { kind: string; severity: "high" | "medium" | "low"; user_ids: number[]; detail: string };
type Revenue = { commission: string; sponsored_listings: string; total: string };

const FLAG_KIND: Record<string, string> = {
  cancel_abuse: "বারবার অর্ডার বাতিল",
  order_burst: "এক ঘণ্টায় অনেক অর্ডার",
  shared_location: "একই ঠিকানায় অনেক অ্যাকাউন্ট",
  big_first_cod: "প্রথম অর্ডারেই বড় ক্যাশ অন ডেলিভারি",
};
const SEVERITY_TONE = { high: "bad", medium: "warn", low: "info" } as const;

/** Next 7 days per category; bar height is expected bookings, the hover shows how many providers that needs. */
function ForecastView({ city }: { city?: string }) {
  const { data, isPending } = useQuery({
    queryKey: ["forecast", city],
    queryFn: async () => (await api.get<Forecast[]>("/admin/analytics/forecast/", { params: { city } })).data,
  });
  if (isPending) return null;
  if (!data?.length) return <Card><span className="text-muted">{t("পূর্বাভাসের জন্য অন্তত কয়েক সপ্তাহের বুকিং দরকার।")}</span></Card>;
  return (
    <div className="flex flex-col gap-4">
      <p className="m-0 text-sm text-muted">{t("গত ৮ সপ্তাহের একই বারের গড় × সাম্প্রতিক প্রবণতা (গত ১৪ দিন বনাম আগের ১৪ দিন)।")}</p>
      <div className="grid gap-4 lg:grid-cols-2">
        {data.map((c) => {
          const max = Math.max(1, ...c.days.map((d) => d.expected));
          return (
            <Card key={c.category} className="flex flex-col gap-3">
              <div className="flex items-center justify-between gap-2">
                <h2 className="m-0 text-lg font-bold">{c.category}</h2>
                <span className="text-sm text-muted">
                  {t("সপ্তাহে ~{n} বুকিং", { n: c.week_total })} · {c.trend >= 1 ? "↑" : "↓"} {Math.round((c.trend - 1) * 100)}%
                </span>
              </div>
              <div className="flex h-28 items-end gap-2" role="img" aria-label={t("সপ্তাহে ~{n} বুকিং", { n: c.week_total })}>
                {c.days.map((d) => (
                  <div key={d.date} className="flex flex-1 flex-col items-center gap-1" title={`${formatDate(d.date)}: ${d.expected} · ${t("প্রোভাইডার লাগবে")} ${d.providers_needed}`}>
                    <span className="text-[12px] tabular-nums text-muted">{d.expected}</span>
                    <div className="w-full rounded-t bg-brand" style={{ height: `${(d.expected / max) * 72}px`, minHeight: d.expected ? 2 : 0 }} />
                    <span className="text-[12px] text-muted">{new Date(d.date).toLocaleDateString(undefined, { weekday: "short" })}</span>
                  </div>
                ))}
              </div>
              <span className="text-sm">{t("সবচেয়ে ব্যস্ত দিনে প্রোভাইডার লাগবে")}: <b>{Math.max(...c.days.map((d) => d.providers_needed))}</b></span>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

function ChurnView({ city }: { city?: string }) {
  const { data, isPending } = useQuery({
    queryKey: ["churn", city],
    queryFn: async () => (await api.get<Churn[]>("/admin/analytics/churn/", { params: { city } })).data,
  });
  const [picked, setPicked] = useState<number[]>([]);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  async function winback() {
    setError("");
    try {
      const { data: r } = await api.post<{ sent: number }>("/admin/analytics/churn/winback/", { user_ids: picked });
      setNotice(t("{n} জন গ্রাহককে বার্তা পাঠানো হয়েছে।", { n: r.sent }));
      setPicked([]);
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  const toggle = (id: number) => setPicked(picked.includes(id) ? picked.filter((x) => x !== id) : [...picked, id]);
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <p className="m-0 flex-1 text-sm text-muted">{t("শেষ অর্ডারের পর যতদিন গেছে ÷ গ্রাহকের স্বাভাবিক বিরতি। ২× হলে ঝুঁকি, ৩× হলে বেশি ঝুঁকি।")}</p>
        <Button icon="send" disabled={!picked.length} onClick={winback}>{t("ফিরে আসার বার্তা পাঠান ({n})", { n: picked.length })}</Button>
      </div>
      <SuccessNote>{notice}</SuccessNote>
      <ErrorNote>{error}</ErrorNote>
      <DataTable
        loading={isPending}
        rows={data?.map((c) => ({ ...c, id: c.user_id }))}
        columns={[
          { label: "", render: (c) => <input type="checkbox" aria-label={`#${c.user_id}`} checked={picked.includes(c.user_id)} onChange={() => toggle(c.user_id)} className="size-5 accent-brand" /> },
          { label: t("গ্রাহক"), render: (c) => `#${c.user_id}` },
          { label: t("অর্ডার"), render: (c) => c.orders },
          { label: t("মোট মূল্য"), render: (c) => formatTaka(c.value) },
          { label: t("শেষ অর্ডার"), render: (c) => `${formatDate(c.last_order)} (${t("{n} দিন আগে", { n: c.days_since })})` },
          { label: t("স্বাভাবিক বিরতি"), render: (c) => (c.usual_gap_days ? t("{n} দিন", { n: c.usual_gap_days }) : t("একবার অর্ডার")) },
          { label: t("ঝুঁকি"), render: (c) => <Badge tone={c.risk === "high" ? "bad" : "warn"}>{`${c.risk === "high" ? t("বেশি") : t("মাঝারি")} · ${c.score}×`}</Badge> },
        ]}
      />
    </div>
  );
}

function FraudView({ days }: { days: string }) {
  const { data, isPending } = useQuery({
    queryKey: ["fraud", days],
    queryFn: async () => (await api.get<Flag[]>("/admin/analytics/fraud/", { params: { days } })).data,
  });
  return (
    <div className="flex flex-col gap-3">
      <p className="m-0 text-sm text-muted">{t("এগুলো সন্দেহের সংকেত, প্রমাণ নয় — কাউকে ব্লক করার আগে অর্ডার ও ইউজার দেখে নিন।")}</p>
      <DataTable
        loading={isPending}
        rows={data?.map((f, i) => ({ ...f, id: i }))}
        columns={[
          { label: t("ঝুঁকি"), render: (f) => <Badge tone={SEVERITY_TONE[f.severity]}>{t(f.severity === "high" ? "বেশি" : f.severity === "medium" ? "মাঝারি" : "কম")}</Badge> },
          { label: t("সংকেত"), render: (f) => <span className="font-semibold">{t(FLAG_KIND[f.kind] ?? f.kind)}</span> },
          { label: t("বিস্তারিত"), render: (f) => f.detail },
          { label: t("ইউজার"), render: (f) => f.user_ids.map((u) => `#${u}`).join(", ") },
        ]}
      />
    </div>
  );
}

export default function Analytics() {
  const [tab, setTab] = useState<"overview" | "forecast" | "churn" | "fraud">("overview");
  const [days, setDays] = useState("30");
  const [city, setCity] = useState("");
  const { data: cities } = useCities();
  const params = { days, city: city || undefined };
  const { data: s } = useQuery({ queryKey: ["analytics", params], queryFn: async () => (await api.get<Summary>("/admin/analytics/summary/", { params })).data });
  const { data: heat } = useQuery({ queryKey: ["heatmap", params], queryFn: async () => (await api.get<{ lat: number; lng: number; n: number }[]>("/admin/analytics/heatmap/", { params })).data });
  const { data: revenue } = useQuery({ queryKey: ["revenue", params], queryFn: async () => (await api.get<Revenue>("/admin/analytics/revenue/", { params })).data });
  const points: MapPoint[] = (heat ?? []).map((h, i) => ({ id: i, lat: h.lat, lng: h.lng, radius: 5 + Math.min(h.n * 2, 20), color: "#B45309", label: `${h.n}` }));

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title={t("অ্যানালিটিক্স")}
        subtitle={t("বিক্রি, আয়, জনপ্রিয় সার্ভিস ও এলাকাভিত্তিক চাহিদা")}
        actions={
          <div className="flex gap-2">
            <Select label={t("সময়")} value={days} onChange={(e) => setDays(e.target.value)} options={[{ value: "7", label: t("৭ দিন") }, { value: "30", label: t("৩০ দিন") }, { value: "90", label: t("৯০ দিন") }, { value: "365", label: t("১ বছর") }]} />
            <Select label={t("শহর")} value={city} onChange={(e) => setCity(e.target.value)} options={[{ value: "", label: t("সব শহর") }, ...(cities ?? []).map((c) => ({ value: c, label: t(c) }))]} />
          </div>
        }
      />
      <Tabs value={tab} onChange={setTab} tabs={[
        { value: "overview", label: t("সারসংক্ষেপ") },
        { value: "forecast", label: t("চাহিদার পূর্বাভাস") },
        { value: "churn", label: t("হারানোর ঝুঁকিতে গ্রাহক") },
        { value: "fraud", label: t("জালিয়াতির সংকেত") },
      ]} />
      {tab === "forecast" && <ForecastView city={city || undefined} />}
      {tab === "churn" && <ChurnView city={city || undefined} />}
      {tab === "fraud" && <FraudView days={days} />}
      {tab === "overview" && <>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-3">
        <Stat label={t("মোট অর্ডার মূল্য (GMV)")} value={formatTaka(s?.gmv)} icon="cart" />
        <Stat label={t("সম্পন্ন অর্ডারের আয়")} value={formatTaka(s?.revenue_completed)} icon="money" />
        <Stat label={t("প্ল্যাটফর্ম কমিশন")} value={formatTaka(s?.commission)} icon="chart" />
        <Stat label={t("অর্ডার / সম্পন্ন / বাতিল")} value={s ? `${s.orders} / ${s.orders_completed} / ${s.orders_cancelled}` : "–"} icon="list" />
        <Stat label={t("বুকিং (জরুরি)")} value={s ? `${s.bookings} (${s.emergency_bookings})` : "–"} icon="wrench" />
        <Stat label={t("নতুন / রিনিউ সাবস্ক্রিপশন")} value={s ? `${s.subscriptions_new} / ${s.subscriptions_renewed}` : "–"} icon="repeat" />
        <Stat label={t("নতুন বনাম পুরনো গ্রাহক")} value={s ? `${s.customers_new} / ${s.customers_returning}` : "–"} icon="user" />
        <Stat label={t("সমাধান হওয়া সমস্যা")} value={s?.issues_resolved ?? "–"} icon="flag" />
        <Stat label={t("স্পন্সরড লিস্টিং আয়")} value={formatTaka(revenue?.sponsored_listings)} icon="gift" />
        <Stat label={t("প্ল্যাটফর্মের মোট আয়")} value={formatTaka(revenue?.total)} icon="money" />
      </div>
      <Daily rows={s?.daily ?? []} />
      <div className="grid gap-4 lg:grid-cols-2">
        <Bars label={t("জনপ্রিয় সার্ভিস")} rows={(s?.top_services ?? []).map((r) => ({ key: r.title, label: r.title, n: r.n }))} />
        <Bars label={t("এলাকাভিত্তিক চাহিদা")} rows={(s?.by_area ?? []).map((r) => ({ key: String(r.area_id), label: r.area_name, n: r.n }))} />
      </div>
      <Card className="flex flex-col gap-3">
        <h2 className="m-0 text-lg font-bold">{t("চাহিদার হিটম্যাপ")}</h2>
        <p className="m-0 text-sm text-muted">{t("বড় বৃত্ত মানে বেশি বুকিং; নতুন প্রোভাইডার কোথায় দরকার বুঝতে সাহায্য করে।")}</p>
        <MapView points={points} zoom={12} height={380} />
      </Card>
      </>}
    </div>
  );
}
