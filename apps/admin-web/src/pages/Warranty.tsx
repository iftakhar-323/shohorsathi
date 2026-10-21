import { api, Button, errorMessage, formatDate, PageHeader, StatusBadge, t } from "@shohor/web-core";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { DataTable, FilterChips, usePaged } from "../components";

type Claim = { id: number; booking: number; service_name: string; description: string; photo_urls: string[]; status: string; admin_note: string; created_at: string };

export default function Warranty() {
  const [status, setStatus] = useState("open");
  const { data, isPending } = usePaged<Claim>(["admin-warranty"], "/admin/warranty-claims/", { status: status || undefined });
  const qc = useQueryClient();

  async function decide(c: Claim, action: "approve" | "reject") {
    const note = prompt(action === "approve" ? t("নোট (ঐচ্ছিক) — আগের প্রোভাইডারকে বিনা খরচে রি-ওয়ার্ক দেওয়া হবে") : t("কেন বাতিল?")) ?? "";
    if (action === "reject" && !note) return;
    try {
      await api.post(`/admin/warranty-claims/${c.id}/${action}/`, { note });
      qc.invalidateQueries({ queryKey: ["admin-warranty"] });
    } catch (e) {
      alert(errorMessage(e));
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t("ওয়ারেন্টি দাবি")} subtitle={t("অনুমোদন দিলে একই প্রোভাইডারের কাছে বিনা খরচের রি-ওয়ার্ক জব যায়")} />
      <FilterChips value={status} onChange={setStatus} options={[{ value: "open", label: t("নতুন") }, { value: "approved", label: t("অনুমোদিত") }, { value: "resolved", label: t("সমাধান") }, { value: "rejected", label: t("বাতিল") }]} />
      <DataTable
        loading={isPending}
        rows={data?.results}
        columns={[
          { label: t("সার্ভিস"), render: (c) => <span className="font-semibold">{c.service_name}</span> },
          { label: t("সমস্যা"), render: (c) => <span className="line-clamp-2">{c.description}</span>, className: "max-w-sm" },
          { label: t("ছবি"), render: (c) => <div className="flex gap-1">{c.photo_urls.map((u) => <img key={u} src={u} alt="" className="size-10 rounded-lg object-cover" />)}</div> },
          { label: t("তারিখ"), render: (c) => formatDate(c.created_at) },
          { label: t("অবস্থা"), render: (c) => <StatusBadge status={c.status} /> },
          {
            label: "",
            render: (c) =>
              c.status === "open" && (
                <div className="flex gap-2">
                  <Button onClick={() => decide(c, "approve")}>{t("অনুমোদন")}</Button>
                  <Button variant="ghost" onClick={() => decide(c, "reject")}>{t("বাতিল")}</Button>
                </div>
              ),
          },
        ]}
      />
    </div>
  );
}
