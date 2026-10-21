import { api, Badge, Button, errorMessage, ErrorNote, formatDateTime, formatDate, Modal, PageHeader, StatusBadge, t, Tabs, TextArea } from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { DataTable, FilterChips } from "../components";

type SafetyIncident = {
  id: number;
  job_title: string;
  area_name: string;
  role: "customer" | "provider";
  latitude: string | null;
  longitude: string | null;
  note: string;
  status: "open" | "resolved";
  resolution: string;
  customer: { name: string; phone: string } | null;
  provider: { name: string; phone: string; emergency_contact: string } | null;
  created_at: string;
  resolved_at: string | null;
};

type Dispute = {
  id: number;
  job_title: string;
  provider_name: string;
  rating: number;
  comment: string;
  dispute: "open" | "upheld" | "rejected";
  dispute_reason: string;
  dispute_note: string;
  hidden: boolean;
  created_at: string;
};

export default function Safety() {
  const [tab, setTab] = useState<"incidents" | "disputes">("incidents");

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t("সেফটি ও ট্রাস্ট")}
        subtitle={t("জরুরি এসওএস অ্যালার্ট এবং প্রোভাইডারদের রিভিউ আপত্তির মীমাংসা")}
      />

      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[
          { value: "incidents", label: t("জরুরি SOS অ্যালার্ট") },
          { value: "disputes", label: t("রিভিউ আপত্তি") },
        ]}
      />

      {tab === "incidents" ? <IncidentsView /> : <DisputesView />}
    </div>
  );
}

