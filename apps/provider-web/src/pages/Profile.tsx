import { api, Badge, Button, Card, errorMessage, ErrorNote, formatDate, Loading, PageHeader, SuccessNote, t } from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";

import { useProvider } from "../api";
import ProviderFields, { EMPTY_FORM, type ProviderForm } from "./ProviderFields";

const BADGES: Record<string, string> = { top_rated: "টপ রেটেড", "50_jobs": "৫০+ কাজ" };
// Identity documents are fixed after approval; the profile page edits only these.
const WORK_FIELDS = ["provider_type", "skills", "area_ids", "bio", "experience_years", "gender", "working_days", "work_start", "work_end", "payout_method", "payout_account"] as const;

export default function Profile() {
  const { data: provider } = useProvider();
  const qc = useQueryClient();
  const [form, setForm] = useState<ProviderForm>(EMPTY_FORM);
  const [saved, setSaved] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (provider) setForm(Object.fromEntries(Object.keys(EMPTY_FORM).map((k) => [k, provider[k as keyof typeof provider]])) as ProviderForm);
  }, [provider]);

  const { data: reviews } = useQuery({
    queryKey: ["my-reviews", provider?.id],
    queryFn: async () => (await api.get<{ results: { id: number; job_title: string; rating: number; comment: string; created_at: string }[] }>(`/providers/public/${provider!.id}/reviews/`)).data.results,
    enabled: !!provider,
  });

  if (!provider) return <Loading />;

  async function save(e: FormEvent) {
    e.preventDefault();
    setError("");
    setSaved("");
    try {
      await api.patch("/providers/me/", Object.fromEntries(WORK_FIELDS.map((k) => [k, form[k]])));
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
            {t(BADGES[b] ?? b)}
          </Badge>
        ))}
      />
      <Card>
        <ProviderFields form={form} setForm={setForm} identity={false} />
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
          </div>
        ))}
      </Card>
    </form>
  );
}
