import { Button, ErrorNote, Field, Modal, PageHeader, Select, StatusBadge, Tabs, TextArea, api, errorMessage, formatDate, formatTaka, slotOptions, t, todayISO, useCategories, localName } from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { DataTable, FilterChips } from "../components";

type Org = { id: number; name: string; kind: string; contact_name: string; contact_phone: string; address_line: string; area_name: string; units: number; status: string; created_at: string };
type Invoice = { id: number; number: string; organization_name: string; period_start: string; total: string; status: string; payment_reference: string };

async function openInvoice(id: number) {
  const { data } = await api.get(`/b2b/invoices/${id}/print/`, { responseType: "blob" });
  window.open(URL.createObjectURL(new Blob([data], { type: "text/html" })), "_blank");
}

function ContractForm({ org, onDone }: { org: Org; onDone: () => void }) {
  const { data: categories } = useCategories("service");
  const [f, setF] = useState({ title: "", description: "", category_slug: "", visits_per_month: "1", preferred_weekday: "5", slot: "09-11", monthly_fee: "", start_date: todayISO(1), end_date: todayISO(365) });
  const [error, setError] = useState("");
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  async function save(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.post(`/admin/b2b/orgs/${org.id}/contracts/`, f);
      onDone();
    } catch (err) {
      setError(errorMessage(err));
    }
  }
  return (
    <form onSubmit={save} className="grid gap-3 sm:grid-cols-2">
      <Field label={t("চুক্তির নাম")} required value={f.title} onChange={set("title")} placeholder={t("যেমন: মাসিক পেস্ট কন্ট্রোল")} />
      <Select label={t("প্রোভাইডার ক্যাটাগরি")} value={f.category_slug} onChange={set("category_slug")} options={[{ value: "", label: t("বাছুন") }, ...(categories ?? []).map((c) => ({ value: c.slug, label: localName(c) }))]} />
      <Field label={t("মাসে ভিজিট")} type="number" min={1} max={30} value={f.visits_per_month} onChange={set("visits_per_month")} />
      <Field label={t("মাসিক ফি (৳)")} type="number" min={0} required value={f.monthly_fee} onChange={set("monthly_fee")} />
      <Select label={t("পছন্দের দিন")} value={f.preferred_weekday} onChange={set("preferred_weekday")} options={["সোম", "মঙ্গল", "বুধ", "বৃহঃ", "শুক্র", "শনি", "রবি"].map((d, i) => ({ value: i, label: t(d) }))} />
      <Select label={t("সময়")} value={f.slot} onChange={set("slot")} options={slotOptions()} />
      <Field label={t("শুরুর তারিখ")} type="date" value={f.start_date} onChange={set("start_date")} />
      <Field label={t("শেষ তারিখ")} type="date" value={f.end_date} onChange={set("end_date")} />
      <div className="sm:col-span-2"><TextArea label={t("বিবরণ")} value={f.description} onChange={set("description")} /></div>
      <ErrorNote>{error}</ErrorNote>
      <Button type="submit" disabled={!f.category_slug} className="sm:col-span-2 sm:justify-self-start">{t("চুক্তি তৈরি করুন")}</Button>
    </form>
  );
}

