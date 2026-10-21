import {
  Badge,
  Button,
  Card,
  Empty,
  ErrorNote,
  Field,
  Icon,
  Loading,
  MapPicker,
  MapView,
  PageHeader,
  PhotoUpload,
  Select,
  StatusBadge,
  TextArea,
  Timeline,
  api,
  getCity,
  errorMessage,
  formatDate,
  getLang,
  localName,
  t,
  useAreas,
  useAuth,
  type MapPoint,
  type Paginated,
} from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { useSelectedArea } from "../lib/area";

type Issue = {
  id: number;
  category: string;
  title: string;
  description: string;
  photo_urls: string[];
  latitude: string;
  longitude: string;
  landmark: string;
  area_name: string;
  status: string;
  authority_name: { bn: string; en: string } | null;
  admin_note: string;
  resolved_photo_urls: string[];
  upvote_count: number;
  upvoted: boolean;
  distance_km: number | null;
  reporter_name: string;
  created_at: string;
  updates: { status: string; note: string; created_at: string }[];
};

export const ISSUE_CATEGORIES: Record<string, string> = {
  garbage: "ময়লা-আবর্জনা",
  streetlight: "নষ্ট রাস্তার বাতি",
  waterlogging: "জলাবদ্ধতা",
  road_damage: "ভাঙা রাস্তা",
  drainage: "ড্রেন বন্ধ",
  mosquito: "মশার উপদ্রব",
  water_supply: "পানি সরবরাহ",
  other: "অন্যান্য",
};
const STATUS_COLOR: Record<string, string> = { reported: "#B45309", forwarded: "#1D4ED8", in_progress: "#1D4ED8", resolved: "#17784A", rejected: "#6B7280" };

function UpvoteButton({ issue }: { issue: Issue }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [state, setState] = useState({ on: issue.upvoted, count: issue.upvote_count });
  async function toggle() {
    if (!user) return navigate("/login?next=/issues");
    const { data } = await api.post<{ upvoted: boolean; upvote_count: number }>(`/issues/${issue.id}/upvote/`);
    setState({ on: data.upvoted, count: data.upvote_count });
    qc.invalidateQueries({ queryKey: ["issues"] });
  }
  return (
    <button type="button" aria-pressed={state.on} aria-label={t("সমর্থন দিন")} onClick={toggle}
      className={`flex h-11 min-w-16 items-center justify-center gap-1 rounded-xl border px-3 font-semibold ${state.on ? "border-brand bg-brand-soft text-brand-strong" : "border-line bg-surface"}`}>
      <Icon name="up" size={18} /> {state.count}
    </button>
  );
}

function IssueCard({ issue }: { issue: Issue }) {
  return (
    <Card className="flex items-center gap-4 p-4">
      {issue.photo_urls[0] ? <img src={issue.photo_urls[0]} alt="" className="size-16 shrink-0 rounded-xl object-cover" /> : <span className="size-16 shrink-0 rounded-xl bg-subtle" />}
      <Link to={`/issues/${issue.id}`} className="flex min-w-0 flex-1 flex-col text-ink no-underline">
        <span className="font-semibold">{issue.title}</span>
        <span className="text-sm text-muted">
          {t(ISSUE_CATEGORIES[issue.category] ?? issue.category)} · {issue.area_name}
          {issue.distance_km !== null && ` · ${t("{km} কিমি", { km: issue.distance_km })}`}
        </span>
      </Link>
      <StatusBadge status={issue.status} />
      <UpvoteButton issue={issue} />
    </Card>
  );
}

