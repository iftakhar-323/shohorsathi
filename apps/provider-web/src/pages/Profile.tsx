import { api, Badge, Button, Card, errorMessage, ErrorNote, Field, formatDate, Loading, Modal, PageHeader, SuccessNote, t, TextArea } from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";

import { useProvider } from "../api";
import ProviderFields, { EMPTY_FORM, type ProviderForm } from "./ProviderFields";

type Review = { id: number; job_title: string; rating: number; comment: string; created_at: string; dispute: string; dispute_note: string };
const DISPUTE: Record<string, string> = { open: "আপত্তি যাচাই চলছে", upheld: "আপত্তি গৃহীত", rejected: "আপত্তি বাতিল" };
const BADGES: Record<string, string> = { top_rated: "টপ রেটেড", "50_jobs": "৫০+ কাজ" };

function badgeLabel(b: string) {
  if (b.startsWith("trained")) return t("প্রশিক্ষিত");
  return t(BADGES[b] ?? b);
}
// Identity documents are fixed after approval; the profile page edits only these.
const WORK_FIELDS = ["provider_type", "skills", "area_ids", "bio", "experience_years", "gender", "working_days", "work_start", "work_end", "payout_method", "payout_account"] as const;

export default function Profile() {
  const { data: provider } = useProvider();
  const qc = useQueryClient();
  const [form, setForm] = useState<ProviderForm>(EMPTY_FORM);
  const [emergency, setEmergency] = useState({ emergency_contact_name: "", emergency_contact_phone: "" });
  const [saved, setSaved] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!provider) return;
    setForm(Object.fromEntries(Object.keys(EMPTY_FORM).map((k) => [k, provider[k as keyof typeof provider]])) as ProviderForm);
    setEmergency({ emergency_contact_name: provider.emergency_contact_name ?? "", emergency_contact_phone: provider.emergency_contact_phone ?? "" });
  }, [provider]);

  const [disputing, setDisputing] = useState<Review | null>(null);
  const { data: reviews } = useQuery({
    queryKey: ["my-reviews", provider?.id],
    queryFn: async () => (await api.get<{ results: Review[] }>(`/providers/public/${provider!.id}/reviews/`)).data.results,
    enabled: !!provider,
  });

  if (!provider) return <Loading />;

  async function save(e: FormEvent) {
    e.preventDefault();
    setError("");
    setSaved("");
    try {
      await api.patch("/providers/me/", { ...Object.fromEntries(WORK_FIELDS.map((k) => [k, form[k]])), ...emergency });
      setSaved(t("সেভ হয়েছে।"));
      qc.invalidateQueries({ queryKey: ["provider-me"] });
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <form onSubmit={save} className="flex max-w-[860px] flex-col gap-6">
      <PageHeader
        title={t("প্রোফাইল")}
        subtitle={`${provider.full_name} · ${provider.phone}`}
        actions={provider.badges.map((b) => (
          <Badge key={b} tone="ok">
            {badgeLabel(b)}
          </Badge>
        ))}
      />
      <Card>
        <ProviderFields form={form} setForm={setForm} identity={false} />
      </Card>
      <Card className="flex flex-col gap-3">
        <h2 className="m-0 text-lg font-bold">{t("জরুরি যোগাযোগ")}</h2>
        <p className="m-0 text-sm text-muted">{t("SOS চাপলে এই নম্বরে এসএমএস যাবে।")}</p>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t("নাম")} value={emergency.emergency_contact_name} onChange={(e) => setEmergency({ ...emergency, emergency_contact_name: e.target.value })} />
          <Field label={t("মোবাইল নম্বর")} inputMode="tel" maxLength={11} value={emergency.emergency_contact_phone} onChange={(e) => setEmergency({ ...emergency, emergency_contact_phone: e.target.value })} />
        </div>
      </Card>
      <SuccessNote>{saved}</SuccessNote>
      <ErrorNote>{error}</ErrorNote>
      <Button type="submit" className="self-start">
        {t("সেভ করুন")}
      </Button>
      <Card className="flex flex-col gap-3">
        <h2 className="m-0 text-lg font-bold">{t("গ্রাহকের রিভিউ")}</h2>
        {reviews?.length === 0 && <p className="m-0 text-muted">{t("এখনো কোনো রিভিউ নেই।")}</p>}
        {reviews?.map((r) => (
          <div key={r.id} className="flex flex-col border-b border-subtle pb-2 last:border-0">
            <span className="text-alert-strong">{"★".repeat(r.rating)}<span className="text-line">{"★".repeat(5 - r.rating)}</span></span>
            <span className="text-sm text-muted">{r.job_title} · {formatDate(r.created_at)}</span>
            {r.comment && <span>{r.comment}</span>}
            {r.dispute ? (
              <span className="text-sm text-muted">{t(DISPUTE[r.dispute] ?? r.dispute)}{r.dispute_note && ` · ${r.dispute_note}`}</span>
            ) : (
              <button type="button" onClick={() => setDisputing(r)} className="self-start text-sm font-semibold text-brand-strong">{t("রিভিউ নিয়ে আপত্তি জানান")}</button>
            )}
          </div>
        ))}
      </Card>
      <DisputeModal review={disputing} onClose={() => setDisputing(null)} />
    </form>
  );
}

function DisputeModal({ review, onClose }: { review: Review | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");

  async function send() {
    setError("");
    try {
      await api.post(`/providers/reviews/${review!.id}/dispute/`, { reason });
      qc.invalidateQueries({ queryKey: ["my-reviews"] });
      setReason("");
      onClose();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <Modal title={t("রিভিউ নিয়ে আপত্তি")} open={!!review} onClose={onClose}>
      <p className="m-0 text-muted">{t("রিভিউটি ভুল বা অন্যায্য হলে কারণ লিখুন। আমাদের টিম যাচাই করে সিদ্ধান্ত জানাবে।")}</p>
      <TextArea label={t("কারণ")} value={reason} onChange={(e) => setReason(e.target.value)} />
      <ErrorNote>{error}</ErrorNote>
      <Button onClick={send} disabled={reason.trim().length < 10}>{t("আপত্তি পাঠান")}</Button>
    </Modal>
  );
}
