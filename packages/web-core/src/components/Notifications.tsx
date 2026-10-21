import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";

import { api, type Paginated } from "../lib/api";
import { formatDateTime } from "../lib/format";
import { getLang, t } from "../lib/i18n";
import Icon from "./Icon";
import { Button, Empty, Loading, PageHeader } from "./ui";

export type AppNotification = { id: number; kind: string; title_bn: string; title_en: string; body_bn: string; body_en: string; link: string; read_at: string | null; created_at: string };

// A person can be both customer and provider, so every app shows all of their notifications.
export function NotificationBell() {
  const { data: unread } = useQuery({
    queryKey: ["notif-unread"],
    queryFn: async () => (await api.get<{ unread: number }>("/notifications/unread-count/")).data.unread,
    refetchInterval: 30_000,
  });
  return (
    <Link
      to="/notifications"
      aria-label={t("নোটিফিকেশন, {count}টি নতুন", { count: unread ?? 0 })}
      className="relative flex size-11 items-center justify-center rounded-full border border-line bg-surface text-ink"
    >
      <Icon name="bell" />
      {!!unread && <span className="absolute -top-1 -right-1 flex min-w-5 items-center justify-center rounded-full bg-alert px-1 text-xs font-bold text-ink">{unread}</span>}
    </Link>
  );
}

export function NotificationsPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { data, isPending } = useQuery({
    queryKey: ["notifications"],
    queryFn: async () => (await api.get<Paginated<AppNotification>>("/notifications/")).data,
  });
  const en = getLang() === "en";

  async function open(n: AppNotification) {
    if (!n.read_at) await api.post(`/notifications/${n.id}/read/`);
    qc.invalidateQueries({ queryKey: ["notif-unread"] });
    qc.invalidateQueries({ queryKey: ["notifications"] });
    if (n.link) navigate(n.link);
  }

  async function readAll() {
    await api.post("/notifications/read-all/");
    qc.invalidateQueries({ queryKey: ["notif-unread"] });
    qc.invalidateQueries({ queryKey: ["notifications"] });
  }

  return (
    <div className="mx-auto flex w-full max-w-[760px] flex-col gap-5">
      <PageHeader title={t("নোটিফিকেশন")} actions={<Button variant="ghost" icon="check" onClick={readAll}>{t("সব পড়া হয়েছে")}</Button>} />
      {isPending && <Loading />}
      {data?.results.length === 0 && <Empty icon="bell" title={t("কোনো নোটিফিকেশন নেই")} />}
      <div className="flex flex-col gap-2">
        {data?.results.map((n) => (
          <button
            key={n.id}
            type="button"
            onClick={() => open(n)}
            className={`flex items-start gap-3 rounded-2xl border p-4 text-left ${n.read_at ? "border-line bg-surface" : "border-brand bg-brand-tint"}`}
          >
            <Icon name="bell" className={n.read_at ? "text-muted" : "text-brand"} />
            <span className="flex flex-1 flex-col gap-0.5">
              <span className="font-semibold">{en ? n.title_en : n.title_bn}</span>
              {(n.body_bn || n.body_en) && <span className="text-[15px] text-muted">{en ? n.body_en : n.body_bn}</span>}
              <span className="text-[12px] text-muted">{formatDateTime(n.created_at)}</span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
