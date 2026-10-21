import { Button, ChatThread, Empty, ErrorNote, Field, PageHeader, Select, SuccessNote, TextArea, api, errorMessage, formatDateTime, t, type Conversation } from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

export function SupportInbox() {
  const qc = useQueryClient();
  const [onlyOpen, setOnlyOpen] = useState(true);
  const { data } = useQuery({
    queryKey: ["support", onlyOpen],
    queryFn: async () => (await api.get<Conversation[]>("/admin/chat/support/", { params: onlyOpen ? { open: 1 } : {} })).data,
    refetchInterval: 20_000,
  });
  const [current, setCurrent] = useState<number | null>(null);

  async function close() {
    await api.post(`/admin/chat/support/${current}/close/`);
    qc.invalidateQueries({ queryKey: ["support"] });
    qc.invalidateQueries({ queryKey: ["chat", current] });
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t("সাপোর্ট চ্যাট")} actions={<label className="flex items-center gap-2"><input type="checkbox" checked={onlyOpen} onChange={(e) => setOnlyOpen(e.target.checked)} className="size-5 accent-brand" />{t("শুধু খোলা")}</label>} />
      <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
        <div className="flex flex-col gap-2">
          {data?.length === 0 && <Empty icon="chat" title={t("কোনো সাপোর্ট চ্যাট নেই")} />}
          {data?.map((c) => (
            <button key={c.id} type="button" onClick={() => setCurrent(c.id)} className={`flex flex-col items-start rounded-2xl border p-3 text-left ${current === c.id ? "border-brand bg-brand-tint" : "border-line bg-surface"}`}>
              <span className="font-semibold">{c.title}</span>
              <span className="text-[13px] text-muted">{c.customer_name} · {c.last_message_at && formatDateTime(c.last_message_at)}</span>
              <span className="line-clamp-1 text-sm">{c.last_message}</span>
            </button>
          ))}
        </div>
        {current ? (
          <div className="flex flex-col gap-2">
            <ChatThread key={current} conversationId={current} adminView />
            <Button variant="ghost" className="self-end" onClick={close}>{t("চ্যাট বন্ধ করুন")}</Button>
          </div>
        ) : (
          <Empty icon="chat" title={t("বাঁ দিক থেকে একটি চ্যাট বাছুন")} />
        )}
      </div>
    </div>
  );
}

export function Broadcast() {
  const [f, setF] = useState({ audience: "customers", title_bn: "", title_en: "", body_bn: "", body_en: "", link: "" });
  const [error, setError] = useState("");
  const [sent, setSent] = useState("");
  const { data: history, refetch } = useQuery({
    queryKey: ["broadcasts"],
    queryFn: async () => (await api.get<{ id: number; audience: string; title_bn: string; sent_count: number; created_at: string }[]>("/admin/notifications/broadcast/")).data,
  });
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });

  async function send(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const { data } = await api.post<{ sent_count: number }>("/admin/notifications/broadcast/", f);
      setSent(t("{n} জনকে পাঠানো হয়েছে।", { n: data.sent_count }));
      refetch();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div className="flex max-w-[860px] flex-col gap-5">
      <PageHeader title={t("নোটিফিকেশন পাঠান")} subtitle={t("অফার, মৌসুমি সতর্কতা বা ঘোষণা — দুই ভাষায় লিখুন")} />
      <form onSubmit={send} className="flex flex-col gap-3 rounded-[20px] border border-line bg-surface p-5">
        <Select label={t("কাদের")} value={f.audience} onChange={set("audience")} options={[{ value: "customers", label: t("সব গ্রাহক") }, { value: "providers", label: t("সব প্রোভাইডার") }, { value: "all", label: t("সবাই") }]} />
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t("শিরোনাম (বাংলা)")} required value={f.title_bn} onChange={set("title_bn")} />
          <Field label={t("শিরোনাম (English)")} required value={f.title_en} onChange={set("title_en")} />
          <TextArea label={t("বার্তা (বাংলা)")} value={f.body_bn} onChange={set("body_bn")} />
          <TextArea label={t("বার্তা (English)")} value={f.body_en} onChange={set("body_en")} />
        </div>
        <Field label={t("লিংক (ঐচ্ছিক)")} value={f.link} onChange={set("link")} placeholder="/subscriptions" />
        <ErrorNote>{error}</ErrorNote>
        <SuccessNote>{sent}</SuccessNote>
        <Button type="submit" icon="send" className="self-start">{t("পাঠান")}</Button>
      </form>
      {history?.map((b) => (
        <div key={b.id} className="flex justify-between rounded-xl border border-line bg-surface p-3 text-[15px]">
          <span>{b.title_bn} · <span className="text-muted">{b.audience}</span></span>
          <span className="text-muted">{b.sent_count} · {formatDateTime(b.created_at)}</span>
        </div>
      ))}
    </div>
  );
}
