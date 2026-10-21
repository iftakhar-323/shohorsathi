import { api, Badge, Button, errorMessage, ErrorNote, formatDate, formatTaka, Modal, PageHeader, Select, StatusBadge, t, Tabs, TextArea, Field } from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { DataTable, FilterChips } from "../components";

type InsurancePlan = {
  id: number;
  name_bn: string;
  name_en: string;
  partner: string;
  weekly_premium: string;
  coverage_bn: string;
  coverage_en: string;
  is_active: boolean;
};

type InsuranceClaim = {
  id: number;
  provider_name: string;
  plan_name: string;
  description: string;
  photo_urls: string[];
  status: "submitted" | "forwarded" | "paid" | "rejected";
  amount: string | null;
  note: string;
  created_at: string;
};

export default function Insurance() {
  const [tab, setTab] = useState<"claims" | "plans">("claims");

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t("সুরক্ষা বিমা")}
        subtitle={t("বিমা প্ল্যান পরিচালনা এবং পার্টনারদের ক্লেইম যাচাই ও অনুমোদন")}
      />

      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[
          { value: "claims", label: t("বিমা ক্লেইমসমূহ") },
          { value: "plans", label: t("বিমা প্ল্যানসমূহ") },
        ]}
      />

      {tab === "claims" ? <ClaimsView /> : <PlansView />}
    </div>
  );
}

