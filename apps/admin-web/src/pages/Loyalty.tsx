import { Button, PageHeader, api, errorMessage, formatTaka, t } from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { DataTable } from "../components";

type Account = { user_id: number; points: number; wallet: string; referral_code: string; completed_orders: number; referrals: number; badges: string[] };

export default function Loyalty() {
  const qc = useQueryClient();
  const [userId, setUserId] = useState("");
  const { data, isPending } = useQuery({
    queryKey: ["admin-loyalty", userId],
    queryFn: async () => (await api.get<Account[]>("/admin/loyalty/accounts/", { params: { user_id: userId || undefined } })).data,
  });

  async function adjust(a: Account) {
    const wallet = prompt(t("ক্রেডিট যোগ/বিয়োগ (৳, যেমন 100 বা -50)"), "0");
    if (wallet === null) return;
    const points = prompt(t("পয়েন্ট যোগ/বিয়োগ"), "0");
    if (points === null) return;
    const reason = prompt(t("কারণ (লেজারে থাকবে)"));
    if (!reason) return;
    try {
      await api.post(`/admin/loyalty/accounts/${a.user_id}/adjust/`, { wallet, points, reason });
      qc.invalidateQueries({ queryKey: ["admin-loyalty"] });
    } catch (e) {
      alert(errorMessage(e));
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t("লয়্যালটি ও ক্রেডিট")} subtitle={t("পয়েন্ট, ক্রেডিট ও রেফারেল; গুডউইল ক্রেডিট দিন")} />
      <input type="search" aria-label={t("ইউজার আইডি")} placeholder={t("ইউজার আইডি")} value={userId} onChange={(e) => setUserId(e.target.value)} className="h-10 w-48 rounded-xl border border-line px-3" />
      <DataTable loading={isPending} rows={data?.map((a) => ({ ...a, id: a.user_id }))} columns={[
        { label: t("ইউজার আইডি"), render: (a) => a.user_id },
        { label: t("পয়েন্ট"), render: (a) => a.points },
        { label: t("ক্রেডিট"), render: (a) => formatTaka(a.wallet) },
        { label: t("সম্পন্ন অর্ডার"), render: (a) => a.completed_orders },
        { label: t("রেফারেল"), render: (a) => `${a.referral_code} · ${a.referrals}` },
        { label: "", render: (a) => <Button variant="ghost" onClick={() => adjust(a)}>{t("সমন্বয়")}</Button> },
      ]} />
    </div>
  );
}
