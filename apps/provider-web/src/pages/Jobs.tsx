import { api, Badge, Button, Card, Empty, errorMessage, ErrorNote, formatDate, formatTaka, Icon, Loading, PageHeader, slotLabel, Stat, StatusBadge, t, Tabs } from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useJobs, useProvider, type Job } from "../api";

type Tab = "available" | "active" | "history";

const SOURCE: Record<string, string> = {
  booking: "বুকিং",
  warranty: "ওয়ারেন্টি",
  custom_request: "কাস্টম",
  subscription_visit: "সাবস্ক্রিপশন",
};

function JobRow({ job, tab }: { job: Job; tab: Tab }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function act(action: "accept" | "reject") {
    setBusy(true);
    setError("");
    try {
      await api.post(`/providers/jobs/${job.id}/${action}/`);
      qc.invalidateQueries({ queryKey: ["jobs"] });
      if (action === "accept") navigate(`/jobs/${job.id}`);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="flex flex-wrap items-center gap-4">
      <div className="flex min-w-0 flex-[1_1_320px] flex-col gap-1.5">
        <div className="flex flex-wrap items-center gap-2">
          {job.is_emergency ? <Badge tone="bad">{t("জরুরি")}</Badge> : <Badge tone="ok">{t(SOURCE[job.source] ?? job.source)}</Badge>}
          <span className="text-sm text-muted">
            {formatDate(job.scheduled_date)}, {slotLabel(job.slot)}
          </span>
          {tab !== "available" && <StatusBadge status={job.status} />}
        </div>
        <Link to={`/jobs/${job.id}`} className="text-lg font-bold text-ink no-underline">
          {job.title}
        </Link>
        <span className="text-sm text-muted">
          {job.area_name} · {formatTaka(job.amount)}
        </span>
        <ErrorNote>{error}</ErrorNote>
      </div>
      {tab === "available" ? (
        <Button loading={busy} onClick={() => act("accept")}>
          {t("গ্রহণ করুন")}
        </Button>
      ) : job.status === "assigned" ? (
        <div className="flex gap-2">
          <Button variant="ghost" loading={busy} onClick={() => act("reject")}>
            {t("বাতিল")}
          </Button>
          <Button loading={busy} onClick={() => act("accept")}>
            {t("গ্রহণ করুন")}
          </Button>
        </div>
      ) : (
        <Link to={`/jobs/${job.id}`} className="flex h-11 items-center gap-1 rounded-xl border border-line px-4 font-semibold text-ink no-underline">
          {t("খুলুন")} <Icon name="next" size={16} />
        </Link>
      )}
    </Card>
  );
}

export default function Jobs() {
  const [tab, setTab] = useState<Tab>("active");
  const { data: provider } = useProvider();
  const { data, isPending } = useJobs(tab);
  const qc = useQueryClient();
  const { data: earnings } = useQuery({
    queryKey: ["earnings"],
    queryFn: async () => (await api.get<{ summary: Record<string, string | number> }>("/providers/earnings/")).data,
  });

  async function toggleOnline() {
    await api.patch("/providers/me/", { is_online: !provider?.is_online });
    qc.invalidateQueries({ queryKey: ["provider-me"] });
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t("জব ইনবক্স")}
        subtitle={`${provider?.full_name} · ${t("যাচাইকৃত")}`}
        actions={
          <Button variant={provider?.is_online ? "primary" : "ghost"} icon={provider?.is_online ? "check" : "clock"} onClick={toggleOnline}>
            {provider?.is_online ? t("অনলাইন") : t("অফলাইন")}
          </Button>
        }
      />
      <div className="grid grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-3">
        <Stat label={t("সম্পন্ন কাজ")} value={provider?.jobs_completed ?? 0} icon="check" />
        <Stat label={t("এই সপ্তাহের আয়")} value={formatTaka(earnings?.summary.this_week as string)} icon="money" />
        <Stat label={t("রেটিং")} value={provider?.rating_count ? `${provider.rating_avg} ★` : t("নতুন")} icon="star" />
        <Stat label={t("ট্রাস্ট স্কোর")} value={provider?.trust_score ?? "-"} icon="shield" />
      </div>
      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[
          { value: "active", label: t("আমার কাজ") },
          { value: "available", label: t("নতুন কাজ") },
          { value: "history", label: t("ইতিহাস") },
        ]}
      />
      {isPending && <Loading />}
      {data?.results.length === 0 && (
        <Empty icon="list" title={tab === "available" ? t("আপনার এলাকায় এখন নতুন কাজ নেই") : t("কোনো কাজ নেই")}>
          {tab === "available" && t("অনলাইন থাকুন, নতুন কাজ এলে এখানে দেখাবে।")}
        </Empty>
      )}
      <div className="flex flex-col gap-3">
        {data?.results.map((job) => <JobRow key={job.id} job={job} tab={tab} />)}
      </div>
    </div>
  );
}
