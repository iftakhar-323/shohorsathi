import { api, Button, errorMessage, formatDate, formatTaka, PageHeader, StatusBadge, t } from "@shohor/web-core";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { DataTable, FilterChips, usePaged } from "../components";

type Payout = { id: number; provider_name: string; amount: string; method: string; account: string; status: string; reference: string; created_at: string; paid_at: string | null };

export default function Payouts() {
  const [status, setStatus] = useState("requested");
  const { data, isPending } = usePaged<Payout>(["admin-payouts"], "/admin/payouts/", { status: status || undefined });
  const qc = useQueryClient();

  async function markPaid(p: Payout) {
    const reference = prompt(t("{name}-কে {amount} পাঠানোর পর {method} TxID দিন", { name: p.provider_name, amount: formatTaka(p.amount), method: t(p.method === "bkash" ? "বিকাশ" : "নগদ") }));
    if (!reference) return;
    try {
      await api.post(`/admin/payouts/${p.id}/mark-paid/`, { reference });
      qc.invalidateQueries({ queryKey: ["admin-payouts"] });
    } catch (e) {
      alert(errorMessage(e));
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t("প্রোভাইডার পেআউট")} subtitle={t("প্রতি রবিবার জমা আয় থেকে পেআউট তৈরি হয়; টাকা পাঠিয়ে TxID দিন")} />
      <FilterChips value={status} onChange={setStatus} options={[{ value: "requested", label: t("পাঠাতে হবে") }, { value: "paid", label: t("পরিশোধিত") }, { value: "", label: t("সব") }]} />
      <DataTable
        loading={isPending}
        rows={data?.results}
        columns={[
          { label: t("প্রোভাইডার"), render: (p) => <span className="font-semibold">{p.provider_name}</span> },
          { label: t("পরিমাণ"), render: (p) => <span className="font-bold">{formatTaka(p.amount)}</span> },
          { label: t("মাধ্যম"), render: (p) => `${t(p.method === "bkash" ? "বিকাশ" : "নগদ")} ${p.account}` },
          { label: t("তারিখ"), render: (p) => formatDate(p.created_at) },
          { label: "TxID", render: (p) => p.reference || "—" },
          { label: t("অবস্থা"), render: (p) => <StatusBadge status={p.status} /> },
          { label: "", render: (p) => p.status === "requested" && <Button onClick={() => markPaid(p)}>{t("পরিশোধিত")}</Button> },
        ]}
      />
    </div>
  );
}