function IncidentsView() {
  const qc = useQueryClient();
  const [status, setStatus] = useState("open");
  const [selected, setSelected] = useState<SafetyIncident | null>(null);
  const [resolution, setResolution] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const { data: incidents, isPending } = useQuery({
    queryKey: ["admin-safety", status],
    queryFn: async () =>
      (await api.get<SafetyIncident[]>("/admin/safety/", { params: status ? { status } : {} })).data,
  });

  async function handleResolve() {
    if (!resolution.trim()) {
      setError(t("কী ব্যবস্থা নেওয়া হয়েছে তা লিখুন।"));
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      await api.post(`/admin/safety/${selected!.id}/resolve/`, { resolution: resolution.trim() });
      setSelected(null);
      setResolution("");
      qc.invalidateQueries({ queryKey: ["admin-safety"] });
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
          { value: "open", label: t("অমীমাংসিত") },
          { value: "resolved", label: t("মীমাংসিত") },
          { value: "", label: t("সব") },
        ]}
      />

      <DataTable
        loading={isPending}
        rows={incidents}
        onRowClick={(row) => {
          setSelected(row);
          setResolution(row.resolution || "");
          setError("");
        }}
        columns={[
          { label: t("আইডি"), render: (r) => `#${r.id}` },
          {
            label: t("জব ও এলাকা"),
            render: (r) => (
              <div className="flex flex-col">
                <span className="font-semibold">{r.job_title || t("নির্দিষ্ট কাজ নেই")}</span>
                <span className="text-xs text-muted">{r.area_name}</span>
              </div>
            ),
          },
          {
            label: t("SOS তুলেছেন"),
            render: (r) => (
              <Badge tone={r.role === "customer" ? "warn" : "bad"}>
                {r.role === "customer" ? t("গ্রাহক") : t("প্রোভাইডার")}
              </Badge>
            ),
          },
          {
            label: t("গ্রাহক"),
            render: (r) => r.customer ? `${r.customer.name} (${r.customer.phone})` : "—",
          },
          {
            label: t("প্রোভাইডার"),
            render: (r) => r.provider ? `${r.provider.name} (${r.provider.phone})` : "—",
          },
          { label: t("অবস্থা"), render: (r) => <StatusBadge status={r.status} /> },
          { label: t("সময়"), render: (r) => formatDateTime(r.created_at) },
        ]}
      />

      {selected && (
        <Modal
          title={`${t("জরুরি SOS")} #${selected.id}`}
          open
          onClose={() => setSelected(null)}
        >
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={selected.status} />
              <Badge tone={selected.role === "customer" ? "warn" : "bad"}>
                {selected.role === "customer" ? t("গ্রাহক SOS তুলেছেন") : t("প্রোভাইডার SOS তুলেছেন")}
              </Badge>
              <span className="text-sm text-muted">{formatDateTime(selected.created_at)}</span>
            </div>

            <div className="rounded-xl bg-subtle p-3 text-sm">
              <div className="font-semibold">{selected.job_title}</div>
              <div className="text-muted">{selected.area_name}</div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 text-sm">
              <div className="rounded-xl border border-line p-3">
                <div className="font-semibold text-muted">{t("গ্রাহকের তথ্য")}</div>
                {selected.customer ? (
                  <>
                    <div className="text-base font-bold">{selected.customer.name}</div>
                    <a href={`tel:${selected.customer.phone}`} className="text-brand font-semibold">
                      {selected.customer.phone}
                    </a>
                  </>
                ) : (
                  <span>—</span>
                )}
              </div>

              <div className="rounded-xl border border-line p-3">
                <div className="font-semibold text-muted">{t("প্রোভাইডারের তথ্য")}</div>
                {selected.provider ? (
                  <>
                    <div className="text-base font-bold">{selected.provider.name}</div>
                    <a href={`tel:${selected.provider.phone}`} className="text-brand font-semibold">
                      {selected.provider.phone}
                    </a>
                    {selected.provider.emergency_contact && (
                      <div className="mt-1 text-xs text-muted">
                        {t("জরুরি নম্বর:")} <a href={`tel:${selected.provider.emergency_contact}`}>{selected.provider.emergency_contact}</a>
                      </div>
                    )}
                  </>
                ) : (
                  <span>—</span>
                )}
              </div>
            </div>

            {selected.latitude && selected.longitude && (
              <a
                href={`https://www.openstreetmap.org/?mlat=${selected.latitude}&mlon=${selected.longitude}#map=17/${selected.latitude}/${selected.longitude}`}
                target="_blank"
                rel="noreferrer"
                className="self-start text-sm font-semibold text-brand-strong"
              >
                {t("ঘটনাস্থলের ম্যাপ লোকেশন")}
              </a>
            )}

            {selected.note && (
              <div className="flex flex-col gap-1">
                <span className="text-xs font-semibold text-muted">{t("বিপদের কারণ / নোট:")}</span>
                <p className="m-0 rounded-xl bg-subtle p-3 text-sm">{selected.note}</p>
              </div>
            )}

            {selected.status === "open" ? (
              <div className="flex flex-col gap-2 pt-2 border-t border-line">
                <TextArea
                  label={t("কী ব্যবস্থা নেওয়া হয়েছে?")}
                  required
                  rows={3}
                  value={resolution}
                  onChange={(e) => setResolution(e.target.value)}
                  placeholder={t("যেমন: ফোনে কথা বলে সমাধান নিশ্চিত করা হয়েছে…")}
                />
                <ErrorNote>{error}</ErrorNote>
                <div className="flex justify-end gap-2 pt-2">
                  <Button variant="ghost" onClick={() => setSelected(null)}>{t("বন্ধ করুন")}</Button>
                  <Button loading={submitting} onClick={handleResolve}>
                    {t("মীমাংসিত হিসেবে চিহ্নিত করুন")}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-1 rounded-xl bg-ok-soft p-3 text-sm text-ok-strong">
                <span className="font-semibold">{t("গৃহীত পদক্ষেপ:")}</span>
                <span>{selected.resolution}</span>
                {selected.resolved_at && (
                  <span className="text-xs text-muted">{formatDateTime(selected.resolved_at)}</span>
                )}
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}

function DisputesView() {
  const qc = useQueryClient();
  const [status, setStatus] = useState("open");
  const [selected, setSelected] = useState<Dispute | null>(null);
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const { data: disputes, isPending } = useQuery({
    queryKey: ["admin-review-disputes", status],
    queryFn: async () =>
      (await api.get<Dispute[]>("/admin/review-disputes/", { params: status ? { status } : {} })).data,
  });

  async function handleDecide(uphold: boolean) {
    setError("");
    setSubmitting(true);
    try {
      await api.post(`/admin/review-disputes/${selected!.id}/decide/`, {
        uphold,
        note: note.trim(),
      });
      setSelected(null);
      setNote("");
      qc.invalidateQueries({ queryKey: ["admin-review-disputes"] });
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
          { value: "open", label: t("অমীমাংসিত") },
          { value: "upheld", label: t("আপত্তি গৃহীত") },
          { value: "rejected", label: t("আপত্তি বাতিল") },
          { value: "", label: t("সব") },
        ]}
      />

      <DataTable
        loading={isPending}
        rows={disputes}
        onRowClick={(row) => {
          setSelected(row);
          setNote(row.dispute_note || "");
          setError("");
        }}
        columns={[
          { label: t("আইডি"), render: (r) => `#${r.id}` },
          { label: t("জব"), render: (r) => <span className="font-semibold">{r.job_title}</span> },
          { label: t("প্রোভাইডার"), render: (r) => r.provider_name },
          {
            label: t("রেটিং"),
            render: (r) => (
              <span className="font-semibold text-alert-strong">
                {"★".repeat(r.rating)}
              </span>
            ),
          },
          {
            label: t("গ্রাহকের মন্তব্য"),
            render: (r) => <span className="line-clamp-1 text-sm">{r.comment || "—"}</span>,
          },
          {
            label: t("আপত্তির কারণ"),
            render: (r) => <span className="line-clamp-1 text-sm">{r.dispute_reason}</span>,
          },
          { label: t("অবস্থা"), render: (r) => <StatusBadge status={r.dispute} /> },
          { label: t("তারিখ"), render: (r) => formatDate(r.created_at) },
        ]}
      />

      {selected && (
        <Modal
          title={`${t("রিভিউ আপত্তি যাচাই")} #${selected.id}`}
          open
          onClose={() => setSelected(null)}
        >
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-semibold">{selected.job_title}</span>
              <StatusBadge status={selected.dispute} />
            </div>

            <div className="rounded-xl border border-line p-3 text-sm">
              <div className="flex items-center justify-between pb-1">
                <span className="font-semibold text-muted">{t("গ্রাহকের রিভিউ")}</span>
                <span className="font-bold text-alert-strong">{"★".repeat(selected.rating)}</span>
              </div>
              <p className="m-0">{selected.comment || t("কোনো লিখিত মন্তব্য নেই।")}</p>
            </div>

            <div className="rounded-xl bg-subtle p-3 text-sm">
              <div className="font-semibold text-muted">
                {t("প্রোভাইডারের আপত্তি ({name}):", { name: selected.provider_name })}
              </div>
              <p className="m-0 mt-1 font-medium">{selected.dispute_reason}</p>
            </div>

            {selected.dispute === "open" ? (
              <div className="flex flex-col gap-3 pt-2 border-t border-line">
                <TextArea
                  label={t("অ্যাডমিন সিদ্ধান্ত ও নোট (ঐচ্ছিক)")}
                  rows={2}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder={t("সিদ্ধান্তের কারণ লিখুন…")}
                />
                <ErrorNote>{error}</ErrorNote>
                <div className="flex flex-wrap justify-end gap-2 pt-2">
                  <Button variant="ghost" onClick={() => setSelected(null)}>{t("বন্ধ করুন")}</Button>
                  <Button
                    variant="danger"
                    loading={submitting}
                    onClick={() => handleDecide(false)}
                  >
                    {t("আপত্তি বাতিল")}
                  </Button>
                  <Button
                    loading={submitting}
                    onClick={() => handleDecide(true)}
                  >
                    {t("আপত্তি গ্রহণ (রিভিউ লুকান)")}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-1 rounded-xl bg-subtle p-3 text-sm">
                <span className="font-semibold">{t("অ্যাডমিন নোট:")}</span>
                <span>{selected.dispute_note || t("কোনো নোট নেই")}</span>
                {selected.hidden && (
                  <Badge tone="ok">{t("এই রিভিউটি জনসমক্ষে লুকানো হয়েছে")}</Badge>
                )}
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}
