import { Badge, Button, Card, Empty, ErrorNote, Field, Loading, PageHeader, Select, Stat, StatusBadge, api, errorMessage, formatDate, formatTaka, localName, slotLabel, t, useAreas } from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

export type Org = { id: number; name: string; kind: string; contact_name: string; contact_phone: string; address_line: string; area_name: string; units: number; status: string };
type Detail = Org & {
  my_role: string;
  members: { id: number; user_id: number; name: string; phone: string; role: string }[];
  contracts: { id: number; title: string; visits_per_month: number; monthly_fee: string; start_date: string; end_date: string; status: string; upcoming: { id: number; date: string; slot: string; status: string; provider_name: string }[] }[];
  stats: { members: number; active_contracts: number; visits_this_month: number; unpaid_total: string; paid_this_year: string };
};
type Invoice = { id: number; number: string; period_start: string; period_end: string; total: string; status: string; lines: { description: string; amount: string }[] };

export function useMyOrgs(enabled = true) {
  return useQuery({ queryKey: ["orgs"], queryFn: async () => (await api.get<Org[]>("/b2b/orgs/")).data, enabled });
}

/** Invoices render as a printable page; it needs the auth header, so open it from a blob. */
async function openInvoice(id: number) {
  const { data } = await api.get(`/b2b/invoices/${id}/print/`, { responseType: "blob" });
  window.open(URL.createObjectURL(new Blob([data], { type: "text/html" })), "_blank");
}

export function BusinessHome() {
  const qc = useQueryClient();
  const { data: orgs, isPending } = useMyOrgs();
  const { data: areas } = useAreas();
  const [f, setF] = useState({ name: "", kind: "building", contact_name: "", contact_phone: "", address_line: "", area_id: "", units: "" });
  const [error, setError] = useState("");
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });

  async function apply(e: FormEvent) {
    e.preventDefault();
    const area = areas?.find((a) => a.id === Number(f.area_id));
    if (!area) return setError(t("এলাকা বাছুন।"));
    setError("");
    try {
      await api.post("/b2b/orgs/", { ...f, area_id: area.id, area_name: area.name_bn, units: Number(f.units || 0) });
      qc.invalidateQueries({ queryKey: ["orgs"] });
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <section className="mx-auto flex max-w-[960px] flex-col gap-5 px-4 py-8 sm:px-6">
      <PageHeader title={t("বিল্ডিং ও ব্যবসা পোর্টাল")} subtitle={t("অ্যাপার্টমেন্ট কমিটি ও অফিসের জন্য: বাৎসরিক রক্ষণাবেক্ষণ চুক্তি, একসাথে অর্ডার, মাসিক ইনভয়েস")} />
      {isPending && <Loading />}
      {orgs?.map((o) => (
        <Link key={o.id} to={`/business/${o.id}`} className="text-ink no-underline">
          <Card className="flex flex-wrap items-center gap-4 hover:border-brand">
            <div className="flex flex-1 flex-col"><span className="font-bold">{o.name}</span><span className="text-sm text-muted">{o.address_line}, {o.area_name}</span></div>
            <StatusBadge status={o.status} />
          </Card>
        </Link>
      ))}
      <Card>
        <form onSubmit={apply} className="grid gap-3 sm:grid-cols-2">
          <h2 className="m-0 text-lg font-bold sm:col-span-2">{t("নতুন প্রতিষ্ঠান যোগ করুন")}</h2>
          <Field label={t("নাম")} required value={f.name} onChange={set("name")} placeholder={t("যেমন: গ্রিন ভিউ অ্যাপার্টমেন্ট")} />
          <Select label={t("ধরন")} value={f.kind} onChange={set("kind")} options={[{ value: "building", label: t("অ্যাপার্টমেন্ট / বিল্ডিং কমিটি") }, { value: "business", label: t("ছোট ব্যবসা / অফিস") }]} />
          <Field label={t("যোগাযোগের নাম")} required value={f.contact_name} onChange={set("contact_name")} />
          <Field label={t("মোবাইল")} required pattern="01[3-9][0-9]{8}" value={f.contact_phone} onChange={set("contact_phone")} />
          <Field label={t("ঠিকানা")} required value={f.address_line} onChange={set("address_line")} />
          <Select label={t("এলাকা")} value={f.area_id} onChange={set("area_id")} options={[{ value: "", label: t("এলাকা বাছুন") }, ...(areas ?? []).map((a) => ({ value: a.id, label: localName(a) }))]} />
          <Field label={t("ফ্ল্যাট/ডেস্ক সংখ্যা")} type="number" min={0} value={f.units} onChange={set("units")} />
          <ErrorNote>{error}</ErrorNote>
          <Button type="submit" className="sm:col-span-2 sm:justify-self-start">{t("আবেদন করুন")}</Button>
        </form>
      </Card>
    </section>
  );
}