export function IssuesHome({ mine = false }: { mine?: boolean }) {
  const [area, setArea] = useSelectedArea();
  const { data: areas } = useAreas();
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("reported,forwarded,in_progress");
  const [near, setNear] = useState<[number, number] | null>(null);
  const [locError, setLocError] = useState("");
  const params = { category: category || undefined, status: status || undefined, area: near || mine ? undefined : area, city: near || mine || area ? undefined : getCity() || undefined, near: near ? near.join(",") : undefined, radius_km: near ? 2 : undefined, mine: mine ? 1 : undefined, sort: "top" };
  const { data, isPending } = useQuery({ queryKey: ["issues", params], queryFn: async () => (await api.get<Paginated<Issue>>("/issues/", { params })).data });

  function nearMe() {
    setLocError("");
    navigator.geolocation?.getCurrentPosition((p) => setNear([p.coords.latitude, p.coords.longitude]), () => setLocError(t("লোকেশনের অনুমতি পাওয়া যায়নি।")));
  }

  const points: MapPoint[] = (data?.results ?? []).map((i) => ({
    id: i.id, lat: Number(i.latitude), lng: Number(i.longitude), color: STATUS_COLOR[i.status],
    label: <Link to={`/issues/${i.id}`}>{i.title} ({i.upvote_count})</Link>,
  }));

  return (
    <section className="mx-auto flex max-w-[1200px] flex-col gap-5 px-4 py-8 sm:px-6">
      <PageHeader
        title={mine ? t("আমার রিপোর্ট") : t("শহরের সমস্যা")}
        subtitle={t("ময়লা, নষ্ট বাতি, জলাবদ্ধতা — ছবি ও লোকেশন দিয়ে জানান, সমর্থন দিন, অগ্রগতি দেখুন")}
        actions={
          <div className="flex flex-wrap gap-2">
            <Link to="/transparency" className="flex h-11 items-center gap-2 rounded-xl border border-line px-4 font-semibold text-ink no-underline"><Icon name="chart" size={18} />{t("স্বচ্ছতা ড্যাশবোর্ড")}</Link>
            <Link to="/issues/new" className="flex h-11 items-center gap-2 rounded-xl bg-alert px-4 font-semibold text-ink no-underline"><Icon name="flag" size={18} />{t("সমস্যা রিপোর্ট করুন")}</Link>
          </div>
        }
      />
      {!mine && (
        <div className="grid gap-3 sm:grid-cols-[1fr_1fr_1fr_auto] sm:items-end">
          <Select label={t("এলাকা")} value={area ?? ""} onChange={(e) => { setNear(null); setArea(e.target.value ? Number(e.target.value) : undefined); }}
            options={[{ value: "", label: t("সব এলাকা") }, ...(areas ?? []).map((a) => ({ value: a.id, label: localName(a) }))]} />
          <Select label={t("ধরন")} value={category} onChange={(e) => setCategory(e.target.value)} options={[{ value: "", label: t("সব") }, ...Object.entries(ISSUE_CATEGORIES).map(([value, label]) => ({ value, label: t(label) }))]} />
          <Select label={t("অবস্থা")} value={status} onChange={(e) => setStatus(e.target.value)} options={[{ value: "reported,forwarded,in_progress", label: t("সমাধান বাকি") }, { value: "resolved", label: t("সমাধান হয়েছে") }, { value: "", label: t("সব") }]} />
          <Button variant={near ? "primary" : "ghost"} icon="pin" onClick={near ? () => setNear(null) : nearMe}>{near ? t("আমার কাছে (২ কিমি)") : t("আমার কাছে")}</Button>
        </div>
      )}
      <ErrorNote>{locError}</ErrorNote>
      <MapView points={points} center={near ?? undefined} height={340} />
      {isPending && <Loading />}
      {data?.results.length === 0 && <Empty icon="flag" title={t("এই এলাকায় কোনো রিপোর্ট নেই")} />}
      <div className="flex flex-col gap-3">{data?.results.map((i) => <IssueCard key={i.id} issue={i} />)}</div>
    </section>
  );
}

