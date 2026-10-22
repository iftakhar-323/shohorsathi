import { api, Button, Card, errorMessage, ErrorNote, Field, formatDate, formatTaka, localName, Modal, PageHeader, StatusBadge, t, TextArea, Timeline, useCategories } from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { DataTable, FilterChips, usePaged } from "../components";

type Quote = { id: number; labor: string; materials: string; transport: string; platform_fee: string; total: string; timeline_days: number; note: string; is_current: boolean; created_at: string };
type Req = {
  id: number;
  service_type: string;
  description: string;
  media_urls: string[];
  customer_name: string;
  customer_phone: string;
  area_name: string;
  address_line: string;
  preferred_date: string;
  budget_min: string | null;
  budget_max: string | null;
  status: string;
  category_slug: string;
  quote: Quote | null;
  quotes: Quote[];
  counter: { amount: string; message: string } | null;
  logs: { status: string; note: string; created_at: string }[];
  created_at: string;
};

function QuoteForm({ req, onDone }: { req: Req; onDone: () => void }) {
  const { data: categories } = useCategories("service");
  const [q, setQ] = useState({ labor: "", materials: "0", transport: "0", platform_fee: "0", timeline_days: "1", note: "", category_slug: req.category_slug });
  const [error, setError] = useState("");
  const total = ["labor", "materials", "transport", "platform_fee"].reduce((s, k) => s + Number(q[k as keyof typeof q] || 0), 0);
  const set = (k: keyof typeof q) => (e: { target: { value: string } }) => setQ({ ...q, [k]: e.target.value });

  async function send() {
    setError("");
    try {
      await api.patch(`/admin/custom-requests/${req.id}/quote/`, q);
      onDone();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <Card className="flex flex-col gap-3 bg-brand-tint">
      <span className="font-bold">{t("খরচের হিসাব পাঠান")}</span>
      <div className="grid grid-cols-2 gap-3">
        <Field label={t("মজুরি")} type="number" min={0} value={q.labor} onChange={set("labor")} required />
        <Field label={t("উপকরণ")} type="number" min={0} value={q.materials} onChange={set("materials")} />
        <Field label={t("যাতায়াত")} type="number" min={0} value={q.transport} onChange={set("transport")} />
        <Field label={t("প্ল্যাটফর্ম ফি")} type="number" min={0} value={q.platform_fee} onChange={set("platform_fee")} />
        <Field label={t("সময় (দিন)")} type="number" min={1} value={q.timeline_days} onChange={set("timeline_days")} />
        <div className="flex flex-col gap-1.5">
          <label htmlFor="cat" className="text-[15px] font-semibold">{t("প্রোভাইডার ক্যাটাগরি")}</label>
          <select id="cat" value={q.category_slug} onChange={set("category_slug")} className="h-11 rounded-xl border border-line px-3">
            <option value="">{t("বাছুন")}</option>
            {categories?.map((c) => <option key={c.slug} value={c.slug}>{localName(c)}</option>)}
          </select>
        </div>
      </div>
      <TextArea label={t("নোট")} value={q.note} onChange={set("note")} />
      <span className="text-lg font-bold">{t("মোট")} {formatTaka(total)}</span>
      <ErrorNote>{error}</ErrorNote>
      <Button onClick={send} disabled={!q.labor || !q.category_slug}>{t("কোট পাঠান")}</Button>
    </Card>
  );
}

export default function CustomRequests() {
  const [status, setStatus] = useState("submitted,under_review,countered");
  const { data, isPending } = usePaged<Req>(["admin-cr"], "/admin/custom-requests/", { status: status || undefined });
  const { data: trends } = useQuery({ queryKey: ["cr-trends"], queryFn: async () => (await api.get<{ name: string; count: number }[]>("/admin/custom-requests/trends/")).data });
  const [openId, setOpenId] = useState<number | null>(null);
  const { data: open } = useQuery({
    queryKey: ["admin-cr", openId],
    queryFn: async () => (await api.get<Req>(`/admin/custom-requests/${openId}/`)).data,
    enabled: !!openId,
  });
  const [error, setError] = useState("");
  const qc = useQueryClient();

  function refresh() {
    qc.invalidateQueries({ queryKey: ["admin-cr"] });
  }

  async function act(path: string, body?: object) {
    setError("");
    try {
      await api.post(`/admin/custom-requests/${openId}/${path}/`, body);
      refresh();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t("কাস্টম রিকোয়েস্ট")} />
      <FilterChips
        value={status}
        onChange={setStatus}
        options={[
          { value: "submitted,under_review,countered", label: t("অ্যাকশন দরকার") },
          { value: "quote_sent", label: t("কোট পাঠানো") },
          { value: "accepted,provider_assigned,in_progress", label: t("চলমান") },
          { value: "completed", label: t("সম্পন্ন") },
          { value: "rejected,cancelled", label: t("বাতিল") },
          { value: "", label: t("সব") },
        ]}
      />
      <DataTable
        loading={isPending}
        rows={data?.results}
        onRowClick={(r) => setOpenId(r.id)}
        columns={[
          { label: t("কাজ"), render: (r) => <span className="font-semibold">{r.service_type}</span> },
          { label: t("গ্রাহক"), render: (r) => r.customer_name },
          { label: t("এলাকা"), render: (r) => r.area_name },
          { label: t("বাজেট"), render: (r) => (r.budget_max ? `${formatTaka(r.budget_min)}–${formatTaka(r.budget_max)}` : "—") },
          { label: t("কোট"), render: (r) => (r.quote ? formatTaka(r.quote.total) : "—") },
          { label: t("অবস্থা"), render: (r) => <StatusBadge status={r.status} /> },
          { label: t("তারিখ"), render: (r) => formatDate(r.created_at) },
        ]}
      />
      {trends && trends.length > 0 && (
        <Card className="flex flex-col gap-2">
          <h2 className="m-0 text-lg font-bold">{t("বেশি চাওয়া কাজ")}</h2>
          <p className="m-0 text-sm text-muted">{t("বারবার আসা রিকোয়েস্টগুলো নিয়মিত ক্যাটালগে যোগ করার কথা ভাবুন।")}</p>
          <div className="flex flex-wrap gap-2">
            {trends.slice(0, 10).map((t) => (
              <span key={t.name} className="rounded-full border border-line px-3 py-1 text-sm">{t.name} · {t.count}</span>
            ))}
          </div>
        </Card>
      )}
      <Modal title={open?.service_type ?? ""} open={!!openId && !!open} onClose={() => setOpenId(null)}>
        {open && (
          <>
            <div className="flex flex-col gap-1 text-[15px]">
              <span>{open.customer_name} · <a href={`tel:${open.customer_phone}`}>{open.customer_phone}</a></span>
              <span className="text-muted">{open.address_line}, {open.area_name} · {formatDate(open.preferred_date)}</span>
              <p className="m-0 rounded-xl bg-subtle p-3 whitespace-pre-line">{open.description}</p>
              {open.media_urls.length > 0 && <div className="flex flex-wrap gap-2">{open.media_urls.map((u) => <img key={u} src={u} alt="" className="size-20 rounded-xl object-cover" />)}</div>}
              {open.counter && <span className="font-semibold text-alert-strong">{t("গ্রাহকের পাল্টা প্রস্তাব:")} {formatTaka(open.counter.amount)} {open.counter.message && `— ${open.counter.message}`}</span>}
            </div>
            <ErrorNote>{error}</ErrorNote>
            {open.status === "submitted" && <Button variant="secondary" onClick={() => act("review")}>{t("রিভিউ শুরু করুন")}</Button>}
            {["submitted", "under_review", "countered"].includes(open.status) && (
              <>
                <QuoteForm req={open} onDone={() => { refresh(); setOpenId(null); }} />
                <Button variant="danger" onClick={() => { const reason = prompt(t("কেন বাতিল করছেন?")); if (reason) act("decline", { reason }); }}>
                  {t("রিকোয়েস্ট বাতিল")}
                </Button>
              </>
            )}
            {open.quotes.length > 0 && (
              <div className="flex flex-col gap-1 text-sm text-muted">
                {open.quotes.map((q) => <span key={q.id}>{formatDate(q.created_at)}: {formatTaka(q.total)} {q.is_current && t("(বর্তমান)")}</span>)}
              </div>
            )}
            <Timeline events={[...open.logs].reverse()} />
          </>
        )}
      </Modal>
    </div>
  );
}
