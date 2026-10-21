import { Card, Loading, PageHeader, Select, Stat, api, formatNumber, getLang, t } from "@shohor/web-core";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { ISSUE_CATEGORIES } from "./Issues";

type Report = {
  reported: number;
  resolved: number;
  open: number;
  resolution_rate: number;
  median_days_to_resolve: number | null;
  by_category: { category: string; n: number; done: number; median_days: number | null }[];
  by_authority: { name_bn: string; name_en: string; assigned: number; resolved: number; open: number; median_days: number | null }[];
  open_hotspots: { area_id: number; area_name: string; n: number }[];
  months: { month: string; reported: number; resolved: number }[];
};

const days = (n: number | null) => (n == null ? "—" : n < 1 ? t("১ দিনের কম") : t("{n} দিন", { n }));

/** Share of a row that is done, drawn as a filled track; the numbers sit beside it so the bar is never the only cue. */
function Progress({ done, total }: { done: number; total: number }) {
  return (
    <div className="h-2.5 rounded-full bg-subtle" role="presentation">
      <div className="h-2.5 rounded-full bg-brand" style={{ width: `${total ? (done / total) * 100 : 0}%` }} />
    </div>
  );
}

/** Public: how many city problems were reported through ShohorSathi, how many got fixed, by whom, how fast. */
export default function Transparency() {
  const [period, setPeriod] = useState("90");
  const { data, isPending } = useQuery({
    queryKey: ["transparency", period],
    queryFn: async () => (await api.get<Report>("/issues/transparency/", { params: { days: period } })).data,
  });
  const en = getLang() === "en";

  return (
    <section className="mx-auto flex max-w-[1100px] flex-col gap-6 px-4 py-8 sm:px-6">
      <PageHeader
        title={t("শহরের স্বচ্ছতা ড্যাশবোর্ড")}
        subtitle={t("নাগরিকদের রিপোর্ট করা সমস্যা কতটা, কত দ্রুত এবং কোন কর্তৃপক্ষ সমাধান করছে")}
        actions={<Select label={t("সময়")} value={period} onChange={(e) => setPeriod(e.target.value)} options={[{ value: "30", label: t("৩০ দিন") }, { value: "90", label: t("৯০ দিন") }, { value: "365", label: t("১ বছর") }]} />}
      />
      {isPending || !data ? <Loading /> : (
        <>
          <div className="grid grid-cols-[repeat(auto-fit,minmax(160px,1fr))] gap-3">
            <Stat label={t("রিপোর্ট হয়েছে")} value={formatNumber(data.reported)} icon="flag" />
            <Stat label={t("সমাধান হয়েছে")} value={`${formatNumber(data.resolved)} (${data.resolution_rate}%)`} icon="check" />
            <Stat label={t("চলমান")} value={formatNumber(data.open)} icon="clock" />
            <Stat label={t("সমাধানে সাধারণত লাগে")} value={days(data.median_days_to_resolve)} icon="calendar" />
          </div>

          <Card className="flex flex-col gap-3">
            <h2 className="m-0 text-lg font-bold">{t("কর্তৃপক্ষভিত্তিক কাজ")}</h2>
            {data.by_authority.length === 0 && <span className="text-muted">{t("এখনো কোনো সমস্যা কর্তৃপক্ষকে পাঠানো হয়নি।")}</span>}
            {data.by_authority.map((a) => (
              <div key={a.name_en} className="grid gap-1.5 sm:grid-cols-[minmax(0,16rem)_1fr_auto] sm:items-center sm:gap-4">
                <span className="font-semibold">{en ? a.name_en : a.name_bn}</span>
                <Progress done={a.resolved} total={a.assigned} />
                <span className="text-sm tabular-nums text-muted">
                  {t("{done}/{total} সমাধান", { done: a.resolved, total: a.assigned })} · {days(a.median_days)}
                </span>
              </div>
            ))}
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card className="flex flex-col gap-3">
              <h2 className="m-0 text-lg font-bold">{t("ধরন অনুযায়ী")}</h2>
              {data.by_category.map((c) => (
                <div key={c.category} className="flex flex-col gap-1">
                  <div className="flex justify-between gap-2 text-[15px]">
                    <span>{t(ISSUE_CATEGORIES[c.category] ?? c.category)}</span>
                    <span className="tabular-nums text-muted">{t("{done}/{total} সমাধান", { done: c.done, total: c.n })}</span>
                  </div>
                  <Progress done={c.done} total={c.n} />
                </div>
              ))}
            </Card>
            <Card className="flex flex-col gap-2">
              <h2 className="m-0 text-lg font-bold">{t("সবচেয়ে বেশি চলমান সমস্যা যেখানে")}</h2>
              {data.open_hotspots.length === 0 && <span className="text-muted">{t("এখন কোনো চলমান সমস্যা নেই।")}</span>}
              {data.open_hotspots.map((h) => (
                <div key={h.area_id} className="flex justify-between border-b border-subtle py-1.5 last:border-0">
                  <span>{h.area_name}</span>
                  <span className="font-semibold tabular-nums">{formatNumber(h.n)}</span>
                </div>
              ))}
            </Card>
          </div>

          <Card className="flex flex-col gap-2 overflow-x-auto">
            <h2 className="m-0 text-lg font-bold">{t("মাসভিত্তিক")}</h2>
            <table className="w-full min-w-[420px] border-collapse text-[15px]">
              <thead>
                <tr className="text-left text-[13px] text-muted">
                  {[t("মাস"), t("রিপোর্ট"), t("সমাধান")].map((h) => <th key={h} className="border-b border-line py-2 font-semibold">{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {data.months.map((m) => (
                  <tr key={m.month}>
                    <td className="border-b border-subtle py-2">{new Date(`${m.month}-01`).toLocaleDateString(en ? "en-GB" : "bn-BD", { month: "long", year: "numeric" })}</td>
                    <td className="border-b border-subtle py-2 tabular-nums">{formatNumber(m.reported)}</td>
                    <td className="border-b border-subtle py-2 tabular-nums">{formatNumber(m.resolved)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          <p className="m-0 text-[13px] text-muted">{t("এখানে কারও নাম বা ফোন নম্বর দেখানো হয় না। বাতিল করা রিপোর্ট গণনায় নেই।")}</p>
        </>
      )}
    </section>
  );
}
