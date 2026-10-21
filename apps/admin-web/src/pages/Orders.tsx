import { api, Button, errorMessage, ErrorNote, formatDate, formatTaka, Modal, PageHeader, slotLabel, StatusBadge, t } from "@shohor/web-core";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { DataTable, FilterChips, usePaged } from "../components";

type Order = {
  id: number;
  number: string;
  status: string;
  payment_method: string;
  payment_status: string;
  total: string;
  contact_name: string;
  contact_phone: string;
  address_line: string;
  area_name: string;
  note: string;
  items: { slug: string; name: string; quantity: number; line_total: string }[];
  bookings: { id: number; service_name: string; scheduled_date: string; slot: string; status: string; provider_name: string; is_emergency: boolean }[];
  created_at: string;
};

const NEXT: Record<string, { status: string; label: string }[]> = {
  pending: [{ status: "confirmed", label: "কনফার্ম" }, { status: "cancelled", label: "বাতিল" }],
  confirmed: [{ status: "on_the_way", label: "ডেলিভারিতে পাঠান" }, { status: "cancelled", label: "বাতিল" }],
  on_the_way: [{ status: "delivered", label: "ডেলিভারি হয়েছে" }],
};

export default function Orders() {
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [params] = useSearchParams();
  const overdue = params.get("overdue") === "1";
  const { data, isPending } = usePaged<Order>(["admin-orders"], "/admin/orders/", { status: status || undefined, q: q || undefined, overdue: overdue ? 1 : undefined });
  const [open, setOpen] = useState<Order | null>(null);
  const [error, setError] = useState("");
  const qc = useQueryClient();

  async function setOrderStatus(next: string) {
    setError("");
    try {
      const { data: updated } = await api.patch<Order>(`/admin/orders/${open!.id}/status/`, { status: next });
      setOpen(updated);
      qc.invalidateQueries({ queryKey: ["admin-orders"] });
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t("অর্ডার ও বুকিং")} />
      <div className="flex flex-wrap items-center gap-3">
        <FilterChips
          value={status}
          onChange={setStatus}
          options={[{ value: "", label: t("সব") }, ...["pending", "confirmed", "on_the_way", "completed", "cancelled"].map((s) => ({ value: s, label: s === "pending" ? t("অপেক্ষমাণ") : s === "confirmed" ? t("কনফার্মড") : s === "on_the_way" ? t("পথে") : s === "completed" ? t("সম্পন্ন") : t("বাতিল") }))]}
        />
        <input type="search" aria-label={t("ফোন বা নাম")} placeholder={t("ফোন বা নাম")} value={q} onChange={(e) => setQ(e.target.value)} className="h-10 rounded-xl border border-line px-3" />
      </div>
      <DataTable
        loading={isPending}
        rows={data?.results}
        onRowClick={setOpen}
        columns={[
          { label: t("অর্ডার"), render: (o) => <span className="font-semibold">{o.number}</span> },
          { label: t("গ্রাহক"), render: (o) => <>{o.contact_name}<span className="block text-[13px] text-muted">{o.contact_phone}</span></> },
          { label: t("এলাকা"), render: (o) => o.area_name },
          { label: t("আইটেম"), render: (o) => t("{services} সার্ভিস, {products} পণ্য", { services: o.bookings.length, products: o.items.length }) },
          { label: t("মোট"), render: (o) => formatTaka(o.total) },
          { label: t("অবস্থা"), render: (o) => <StatusBadge status={o.status} /> },
          { label: t("তারিখ"), render: (o) => formatDate(o.created_at) },
        ]}
      />
      <Modal title={t("অর্ডার {number}", { number: open?.number ?? "" })} open={!!open} onClose={() => setOpen(null)}>
        {open && (
          <>
            <div className="flex flex-col gap-1 text-[15px]">
              <span>{open.contact_name} · <a href={`tel:${open.contact_phone}`}>{open.contact_phone}</a></span>
              <span className="text-muted">{open.address_line}, {open.area_name}</span>
              {open.note && <span className="rounded-xl bg-subtle p-2">{open.note}</span>}
            </div>
            {open.bookings.map((b) => (
              <div key={b.id} className="flex items-center justify-between gap-2 rounded-xl border border-line p-3">
                <span>
                  {b.is_emergency && <span className="mr-1 text-bad">{t("[জরুরি]")}</span>}
                  {b.service_name}
                  <span className="block text-[13px] text-muted">{formatDate(b.scheduled_date)}, {slotLabel(b.slot)} · {b.provider_name || t("প্রোভাইডার নেই")}</span>
                </span>
                <StatusBadge status={b.status} />
              </div>
            ))}
            {open.items.map((i) => (
              <div key={i.slug} className="flex justify-between rounded-xl border border-line p-3">
                <span>{i.name} × {i.quantity}</span>
                <span>{formatTaka(i.line_total)}</span>
              </div>
            ))}
            <div className="flex items-center justify-between">
              <span className="font-bold">{formatTaka(open.total)}</span>
              <span className="flex items-center gap-2"><StatusBadge status={open.status} /><StatusBadge status={open.payment_status} /></span>
            </div>
            <ErrorNote>{error}</ErrorNote>
            {open.items.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {(NEXT[open.status] ?? []).map((n) => (
                  <Button key={n.status} variant={n.status === "cancelled" ? "danger" : "primary"} onClick={() => setOrderStatus(n.status)}>
                    {t(n.label)}
                  </Button>
                ))}
              </div>
            )}
          </>
        )}
      </Modal>
    </div>
  );
}
