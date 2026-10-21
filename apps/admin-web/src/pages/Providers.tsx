import { api, areaName, Badge, Button, errorMessage, ErrorNote, formatDate, Modal, PageHeader, StatusBadge, t, useAreas } from "@shohor/web-core";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { DataTable, FilterChips, PrivateImage, usePaged } from "../components";

type Provider = {
  id: number;
  full_name: string;
  phone: string;
  gender: string;
  provider_type: string;
  skills: string[];
  area_ids: number[];
  bio: string;
  experience_years: number;
  nid_number: string;
  photo_url: string;
  nid_front_url: string;
  nid_back_url: string;
  kitchen_photo_urls: string[];
  status: string;
  rejection_reason: string;
  rating_avg: string;
  rating_count: number;
  jobs_completed: number;
  trust_score: number;
  is_online: boolean;
  created_at: string;
};

export default function Providers() {
  const [status, setStatus] = useState("pending");
  const [q, setQ] = useState("");
  const { data, isPending } = usePaged<Provider>(["admin-providers"], "/admin/providers/", { status: status || undefined, q: q || undefined });
  const { data: areas } = useAreas();
  const [open, setOpen] = useState<Provider | null>(null);
  const [error, setError] = useState("");
  const qc = useQueryClient();

  async function review(decision: "approve" | "reject" | "suspend") {
    let reason = "";
    if (decision !== "approve") {
      reason = prompt(decision === "reject" ? t("আবেদন কেন বাতিল? (প্রোভাইডার দেখতে পাবেন)") : t("স্থগিতের কারণ?")) ?? "";
      if (!reason) return;
    }
    setError("");
    try {
      const { data: updated } = await api.post<Provider>(`/admin/providers/${open!.id}/${decision}/`, { reason });
      setOpen(updated);
      qc.invalidateQueries({ queryKey: ["admin-providers"] });
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t("প্রোভাইডার যাচাই")} subtitle={t("NID, ছবি ও দক্ষতা যাচাই করে অনুমোদন দিন")} />
      <div className="flex flex-wrap items-center gap-3">
        <FilterChips
          value={status}
          onChange={setStatus}
          options={[
            { value: "pending", label: t("অপেক্ষমাণ") },
            { value: "approved", label: t("অনুমোদিত") },
            { value: "rejected", label: t("প্রত্যাখ্যাত") },
            { value: "suspended", label: t("স্থগিত") },
            { value: "", label: t("সব") },
          ]}
        />
        <input type="search" aria-label={t("নাম বা ফোন")} placeholder={t("নাম বা ফোন")} value={q} onChange={(e) => setQ(e.target.value)} className="h-10 rounded-xl border border-line px-3" />
      </div>
      <DataTable
        loading={isPending}
        rows={data?.results}
        onRowClick={setOpen}
        columns={[
          { label: t("নাম"), render: (p) => <><span className="font-semibold">{p.full_name}</span><span className="block text-[13px] text-muted">{p.phone}</span></> },
          { label: t("ধরন"), render: (p) => p.provider_type },
          { label: t("এলাকা"), render: (p) => p.area_ids.map((id) => areaName(areas, id)).join(", ") },
          { label: t("কাজ / রেটিং"), render: (p) => `${p.jobs_completed} · ${p.rating_count ? `${p.rating_avg}★` : "—"}` },
          { label: t("ট্রাস্ট"), render: (p) => p.trust_score },
          { label: t("অবস্থা"), render: (p) => <StatusBadge status={p.status} /> },
          { label: t("আবেদন"), render: (p) => formatDate(p.created_at) },
        ]}
      />
      <Modal title={open?.full_name ?? ""} open={!!open} onClose={() => setOpen(null)}>
        {open && (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={open.status} />
              <Badge>{open.provider_type}</Badge>
              {open.gender && <Badge>{open.gender === "female" ? t("মহিলা") : t("পুরুষ")}</Badge>}
              {open.is_online && <Badge tone="ok">{t("অনলাইন")}</Badge>}
            </div>
            <div className="flex flex-col gap-1 text-[15px]">
              <span><a href={`tel:${open.phone}`}>{open.phone}</a> {t("· অভিজ্ঞতা")} {open.experience_years} {t("বছর")}</span>
              <span>NID: <strong>{open.nid_number}</strong></span>
              <span>{t("দক্ষতা:")} {open.skills.join(", ")}</span>
              <span>{t("এলাকা:")} {open.area_ids.map((id) => areaName(areas, id)).join(", ")}</span>
              {open.bio && <p className="m-0 rounded-xl bg-subtle p-3">{open.bio}</p>}
            </div>
            <div className="flex flex-wrap gap-3">
              <PrivateImage url={open.photo_url} alt={t("প্রোভাইডারের ছবি")} />
              <PrivateImage url={open.nid_front_url} alt={t("NID সামনে")} />
              <PrivateImage url={open.nid_back_url} alt={t("NID পেছনে")} />
            </div>
            {open.kitchen_photo_urls.length > 0 && (
              <div className="flex flex-col gap-2">
                <span className="font-semibold">{t("রান্নাঘরের হাইজিন চেক")}</span>
                <div className="flex flex-wrap gap-2">{open.kitchen_photo_urls.map((u) => <PrivateImage key={u} url={u} alt={t("রান্নাঘর")} />)}</div>
              </div>
            )}
            {open.rejection_reason && <ErrorNote>{open.rejection_reason}</ErrorNote>}
            <ErrorNote>{error}</ErrorNote>
            <div className="flex flex-wrap gap-2">
              {open.status !== "approved" && <Button icon="check" onClick={() => review("approve")}>{t("অনুমোদন")}</Button>}
              {open.status === "pending" && <Button variant="danger" onClick={() => review("reject")}>{t("প্রত্যাখ্যান")}</Button>}
              {open.status === "approved" && <Button variant="danger" onClick={() => review("suspend")}>{t("স্থগিত")}</Button>}
            </div>
          </>
        )}
      </Modal>
    </div>
  );
}
