import { Badge, Button, Card, Empty, ErrorNote, Icon, Loading, PageHeader, PhotoUpload, Select, TextArea, api, errorMessage, formatDateTime, getCity, localName, t, useAreas, useAuth, type Paginated } from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { useSelectedArea } from "../lib/area";

type Post = { id: number; author_name: string; area_name: string; kind: string; body: string; photo_urls: string[]; provider_name: string; like_count: number; comment_count: number; liked: boolean; mine: boolean; created_at: string };
type Comment = { id: number; author_name: string; body: string; created_at: string };

const KINDS: Record<string, string> = { tip: "টিপস", recommendation: "প্রোভাইডার সুপারিশ", question: "প্রশ্ন", alert: "এলাকার সতর্কতা" };

function Comments({ post }: { post: Post }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["comments", post.id], queryFn: async () => (await api.get<Comment[]>(`/community/posts/${post.id}/comments/`)).data });
  const [body, setBody] = useState("");
  async function add(e: FormEvent) {
    e.preventDefault();
    await api.post(`/community/posts/${post.id}/comments/`, { body });
    setBody("");
    qc.invalidateQueries({ queryKey: ["comments", post.id] });
    qc.invalidateQueries({ queryKey: ["posts"] });
  }
  return (
    <div className="flex flex-col gap-2 border-t border-line pt-3">
      {data?.map((c) => (
        <div key={c.id} className="text-[15px]"><strong>{c.author_name}</strong> {c.body} <span className="text-[12px] text-muted">{formatDateTime(c.created_at)}</span></div>
      ))}
      {user && (
        <form onSubmit={add} className="flex gap-2">
          <label htmlFor={`c${post.id}`} className="sr-only">{t("মন্তব্য")}</label>
          <input id={`c${post.id}`} value={body} onChange={(e) => setBody(e.target.value)} placeholder={t("মন্তব্য লিখুন…")} className="h-10 min-w-0 flex-1 rounded-xl border border-line px-3" required />
          <Button type="submit" variant="secondary">{t("পাঠান")}</Button>
        </form>
      )}
    </div>
  );
}

function PostCard({ post }: { post: Post }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [like, setLike] = useState({ on: post.liked, n: post.like_count });
  async function toggle() {
    const { data } = await api.post<{ liked: boolean; like_count: number }>(`/community/posts/${post.id}/like/`);
    setLike({ on: data.liked, n: data.like_count });
  }
  async function remove() {
    if (!confirm(t("পোস্টটি মুছবেন?"))) return;
    await api.delete(`/community/posts/${post.id}/`);
    qc.invalidateQueries({ queryKey: ["posts"] });
  }
  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <span className="flex size-9 items-center justify-center rounded-full bg-brand-soft text-brand-strong"><Icon name="user" size={18} /></span>
        <span className="flex flex-1 flex-col"><span className="font-semibold">{post.author_name}</span><span className="text-[12px] text-muted">{post.area_name} · {formatDateTime(post.created_at)}</span></span>
        <Badge tone={post.kind === "alert" ? "warn" : "ok"}>{t(KINDS[post.kind] ?? post.kind)}</Badge>
      </div>
      <p className="m-0 leading-relaxed whitespace-pre-line">{post.body}</p>
      {post.provider_name && <span className="text-sm">{t("সুপারিশ:")} <strong>{post.provider_name}</strong></span>}
      {post.photo_urls.length > 0 && <div className="flex flex-wrap gap-2">{post.photo_urls.map((u) => <img key={u} src={u} alt="" className="h-32 rounded-xl object-cover" />)}</div>}
      <div className="flex items-center gap-2">
        <button type="button" disabled={!user} aria-pressed={like.on} onClick={toggle} className={`flex h-10 items-center gap-1 rounded-xl border px-3 ${like.on ? "border-brand text-brand-strong" : "border-line"}`}>
          <Icon name="heart" size={16} /> {like.n}
        </button>
        <button type="button" onClick={() => setOpen(!open)} className="flex h-10 items-center gap-1 rounded-xl border border-line px-3">
          <Icon name="chat" size={16} /> {post.comment_count}
        </button>
        {post.mine && <button type="button" onClick={remove} aria-label={t("পোস্ট মুছুন")} className="ml-auto flex size-10 items-center justify-center rounded-xl text-bad"><Icon name="trash" size={16} /></button>}
      </div>
      {open && <Comments post={post} />}
    </Card>
  );
}

