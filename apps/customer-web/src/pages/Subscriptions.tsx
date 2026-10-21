import {
  Badge,
  Button,
  Card,
  Empty,
  ErrorNote,
  Field,
  Icon,
  Loading,
  Modal,
  PageHeader,
  PhotoUpload,
  Select,
  StatusBadge,
  SuccessNote,
  Tabs,
  TextArea,
  api,
  errorMessage,
  formatDate,
  formatTaka,
  getLang,
  localName,
  payOnline,
  slotLabel,
  slotOptions,
  t,
  todayISO,
  useAreas,
  useAuth,
  type Paginated,
} from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { useAddresses } from "../api/orders";

type PlanPrice = { duration_days: number; home_size: number; price: string };
type Plan = {
  id: number;
  category: string;
  slug: string;
  tier: string;
  name_bn: string;
  name_en: string;
  description_bn: string;
  description_en: string;
  includes: { bn: string; en: string }[];
  frequency: string;
  meal_types: string[];
  sizes_apply: boolean;
  prices: PlanPrice[];
};
type Visit = { id: number; date: string; slot: string; kind: string; meal_type: string; value: string; status: string; provider_name: string; rating: number | null; completed_at: string | null; can_change: boolean; cutoff: string };
type Subscription = {
  id: number;
  plan: Plan;
  duration_days: number;
  home_size: number;
  slot: string;
  start_date: string;
  end_date: string;
  area_name: string;
  address_line: string;
  diet: string;
  members: { name: string; phone: string }[];
  prepaid_months: number;
  student_discount: boolean;
  price: string;
  amount_due: string;
  credit: string;
  credit_applied: string;
  payment_method: string;
  paid: boolean;
  status: string;
  auto_renew: boolean;
  next_plan: string | null;
  preferred_provider_name: string;
  paused_until: string | null;
  upcoming: Visit[];
  stats: Record<string, number>;
};
type Quote = { total: string; months: number; student_discount: boolean; per_member: string | null; lines: { label: string; amount: string }[] };

const CATEGORY_TABS = [
  { value: "cleaning", label: "হোম ক্লিনিং" },
  { value: "meal", label: "মিল (স্টুডেন্ট ও ব্যাচেলর)" },
  { value: "laundry,water,grocery,plant,pest,helper,tiffin", label: "পরিবারের জন্য" },
];
const FREQUENCY: Record<string, string> = {
  daily: "প্রতিদিন",
  alternate: "একদিন পরপর",
  every_3_days: "৩ দিন পরপর",
  weekly: "সপ্তাহে ১ বার",
  biweekly: "মাসে ২ বার",
  monthly: "মাসে ১ বার",
};
const MEALS: Record<string, string> = { breakfast: "সকালের নাস্তা", lunch: "দুপুরের খাবার", dinner: "রাতের খাবার" };
const KINDS: Record<string, string> = { visit: "ভিজিট", deep_clean: "ডিপ ক্লিন", reclean: "ফ্রি রি-ক্লিন", meal: "মিল" };
const DAYS = ["সোম", "মঙ্গল", "বুধ", "বৃহঃ", "শুক্র", "শনি", "রবি"];

const en = () => getLang() === "en";
const planName = (p: Plan) => localName(p);
const fromPrice = (p: Plan) => p.prices.reduce((min, x) => (x.duration_days === 30 && (min === null || Number(x.price) < min) ? Number(x.price) : min), null as number | null);

