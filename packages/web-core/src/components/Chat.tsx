import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { api, errorMessage, getTokens } from "../lib/api";
import { useAuth } from "../lib/auth";
import { formatDateTime } from "../lib/format";
import { t } from "../lib/i18n";
import Icon from "./Icon";
import { Badge, Button, Empty, ErrorNote, Loading, PageHeader } from "./ui";

export type Conversation = {
  id: number;
  kind: "job" | "support";
  source: string;
  source_id: number | null;
  title: string;
  customer_name: string;
  provider_name: string;
  is_open: boolean;
  last_message_at: string | null;
  unread: number;
  last_message: string;
};
export type ChatMessage = { id: number; sender_user_id: number | null; sender_role: string; sender_name: string; body: string; attachment_url: string; created_at: string };

export function useChatUnread(enabled = true) {
  return useQuery({
    queryKey: ["chat-unread"],
    queryFn: async () => (await api.get<{ unread: number }>("/chat/unread/")).data.unread,
    enabled,
    refetchInterval: 30_000,
  });
}

/** Opens (or reuses) the chat about a job and returns its id. */
export async function openJobChat(source: string, sourceId: number) {
  const { data } = await api.post<Conversation>("/chat/conversations/", { kind: "job", source, source_id: sourceId });
  return data.id;
}

function useLiveMessages(conversationId: number, onMessage: (m: ChatMessage) => void) {
  const handler = useRef(onMessage);
  handler.current = onMessage;
  useEffect(() => {
    const token = getTokens()?.access;
    if (!token) return;
    const proto = location.protocol === "https:" ? "wss" : "ws";
    let ws: WebSocket | null = new WebSocket(`${proto}://${location.host}/api/chat/ws/${conversationId}/?token=${token}`);
    ws.onmessage = (e) => handler.current(JSON.parse(e.data));
    ws.onerror = () => ws?.close();
    return () => {
      ws?.close();
      ws = null;
    };
  }, [conversationId]);
}

