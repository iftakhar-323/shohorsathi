import { Badge, Button, ErrorNote, Loading, Modal, PageHeader, StatusBadge, Timeline, api, errorMessage, formatDate, formatTaka, slotLabel } from "@shohor/web-core";
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

const SOURCES: Record<string, string> = { booking: "বুকিং", warranty: "ওয়ারেন্টি", custom_request: "কাস্টম", subscription_visit: "সাবস্ক্রিপশন" };

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

  if (isPending) return <Loading label="প্রোভাইডার খোঁজা হচ্ছে…" />;
  return (
    <div className="flex flex-col gap-2">
      <span className="font-semibold">স্মার্ট ম্যাচ (এলাকা, দক্ষতা, ফাঁকা সময়, ট্রাস্ট স্কোর)</span>
      {suggestions?.length === 0 && <span className="text-muted">এই এলাকা ও দক্ষতায় ফাঁকা প্রোভাইডার নেই।</span>}
      {suggestions?.map((p) => (
        <div key={p.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-line p-3">
          <span className="flex-1">
            <span className="font-semibold">{p.full_name}</span> {p.is_online && <Badge tone="ok">অনলাইন</Badge>}
            <span className="block text-[13px] text-muted">
              ট্রাস্ট {p.trust_score} · {p.rating_count ? `${p.rating_avg}★ (${p.rating_count})` : "নতুন"} · {p.jobs_completed} কাজ
            </span>
          </span>
          <Button onClick={() => assign(p.id)}>অ্যাসাইন</Button>
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
    const reason = prompt("বাতিলের কারণ?");
    if (!reason) return;
    await api.post(`/admin/jobs/${open!.id}/cancel/`, { reason });
    refresh();
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title="জব ও অ্যাসাইন" subtitle="বুকিং, ওয়ারেন্টি, কাস্টম রিকোয়েস্ট আর সাবস্ক্রিপশন ভিজিট — সব কাজ এক জায়গায়" />
      <FilterChips
        value={status}
        onChange={setStatus}
        options={[
          { value: "open", label: "প্রোভাইডার নেই" },
          { value: "assigned", label: "অ্যাসাইন করা" },
          { value: "accepted", label: "গ্রহণ করা" },
          { value: "working", label: "কাজ চলছে" },
          { value: "completed", label: "সম্পন্ন" },
          { value: "", label: "সব" },
        ]}
      />
      <DataTable
        loading={isPending}
        rows={data?.results}
        onRowClick={setOpen}
        columns={[
          { label: "কাজ", render: (j) => <>{j.is_emergency && <Badge tone="bad">জরুরি</Badge>} <span className="font-semibold">{j.title}</span></> },
          { label: "ধরন", render: (j) => SOURCES[j.source] ?? j.source },
          { label: "এলাকা", render: (j) => j.area_name },
          { label: "সময়", render: (j) => `${formatDate(j.scheduled_date)}, ${slotLabel(j.slot)}` },
          { label: "প্রোভাইডার", render: (j) => j.provider_name || "—" },
          { label: "মূল্য", render: (j) => formatTaka(j.amount) },
          { label: "অবস্থা", render: (j) => <StatusBadge status={j.status} /> },
        ]}
      />
      <Modal title={open?.title ?? ""} open={!!open} onClose={() => setOpen(null)}>
        {open && (
          <>
            <div className="flex flex-col gap-1 text-[15px]">
              <span>{open.customer_name} · <a href={`tel:${open.customer_phone}`}>{open.customer_phone}</a></span>
              <span className="text-muted">{open.address_line}, {open.area_name} · ক্যাটাগরি: {open.category_slug}</span>
              <span>{formatDate(open.scheduled_date)}, {slotLabel(open.slot)} · {formatTaka(open.amount)}</span>
              {open.description && <span className="rounded-xl bg-subtle p-2">{open.description}</span>}
            </div>
            {["open", "assigned", "accepted"].includes(open.status) && <AssignPanel job={open} onDone={refresh} />}
            <Timeline events={[...open.logs].reverse()} />
            {!["completed", "cancelled"].includes(open.status) && (
              <Button variant="danger" onClick={cancel} className="self-start">
                জব বাতিল
              </Button>
            )}
          </>
        )}
      </Modal>
    </div>
  );
}