export function SubscriptionPlans() {
  const [params, setParams] = useSearchParams();
  const category = params.get("category") ?? "cleaning";
  const { data: plans, isPending } = useQuery({
    queryKey: ["plans", category],
    queryFn: async () => (await api.get<Plan[]>("/subscription-plans/", { params: { category } })).data,
  });

  return (
    <section className="mx-auto flex max-w-[1200px] flex-col gap-6 px-4 py-8 sm:px-6">
      <PageHeader title={t("সাবস্ক্রিপশন")} subtitle={t("৭ দিন (ট্রায়াল), ১৫ দিন বা ৩০ দিনের প্ল্যান। যেকোনো সময় বিরতি, বাদ বা বাতিল।")} />
      <Tabs value={category} onChange={(c) => setParams({ category: c })} tabs={CATEGORY_TABS.map((c) => ({ value: c.value, label: t(c.label) }))} />
      {isPending && <Loading />}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
        {plans?.map((p) => (
          <Card key={p.id} className={`flex flex-col gap-3 ${p.tier === "standard" && category === "cleaning" ? "border-2 border-brand bg-brand-tint" : ""}`}>
            <div className="flex items-center justify-between gap-2">
              <h2 className="m-0 text-xl font-bold">{planName(p)}</h2>
              {p.tier === "standard" && category === "cleaning" && <Badge tone="ok">{t("সবচেয়ে জনপ্রিয়")}</Badge>}
            </div>
            <span className="text-[15px] text-muted">
              {p.meal_types.length ? p.meal_types.map((m) => t(MEALS[m] ?? m)).join(" + ") : t(FREQUENCY[p.frequency] ?? p.frequency)}
            </span>
            {fromPrice(p) !== null && (
              <span className="text-2xl font-bold">
                {formatTaka(fromPrice(p)!)} <span className="text-sm font-normal text-muted">{t("/ ৩০ দিন থেকে")}</span>
              </span>
            )}
            <ul className="m-0 flex flex-col gap-1 pl-5 text-[15px]">
              {p.includes.map((i) => <li key={i.en}>{en() ? i.en : i.bn}</li>)}
            </ul>
            <Link to={`/subscriptions/new/${p.slug}`} className="mt-auto flex h-12 items-center justify-center rounded-xl bg-brand font-semibold text-white no-underline">
              {t("বেছে নিন")}
            </Link>
          </Card>
        ))}
      </div>
      <Card className="grid gap-3 sm:grid-cols-3">
        {[
          ["user", "একই ক্লিনার প্রতিবার", "যিনি প্রথমবার আসবেন, তিনিই আপনার বাসার নিয়মিত ক্লিনার"],
          ["camera", "আগে-পরের ছবি ও চেকলিস্ট", "প্রতিটি ভিজিটের পর রিপোর্ট"],
          ["refresh", "৪৮ ঘণ্টায় ফ্রি রি-ক্লিন", "পছন্দ না হলে বিনা খরচে আবার"],
        ].map(([icon, title, body]) => (
          <div key={title} className="flex gap-3">
            <Icon name={icon as "user"} className="shrink-0 text-brand" />
            <div className="flex flex-col"><span className="font-semibold">{t(title)}</span><span className="text-sm text-muted">{t(body)}</span></div>
          </div>
        ))}
      </Card>
    </section>
  );
}

