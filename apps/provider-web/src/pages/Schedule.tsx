import { Card, Empty, formatDate, Loading, PageHeader, slotLabel, StatusBadge, t } from "@shohor/web-core";
import { Link } from "react-router-dom";

import { useJobs, type Job } from "../api";

/** Upcoming jobs grouped by day: bookings, subscription visits and meal deliveries together. */
export default function Schedule() {
  const { data, isPending } = useJobs("active");
  const byDay = new Map<string, Job[]>();
  for (const job of data?.results ?? []) {
    byDay.set(job.scheduled_date, [...(byDay.get(job.scheduled_date) ?? []), job]);
  }
  const days = [...byDay.keys()].sort();

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("ক্যালেন্ডার")} subtitle={t("সামনের সব কাজ, সাবস্ক্রিপশন ভিজিট ও মিল ডেলিভারি")} />
      {isPending && <Loading />}
      {!isPending && days.length === 0 && <Empty icon="calendar" title={t("সামনে কোনো কাজ নির্ধারিত নেই")} />}
      {days.map((day) => (
        <section key={day} className="flex flex-col gap-2">
          <h2 className="m-0 text-lg font-bold">{formatDate(day)}</h2>
          {byDay
            .get(day)!
            .sort((a, b) => a.slot.localeCompare(b.slot))
            .map((job) => (
              <Link key={job.id} to={`/jobs/${job.id}`} className="text-ink no-underline">
                <Card className="flex flex-wrap items-center gap-4 p-4 hover:border-brand">
                  <span className="w-28 font-semibold text-brand-strong">{slotLabel(job.slot)}</span>
                  <span className="flex-1">
                    {job.title} · <span className="text-muted">{job.area_name}</span>
                  </span>
                  <StatusBadge status={job.status} />
                </Card>
              </Link>
            ))}
        </section>
      ))}
    </div>
  );
}
