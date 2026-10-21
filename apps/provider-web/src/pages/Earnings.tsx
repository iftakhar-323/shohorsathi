import { api, Button, Card, Empty, errorMessage, ErrorNote, formatDate, formatTaka, Loading, PageHeader, Stat, StatusBadge, SuccessNote, t, type Paginated } from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

type Summary = { pending: string; in_payout: string; paid: string; this_week: string; commission_total: string };
type Earning = { id: number; job_title: string; gross: string; commission: string; bonus: string; net: string; status: string; created_at: string };
type Payout = { id: number; amount: string; method: string; account: string; status: string; reference: string; created_at: string };

export default function Earnings() {
  const qc = useQueryClient();
  const { data, isPending } = useQuery({
    queryKey: ["earnings"],
    queryFn: async () => (await api.get<{ summary: Summary; earnings: Earning[] }>("/providers/earnings/")).data,
  });
  const { data: payouts } = useQuery({
    queryKey: ["payouts"],
    queryFn: async () => (await api.get<Paginated<Payout>>("/providers/payouts/")).data,
  });
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function requestPayout() {
    setError("");
    try {
      await api.post("/providers/payouts/");
      setNotice(t("পেআউটের অনুরোধ পাঠানো হয়েছে।"));
      qc.invalidateQueries({ queryKey: ["earnings"] });
      qc.invalidateQueries({ queryKey: ["payouts"] });
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  if (isPending || !data) return <Loading />;
  const s = data.summary;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t("আয় ও পেআউট")}
        subtitle={t("প্রতি রবিবার জমা আয় স্বয়ংক্রিয়ভাবে বিকাশ/নগদে পাঠানোর জন্য তৈরি হয়")}
        actions={
          <Button icon="money" onClick={requestPayout} disabled={Number(s.pending) <= 0}>
            {t("এখনই পেআউট চান")}
          </Button>
        }
      />
      <SuccessNote>{notice}</SuccessNote>
      <ErrorNote>{error}</ErrorNote>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-3">
        <Stat label={t("জমা (পেআউট বাকি)")} value={formatTaka(s.pending)} />
        <Stat label={t("পেআউট প্রক্রিয়াধীন")} value={formatTaka(s.in_payout)} />
        <Stat label={t("মোট পেয়েছেন")} value={formatTaka(s.paid)} />
        <Stat label={t("মোট কমিশন")} value={formatTaka(s.commission_total)} />
      </div>

      <Card className="flex flex-col gap-0 p-0">
        <h2 className="m-0 p-5 pb-3 text-lg font-bold">{t("কাজভিত্তিক আয়")}</h2>
        {data.earnings.length === 0 && <div className="p-5"><Empty icon="money" title={t("এখনো কোনো আয় নেই")} /></div>}
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] border-collapse text-[15px]">
            <thead>
              <tr className="text-left text-[13px] text-muted">
                {[t("কাজ"), t("মোট"), t("কমিশন"), t("বোনাস"), t("আপনার আয়"), t("অবস্থা")].map((h) => (
                  <th key={h} className="border-b border-line px-5 py-2 font-semibold">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.earnings.map((e) => (
                <tr key={e.id}>
                  <td className="border-b border-subtle px-5 py-3">
                    {e.job_title}
                    <span className="block text-[13px] text-muted">{formatDate(e.created_at)}</span>
                  </td>
                  <td className="border-b border-subtle px-5 py-3">{formatTaka(e.gross)}</td>
                  <td className="border-b border-subtle px-5 py-3 text-muted">− {formatTaka(e.commission)}</td>
                  <td className="border-b border-subtle px-5 py-3">{Number(e.bonus) > 0 ? `+ ${formatTaka(e.bonus)}` : "—"}</td>
                  <td className="border-b border-subtle px-5 py-3 font-bold">{formatTaka(e.net)}</td>
                  <td className="border-b border-subtle px-5 py-3"><StatusBadge status={e.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card className="flex flex-col gap-3">
        <h2 className="m-0 text-lg font-bold">{t("পেআউট ইতিহাস")}</h2>
        {payouts?.results.length === 0 && <p className="m-0 text-muted">{t("এখনো কোনো পেআউট হয়নি।")}</p>}
        {payouts?.results.map((p) => (
          <div key={p.id} className="flex flex-wrap items-center gap-3 border-b border-subtle pb-3 last:border-0">
            <span className="flex-1">
              {formatDate(p.created_at)} · {p.method === "bkash" ? t("বিকাশ") : t("নগদ")} {p.account}
              {p.reference && <span className="block text-[13px] text-muted">TxID: {p.reference}</span>}
            </span>
            <span className="font-bold">{formatTaka(p.amount)}</span>
            <StatusBadge status={p.status} />
          </div>
        ))}
      </Card>
    </div>
  );
}
