import { Button, PageHeader, Stat, StatusBadge, Tabs, api, errorMessage, formatDateTime, formatTaka, t } from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { DataTable, FilterChips, usePaged } from "../components";

type Payment = { id: number; tran_id: string; purpose: string; reference_id: number; amount: string; status: string; method: string; refunded_amount: string; user_id: number; created_at: string };
type Refund = { id: number; tran_id: string; purpose: string; reference_id: number; amount: string; reason: string; status: string; automatic: boolean; admin_note: string; created_at: string };

const PURPOSE: Record<string, string> = { order: "অর্ডার", subscription: "সাবস্ক্রিপশন", custom_request_advance: "কাস্টম অগ্রিম" };

export default function Payments() {
  const [tab, setTab] = useState<"payments" | "refunds">("payments");
  const [status, setStatus] = useState("");
  const [refundStatus, setRefundStatus] = useState("requested");
  const qc = useQueryClient();
  const { data: balances } = useQuery({ queryKey: ["balances"], queryFn: async () => (await api.get<Record<string, string>>("/admin/payments/balances/")).data });
  const payments = usePaged<Payment>(["admin-payments"], "/admin/payments/", { status: status || undefined });
  const refunds = usePaged<Refund>(["admin-refunds"], "/admin/refunds/", { status: refundStatus || undefined });

  async function decide(r: Refund, action: "approve" | "reject") {
    const note = prompt(action === "approve" ? t("রিফান্ডের পরিমাণ (খালি রাখলে অনুরোধ করা পরিমাণ)") : t("কেন বাতিল?"));
    if (note === null || (action === "reject" && !note)) return;
    try {
      await api.post(`/admin/refunds/${r.id}/${action}/`, action === "approve" ? (note ? { amount: note } : {}) : { note });
      qc.invalidateQueries({ queryKey: ["admin-refunds"] });
      qc.invalidateQueries({ queryKey: ["balances"] });
    } catch (e) {
      alert(errorMessage(e));
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t("পেমেন্ট ও রিফান্ড")} subtitle={t("অনলাইনের টাকা কাজ শেষ না হওয়া পর্যন্ত এসক্রোতে থাকে")} />
      <div className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-3">
        <Stat label={t("এসক্রোতে জমা")} value={formatTaka(balances?.escrow)} icon="shield" />
        <Stat label={t("ছাড় করা হয়েছে")} value={formatTaka(balances?.settled)} icon="money" />
        <Stat label={t("রিফান্ড হয়েছে")} value={formatTaka(balances?.refunds)} icon="refresh" />
      </div>
      <Tabs value={tab} onChange={setTab} tabs={[{ value: "payments", label: t("পেমেন্ট") }, { value: "refunds", label: t("রিফান্ড ও অভিযোগ") }]} />
      {tab === "payments" ? (
        <>
          <FilterChips value={status} onChange={setStatus} options={[{ value: "", label: t("সব") }, { value: "held", label: t("জমা রাখা") }, { value: "released", label: t("ছাড় করা") }, { value: "refunded", label: t("রিফান্ড হয়েছে") }, { value: "failed", label: t("ব্যর্থ") }]} />
          <DataTable
            loading={payments.isPending}
            rows={payments.data?.results}
            columns={[
              { label: "TxID", render: (p) => <code className="text-sm">{p.tran_id}</code> },
              { label: t("কিসের জন্য"), render: (p) => `${t(PURPOSE[p.purpose] ?? p.purpose)} #${p.reference_id}` },
              { label: t("পরিমাণ"), render: (p) => <>{formatTaka(p.amount)}{Number(p.refunded_amount) > 0 && <span className="block text-[13px] text-bad">− {formatTaka(p.refunded_amount)}</span>}</> },
              { label: t("মাধ্যম"), render: (p) => p.method || "—" },
              { label: t("সময়"), render: (p) => formatDateTime(p.created_at) },
              { label: t("অবস্থা"), render: (p) => <StatusBadge status={p.status} /> },
            ]}
          />
        </>
      ) : (
        <>
          <FilterChips value={refundStatus} onChange={setRefundStatus} options={[{ value: "requested", label: t("নতুন") }, { value: "refunded", label: t("রিফান্ড হয়েছে") }, { value: "rejected", label: t("বাতিল") }, { value: "", label: t("সব") }]} />
          <DataTable
            loading={refunds.isPending}
            rows={refunds.data?.results}
            columns={[
              { label: t("কিসের জন্য"), render: (r) => `${t(PURPOSE[r.purpose] ?? r.purpose)} #${r.reference_id}` },
              { label: t("কারণ"), render: (r) => <span className="line-clamp-2">{r.automatic ? t("স্বয়ংক্রিয় (বাতিল)") : r.reason}</span>, className: "max-w-sm" },
              { label: t("পরিমাণ"), render: (r) => formatTaka(r.amount) },
              { label: t("সময়"), render: (r) => formatDateTime(r.created_at) },
              { label: t("অবস্থা"), render: (r) => <StatusBadge status={r.status} /> },
              { label: "", render: (r) => r.status === "requested" && <div className="flex gap-2"><Button onClick={() => decide(r, "approve")}>{t("রিফান্ড দিন")}</Button><Button variant="ghost" onClick={() => decide(r, "reject")}>{t("বাতিল")}</Button></div> },
            ]}
          />
        </>
      )}
    </div>
  );
}
