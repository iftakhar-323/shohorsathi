import { api, Button, Card, Empty, errorMessage, ErrorNote, Field, formatDate, formatTaka, Loading, localName, Modal, PageHeader, PhotoUpload, Select, StatusBadge, t, TextArea, Timeline, todayISO, type Paginated, useAreas } from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

type Quote = { labor: string; materials: string; transport: string; platform_fee: string; total: string; timeline_days: number; note: string; created_at: string };
type CustomRequest = {
  id: number;
  service_type: string;
  description: string;
  media_urls: string[];
  area_name: string;
  address_line: string;
  preferred_date: string;
  budget_min: string | null;
  budget_max: string | null;
  status: string;
  rejection_reason: string;
  final_amount: string | null;
  advance_amount: string | null;
  advance_paid: boolean;
  provider_name: string;
  provider_phone: string;
  quote: Quote | null;
  counter: { amount: string; message: string } | null;
  logs: { status: string; note: string; created_at: string }[];
  created_at: string;
};

const EXAMPLES = ["২ রুমের দেয়াল রং", "বাসা বদল", "বিয়েবাড়ি পরিষ্কার", "অফিস ওয়্যারিং"];

export function NewCustomRequest() {
  const { data: areas } = useAreas();
  const navigate = useNavigate();
  const [form, setForm] = useState({ service_type: "", description: "", area_id: "", address_line: "", preferred_date: todayISO(2), budget_min: "", budget_max: "" });
  const [media, setMedia] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });

  async function submit(e: FormEvent) {
    e.preventDefault();
    const area = areas?.find((a) => a.id === Number(form.area_id));
    if (!area) return setError(t("এলাকা বাছুন।"));
    setBusy(true);
    setError("");
    try {
      const { data } = await api.post<CustomRequest>("/custom-requests/", {
        ...form,
        area_id: area.id,
        area_name: area.name_bn,
        media_urls: media,
        budget_min: form.budget_min || null,
        budget_max: form.budget_max || null,
      });
      navigate(`/custom-requests/${data.id}`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mx-auto flex max-w-[760px] flex-col gap-6 px-4 py-8 sm:px-6">
      <PageHeader title={t("কাস্টম রিকোয়েস্ট")} subtitle={t("ক্যাটালগে নেই এমন যেকোনো কাজ। অ্যাডমিন দেখে খরচের হিসাবসহ কোট দেবেন।")} />
      <form onSubmit={submit} className="flex flex-col gap-4 rounded-[20px] border border-line bg-surface p-6">
        <Field label={t("কী কাজ?")} required value={form.service_type} onChange={set("service_type")} placeholder={t("যেমন: ২ রুমের দেয়াল রং")} />
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map((x) => (
            <button key={x} type="button" onClick={() => setForm({ ...form, service_type: t(x) })} className="rounded-full border border-line px-3 py-1.5 text-sm">
              {t(x)}
            </button>
          ))}
        </div>
        <TextArea label={t("বিস্তারিত")} required rows={4} value={form.description} onChange={set("description")} placeholder={t("মাপ, অবস্থা, কী কী লাগবে")} />
        <PhotoUpload label={t("ছবি")} value={media} onChange={setMedia} purpose="problem_photo" max={5} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Select label={t("এলাকা")} required value={form.area_id} onChange={set("area_id")} options={[{ value: "", label: t("এলাকা বাছুন") }, ...(areas ?? []).map((a) => ({ value: a.id, label: localName(a) }))]} />
          <Field label={t("ঠিকানা")} required value={form.address_line} onChange={set("address_line")} />
          <Field label={t("পছন্দের তারিখ")} type="date" min={todayISO()} required value={form.preferred_date} onChange={set("preferred_date")} />
          <div className="grid grid-cols-2 gap-2">
            <Field label={t("বাজেট (কম)")} type="number" min={0} value={form.budget_min} onChange={set("budget_min")} />
            <Field label={t("বাজেট (বেশি)")} type="number" min={0} value={form.budget_max} onChange={set("budget_max")} />
          </div>
        </div>
        <ErrorNote>{error}</ErrorNote>
        <Button type="submit" loading={busy} className="h-12 text-base">
          {t("রিকোয়েস্ট পাঠান")}
        </Button>
      </form>
    </section>
  );
}

export function CustomRequestList() {
  const { data, isPending } = useQuery({
    queryKey: ["custom-requests"],
    queryFn: async () => (await api.get<Paginated<CustomRequest>>("/custom-requests/")).data,
  });
  return (
    <section className="mx-auto flex max-w-[960px] flex-col gap-6 px-4 py-8 sm:px-6">
      <PageHeader title={t("আমার কাস্টম রিকোয়েস্ট")} actions={<Link to="/custom-requests/new" className="flex h-11 items-center rounded-xl bg-brand px-4 font-semibold text-white no-underline">{t("নতুন রিকোয়েস্ট")}</Link>} />
      {isPending && <Loading />}
      {data?.results.length === 0 && <Empty icon="send" title={t("এখনো কোনো রিকোয়েস্ট নেই")} />}
      {data?.results.map((r) => (
        <Link key={r.id} to={`/custom-requests/${r.id}`} className="text-ink no-underline">
          <Card className="flex flex-wrap items-center gap-4 hover:border-brand">
            <div className="flex flex-1 flex-col">
              <span className="font-bold">{r.service_type}</span>
              <span className="text-sm text-muted">{formatDate(r.created_at)}</span>
            </div>
            {r.quote && <span className="font-semibold">{formatTaka(r.quote.total)}</span>}
            <StatusBadge status={r.status} />
          </Card>
        </Link>
      ))}
    </section>
  );
}

