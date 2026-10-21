import { Card, Empty, formatDate, formatTaka, Loading, PageHeader, StatusBadge, t } from "@shohor/web-core";
import { Link } from "react-router-dom";

import { useOrders } from "../api/orders";

export default function Orders() {
  const { data, isPending } = useOrders();

  return (
    <section className="mx-auto flex max-w-[960px] flex-col gap-6 px-4 py-8 sm:px-6">
      <PageHeader title={t("আমার অর্ডার")} />
      {isPending && <Loading />}
      {data?.results.length === 0 && (
        <Empty icon="list" title={t("এখনো কোনো অর্ডার নেই")}>
          <Link to="/services">{t("একটি সার্ভিস বুক করুন")}</Link>
        </Empty>
      )}
      <div className="flex flex-col gap-3">
        {data?.results.map((o) => (
          <Link key={o.id} to={`/orders/${o.id}`} className="text-ink no-underline">
            <Card className="flex flex-wrap items-center gap-4 hover:border-brand">
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <span className="font-bold">{o.number}</span>
                <span className="text-sm text-muted">
                  {formatDate(o.created_at)} · {[...o.bookings.map((b) => b.service_name), ...o.items.map((i) => i.name)].join(", ")}
                </span>
              </div>
              <StatusBadge status={o.status} />
              <span className="w-24 text-right font-bold">{formatTaka(o.total)}</span>
            </Card>
          </Link>
        ))}
      </div>
    </section>
  );
}
