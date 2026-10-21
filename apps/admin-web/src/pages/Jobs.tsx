import { api, Badge, Button, errorMessage, ErrorNote, formatDate, formatTaka, Loading, Modal, PageHeader, slotLabel, StatusBadge, t, Timeline } from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { DataTable, FilterChips, usePaged } from "../components";

type Job = {
  id: number;
  source: string;
  title: string;
  category_slug: string;
  area_name: string;
  address_line: string;
  customer_name: string;
  customer_phone: string;
  scheduled_date: string;
  slot: string;
  amount: string;
  is_emergency: boolean;
  description: string;
  status: string;
  provider_name: string;
  logs: { status: string; note: string; created_at: string }[];
};
type Suggestion = { id: number; full_name: string; phone: string; rating_avg: string; rating_count: number; trust_score: number; is_online: boolean; jobs_completed: number };

const SOURCES: Record<string, string> = { booking: "বুকিং", warranty: "ওয়ারেন্টি", custom_request: "কাস্টম", subscription_visit: "সাবস্ক্রিপশন", b2b_visit: "রক্ষণাবেক্ষণ চুক্তি" };

function AssignPanel({ job, onDone }: { job: Job; onDone: () => void }) {
  const { data: suggestions, isPending } = useQuery({
    queryKey: ["suggestions", job.id],
    queryFn: async () => (await api.get<Suggestion[]>(`/admin/jobs/${job.id}/suggestions/`)).data,
  });
  const [error, setError] = useState("");

  async function assign(providerId: number) {
    setError("");
    try {
      await api.post(`/admin/jobs/${job.id}/assign/`, { provider_id: providerId });
      onDone();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  if (isPending) return <Loading label={t("প্রোভাইডার খোঁজা হচ্ছে…")} />;
  return (
    <div className="flex flex-col gap-2">
      <span className="font-semibold">{t("স্মার্ট ম্যাচ (এলাকা, দক্ষতা, ফাঁকা সময়, ট্রাস্ট স্কোর)")}</span>
      {suggestions?.length === 0 && <span className="text-muted">{t("এই এলাকা ও দক্ষতায় ফাঁকা প্রোভাইডার নেই।")}</span>}
      {suggestions?.map((p) => (
        <div key={p.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-line p-3">
          <span className="flex-1">
            <span className="font-semibold">{p.full_name}</span> {p.is_online && <Badge tone="ok">{t("অনলাইন")}</Badge>}
            <span className="block text-[13px] text-muted">
              {t("ট্রাস্ট")} {p.trust_score} · {p.rating_count ? `${p.rating_avg}★ (${p.rating_count})` : t("নতুন")} · {p.jobs_completed} {t("কাজ")}
            </span>
          </span>
          <Button onClick={() => assign(p.id)}>{t("অ্যাসাইন")}</Button>
        </div>
      ))}
      <ErrorNote>{error}</ErrorNote>
    </div>
  );
}

export default function Jobs() {
  const [status, setStatus] = useState("open");
  const { data, isPending } = usePaged<Job>(["admin-jobs"], "/admin/jobs/", { status: status || undefined });
  const [open, setOpen] = useState<Job | null>(null);
  const qc = useQueryClient();

  function refresh() {
    setOpen(null);
    qc.invalidateQueries({ queryKey: ["admin-jobs"] });
  }

  async function cancel() {
    const reason = prompt(t("বাতিলের কারণ?"));
    if (!reason) return;
    await api.post(`/admin/jobs/${open!.id}/cancel/`, { reason });
    refresh();
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t("জব ও অ্যাসাইন")} subtitle={t("বুকিং, ওয়ারেন্টি, কাস্টম রিকোয়েস্ট আর সাবস্ক্রিপশন ভিজিট — সব কাজ এক জায়গায়")} />
      <FilterChips
        value={status}
        onChange={setStatus}
        options={[
          { value: "open", label: t("প্রোভাইডার নেই") },
          { value: "assigned", label: t("অ্যাসাইন করা") },
          { value: "accepted", label: t("গ্রহণ করা") },
          { value: "working", label: t("কাজ চলছে") },
          { value: "completed", label: t("সম্পন্ন") },
          { value: "", label: t("সব") },
        ]}
      />
      <DataTable
        loading={isPending}
        rows={data?.results}
        onRowClick={setOpen}
        columns={[
          { label: t("কাজ"), render: (j) => <>{j.is_emergency && <Badge tone="bad">{t("জরুরি")}</Badge>} <span className="font-semibold">{j.title}</span></> },
          { label: t("ধরন"), render: (j) => t(SOURCES[j.source] ?? j.source) },
          { label: t("এলাকা"), render: (j) => j.area_name },
          { label: t("সময়"), render: (j) => `${formatDate(j.scheduled_date)}, ${slotLabel(j.slot)}` },
          { label: t("প্রোভাইডার"), render: (j) => j.provider_name || "—" },
          { label: t("মূল্য"), render: (j) => formatTaka(j.amount) },
          { label: t("অবস্থা"), render: (j) => <StatusBadge status={j.status} /> },
        ]}
      />
      <Modal title={open?.title ?? ""} open={!!open} onClose={() => setOpen(null)}>
        {open && (
          <>
            <div className="flex flex-col gap-1 text-[15px]">
              <span>{open.customer_name} · <a href={`tel:${open.customer_phone}`}>{open.customer_phone}</a></span>
              <span className="text-muted">{open.address_line}, {open.area_name} {t("· ক্যাটাগরি:")} {open.category_slug}</span>
              <span>{formatDate(open.scheduled_date)}, {slotLabel(open.slot)} · {formatTaka(open.amount)}</span>
              {open.description && <span className="rounded-xl bg-subtle p-2">{open.description}</span>}
            </div>
            {["open", "assigned", "accepted"].includes(open.status) && <AssignPanel job={open} onDone={refresh} />}
            <Timeline events={[...open.logs].reverse()} />
            {!["completed", "cancelled"].includes(open.status) && (
              <Button variant="danger" onClick={cancel} className="self-start">
                {t("জব বাতিল")}
              </Button>
            )}
          </>
        )}
      </Modal>
    </div>
  );
}