function StudentBox() {
  const qc = useQueryClient();
  const { data: row } = useQuery({
    queryKey: ["student"],
    queryFn: async () => (await api.get<{ status: string; institution: string } | null>("/subscriptions/student-verification/")).data,
  });
  const [institution, setInstitution] = useState("");
  const [card, setCard] = useState<string[]>([]);
  const [error, setError] = useState("");

  async function submit() {
    setError("");
    try {
      await api.post("/subscriptions/student-verification/", { institution, id_card_url: card[0] });
      qc.invalidateQueries({ queryKey: ["student"] });
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  if (row?.status === "approved") return <SuccessNote>{t("স্টুডেন্ট যাচাই হয়েছে: অতিরিক্ত ছাড় যোগ হবে।")}</SuccessNote>;
  if (row?.status === "pending") return <p className="m-0 text-sm text-muted">{t("স্টুডেন্ট আইডি যাচাই চলছে।")}</p>;
  return (
    <details className="rounded-xl border border-line p-3">
      <summary className="cursor-pointer font-semibold">{t("স্টুডেন্ট? আইডি দিয়ে বাড়তি ছাড় নিন")}</summary>
      <div className="mt-3 flex flex-col gap-3">
        <Field label={t("প্রতিষ্ঠান")} value={institution} onChange={(e) => setInstitution(e.target.value)} />
        <PhotoUpload label={t("স্টুডেন্ট আইডি কার্ড")} value={card} onChange={setCard} purpose="other" max={1} visibility="private" />
        <ErrorNote>{error}</ErrorNote>
        <Button variant="secondary" disabled={!institution || !card.length} onClick={submit}>{t("যাচাইয়ের জন্য পাঠান")}</Button>
      </div>
    </details>
  );
}

export function Subscribe() {
  const { slug } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const { data: plan } = useQuery({ queryKey: ["plan", slug], queryFn: async () => (await api.get<Plan>(`/subscription-plans/${slug}/`)).data });
  const { data: addons } = useQuery({
    queryKey: ["addons", plan?.category],
    queryFn: async () => (await api.get<{ slug: string; name_bn: string; name_en: string; price: string }[]>("/subscription-addons/", { params: { category: plan!.category } })).data,
    enabled: !!plan,
  });
  const { data: addresses } = useAddresses(!!user);
  const { data: areas } = useAreas();
  const tomorrow = todayISO(1);
  const [f, setF] = useState({ duration_days: 30, home_size: 1, prepaid_months: 1, start_date: tomorrow, preferred_weekday: 5, slot: "09-11", diet: "bangla", payment_method: "cod", auto_renew: true });
  const [picked, setPicked] = useState<string[]>([]);
  const [members, setMembers] = useState<{ name: string; phone: string }[]>([]);
  const [addressId, setAddressId] = useState<number | "new">("new");
  const [newArea, setNewArea] = useState("");
  const [newLine, setNewLine] = useState("");
  const [quote, setQuote] = useState<Quote | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const isMeal = plan && ["meal", "tiffin"].includes(plan.category);

  useEffect(() => {
    const def = addresses?.find((a) => a.is_default) ?? addresses?.[0];
    if (def) setAddressId(def.id);
  }, [addresses]);

  useEffect(() => {
    if (!plan) return;
    api
      .post<Quote>("/subscriptions/quote/", { plan: plan.slug, duration_days: f.duration_days, home_size: plan.sizes_apply ? f.home_size : 0, prepaid_months: f.prepaid_months, addons: picked, members })
      .then((r) => { setQuote(r.data); setError(""); })
      .catch((e) => { setQuote(null); setError(errorMessage(e)); });
  }, [plan, f.duration_days, f.home_size, f.prepaid_months, picked, members]);

  if (!plan) return <Loading />;
  const set = (k: keyof typeof f, v: string | number | boolean) => setF({ ...f, [k]: v });

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!user) return navigate(`/login?next=/subscriptions/new/${slug}`);
    let address: { area_id: number; area_name: string; address_line: string; latitude?: string | null; longitude?: string | null };
    if (addressId === "new") {
      const area = areas?.find((a) => a.id === Number(newArea));
      if (!area) return setError(t("এলাকা বাছুন।"));
      address = { area_id: area.id, area_name: area.name_bn, address_line: newLine };
    } else {
      const a = addresses!.find((x) => x.id === addressId)!;
      address = { area_id: a.area, area_name: a.area_detail.name_bn, address_line: a.line, latitude: a.latitude, longitude: a.longitude };
    }
    setBusy(true);
    setError("");
    try {
      const { data: sub } = await api.post<Subscription>("/subscriptions/", {
        ...f, plan: plan!.slug, home_size: plan!.sizes_apply ? f.home_size : 0, diet: isMeal ? f.diet : "", addons: picked, members, ...address,
      });
      if (f.payment_method === "online") await payOnline("subscription", sub.id);
      else navigate(`/subscriptions/${sub.id}`);
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  const durations = [...new Set(plan.prices.map((p) => p.duration_days))];
  return (
    <form onSubmit={submit} className="mx-auto grid max-w-[1100px] gap-6 px-4 py-8 sm:px-6 lg:grid-cols-[1.4fr_1fr]">
      <div className="flex flex-col gap-5">
        <PageHeader title={planName(plan)} subtitle={plan.includes.map((i) => (en() ? i.en : i.bn)).join(" · ")} />
        <Card className="flex flex-col gap-4">
          <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
            <legend className="mb-2 font-semibold">{t("মেয়াদ")}</legend>
            <div className="flex flex-wrap gap-2">
              {durations.map((d) => (
                <button key={d} type="button" aria-pressed={f.duration_days === d} onClick={() => setF({ ...f, duration_days: d, prepaid_months: 1 })}
                  className={`h-11 rounded-full border px-4 font-semibold ${f.duration_days === d ? "border-brand bg-brand text-white" : "border-line"}`}>
                  {d === 7 ? t("৭ দিন (ট্রায়াল)") : d === 15 ? t("১৫ দিন") : t("৩০ দিন")}
                </button>
              ))}
            </div>
          </fieldset>
          {plan.sizes_apply && (
            <Select label={t("বাসার আকার")} value={f.home_size} onChange={(e) => set("home_size", Number(e.target.value))}
              options={[{ value: 1, label: t("১ বেডরুম") }, { value: 2, label: t("২ বেডরুম") }, { value: 3, label: t("৩+ বেডরুম") }]} />
          )}
          {f.duration_days === 30 && (
            <Select label={t("অগ্রিম পরিশোধ (ছাড়)")} value={f.prepaid_months} onChange={(e) => set("prepaid_months", Number(e.target.value))}
              options={[{ value: 1, label: t("১ মাস") }, { value: 3, label: t("৩ মাস (৫% ছাড়)") }, { value: 6, label: t("৬ মাস (১০% ছাড়)") }, { value: 12, label: t("১২ মাস (১৫% ছাড়)") }]} />
          )}
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label={t("শুরুর তারিখ")} type="date" min={tomorrow} value={f.start_date} onChange={(e) => set("start_date", e.target.value)} />
            {!isMeal && ["weekly", "biweekly", "monthly"].includes(plan.frequency) && (
              <Select label={t("পছন্দের দিন")} value={f.preferred_weekday} onChange={(e) => set("preferred_weekday", Number(e.target.value))} options={DAYS.map((d, i) => ({ value: i, label: t(d) }))} />
            )}
            {!isMeal && <Select label={t("সময়")} value={f.slot} onChange={(e) => set("slot", e.target.value)} options={slotOptions()} />}
            {isMeal && (
              <Select label={t("খাবারের ধরন")} value={f.diet} onChange={(e) => set("diet", e.target.value)}
                options={[{ value: "bangla", label: t("বাংলা ঘরোয়া খাবার") }, { value: "light", label: t("হালকা খাবার") }, { value: "protein", label: t("প্রোটিন-সমৃদ্ধ") }]} />
            )}
          </div>
          {addons && addons.length > 0 && (
            <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
              <legend className="mb-2 font-semibold">{t("অ্যাড-অন")}</legend>
              {addons.map((a) => (
                <label key={a.slug} className="flex items-center gap-3">
                  <input type="checkbox" checked={picked.includes(a.slug)} onChange={() => setPicked(picked.includes(a.slug) ? picked.filter((x) => x !== a.slug) : [...picked, a.slug])} className="size-5 accent-brand" />
                  <span className="flex-1">{localName(a)}</span>
                  <span className="font-semibold">+ {formatTaka(a.price)}</span>
                </label>
              ))}
            </fieldset>
          )}
          {isMeal && (
            <>
              <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
                <legend className="mb-2 font-semibold">{t("মেস/গ্রুপ প্ল্যান (ঐচ্ছিক)")}</legend>
                <p className="m-0 text-sm text-muted">{t("৩–৫ জন বন্ধু একসাথে নিলে এক বিল, ভাগ করে দিন।")}</p>
                {members.map((m, i) => (
                  <div key={i} className="grid grid-cols-[1fr_1fr_auto] gap-2">
                    <input aria-label={t("নাম")} placeholder={t("নাম")} value={m.name} onChange={(e) => setMembers(members.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} className="h-10 rounded-xl border border-line px-3" />
                    <input aria-label={t("মোবাইল")} placeholder="01XXXXXXXXX" value={m.phone} onChange={(e) => setMembers(members.map((x, j) => (j === i ? { ...x, phone: e.target.value } : x)))} className="h-10 rounded-xl border border-line px-3" />
                    <button type="button" aria-label={t("সরান")} onClick={() => setMembers(members.filter((_, j) => j !== i))} className="flex size-10 items-center justify-center rounded-xl text-bad"><Icon name="x" size={16} /></button>
                  </div>
                ))}
                {members.length < 5 && <Button variant="ghost" icon="plus" className="self-start" onClick={() => setMembers([...members, { name: "", phone: "" }])}>{t("সদস্য যোগ করুন")}</Button>}
              </fieldset>
              {user && <StudentBox />}
            </>
          )}
        </Card>

        <Card className="flex flex-col gap-3">
          <h2 className="m-0 text-lg font-bold">{t("ঠিকানা")}</h2>
          {addresses?.map((a) => (
            <label key={a.id} className={`flex items-start gap-3 rounded-xl border p-3 ${addressId === a.id ? "border-brand bg-brand-tint" : "border-line"}`}>
              <input type="radio" checked={addressId === a.id} onChange={() => setAddressId(a.id)} className="mt-1 accent-brand" />
              <span>{a.label} — <span className="text-muted">{a.line}, {localName(a.area_detail)}</span></span>
            </label>
          ))}
          <label className="flex items-center gap-3"><input type="radio" checked={addressId === "new"} onChange={() => setAddressId("new")} className="accent-brand" /> {t("নতুন ঠিকানা")}</label>
          {addressId === "new" && (
            <div className="grid gap-3 sm:grid-cols-2">
              <Select label={t("এলাকা")} value={newArea} onChange={(e) => setNewArea(e.target.value)} options={[{ value: "", label: t("এলাকা বাছুন") }, ...(areas ?? []).map((a) => ({ value: a.id, label: localName(a) }))]} />
              <Field label={t("বাসা ও রাস্তা")} value={newLine} onChange={(e) => setNewLine(e.target.value)} />
            </div>
          )}
        </Card>
      </div>

      <Card className="flex h-fit flex-col gap-3 lg:sticky lg:top-24">
        <h2 className="m-0 text-lg font-bold">{t("মোট খরচ")}</h2>
        {quote ? (
          <>
            <span className="text-3xl font-bold">{formatTaka(quote.total)}</span>
            {quote.months > 1 && <span className="text-sm text-muted">{t("{n} মাসের জন্য", { n: quote.months })}</span>}
            {quote.student_discount && <Badge tone="ok">{t("স্টুডেন্ট ছাড় যোগ হয়েছে")}</Badge>}
            {quote.per_member && <span className="text-sm">{t("প্রতিজনের ভাগ: {amount}", { amount: formatTaka(quote.per_member) })}</span>}
          </>
        ) : (
          <span className="text-muted">{t("হিসাব করা হচ্ছে…")}</span>
        )}
        <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
          <legend className="mb-2 font-semibold">{t("পেমেন্ট")}</legend>
          {[["cod", "ক্যাশ (প্রথম ভিজিটে)"], ["online", "বিকাশ / নগদ / কার্ড"]].map(([v, label]) => (
            <label key={v} className={`flex items-center gap-3 rounded-xl border p-3 ${f.payment_method === v ? "border-brand bg-brand-tint" : "border-line"}`}>
              <input type="radio" checked={f.payment_method === v} onChange={() => set("payment_method", v)} className="accent-brand" /> {t(label)}
            </label>
          ))}
        </fieldset>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={f.auto_renew} onChange={(e) => set("auto_renew", e.target.checked)} className="size-5 accent-brand" />
          {t("মেয়াদ শেষে স্বয়ংক্রিয় রিনিউ")}
        </label>
        <ErrorNote>{error}</ErrorNote>
        <Button type="submit" loading={busy} disabled={!quote} className="h-12 text-base">{t("সাবস্ক্রাইব করুন")}</Button>
      </Card>
    </form>
  );
}

export function MySubscriptions() {
  const { data, isPending } = useQuery({
    queryKey: ["subscriptions"],
    queryFn: async () => (await api.get<Paginated<Subscription>>("/subscriptions/")).data,
  });
  return (
    <section className="mx-auto flex max-w-[960px] flex-col gap-5 px-4 py-8 sm:px-6">
      <PageHeader title={t("আমার সাবস্ক্রিপশন")} actions={<Link to="/subscriptions" className="flex h-11 items-center rounded-xl bg-brand px-4 font-semibold text-white no-underline">{t("নতুন প্ল্যান")}</Link>} />
      {isPending && <Loading />}
      {data?.results.length === 0 && <Empty icon="repeat" title={t("কোনো সাবস্ক্রিপশন নেই")} />}
      {data?.results.map((s) => (
        <Link key={s.id} to={`/subscriptions/${s.id}`} className="text-ink no-underline">
          <Card className="flex flex-wrap items-center gap-4 hover:border-brand">
            <Icon name={s.plan.category === "meal" ? "meal" : "repeat"} className="text-brand" />
            <div className="flex flex-1 flex-col">
              <span className="font-bold">{planName(s.plan)}</span>
              <span className="text-sm text-muted">{formatDate(s.start_date)} – {formatDate(s.end_date)}</span>
            </div>
            <span className="font-semibold">{formatTaka(s.price)}</span>
            <StatusBadge status={s.status} />
          </Card>
        </Link>
      ))}
    </section>
  );
}

function VisitRow({ visit, onChanged }: { visit: Visit; onChanged: () => void }) {
  const [rating, setRating] = useState(0);
  const [feedback, setFeedback] = useState("");
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  const recleanOpen = visit.kind !== "meal" && visit.status === "completed" && visit.completed_at && Date.now() - new Date(visit.completed_at).getTime() < 48 * 3600 * 1000;

  async function act(fn: () => Promise<unknown>) {
    setError("");
    try {
      await fn();
      setOpen(false);
      onChanged();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-subtle py-3 last:border-0">
      <span className="w-32 font-semibold">{formatDate(visit.date)}</span>
      <span className="flex-1">
        {visit.meal_type ? t(MEALS[visit.meal_type] ?? visit.meal_type) : t(KINDS[visit.kind] ?? visit.kind)} · {slotLabel(visit.slot)}
        {visit.provider_name && <span className="block text-[13px] text-muted">{visit.provider_name}</span>}
      </span>
      <StatusBadge status={visit.status} />
      {visit.can_change && <Button variant="ghost" onClick={() => act(() => api.patch(`/subscriptions/visits/${visit.id}/skip/`))}>{visit.meal_type ? t("এই মিল বাদ দিন") : t("এই ভিজিট বাদ দিন")}</Button>}
      {visit.status === "skipped" && new Date(visit.cutoff) > new Date() && <Button variant="ghost" onClick={() => act(() => api.patch(`/subscriptions/visits/${visit.id}/unskip/`))}>{t("ফিরিয়ে আনুন")}</Button>}
      {visit.status === "completed" && !visit.rating && <Button variant="secondary" icon="star" onClick={() => setOpen(true)}>{t("রেটিং দিন")}</Button>}
      {visit.rating && <span className="text-alert-strong">{"★".repeat(visit.rating)}</span>}
      {recleanOpen && <Button variant="ghost" icon="refresh" onClick={() => act(() => api.post(`/subscriptions/visits/${visit.id}/reclean/`))}>{t("ফ্রি রি-ক্লিন")}</Button>}
      {error && <span className="w-full text-sm text-bad">{error}</span>}
      <Modal title={t("কেমন হলো?")} open={open} onClose={() => setOpen(false)}>
        <div className="flex gap-1" role="radiogroup" aria-label={t("রেটিং")}>
          {[1, 2, 3, 4, 5].map((n) => (
            <button key={n} type="button" role="radio" aria-checked={rating === n} aria-label={`${n}`} onClick={() => setRating(n)} className={`text-3xl ${n <= rating ? "text-alert" : "text-line"}`}>★</button>
          ))}
        </div>
        <TextArea label={t("মন্তব্য (ঐচ্ছিক)")} value={feedback} onChange={(e) => setFeedback(e.target.value)} />
        {visit.meal_type && rating > 0 && rating <= 2 && <p className="m-0 text-sm text-muted">{t("খারাপ মিলের টাকা পরের রিনিউয়ে ফেরত (ক্রেডিট) পাবেন।")}</p>}
        <Button disabled={!rating} onClick={() => act(() => api.post(`/subscriptions/visits/${visit.id}/rate/`, { rating, feedback }))}>{t("জমা দিন")}</Button>
      </Modal>
    </div>
  );
}

export function SubscriptionDetail() {
  const { id } = useParams();
  const qc = useQueryClient();
  const { data: sub } = useQuery({ queryKey: ["subscriptions", id], queryFn: async () => (await api.get<Subscription>(`/subscriptions/${id}/`)).data });
  const { data: visits } = useQuery({ queryKey: ["subscriptions", id, "visits"], queryFn: async () => (await api.get<Visit[]>(`/subscriptions/${id}/visits/`)).data, enabled: !!sub });
  const { data: upgrades } = useQuery({ queryKey: ["plans", sub?.plan.category], queryFn: async () => (await api.get<Plan[]>("/subscription-plans/", { params: { category: sub!.plan.category } })).data, enabled: !!sub });
  const { data: menu } = useQuery({
    queryKey: ["menu", sub?.diet],
    queryFn: async () => (await api.get<{ date: string; meal_type: string; items_bn: string; items_en: string }[]>("/meal-menu/", { params: { diet: sub!.diet || "bangla" } })).data,
    enabled: !!sub && ["meal", "tiffin"].includes(sub.plan.category),
  });
  const [pauseOpen, setPauseOpen] = useState(false);
  const [until, setUntil] = useState(todayISO(7));
  const [error, setError] = useState("");
  const [showAll, setShowAll] = useState(false);

  if (!sub) return <Loading />;
  const refresh = () => qc.invalidateQueries({ queryKey: ["subscriptions"] });

  async function act(fn: () => Promise<unknown>) {
    setError("");
    try {
      await fn();
      setPauseOpen(false);
      refresh();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  const today = todayISO();
  const list = (visits ?? []).filter((v) => showAll || v.date >= today).slice(0, showAll ? undefined : 14);
  return (
    <section className="mx-auto grid max-w-[1100px] gap-6 px-4 py-8 sm:px-6 lg:grid-cols-[1.5fr_1fr]">
      <div className="flex flex-col gap-5">
        <PageHeader title={planName(sub.plan)} subtitle={`${formatDate(sub.start_date)} – ${formatDate(sub.end_date)} · ${sub.address_line}, ${sub.area_name}`} actions={<StatusBadge status={sub.status} />} />
        {sub.status === "pending_payment" && (
          <Card className="flex flex-wrap items-center justify-between gap-3 border-alert">
            <span>{t("পেমেন্ট বাকি: {amount}", { amount: formatTaka(sub.amount_due) })}</span>
            <Button onClick={() => payOnline("subscription", sub.id)}>{t("এখনই পরিশোধ করুন")}</Button>
          </Card>
        )}
        {sub.preferred_provider_name && (
          <Card className="flex items-center gap-3">
            <Icon name="user" className="text-brand" />
            <span>{t("আপনার নিয়মিত প্রোভাইডার:")} <strong>{sub.preferred_provider_name}</strong></span>
          </Card>
        )}
        <Card className="flex flex-col">
          <div className="flex items-center justify-between">
            <h2 className="m-0 text-lg font-bold">{t("সময়সূচি")}</h2>
            <button type="button" className="font-semibold text-brand" onClick={() => setShowAll(!showAll)}>{showAll ? t("সামনের দেখুন") : t("সব দেখুন")}</button>
          </div>
          <p className="m-0 mb-2 text-sm text-muted">{t("আগের দিন রাত ১০টা পর্যন্ত বাদ দিতে পারবেন; বাদ দেওয়া ভিজিট/মিলের টাকা ক্রেডিট হয়।")}</p>
          {list.map((v) => <VisitRow key={v.id} visit={v} onChanged={refresh} />)}
        </Card>
        {menu && menu.length > 0 && (
          <Card className="flex flex-col gap-2">
            <h2 className="m-0 text-lg font-bold">{t("এই সপ্তাহের মেনু")}</h2>
            {menu.slice(0, 14).map((m) => (
              <div key={`${m.date}${m.meal_type}`} className="flex gap-3 text-[15px]">
                <span className="w-32 text-muted">{formatDate(m.date)}</span>
                <span className="w-28">{t(MEALS[m.meal_type] ?? m.meal_type)}</span>
                <span className="flex-1">{en() ? m.items_en : m.items_bn}</span>
              </div>
            ))}
          </Card>
        )}
      </div>

      <div className="flex flex-col gap-5">
        <Card className="flex flex-col gap-2">
          <div className="flex justify-between"><span className="text-muted">{t("মূল্য")}</span><span className="font-bold">{formatTaka(sub.price)}</span></div>
          {Number(sub.credit_applied) > 0 && <div className="flex justify-between text-brand-strong"><span>{t("আগের ক্রেডিট")}</span><span>− {formatTaka(sub.credit_applied)}</span></div>}
          <div className="flex justify-between"><span className="text-muted">{t("জমা ক্রেডিট (পরের রিনিউয়ে)")}</span><span>{formatTaka(sub.credit)}</span></div>
          <div className="flex items-center justify-between"><span className="text-muted">{sub.payment_method === "cod" ? t("ক্যাশ") : t("অনলাইন")}</span><StatusBadge status={sub.paid ? "paid" : "unpaid"} /></div>
        </Card>
        <Card className="flex flex-col gap-3">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={sub.auto_renew} onChange={(e) => act(() => api.patch(`/subscriptions/${sub.id}/settings/`, { auto_renew: e.target.checked }))} className="size-5 accent-brand" disabled={["cancelled", "expired"].includes(sub.status)} />
            {t("স্বয়ংক্রিয় রিনিউ")}
          </label>
          {upgrades && (
            <Select label={t("পরের মেয়াদে প্ল্যান")} value={sub.next_plan ?? ""} onChange={(e) => act(() => api.patch(`/subscriptions/${sub.id}/settings/`, { next_plan: e.target.value }))}
              options={[{ value: "", label: t("একই প্ল্যান") }, ...upgrades.filter((p) => p.slug !== sub.plan.slug).map((p) => ({ value: p.slug, label: planName(p) }))]} />
          )}
          <ErrorNote>{error}</ErrorNote>
          {sub.status === "active" && <Button variant="ghost" icon="clock" onClick={() => setPauseOpen(true)}>{t("বিরতি দিন")}</Button>}
          {sub.status === "paused" && <Button icon="refresh" onClick={() => act(() => api.patch(`/subscriptions/${sub.id}/resume/`))}>{t("আবার চালু করুন")}</Button>}
          {["active", "expired"].includes(sub.status) && <Button variant="secondary" icon="repeat" onClick={() => act(() => api.post(`/subscriptions/${sub.id}/renew/`, {}))}>{t("এখনই রিনিউ করুন")}</Button>}
          {!["cancelled", "expired"].includes(sub.status) && <Button variant="danger" onClick={() => confirm(t("সাবস্ক্রিপশন বাতিল করবেন?")) && act(() => api.patch(`/subscriptions/${sub.id}/cancel/`))}>{t("বাতিল করুন")}</Button>}
        </Card>
      </div>
      <Modal title={t("বিরতি দিন")} open={pauseOpen} onClose={() => setPauseOpen(false)}>
        <Field label={t("কবে থেকে আবার চালু হবে")} type="date" min={todayISO(1)} value={until} onChange={(e) => setUntil(e.target.value)} />
        <p className="m-0 text-sm text-muted">{t("বিরতির সময়ের ভিজিট/মিলের টাকা ক্রেডিট হিসেবে জমা থাকবে।")}</p>
        <Button onClick={() => act(() => api.patch(`/subscriptions/${sub.id}/pause/`, { until }))}>{t("বিরতি নিশ্চিত করুন")}</Button>
      </Modal>
    </section>
  );
}