export default function Community() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [area, setArea] = useSelectedArea();
  const { data: areas } = useAreas();
  const [kind, setKind] = useState("");
  const { data, isPending } = useQuery({
    queryKey: ["posts", area, kind],
    queryFn: async () => (await api.get<Paginated<Post>>("/community/posts/", { params: { area, city: area ? undefined : getCity() || undefined, kind: kind || undefined } })).data,
  });
  const [f, setF] = useState({ kind: "tip", body: "", provider_name: "" });
  const [photos, setPhotos] = useState<string[]>([]);
  const [error, setError] = useState("");

  async function post(e: FormEvent) {
    e.preventDefault();
    const a = areas?.find((x) => x.id === area);
    if (!a) return setError(t("এলাকা বাছুন।"));
    setError("");
    try {
      await api.post("/community/posts/", { ...f, area_id: a.id, area_name: a.name_bn, photo_urls: photos });
      setF({ ...f, body: "", provider_name: "" });
      setPhotos([]);
      qc.invalidateQueries({ queryKey: ["posts"] });
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <section className="mx-auto flex max-w-[760px] flex-col gap-5 px-4 py-8 sm:px-6">
      <PageHeader title={t("কমিউনিটি")} subtitle={t("প্রতিবেশীদের টিপস, প্রোভাইডার সুপারিশ ও এলাকার খবর")} />
      <div className="grid gap-3 sm:grid-cols-2">
        <Select label={t("এলাকা")} value={area ?? ""} onChange={(e) => setArea(e.target.value ? Number(e.target.value) : undefined)} options={[{ value: "", label: t("সব এলাকা") }, ...(areas ?? []).map((a) => ({ value: a.id, label: localName(a) }))]} />
        <Select label={t("ধরন")} value={kind} onChange={(e) => setKind(e.target.value)} options={[{ value: "", label: t("সব") }, ...Object.entries(KINDS).map(([value, label]) => ({ value, label: t(label) }))]} />
      </div>
      {user ? (
        <form onSubmit={post} className="flex flex-col gap-3 rounded-[20px] border border-line bg-surface p-4">
          <div className="flex flex-wrap gap-2">
            {Object.entries(KINDS).map(([value, label]) => (
              <button key={value} type="button" aria-pressed={f.kind === value} onClick={() => setF({ ...f, kind: value })} className={`h-9 rounded-full border px-3 text-sm ${f.kind === value ? "border-brand bg-brand text-white" : "border-line"}`}>{t(label)}</button>
            ))}
          </div>
          <TextArea label={t("কী জানাতে চান?")} value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })} required />
          {f.kind === "recommendation" && (
            <input aria-label={t("প্রোভাইডারের নাম")} placeholder={t("প্রোভাইডারের নাম")} value={f.provider_name} onChange={(e) => setF({ ...f, provider_name: e.target.value })} className="h-11 rounded-xl border border-line px-3" />
          )}
          <PhotoUpload label={t("ছবি (ঐচ্ছিক)")} value={photos} onChange={setPhotos} purpose="other" max={3} />
          <ErrorNote>{error}</ErrorNote>
          <Button type="submit" className="self-start">{t("পোস্ট করুন")}</Button>
        </form>
      ) : (
        <p className="m-0 text-muted"><Link to="/login?next=/community">{t("লগইন")}</Link> {t("করে পোস্ট করুন")}</p>
      )}
      {isPending && <Loading />}
      {data?.results.length === 0 && <Empty icon="chat" title={t("এখনো কোনো পোস্ট নেই")} />}
      {data?.results.map((p) => <PostCard key={p.id} post={p} />)}
    </section>
  );
}
