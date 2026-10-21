import { Badge, Button, Card, ErrorNote, Field, MapView, Modal, PageHeader, PhotoUpload, Select, Stat, StatusBadge, Tabs, TextArea, Timeline, api, errorMessage, formatDate, formatDateTime, getLang, t, type MapPoint } from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { DataTable, FilterChips, usePaged } from "../components";

type Authority = { id: number; name_bn: string; name_en: string; contact_phone: string; email: string; categories: string[]; area_ids: number[]; is_active: boolean; feed_token: string };

/** The admin export needs the login token, so it is fetched and handed to the browser as a file. */
async function downloadCsv() {
  const { data } = await api.get<Blob>("/admin/issues/export/", { responseType: "blob" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(data);
  a.download = "shohorsathi-issues.csv";
  a.click();
  URL.revokeObjectURL(a.href);
}

/** The authority's own link: its issues as CSV, which it can also use to mark them in progress or resolved. */
function FeedLink({ authority }: { authority: Authority }) {
  const qc = useQueryClient();
  const [copied, setCopied] = useState(false);
  const url = authority.feed_token ? `${window.location.origin}/api/issues/feed/${authority.feed_token}/` : "";
  async function rotate() {
    if (authority.feed_token && !confirm(t("নতুন লিংক দিলে পুরনো লিংক আর কাজ করবে না। চালিয়ে যাবেন?"))) return;
    await api.post(`/admin/authorities/${authority.id}/rotate-feed/`);
    qc.invalidateQueries({ queryKey: ["authorities"] });
  }
  return (
    <div className="flex flex-wrap items-center gap-2">
      {url && (
        <Button variant="ghost" onClick={async () => { await navigator.clipboard?.writeText(url); setCopied(true); }}>
          {copied ? t("কপি হয়েছে") : t("লিংক কপি")}
        </Button>
      )}
      <Button variant="ghost" icon="refresh" onClick={rotate}>{url ? t("নতুন লিংক") : t("ফিড লিংক তৈরি")}</Button>
    </div>
  );
}
type Issue = {
  id: number; category: string; title: string; description: string; photo_urls: string[]; latitude: string; longitude: string; landmark: string;
  area_name: string; status: string; authority_name: { bn: string; en: string } | null; admin_note: string; upvote_count: number; reporter_name: string;
  created_at: string; updates: { status: string; note: string; created_at: string }[];
};
type Post = { id: number; author_name: string; area_name: string; kind: string; body: string; like_count: number; comment_count: number; created_at: string };

const CATEGORIES: Record<string, string> = { garbage: "ময়লা-আবর্জনা", streetlight: "নষ্ট রাস্তার বাতি", waterlogging: "জলাবদ্ধতা", road_damage: "ভাঙা রাস্তা", drainage: "ড্রেন বন্ধ", mosquito: "মশার উপদ্রব", water_supply: "পানি সরবরাহ", other: "অন্যান্য" };
const NEXT: Record<string, string[]> = { reported: ["forwarded", "in_progress", "resolved", "rejected"], forwarded: ["in_progress", "resolved", "rejected"], in_progress: ["resolved"], rejected: ["reported"], resolved: [] };
const COLOR: Record<string, string> = { reported: "#B45309", forwarded: "#1D4ED8", in_progress: "#1D4ED8", resolved: "#17784A", rejected: "#6B7280" };

function IssueModal({ issue, authorities, onClose }: { issue: Issue; authorities: Authority[]; onClose: () => void }) {
  const qc = useQueryClient();
  const [status, setStatus] = useState(NEXT[issue.status]?.[0] ?? "");
  const [authority, setAuthority] = useState("");
  const [note, setNote] = useState("");
  const [photos, setPhotos] = useState<string[]>([]);
  const [error, setError] = useState("");
  const options = authorities.filter((a) => a.is_active && (!a.categories.length || a.categories.includes(issue.category)));

  async function save() {
    setError("");
    try {
      await api.post(`/admin/issues/${issue.id}/status/`, { status, note, authority: authority || undefined, photos });
      qc.invalidateQueries({ queryKey: ["admin-issues"] });
      onClose();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <Modal title={issue.title} open onClose={onClose}>
      <div className="flex flex-wrap items-center gap-2"><StatusBadge status={issue.status} /><Badge>{t(CATEGORIES[issue.category] ?? issue.category)}</Badge><Badge tone="warn">▲ {issue.upvote_count}</Badge></div>
      <span className="text-[15px] text-muted">{issue.area_name}{issue.landmark && ` · ${issue.landmark}`} · {issue.reporter_name} · {formatDate(issue.created_at)}</span>
      {issue.description && <p className="m-0 rounded-xl bg-subtle p-3">{issue.description}</p>}
      <div className="flex flex-wrap gap-2">{issue.photo_urls.map((u) => <a key={u} href={u} target="_blank" rel="noreferrer"><img src={u} alt="" className="h-24 rounded-xl object-cover" /></a>)}</div>
      <MapView points={[{ id: issue.id, lat: Number(issue.latitude), lng: Number(issue.longitude), color: COLOR[issue.status] }]} height={200} />
      {NEXT[issue.status]?.length > 0 && (
        <Card className="flex flex-col gap-3 bg-brand-tint">
          <Select label={t("নতুন অবস্থা")} value={status} onChange={(e) => setStatus(e.target.value)} options={NEXT[issue.status].map((s) => ({ value: s, label: t({ forwarded: "কর্তৃপক্ষকে পাঠানো", in_progress: "কাজ চলছে", resolved: "সমাধান হয়েছে", rejected: "বাতিল", reported: "আবার খুলুন" }[s] ?? s) }))} />
          {status === "forwarded" && (
            <Select label={t("কর্তৃপক্ষ")} value={authority} onChange={(e) => setAuthority(e.target.value)} options={[{ value: "", label: t("বাছুন") }, ...options.map((a) => ({ value: a.id, label: getLang() === "en" ? a.name_en : a.name_bn }))]} />
          )}
          <TextArea label={status === "rejected" ? t("কারণ (রিপোর্টকারী দেখবেন)") : t("নোট (ঐচ্ছিক)")} value={note} onChange={(e) => setNote(e.target.value)} />
          {status === "resolved" && <PhotoUpload label={t("সমাধানের ছবি")} value={photos} onChange={setPhotos} purpose="issue_photo" max={4} />}
          <ErrorNote>{error}</ErrorNote>
          <Button onClick={save}>{t("আপডেট করুন")}</Button>
        </Card>
      )}
      <Timeline events={[...issue.updates].reverse()} />
    </Modal>
  );
}

function IssueList({ authorities }: { authorities: Authority[] }) {
  const [status, setStatus] = useState("reported,forwarded,in_progress");
  const [category, setCategory] = useState("");
  const { data, isPending } = usePaged<Issue>(["admin-issues"], "/admin/issues/", { status: status || undefined, category: category || undefined });
  const [open, setOpen] = useState<Issue | null>(null);
  const points: MapPoint[] = (data?.results ?? []).map((i) => ({ id: i.id, lat: Number(i.latitude), lng: Number(i.longitude), color: COLOR[i.status], radius: 6 + Math.min(i.upvote_count, 10), label: `${i.title} (▲${i.upvote_count})` }));
  return (
    <>
      <div className="flex flex-wrap items-center gap-3">
        <FilterChips value={status} onChange={setStatus} options={[{ value: "reported,forwarded,in_progress", label: t("সমাধান বাকি") }, { value: "reported", label: t("নতুন") }, { value: "resolved", label: t("সমাধান হয়েছে") }, { value: "", label: t("সব") }]} />
        <select aria-label={t("ধরন")} value={category} onChange={(e) => setCategory(e.target.value)} className="h-10 rounded-xl border border-line px-3">
          <option value="">{t("সব ধরন")}</option>
          {Object.entries(CATEGORIES).map(([v, l]) => <option key={v} value={v}>{t(l)}</option>)}
        </select>
      </div>
      <MapView points={points} height={320} zoom={12} />
      <DataTable
        loading={isPending}
        rows={data?.results}
        onRowClick={setOpen}
        columns={[
          { label: t("সমস্যা"), render: (i) => <span className="font-semibold">{i.title}</span> },
          { label: t("ধরন"), render: (i) => t(CATEGORIES[i.category] ?? i.category) },
          { label: t("এলাকা"), render: (i) => i.area_name },
          { label: t("সমর্থন"), render: (i) => `▲ ${i.upvote_count}` },
          { label: t("কর্তৃপক্ষ"), render: (i) => (i.authority_name ? (getLang() === "en" ? i.authority_name.en : i.authority_name.bn) : "—") },
          { label: t("তারিখ"), render: (i) => formatDate(i.created_at) },
          { label: t("অবস্থা"), render: (i) => <StatusBadge status={i.status} /> },
        ]}
      />
      {open && <IssueModal issue={open} authorities={authorities} onClose={() => setOpen(null)} />}
    </>
  );
}

function Authorities({ authorities }: { authorities: Authority[] }) {
  const qc = useQueryClient();
  const [f, setF] = useState({ name_bn: "", name_en: "", contact_phone: "", email: "", categories: [] as string[] });
  const [error, setError] = useState("");
  async function add(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.post("/admin/authorities/", f);
      setF({ name_bn: "", name_en: "", contact_phone: "", email: "", categories: [] });
      qc.invalidateQueries({ queryKey: ["authorities"] });
    } catch (err) {
      setError(errorMessage(err));
    }
  }
  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={add} className="grid items-end gap-3 rounded-[20px] border border-line bg-surface p-4 sm:grid-cols-2">
        <Field label={t("নাম (বাংলা)")} required value={f.name_bn} onChange={(e) => setF({ ...f, name_bn: e.target.value })} placeholder="ঢাকা উত্তর সিটি কর্পোরেশন, ওয়ার্ড ৫" />
        <Field label={t("নাম (English)")} required value={f.name_en} onChange={(e) => setF({ ...f, name_en: e.target.value })} placeholder="DNCC Ward 5" />
        <Field label={t("ফোন")} value={f.contact_phone} onChange={(e) => setF({ ...f, contact_phone: e.target.value })} />
        <Field label={t("ইমেইল")} type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />
        <fieldset className="m-0 flex flex-wrap gap-2 border-0 p-0 sm:col-span-2">
          <legend className="mb-2 text-[15px] font-semibold">{t("কোন ধরনের সমস্যা দেখে")}</legend>
          {Object.entries(CATEGORIES).map(([v, l]) => {
            const on = f.categories.includes(v);
            return <button key={v} type="button" aria-pressed={on} onClick={() => setF({ ...f, categories: on ? f.categories.filter((x) => x !== v) : [...f.categories, v] })} className={`h-9 rounded-full border px-3 text-sm ${on ? "border-brand bg-brand text-white" : "border-line"}`}>{t(l)}</button>;
          })}
        </fieldset>
        <ErrorNote>{error}</ErrorNote>
        <Button type="submit" icon="plus" className="sm:justify-self-start">{t("যোগ করুন")}</Button>
      </form>
      <DataTable rows={authorities} columns={[
        { label: t("নাম"), render: (a) => <><span className="font-semibold">{a.name_bn}</span><span className="block text-[13px] text-muted">{a.name_en}</span></> },
        { label: t("যোগাযোগ"), render: (a) => [a.contact_phone, a.email].filter(Boolean).join(" · ") || "—" },
        { label: t("ধরন"), render: (a) => a.categories.map((c) => t(CATEGORIES[c] ?? c)).join(", ") || t("সব") },
        { label: t("কর্তৃপক্ষের ফিড (CSV)"), render: (a) => <FeedLink authority={a} /> },
      ]} />
    </div>
  );
}

function Moderation() {
  const qc = useQueryClient();
  const { data, isPending } = usePaged<Post>(["admin-posts"], "/community/posts/", {});
  async function hide(p: Post) {
    if (!confirm(t("পোস্টটি লুকাবেন?"))) return;
    await api.post(`/admin/community/posts/${p.id}/hide/`);
    qc.invalidateQueries({ queryKey: ["admin-posts"] });
  }
  return (
    <DataTable loading={isPending} rows={data?.results} columns={[
      { label: t("লেখক"), render: (p) => <>{p.author_name}<span className="block text-[13px] text-muted">{p.area_name}</span></> },
      { label: t("পোস্ট"), render: (p) => <span className="line-clamp-2">{p.body}</span>, className: "max-w-md" },
      { label: t("লাইক / মন্তব্য"), render: (p) => `${p.like_count} / ${p.comment_count}` },
      { label: t("সময়"), render: (p) => formatDateTime(p.created_at) },
      { label: "", render: (p) => <Button variant="danger" onClick={() => hide(p)}>{t("লুকান")}</Button> },
    ]} />
  );
}

export default function Issues() {
  const [tab, setTab] = useState<"issues" | "authorities" | "community">("issues");
  const { data: authorities } = useQuery({ queryKey: ["authorities"], queryFn: async () => (await api.get<Authority[]>("/admin/authorities/")).data });
  const { data: stats } = useQuery({ queryKey: ["issue-stats"], queryFn: async () => (await api.get<{ by_status: Record<string, number> }>("/admin/issues/stats/")).data });
  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title={t("শহরের সমস্যা")}
        subtitle={t("যাচাই করুন, সংশ্লিষ্ট কর্তৃপক্ষকে পাঠান, সমাধান হলে ছবি দিন")}
        actions={<Button variant="ghost" icon="list" onClick={downloadCsv}>{t("CSV এক্সপোর্ট")}</Button>}
      />
      <div className="grid grid-cols-[repeat(auto-fit,minmax(160px,1fr))] gap-3">
        <Stat label={t("নতুন রিপোর্ট")} value={stats?.by_status.reported ?? 0} icon="flag" />
        <Stat label={t("পাঠানো হয়েছে")} value={(stats?.by_status.forwarded ?? 0) + (stats?.by_status.in_progress ?? 0)} icon="send" />
        <Stat label={t("সমাধান হয়েছে")} value={stats?.by_status.resolved ?? 0} icon="check" />
      </div>
      <Tabs value={tab} onChange={setTab} tabs={[{ value: "issues", label: t("রিপোর্ট") }, { value: "authorities", label: t("কর্তৃপক্ষ") }, { value: "community", label: t("কমিউনিটি মডারেশন") }]} />
      {tab === "issues" && <IssueList authorities={authorities ?? []} />}
      {tab === "authorities" && <Authorities authorities={authorities ?? []} />}
      {tab === "community" && <Moderation />}
    </div>
  );
}