function ClaimsView() {
  const qc = useQueryClient();
  const [status, setStatus] = useState("submitted");
  const [selected, setSelected] = useState<InsuranceClaim | null>(null);
  const [newStatus, setNewStatus] = useState<string>("submitted");
  const [amount, setAmount] = useState<string>("");
  const [note, setNote] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const { data: claims, isPending } = useQuery({
    queryKey: ["admin-insurance-claims", status],
    queryFn: async () =>
      (await api.get<InsuranceClaim[]>("/admin/insurance-claims/", { params: status ? { status } : {} })).data,
  });

  async function handleUpdate() {
    setError("");
    setSubmitting(true);
    try {
      await api.post(`/admin/insurance-claims/${selected!.id}/update_status/`, {
        status: newStatus,
        amount: amount || undefined,
        note: note.trim(),
      });
      setSelected(null);
      qc.invalidateQueries({ queryKey: ["admin-insurance-claims"] });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <FilterChips
        value={status}
        onChange={setStatus}
        options={[
          { value: "submitted", label: t("জমা হয়েছে") },
          { value: "forwarded", label: t("ফরওয়ার্ডকৃত") },
          { value: "paid", label: t("পরিশোধিত") },
          { value: "rejected", label: t("বাতিল") },
          { value: "", label: t("সব") },
        ]}
      />

      <DataTable
        loading={isPending}
        rows={claims}
        onRowClick={(row) => {
          setSelected(row);
          setNewStatus(row.status);
          setAmount(row.amount ?? "");
          setNote(row.note ?? "");
          setError("");
        }}
        columns={[
          { label: t("আইডি"), render: (c) => `#${c.id}` },
          { label: t("প্রোভাইডার"), render: (c) => <span className="font-semibold">{c.provider_name}</span> },
          { label: t("প্ল্যান"), render: (c) => c.plan_name },
          { label: t("বিবরণ"), render: (c) => <span className="line-clamp-1 text-sm">{c.description}</span> },
          {
            label: t("ক্ষতিপূরণ"),
            render: (c) => c.amount ? <span className="font-semibold text-ok-strong">{formatTaka(c.amount)}</span> : "—",
          },
          { label: t("অবস্থা"), render: (c) => <StatusBadge status={c.status} /> },
          { label: t("তারিখ"), render: (c) => formatDate(c.created_at) },
        ]}
      />

      {selected && (
        <Modal
          title={`${t("বিমা ক্লেইম যাচাই")} #${selected.id}`}
          open
          onClose={() => setSelected(null)}
        >
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-semibold text-lg">{selected.provider_name}</span>
              <Badge>{selected.plan_name}</Badge>
            </div>

            <div className="flex flex-col gap-1 rounded-xl bg-subtle p-3 text-sm">
              <span className="font-semibold text-muted">{t("ঘটনার বিবরণ:")}</span>
              <p className="m-0 whitespace-pre-line">{selected.description}</p>
            </div>

            {selected.photo_urls.length > 0 && (
              <div className="flex flex-col gap-2">
                <span className="text-xs font-semibold text-muted">{t("প্রমাণস্বরূপ ছবিসমূহ:")}</span>
                <div className="flex flex-wrap gap-2">
                  {selected.photo_urls.map((u) => (
                    <a key={u} href={u} target="_blank" rel="noreferrer">
                      <img src={u} alt={t("প্রমাণ ছবি")} className="size-20 rounded-xl object-cover border border-line" />
                    </a>
                  ))}
                </div>
              </div>
            )}

            <div className="flex flex-col gap-3 border-t border-line pt-3">
              <Select
                label={t("ক্লেইমের বর্তমান অবস্থা")}
                value={newStatus}
                onChange={(e) => setNewStatus(e.target.value)}
                options={[
                  { value: "submitted", label: t("জমা হয়েছে") },
                  { value: "forwarded", label: t("বিমা কোম্পানিতে পাঠানো হয়েছে") },
                  { value: "paid", label: t("ক্ষতিপূরণ পরিশোধিত") },
                  { value: "rejected", label: t("ক্লেইম বাতিল") },
                ]}
              />

              <Field
                label={t("ক্ষতিপূরণের পরিমাণ (৳)")}
                type="number"
                min={0}
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder={t("টাকার অঙ্ক")}
              />

              <TextArea
                label={t("মন্তব্য বা ট্র্যাকিং নোট")}
                rows={2}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder={t("বিমা কোম্পানির রেফারেন্স নম্বর বা কারণ…")}
              />

              <ErrorNote>{error}</ErrorNote>

              <div className="flex justify-end gap-2 pt-2">
                <Button variant="ghost" onClick={() => setSelected(null)}>{t("বন্ধ করুন")}</Button>
                <Button loading={submitting} onClick={handleUpdate}>
                  {t("আপডেট সংরক্ষণ করুন")}
                </Button>
              </div>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

function PlansView() {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<InsurancePlan | null>(null);
  const [creating, setCreating] = useState(false);

  const { data: plans, isPending } = useQuery({
    queryKey: ["admin-insurance-plans"],
    queryFn: async () => (await api.get<InsurancePlan[]>("/admin/insurance-plans/")).data,
  });

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <h3 className="m-0 text-base font-bold">{t("বিমা প্ল্যান তালিকা")}</h3>
        <Button icon="plus" onClick={() => setCreating(true)}>
          {t("নতুন প্ল্যান যোগ করুন")}
        </Button>
      </div>

      <DataTable
        loading={isPending}
        rows={plans}
        onRowClick={(row) => setEditing(row)}
        columns={[
          { label: t("প্ল্যানের নাম (বাংলা)"), render: (p) => <span className="font-semibold">{p.name_bn}</span> },
          { label: t("প্ল্যানের নাম (ইংরেজি)"), render: (p) => p.name_en },
          { label: t("বিমা সহযোগী"), render: (p) => p.partner },
          {
            label: t("সাপ্তাহিক প্রিমিয়াম"),
            render: (p) => `${formatTaka(p.weekly_premium)} / ${t("সপ্তাহ")}`,
          },
          {
            label: t("অবস্থা"),
            render: (p) => (
              <Badge tone={p.is_active ? "ok" : "muted"}>
                {p.is_active ? t("সক্রিয়") : t("নিষ্ক্রিয়")}
              </Badge>
            ),
          },
        ]}
      />

      {(creating || editing) && (
        <PlanFormModal
          plan={editing}
          onClose={() => {
            setCreating(false);
            setEditing(null);
          }}
          onSaved={() => {
            setCreating(false);
            setEditing(null);
            qc.invalidateQueries({ queryKey: ["admin-insurance-plans"] });
          }}
        />
      )}
    </div>
  );
}

function PlanFormModal({
  plan,
  onClose,
  onSaved,
}: {
  plan: InsurancePlan | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [f, setF] = useState({
    name_bn: plan?.name_bn ?? "",
    name_en: plan?.name_en ?? "",
    partner: plan?.partner ?? "",
    weekly_premium: plan?.weekly_premium ?? "",
    coverage_bn: plan?.coverage_bn ?? "",
    coverage_en: plan?.coverage_en ?? "",
    is_active: plan?.is_active ?? true,
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      if (plan) {
        await api.patch(`/admin/insurance-plans/${plan.id}/`, f);
      } else {
        await api.post("/admin/insurance-plans/", f);
      }
      onSaved();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      title={plan ? t("বিমা প্ল্যান সম্পাদনা") : t("নতুন বিমা প্ল্যান তৈরি")}
      open
      onClose={onClose}
    >
      <form onSubmit={handleSave} className="flex flex-col gap-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field
            label={t("নাম (বাংলা)")}
            required
            value={f.name_bn}
            onChange={(e) => setF({ ...f, name_bn: e.target.value })}
            placeholder={t("যেমন: দুর্ঘটনা ও স্বাস্থ্য সুরক্ষা")}
          />
          <Field
            label={t("নাম (ইংরেজি)")}
            required
            value={f.name_en}
            onChange={(e) => setF({ ...f, name_en: e.target.value })}
            placeholder={t("e.g. Accident & Health Cover")}
          />
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <Field
            label={t("বিমা সহযোগী প্রতিষ্ঠান")}
            required
            value={f.partner}
            onChange={(e) => setF({ ...f, partner: e.target.value })}
            placeholder={t("যেমন: গ্রিন ডেল্টা ইন্স্যুরেন্স")}
          />
          <Field
            label={t("সাপ্তাহিক প্রিমিয়াম (৳)")}
            type="number"
            min={0}
            step="0.01"
            required
            value={f.weekly_premium}
            onChange={(e) => setF({ ...f, weekly_premium: e.target.value })}
            placeholder="50"
          />
        </div>

        <TextArea
          label={t("কভারেজ সুবিধা (বাংলা)")}
          required
          rows={3}
          value={f.coverage_bn}
          onChange={(e) => setF({ ...f, coverage_bn: e.target.value })}
          placeholder={t("হাসপাতাল খরচ ৫০,০০০ টাকা পর্যন্ত…")}
        />

        <TextArea
          label={t("কভারেজ সুবিধা (ইংরেজি)")}
          required
          rows={3}
          value={f.coverage_en}
          onChange={(e) => setF({ ...f, coverage_en: e.target.value })}
          placeholder="Hospitalization cover up to 50,000 BDT..."
        />

        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={f.is_active}
            onChange={(e) => setF({ ...f, is_active: e.target.checked })}
            className="size-5 accent-brand"
          />
          <span className="font-semibold text-sm">{t("এই প্ল্যানটি পার্টনারদের জন্য উন্মুক্ত রাখুন")}</span>
        </label>

        <ErrorNote>{error}</ErrorNote>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="ghost" type="button" onClick={onClose}>{t("বাতিল")}</Button>
          <Button loading={submitting} type="submit">
            {t("সংরক্ষণ করুন")}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