export function ChatThread({ conversationId, adminView = false }: { conversationId: number; adminView?: boolean }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const key = ["chat", conversationId];
  const { data, isPending } = useQuery({
    queryKey: key,
    queryFn: async () => (await api.get<{ conversation: Conversation; messages: ChatMessage[] }>(`/chat/conversations/${conversationId}/messages/`)).data,
    refetchInterval: 20_000, // fallback when the socket is blocked
  });
  const [body, setBody] = useState("");
  const [error, setError] = useState("");
  const bottom = useRef<HTMLDivElement>(null);

  useLiveMessages(conversationId, (m) =>
    qc.setQueryData<{ conversation: Conversation; messages: ChatMessage[] }>(key, (old) =>
      old && !old.messages.some((x) => x.id === m.id) ? { ...old, messages: [...old.messages, m] } : old,
    ),
  );

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
    qc.invalidateQueries({ queryKey: ["chat-unread"] });
  }, [data?.messages.length, qc]);

  async function send(e: FormEvent) {
    e.preventDefault();
    if (!body.trim()) return;
    setError("");
    try {
      const { data: m } = await api.post<ChatMessage>(`/chat/conversations/${conversationId}/messages/`, { body });
      setBody("");
      qc.setQueryData<{ conversation: Conversation; messages: ChatMessage[] }>(key, (old) =>
        old && !old.messages.some((x) => x.id === m.id) ? { ...old, messages: [...old.messages, m] } : old,
      );
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  if (isPending || !data) return <Loading />;
  const conv = data.conversation;
  const mine = (m: ChatMessage) => (adminView ? m.sender_role === "admin" : m.sender_user_id === user?.id);

  return (
    <div className="flex h-[70vh] min-h-[420px] flex-col overflow-hidden rounded-[20px] border border-line bg-surface">
      <div className="flex items-center gap-3 border-b border-line px-4 py-3">
        <Icon name="chat" className="text-brand" />
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="truncate font-semibold">{conv.title}</span>
          <span className="text-[13px] text-muted">
            {conv.kind === "support" ? t("শহরসাথী সাপোর্ট") : [conv.customer_name, conv.provider_name].filter(Boolean).join(" · ")}
          </span>
        </div>
        {!conv.is_open && <Badge>{t("বন্ধ")}</Badge>}
      </div>
      <div className="flex flex-1 flex-col gap-2 overflow-y-auto bg-ground p-4" aria-live="polite">
        {data.messages.map((m) => (
          <div key={m.id} className={`flex max-w-[80%] flex-col gap-0.5 ${mine(m) ? "self-end items-end" : "self-start"}`}>
            {!mine(m) && <span className="text-[12px] text-muted">{m.sender_role === "bot" ? t("শহরসাথী") : m.sender_name}</span>}
            <span className={`rounded-2xl px-3.5 py-2 whitespace-pre-line ${mine(m) ? "bg-brand text-white" : m.sender_role === "bot" ? "bg-info-soft text-ink" : "bg-surface text-ink"}`}>
              {m.body}
            </span>
            {m.attachment_url && <a href={m.attachment_url} target="_blank" rel="noreferrer"><img src={m.attachment_url} alt="" className="max-h-40 rounded-xl" /></a>}
            <span className="text-[11px] text-muted">{formatDateTime(m.created_at)}</span>
          </div>
        ))}
        <div ref={bottom} />
      </div>
      <ErrorNote>{error}</ErrorNote>
      {conv.is_open && (
        <form onSubmit={send} className="flex gap-2 border-t border-line p-3">
          <label htmlFor="chat-input" className="sr-only">{t("বার্তা")}</label>
          <input
            id="chat-input"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder={t("বার্তা লিখুন…")}
            className="h-11 min-w-0 flex-1 rounded-xl border border-line px-3 outline-none focus:border-brand"
          />
          <Button type="submit" icon="send" aria-label={t("পাঠান")}>{t("পাঠান")}</Button>
        </form>
      )}
    </div>
  );
}

export function ChatPage({ allowSupport = true }: { allowSupport?: boolean }) {
  const { id } = useParams();
  const qc = useQueryClient();
  const { data, isPending } = useQuery({
    queryKey: ["conversations"],
    queryFn: async () => (await api.get<Conversation[]>("/chat/conversations/")).data,
    refetchInterval: 30_000,
  });
  const [subject, setSubject] = useState("");
  const [first, setFirst] = useState("");
  const [error, setError] = useState("");
  const [started, setStarted] = useState<number | null>(null);
  const current = id ? Number(id) : started;

  async function startSupport(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const { data: conv } = await api.post<Conversation>("/chat/conversations/", { kind: "support", subject: subject || t("সাপোর্ট"), body: first });
      setStarted(conv.id);
      setFirst("");
      qc.invalidateQueries({ queryKey: ["conversations"] });
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t("চ্যাট")} subtitle={t("প্রোভাইডার ও সাপোর্টের সাথে কথা বলুন")} />
      <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
        <div className="flex flex-col gap-2">
          {isPending && <Loading />}
          {data?.length === 0 && <Empty icon="chat" title={t("এখনো কোনো চ্যাট নেই")} />}
          {data?.map((c) => (
            <Link
              key={c.id}
              to={`/chat/${c.id}`}
              onClick={() => setStarted(null)}
              className={`flex items-center gap-3 rounded-2xl border p-3 text-ink no-underline ${current === c.id ? "border-brand bg-brand-tint" : "border-line bg-surface"}`}
            >
              <Icon name={c.kind === "support" ? "shield" : "wrench"} className="text-brand" />
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate font-semibold">{c.title}</span>
                <span className="truncate text-[13px] text-muted">{c.last_message}</span>
              </span>
              {c.unread > 0 && <span className="rounded-full bg-alert px-2 text-xs font-bold">{c.unread}</span>}
            </Link>
          ))}
          {allowSupport && (
            <form onSubmit={startSupport} className="mt-2 flex flex-col gap-2 rounded-2xl border border-dashed border-line p-3">
              <span className="font-semibold">{t("সাপোর্টে লিখুন")}</span>
              <input aria-label={t("বিষয়")} placeholder={t("বিষয়")} value={subject} onChange={(e) => setSubject(e.target.value)} className="h-10 rounded-xl border border-line px-3" />
              <textarea aria-label={t("বার্তা")} placeholder={t("আপনার প্রশ্ন বা সমস্যা")} value={first} onChange={(e) => setFirst(e.target.value)} required rows={2} className="rounded-xl border border-line px-3 py-2" />
              <ErrorNote>{error}</ErrorNote>
              <Button type="submit" variant="secondary">{t("চ্যাট শুরু করুন")}</Button>
            </form>
          )}
        </div>
        {current ? <ChatThread key={current} conversationId={current} /> : <Empty icon="chat" title={t("বাঁ দিক থেকে একটি চ্যাট বাছুন")} />}
      </div>
    </div>
  );
}