export function CustomRequestDetail() {
  const { id } = useParams();
  const qc = useQueryClient();
  const { data: req, isPending } = useQuery({
    queryKey: ["custom-requests", id],
    queryFn: async () => (await api.get<CustomRequest>(`/custom-requests/${id}/`)).data,
    refetchInterval: 20_000,
  });
  const [counterOpen, setCounterOpen] = useState(false);
  const [amount, setAmount] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (isPending || !req) return <Loading />;

  async function act(path: string, body?: object) {
    setBusy(true);
    setError("");
    try {
      await api.post(`/custom-requests/${id}/${path}/`, body);
      setCounterOpen(false);
      qc.invalidateQueries({ queryKey: ["custom-requests"] });
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  const q = req.quote;
  return (
    <section className="mx-auto grid max-w-[1100px] gap-6 px-4 py-8 sm:px-6 lg:grid-cols-[1.5fr_1fr]">
      <div className="flex flex-col gap-5">
        <PageHeader title={req.service_type} subtitle={`${req.address_line}, ${req.area_name} · ${formatDate(req.preferred_date)}`} actions={<StatusBadge status={req.status} />} />
        <Card className="flex flex-col gap-3">
          <p className="m-0 leading-relaxed whitespace-pre-line">{req.description}</p>
          {req.media_urls.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {req.media_urls.map((u) => (
                <img key={u} src={u} alt="" className="size-24 rounded-xl object-cover" />
              ))}
            </div>
          )}
          {(req.budget_min || req.budget_max) && (
            <span className="text-sm text-muted">
              {t("আপনার বাজেট:")} {formatTaka(req.budget_min)} – {formatTaka(req.budget_max)}
            </span>
          )}
        </Card>

        {q && (
          <Card className="flex flex-col gap-3 border-brand">
            <h2 className="m-0 text-lg font-bold">{t("খরচের হিসাব")}</h2>
            {[
              [t("মজুরি"), q.labor],
              [t("উপকরণ"), q.materials],
              [t("যাতায়াত"), q.transport],
              [t("প্ল্যাটফর্ম ফি"), q.platform_fee],
            ].map(([label, value]) => (
              <div key={label} className="flex justify-between text-muted">
                <span>{label}</span>
                <span>{formatTaka(value)}</span>
              </div>
            ))}
            <div className="flex justify-between border-t border-line pt-2 text-xl font-bold">
              <span>{t("মোট")}</span>
              <span>{formatTaka(q.total)}</span>
            </div>
            <span className="text-sm text-muted">{t("সময় লাগবে:")} {q.timeline_days} {t("দিন")}</span>
            {q.note && <p className="m-0 rounded-xl bg-subtle p-3 text-[15px]">{q.note}</p>}
            {req.counter && <span className="text-sm text-muted">{t("আপনার পাল্টা প্রস্তাব ছিল")} {formatTaka(req.counter.amount)}</span>}
            <ErrorNote>{error}</ErrorNote>
            {req.status === "quote_sent" && (
              <div className="flex flex-wrap gap-2">
                <Button loading={busy} onClick={() => act("accept")}>
                  {t("কোট গ্রহণ করুন")}
                </Button>
                {!req.counter && (
                  <Button variant="ghost" onClick={() => setCounterOpen(true)}>
                    {t("পাল্টা প্রস্তাব")}
                  </Button>
                )}
                <Button variant="danger" onClick={() => confirm(t("কোটটি বাতিল করবেন?")) && act("reject")}>
                  {t("বাতিল")}
                </Button>
              </div>
            )}
          </Card>
        )}

        {req.final_amount && (
          <Card className="flex flex-col gap-2">
            <span className="font-semibold">{t("চূড়ান্ত মূল্য")} {formatTaka(req.final_amount)}</span>
            <span className="text-sm text-muted">
              {t("অগ্রিম")} {formatTaka(req.advance_amount)} {req.advance_paid ? t("(পরিশোধিত)") : t("— কাজ শুরুর আগে")}
            </span>
            {req.provider_name && (
              <span>
                {t("প্রোভাইডার:")} <strong>{req.provider_name}</strong> {req.provider_phone && <a href={`tel:${req.provider_phone}`}>{req.provider_phone}</a>}
              </span>
            )}
          </Card>
        )}

        {req.status === "rejected" && req.rejection_reason && <ErrorNote>{t("কারণ:")} {req.rejection_reason}</ErrorNote>}
        {["submitted", "under_review", "quote_sent", "countered"].includes(req.status) && (
          <Button variant="ghost" className="self-start" onClick={() => confirm(t("রিকোয়েস্ট বাতিল করবেন?")) && act("cancel")}>
            {t("রিকোয়েস্ট বাতিল করুন")}
          </Button>
        )}
      </div>
      <Card className="flex h-fit flex-col gap-4">
        <h2 className="m-0 text-lg font-bold">{t("অগ্রগতি")}</h2>
        <Timeline events={[...req.logs].reverse()} />
      </Card>

      <Modal title={t("পাল্টা প্রস্তাব (একবারই)")} open={counterOpen} onClose={() => setCounterOpen(false)}>
        <Field label={t("আপনার প্রস্তাবিত মোট (৳)")} type="number" min={1} value={amount} onChange={(e) => setAmount(e.target.value)} />
        <TextArea label={t("বার্তা")} value={message} onChange={(e) => setMessage(e.target.value)} />
        <ErrorNote>{error}</ErrorNote>
        <Button loading={busy} disabled={!amount} onClick={() => act("counter", { amount, message })}>
          {t("পাঠান")}
        </Button>
      </Modal>
    </section>
  );
}
