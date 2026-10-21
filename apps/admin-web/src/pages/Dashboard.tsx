import { api, Card, formatDate, formatTaka, PageHeader, Stat, StatusBadge, statusInfo, t } from "@shohor/web-core";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { usePaged } from "../components";

type OrderStats = { orders_today: number; revenue_today: string; revenue_completed: string; orders_by_status: Record<string, number>; bookings_by_status: Record<string, number>; open_warranty_claims: number; overdue_deliveries: number };
type ProviderStats = { providers_by_status: Record<string, number>; jobs_by_status: Record<string, number>; online_now: number; payouts_requested: number };

function Breakdown({ title, data }: { title: string; data: Record<string, number> | undefined }) {
  const total = Object.values(data ?? {}).reduce((a, b) => a + b, 0) || 1;
  return (
    <Card className="flex flex-col gap-3">
      <h2 className="m-0 text-lg font-bold">{title}</h2>
      {Object.entries(data ?? {}).map(([status, n]) => (
        <div key={status} className="flex flex-col gap-1">
          <div className="flex justify-between text-[15px]">
            <span>{statusInfo(status).label}</span>
            <span className="font-semibold">{n}</span>
          </div>
          <div className="h-2 rounded-full bg-subtle">
            <div className="h-2 rounded-full bg-brand" style={{ width: `${(n / total) * 100}%` }} />
          </div>
        </div>
      ))}
      {!Object.keys(data ?? {}).length && <span className="text-muted">{t("এখনো ডেটা নেই")}</span>}
    </Card>
  );
}

export default function Dashboard() {
  const { data: orders } = useQuery({ queryKey: ["order-stats"], queryFn: async () => (await api.get<OrderStats>("/admin/order-stats/")).data, refetchInterval: 30_000 });
  const { data: providers } = useQuery({ queryKey: ["provider-stats"], queryFn: async () => (await api.get<ProviderStats>("/admin/provider-stats/")).data, refetchInterval: 30_000 });
  const { data: subs } = useQuery({ queryKey: ["sub-stats"], queryFn: async () => (await api.get<{ active_total: number }>("/admin/subscription-stats/")).data });
  const { data: balances } = useQuery({ queryKey: ["balances"], queryFn: async () => (await api.get<Record<string, string>>("/admin/payments/balances/")).data });
  const { data: requests } = usePaged<{ id: number; service_type: string; area_name: string; status: string; created_at: string }>(["admin-cr"], "/admin/custom-requests/", { status: "submitted,under_review,countered" });
  const { data: openJobs } = usePaged<{ id: number; title: string; area_name: string; scheduled_date: string; is_emergency: boolean }>(["admin-jobs"], "/admin/jobs/", { status: "open" });

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("আজকের অবস্থা")} />
      <div className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-3">
        <Stat label={t("আজকের অর্ডার")} value={orders?.orders_today ?? "–"} icon="cart" />
        <Stat label={t("আজকের অর্ডার মূল্য")} value={formatTaka(orders?.revenue_today)} icon="money" />
        <Stat label={t("অনলাইন প্রোভাইডার")} value={providers?.online_now ?? "–"} icon="user" />
        <Stat label={t("যাচাইয়ের অপেক্ষায়")} value={providers?.providers_by_status.pending ?? 0} icon="shield" />
        <Stat label={t("পেআউট অনুরোধ")} value={providers?.payouts_requested ?? 0} icon="money" />
        <Stat label={t("খোলা ওয়ারেন্টি দাবি")} value={orders?.open_warranty_claims ?? 0} icon="refresh" />
        <Link to="/orders?overdue=1" className="text-ink no-underline"><Stat label={t("সময় পেরোনো ডেলিভারি")} value={orders?.overdue_deliveries ?? 0} icon="alert" /></Link>
        <Stat label={t("চালু সাবস্ক্রাইবার")} value={subs?.active_total ?? "–"} icon="repeat" />
        <Stat label={t("এসক্রোতে জমা")} value={formatTaka(balances?.escrow)} icon="shield" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h2 className="m-0 text-lg font-bold">{t("কাস্টম রিকোয়েস্ট কিউ")}</h2>
            <Link to="/custom-requests" className="font-semibold">{t("সব দেখুন")}</Link>
          </div>
          {requests?.results.slice(0, 6).map((r) => (
            <div key={r.id} className="flex items-center gap-3 border-b border-subtle pb-2 last:border-0">
              <span className="flex-1">
                <span className="font-semibold">{r.service_type}</span>
                <span className="block text-sm text-muted">{r.area_name} · {formatDate(r.created_at)}</span>
              </span>
              <StatusBadge status={r.status} />
            </div>
          ))}
          {requests?.results.length === 0 && <span className="text-muted">{t("কিউ খালি।")}</span>}
        </Card>
        <Card className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h2 className="m-0 text-lg font-bold">{t("প্রোভাইডার ছাড়া জব")}</h2>
            <Link to="/jobs" className="font-semibold">{t("অ্যাসাইন করুন")}</Link>
          </div>
          {openJobs?.results.slice(0, 6).map((j) => (
            <div key={j.id} className="flex items-center gap-3 border-b border-subtle pb-2 last:border-0">
              <span className="flex-1">
                <span className="font-semibold">{j.title}</span>
                <span className="block text-sm text-muted">{j.area_name} · {formatDate(j.scheduled_date)}</span>
              </span>
              {j.is_emergency && <span className="rounded-full bg-bad-soft px-2 py-1 text-xs font-semibold text-bad">{t("জরুরি")}</span>}
            </div>
          ))}
          {openJobs?.results.length === 0 && <span className="text-muted">{t("সব জবে প্রোভাইডার আছে।")}</span>}
        </Card>
        <Breakdown title={t("অর্ডারের অবস্থা")} data={orders?.orders_by_status} />
        <Breakdown title={t("জবের অবস্থা")} data={providers?.jobs_by_status} />
      </div>
    </div>
  );
}