export default function Business() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<"orgs" | "invoices">("orgs");
  const [status, setStatus] = useState("pending");
  const { data: orgs, isPending } = useQuery({ queryKey: ["admin-orgs", status], queryFn: async () => (await api.get<Org[]>("/admin/b2b/orgs/", { params: { status: status || undefined } })).data });
  const { data: invoices } = useQuery({ queryKey: ["admin-invoices"], queryFn: async () => (await api.get<Invoice[]>("/admin/b2b/invoices/")).data, enabled: tab === "invoices" });
  const [open, setOpen] = useState<Org | null>(null);
  const [period, setPeriod] = useState(new Date().toISOString().slice(0, 7));
  const [error, setError] = useState("");

  async function act(path: string, body: object = {}) {
    setError("");
    try {
      await api.post(path, body);
      qc.invalidateQueries({ queryKey: ["admin-orgs"] });
      qc.invalidateQueries({ queryKey: ["admin-invoices"] });
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t("বিল্ডিং ও ব্যবসা (B2B)")} subtitle={t("প্রতিষ্ঠান অনুমোদন, বাৎসরিক রক্ষণাবেক্ষণ চুক্তি ও মাসিক ইনভয়েস")} />
      <Tabs value={tab} onChange={setTab} tabs={[{ value: "orgs", label: t("প্রতিষ্ঠান") }, { value: "invoices", label: t("ইনভয়েস") }]} />
      <ErrorNote>{error}</ErrorNote>
      {tab === "orgs" ? (
        <>
          <FilterChips value={status} onChange={setStatus} options={[{ value: "pending", label: t("অপেক্ষমাণ") }, { value: "approved", label: t("অনুমোদিত") }, { value: "", label: t("সব") }]} />
          <DataTable loading={isPending} rows={orgs} onRowClick={setOpen} columns={[
            { label: t("নাম"), render: (o) => <span className="font-semibold">{o.name}</span> },
            { label: t("ধরন"), render: (o) => (o.kind === "building" ? t("বিল্ডিং") : t("ব্যবসা")) },
            { label: t("যোগাযোগ"), render: (o) => <>{o.contact_name}<span className="block text-[13px] text-muted">{o.contact_phone}</span></> },
            { label: t("এলাকা"), render: (o) => o.area_name },
            { label: t("ফ্ল্যাট/ডেস্ক"), render: (o) => o.units },
            { label: t("অবস্থা"), render: (o) => <StatusBadge status={o.status} /> },
          ]} />
        </>
      ) : (
        <DataTable rows={invoices} columns={[
          { label: t("ইনভয়েস"), render: (i) => <span className="font-semibold">{i.number}</span> },
          { label: t("প্রতিষ্ঠান"), render: (i) => i.organization_name },
          { label: t("মাস"), render: (i) => formatDate(i.period_start) },
          { label: t("মোট"), render: (i) => formatTaka(i.total) },
          { label: t("অবস্থা"), render: (i) => <StatusBadge status={i.status === "issued" ? "unpaid" : "paid"} /> },
          { label: "", render: (i) => (
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => openInvoice(i.id)}>{t("প্রিন্ট")}</Button>
              {i.status === "issued" && <Button onClick={() => { const reference = prompt(t("পেমেন্টের রেফারেন্স (ব্যাংক/বিকাশ TxID)")); if (reference) act(`/admin/b2b/invoices/${i.id}/mark-paid/`, { reference }); }}>{t("পরিশোধিত")}</Button>}
            </div>
          ) },
        ]} />
      )}
      <Modal title={open?.name ?? ""} open={!!open} onClose={() => setOpen(null)}>
        {open && (
          <>
            <span className="text-muted">{open.address_line}, {open.area_name} · {open.contact_name} {open.contact_phone}</span>
            {open.status === "pending" && (
              <div className="flex gap-2">
                <Button onClick={() => act(`/admin/b2b/orgs/${open.id}/approve/`).then(() => setOpen({ ...open, status: "approved" }))}>{t("অনুমোদন")}</Button>
                <Button variant="danger" onClick={() => act(`/admin/b2b/orgs/${open.id}/reject/`).then(() => setOpen(null))}>{t("প্রত্যাখ্যান")}</Button>
              </div>
            )}
            {open.status === "approved" && (
              <>
                <h3 className="m-0 text-lg font-bold">{t("নতুন রক্ষণাবেক্ষণ চুক্তি")}</h3>
                <ContractForm org={open} onDone={() => setOpen(null)} />
                <div className="flex items-end gap-2 border-t border-line pt-3">
                  <Field label={t("ইনভয়েসের মাস")} type="month" value={period} onChange={(e) => setPeriod(e.target.value)} />
                  <Button variant="secondary" onClick={() => act(`/admin/b2b/orgs/${open.id}/invoice/`, { period }).then(() => setTab("invoices"))}>{t("ইনভয়েস তৈরি করুন")}</Button>
                </div>
              </>
            )}
          </>
        )}
      </Modal>
    </div>
  );
}