export function BusinessDetail() {
  const { id } = useParams();
  const qc = useQueryClient();
  const { data: org, isPending } = useQuery({ queryKey: ["orgs", id], queryFn: async () => (await api.get<Detail>(`/b2b/orgs/${id}/`)).data });
  const { data: invoices } = useQuery({ queryKey: ["orgs", id, "invoices"], queryFn: async () => (await api.get<Invoice[]>(`/b2b/orgs/${id}/invoices/`)).data });
  const [phone, setPhone] = useState("");
  const [error, setError] = useState("");

  if (isPending || !org) return <Loading />;
  const isAdmin = org.my_role === "admin";

  async function addMember(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.post(`/b2b/orgs/${id}/members/`, { phone });
      setPhone("");
      qc.invalidateQueries({ queryKey: ["orgs", id] });
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <section className="mx-auto flex max-w-[1100px] flex-col gap-5 px-4 py-8 sm:px-6">
      <PageHeader title={org.name} subtitle={`${org.address_line}, ${org.area_name}`} actions={<StatusBadge status={org.status} />} />
      {org.status === "pending" && <p className="m-0 rounded-xl bg-alert-soft p-3">{t("অ্যাডমিন যাচাই করছেন; অনুমোদনের পর চুক্তি ও অর্ডার শুরু করা যাবে।")}</p>}
      <div className="grid grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-3">
        <Stat label={t("সদস্য")} value={org.stats.members} icon="user" />
        <Stat label={t("চালু চুক্তি")} value={org.stats.active_contracts} icon="repeat" />
        <Stat label={t("এ মাসের ভিজিট")} value={org.stats.visits_this_month} icon="calendar" />
        <Stat label={t("বকেয়া")} value={formatTaka(org.stats.unpaid_total)} icon="money" />
        <Stat label={t("এ বছর পরিশোধ")} value={formatTaka(org.stats.paid_this_year)} icon="check" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="flex flex-col gap-3">
          <h2 className="m-0 text-lg font-bold">{t("রক্ষণাবেক্ষণ চুক্তি")}</h2>
          {org.contracts.length === 0 && <p className="m-0 text-muted">{t("চুক্তির জন্য সাপোর্টে লিখুন; অ্যাডমিন আপনার প্রয়োজন অনুযায়ী তৈরি করবেন।")}</p>}
          {org.contracts.map((c) => (
            <div key={c.id} className="flex flex-col gap-2 rounded-xl border border-line p-3">
              <div className="flex items-center justify-between gap-2"><span className="font-semibold">{c.title}</span><StatusBadge status={c.status} /></div>
              <span className="text-sm text-muted">{t("মাসে {n} ভিজিট", { n: c.visits_per_month })} · {formatTaka(c.monthly_fee)} {t("/মাস")} · {formatDate(c.start_date)} – {formatDate(c.end_date)}</span>
              {c.upcoming.map((v) => (
                <div key={v.id} className="flex items-center justify-between text-sm"><span>{formatDate(v.date)}, {slotLabel(v.slot)} {v.provider_name && `· ${v.provider_name}`}</span><StatusBadge status={v.status} /></div>
              ))}
            </div>
          ))}
        </Card>
        <Card className="flex flex-col gap-3">
          <h2 className="m-0 text-lg font-bold">{t("সদস্য")}</h2>
          <p className="m-0 text-sm text-muted">{t("সদস্যরা চেকআউটে এই প্রতিষ্ঠানের নামে অর্ডার দিতে পারবেন; সব অর্ডার মাসিক ইনভয়েসে আসবে।")}</p>
          {org.members.map((m) => (
            <div key={m.id} className="flex items-center gap-2"><span className="flex-1">{m.name} <span className="text-muted">{m.phone}</span></span>{m.role === "admin" && <Badge tone="ok">{t("অ্যাডমিন")}</Badge>}</div>
          ))}
          {isAdmin && (
            <form onSubmit={addMember} className="flex gap-2">
              <label htmlFor="member-phone" className="sr-only">{t("মোবাইল")}</label>
              <input id="member-phone" value={phone} onChange={(e) => setPhone(e.target.value)} pattern="01[3-9][0-9]{8}" placeholder="01XXXXXXXXX" required className="h-11 min-w-0 flex-1 rounded-xl border border-line px-3" />
              <Button type="submit" variant="secondary" icon="plus">{t("যোগ করুন")}</Button>
            </form>
          )}
          <ErrorNote>{error}</ErrorNote>
        </Card>
      </div>

      <Card className="flex flex-col gap-2">
        <h2 className="m-0 text-lg font-bold">{t("ইনভয়েস ও রিসিট")}</h2>
        {invoices?.length === 0 && <Empty icon="list" title={t("এখনো কোনো ইনভয়েস নেই")} />}
        {invoices?.map((inv) => (
          <div key={inv.id} className="flex flex-wrap items-center gap-3 border-b border-subtle py-2 last:border-0">
            <span className="flex-1"><span className="font-semibold">{inv.number}</span><span className="block text-sm text-muted">{formatDate(inv.period_start)} – {formatDate(inv.period_end)}</span></span>
            <span className="font-bold">{formatTaka(inv.total)}</span>
            <StatusBadge status={inv.status === "issued" ? "unpaid" : "paid"} />
            <Button variant="ghost" icon="list" onClick={() => openInvoice(inv.id)}>{t("দেখুন / প্রিন্ট")}</Button>
          </div>
        ))}
      </Card>
    </section>
  );
}
