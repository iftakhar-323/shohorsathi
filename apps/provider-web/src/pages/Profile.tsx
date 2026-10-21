import { Badge, Button, Card, ErrorNote, Loading, PageHeader, SuccessNote, api, errorMessage } from "@shohor/web-core";
import { useQueryClient } from "@tanstack/react-query";
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

  if (!provider) return <Loading />;

  async function save(e: FormEvent) {
    e.preventDefault();
    setError("");
    setSaved("");
    try {
      await api.patch("/providers/me/", Object.fromEntries(WORK_FIELDS.map((k) => [k, form[k]])));
      setSaved("সেভ হয়েছে।");
      qc.invalidateQueries({ queryKey: ["provider-me"] });
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <form onSubmit={save} className="flex max-w-[860px] flex-col gap-6">
      <PageHeader
        title="প্রোফাইল"
        subtitle={`${provider.full_name} · ${provider.phone}`}
        actions={provider.badges.map((b) => (
          <Badge key={b} tone="ok">
            {BADGES[b] ?? b}
          </Badge>
        ))}
      />
      <Card>
        <ProviderFields form={form} setForm={setForm} identity={false} />
      </Card>
      <SuccessNote>{saved}</SuccessNote>
      <ErrorNote>{error}</ErrorNote>
      <Button type="submit" className="self-start">
        সেভ করুন
      </Button>
    </form>
  );
}