export function ReportIssue() {
  const navigate = useNavigate();
  const { data: areas } = useAreas();
  const [area] = useSelectedArea();
  const [f, setF] = useState({ category: "garbage", title: "", description: "", landmark: "", area_id: area ? String(area) : "" });
  const [photos, setPhotos] = useState<string[]>([]);
  const [point, setPoint] = useState<{ lat: number; lng: number } | null>(null);
  const [duplicate, setDuplicate] = useState<Issue | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });

  async function submit(e: FormEvent | null, force = false) {
    e?.preventDefault();
    const a = areas?.find((x) => x.id === Number(f.area_id));
    if (!a) return setError(t("এলাকা বাছুন।"));
    if (!point) return setError(t("ম্যাপে চাপ দিয়ে জায়গা দেখান"));
    if (!photos.length) return setError(t("অন্তত একটি ছবি দিন।"));
    setBusy(true);
    setError("");
    try {
      const { data } = await api.post<Issue>("/issues/", {
        ...f, title: f.title || t(ISSUE_CATEGORIES[f.category]), area_id: a.id, area_name: a.name_bn,
        latitude: point.lat.toFixed(6), longitude: point.lng.toFixed(6), photo_urls: photos, force,
      });
      navigate(`/issues/${data.id}`);
    } catch (err) {
      if (isAxiosError(err) && err.response?.status === 409) setDuplicate(err.response.data.duplicate);
      else setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mx-auto flex max-w-[760px] flex-col gap-5 px-4 py-8 sm:px-6">
      <PageHeader title={t("সমস্যা রিপোর্ট করুন")} subtitle={t("আমরা যাচাই করে সংশ্লিষ্ট কর্তৃপক্ষের কাছে পাঠাব; অগ্রগতি নোটিফিকেশনে জানাব।")} />
      <form onSubmit={submit} className="flex flex-col gap-4 rounded-[20px] border border-line bg-surface p-5">
        <fieldset className="m-0 flex flex-wrap gap-2 border-0 p-0">
          <legend className="mb-2 font-semibold">{t("কী সমস্যা?")}</legend>
          {Object.entries(ISSUE_CATEGORIES).map(([value, label]) => (
            <button key={value} type="button" aria-pressed={f.category === value} onClick={() => setF({ ...f, category: value })}
              className={`h-10 rounded-full border px-3.5 text-sm ${f.category === value ? "border-brand bg-brand text-white" : "border-line"}`}>{t(label)}</button>
          ))}
        </fieldset>
        <PhotoUpload label={t("ছবি (অন্তত ১টি)")} value={photos} onChange={setPhotos} purpose="issue_photo" max={5} />
        <Field label={t("শিরোনাম (ঐচ্ছিক)")} value={f.title} onChange={set("title")} placeholder={t(ISSUE_CATEGORIES[f.category])} />
        <TextArea label={t("বিস্তারিত (ঐচ্ছিক)")} value={f.description} onChange={set("description")} />
        <div className="grid gap-3 sm:grid-cols-2">
          <Select label={t("এলাকা")} value={f.area_id} onChange={set("area_id")} options={[{ value: "", label: t("এলাকা বাছুন") }, ...(areas ?? []).map((a) => ({ value: a.id, label: localName(a) }))]} />
          <Field label={t("কাছের চিহ্ন (ঐচ্ছিক)")} value={f.landmark} onChange={set("landmark")} placeholder={t("যেমন: মসজিদের পাশে")} />
        </div>
        <span className="font-semibold">{t("জায়গা")}</span>
        <MapPicker value={point} onChange={setPoint} />
        <ErrorNote>{error}</ErrorNote>
        {duplicate ? (
          <Card className="flex flex-col gap-3 border-alert bg-alert-soft">
            <span className="font-semibold">{t("কাছেই একই সমস্যা আগে রিপোর্ট হয়েছে। নতুন রিপোর্টের বদলে সমর্থন দিন?")}</span>
            <IssueCard issue={duplicate} />
            <Button variant="ghost" onClick={() => submit(null, true)}>{t("না, এটা আলাদা — তবুও রিপোর্ট করুন")}</Button>
          </Card>
        ) : (
          <Button type="submit" loading={busy} className="h-12 text-base" variant="alert">{t("রিপোর্ট জমা দিন")}</Button>
        )}
      </form>
    </section>
  );
}

export function IssueDetail() {
  const { id } = useParams();
  const { data: issue, isPending } = useQuery({ queryKey: ["issues", id], queryFn: async () => (await api.get<Issue>(`/issues/${id}/`)).data });
  if (isPending || !issue) return <Loading />;
  const point: MapPoint = { id: issue.id, lat: Number(issue.latitude), lng: Number(issue.longitude), color: STATUS_COLOR[issue.status] };
  return (
    <section className="mx-auto grid max-w-[1100px] gap-6 px-4 py-8 sm:px-6 lg:grid-cols-[1.5fr_1fr]">
      <div className="flex flex-col gap-5">
        <PageHeader title={issue.title} subtitle={`${t(ISSUE_CATEGORIES[issue.category] ?? issue.category)} · ${issue.area_name}${issue.landmark ? ` · ${issue.landmark}` : ""} · ${formatDate(issue.created_at)}`}
          actions={<><StatusBadge status={issue.status} /><UpvoteButton issue={issue} /></>} />
        {issue.description && <p className="m-0 leading-relaxed whitespace-pre-line">{issue.description}</p>}
        <div className="flex flex-wrap gap-2">{issue.photo_urls.map((u) => <img key={u} src={u} alt="" className="h-40 rounded-xl object-cover" />)}</div>
        {issue.authority_name && (
          <Card className="flex items-center gap-3">
            <Icon name="building" className="text-brand" />
            <span>{t("পাঠানো হয়েছে:")} <strong>{getLang() === "en" ? issue.authority_name.en : issue.authority_name.bn}</strong></span>
          </Card>
        )}
        {issue.resolved_photo_urls.length > 0 && (
          <Card className="flex flex-col gap-2">
            <Badge tone="ok">{t("সমাধানের পর")}</Badge>
            <div className="flex flex-wrap gap-2">{issue.resolved_photo_urls.map((u) => <img key={u} src={u} alt="" className="h-40 rounded-xl object-cover" />)}</div>
          </Card>
        )}
        {issue.admin_note && <p className="m-0 rounded-xl bg-subtle p-3">{issue.admin_note}</p>}
        <MapView points={[point]} height={260} />
      </div>
      <Card className="flex h-fit flex-col gap-4">
        <h2 className="m-0 text-lg font-bold">{t("অগ্রগতি")}</h2>
        <Timeline events={[...issue.updates].reverse()} />
      </Card>
    </section>
  );
}
