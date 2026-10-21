import { Card, MapView, PageHeader, Select, Stat, api, formatDate, formatNumber, formatTaka, t, useCities, type MapPoint } from "@shohor/web-core";
import { useQuery } from "@tanstack/react-query";
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

export default function Analytics() {
  const [days, setDays] = useState("30");
  const [city, setCity] = useState("");
  const { data: cities } = useCities();
  const params = { days, city: city || undefined };
  const { data: s } = useQuery({ queryKey: ["analytics", params], queryFn: async () => (await api.get<Summary>("/admin/analytics/summary/", { params })).data });
  const { data: heat } = useQuery({ queryKey: ["heatmap", params], queryFn: async () => (await api.get<{ lat: number; lng: number; n: number }[]>("/admin/analytics/heatmap/", { params })).data });
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
      <div className="grid grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-3">
        <Stat label={t("মোট অর্ডার মূল্য (GMV)")} value={formatTaka(s?.gmv)} icon="cart" />
        <Stat label={t("সম্পন্ন অর্ডারের আয়")} value={formatTaka(s?.revenue_completed)} icon="money" />
        <Stat label={t("প্ল্যাটফর্ম কমিশন")} value={formatTaka(s?.commission)} icon="chart" />
        <Stat label={t("অর্ডার / সম্পন্ন / বাতিল")} value={s ? `${s.orders} / ${s.orders_completed} / ${s.orders_cancelled}` : "–"} icon="list" />
        <Stat label={t("বুকিং (জরুরি)")} value={s ? `${s.bookings} (${s.emergency_bookings})` : "–"} icon="wrench" />
        <Stat label={t("নতুন / রিনিউ সাবস্ক্রিপশন")} value={s ? `${s.subscriptions_new} / ${s.subscriptions_renewed}` : "–"} icon="repeat" />
        <Stat label={t("নতুন বনাম পুরনো গ্রাহক")} value={s ? `${s.customers_new} / ${s.customers_returning}` : "–"} icon="user" />
        <Stat label={t("সমাধান হওয়া সমস্যা")} value={s?.issues_resolved ?? "–"} icon="flag" />
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
    </div>
  );
}
