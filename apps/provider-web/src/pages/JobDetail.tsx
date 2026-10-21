import { api, Button, Card, errorMessage, ErrorNote, Field, formatDate, formatTaka, Icon, Loading, openJobChat, PageHeader, PhotoUpload, slotLabel, SosButton, StatusBadge, t, TextArea, Timeline } from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import type { Job } from "../api";

const DEFAULT_CHECKLIST = ["কাজের জায়গা পরিষ্কার রাখা হয়েছে", "গ্রাহককে কাজ দেখানো হয়েছে", "পুরনো যন্ত্রাংশ গ্রাহককে দেওয়া হয়েছে"];

/** While on the way or working, share the device position every 30s for the customer's live map. */
function useShareLocation(active: boolean) {
  const [sharing, setSharing] = useState(false);
  useEffect(() => {
    if (!active || !sharing || !("geolocation" in navigator)) return;
    const send = () =>
      navigator.geolocation.getCurrentPosition((pos) =>
        api.post("/providers/me/location/", { latitude: pos.coords.latitude.toFixed(6), longitude: pos.coords.longitude.toFixed(6) }).catch(() => {}),
      );
    send();
    const timer = setInterval(send, 30_000);
    return () => clearInterval(timer);
  }, [active, sharing]);
  return [sharing, setSharing] as const;
}

export default function JobDetail() {
  const { id } = useParams();
  const qc = useQueryClient();
  const { data: job, isPending } = useQuery({
    queryKey: ["job", id],
    queryFn: async () => (await api.get<Job>(`/providers/jobs/${id}/`)).data,
  });
  const [code, setCode] = useState("");
  const [photos, setPhotos] = useState<string[]>([]);
  const [note, setNote] = useState("");
  const [checklist, setChecklist] = useState(DEFAULT_CHECKLIST.map((label) => ({ label: t(label), done: false })));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sharing, setSharing] = useShareLocation(!!job && ["on_the_way", "working"].includes(job.status));
  const navigate = useNavigate();

  if (isPending || !job) return <Loading />;

  async function advance(status: string, body: object = {}) {
    setBusy(true);
    setError("");
    try {
      await api.patch(`/providers/jobs/${id}/status/`, { status, ...body });
      setPhotos([]);
      qc.invalidateQueries({ queryKey: ["job", id] });
      qc.invalidateQueries({ queryKey: ["jobs"] });
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  const mapsUrl = job.latitude ? `https://www.openstreetmap.org/?mlat=${job.latitude}&mlon=${job.longitude}#map=17/${job.latitude}/${job.longitude}` : null;

  return (
    <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
      <div className="flex flex-col gap-5">
        <PageHeader title={job.title} subtitle={`${formatDate(job.scheduled_date)}, ${slotLabel(job.slot)}`} actions={<StatusBadge status={job.status} />} />

        <Card className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <span className="flex size-11 items-center justify-center rounded-full bg-brand-soft text-brand-strong">
              <Icon name="user" />
            </span>
            <div className="flex flex-1 flex-col">
              <span className="font-semibold">{job.customer_name}</span>
              <span className="text-sm text-muted">
                {job.address_line ? `${job.address_line}, ` : ""}
                {job.area_name}
              </span>
            </div>
            {job.customer_phone && (
              <Button variant="ghost" icon="chat" onClick={async () => navigate(`/chat/${await openJobChat(job.source, job.source_id)}`)}>
                {t("বার্তা")}
              </Button>
            )}
            {job.customer_phone && (
              <a href={`tel:${job.customer_phone}`} className="flex h-11 items-center gap-2 rounded-xl bg-brand px-4 font-semibold text-white no-underline">
                <Icon name="phone" size={16} /> {t("কল")}
              </a>
            )}
          </div>
          {mapsUrl && (
            <a href={mapsUrl} target="_blank" rel="noreferrer" className="flex items-center gap-2 font-semibold">
              <Icon name="map" size={16} /> {t("ম্যাপে দেখুন")}
            </a>
          )}
          {job.description && <p className="m-0 rounded-xl bg-subtle p-3 whitespace-pre-line">{job.description}</p>}
          {job.photo_urls.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {job.photo_urls.map((u) => (
                <a key={u} href={u} target="_blank" rel="noreferrer">
                  <img src={u} alt={t("গ্রাহকের দেওয়া ছবি")} className="size-24 rounded-xl object-cover" />
                </a>
              ))}
            </div>
          )}
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-lg font-bold">{formatTaka(job.amount)}</span>
            {job.customer_score?.average != null && (
              <span className="text-sm text-muted">
                {t("গ্রাহকের রেটিং")} ★ {Number(job.customer_score.average).toFixed(1)} ({job.customer_score.count})
              </span>
            )}
          </div>
        </Card>

        <ErrorNote>{error}</ErrorNote>

        {job.status === "accepted" && (
          <Card className="flex flex-col gap-3">
            <h2 className="m-0 text-lg font-bold">{t("রওনা দিন")}</h2>
            <p className="m-0 text-muted">{t("রওনা দিলে গ্রাহক জানতে পারবেন এবং আপনার লোকেশন দেখতে পাবেন।")}</p>
            <Button loading={busy} icon="send" onClick={() => { setSharing(true); advance("on_the_way"); }}>
              {t("পথে আছি")}
            </Button>
          </Card>
        )}

        {job.status === "on_the_way" && (
          <Card className="flex flex-col gap-3">
            <h2 className="m-0 text-lg font-bold">{t("পৌঁছে কাজ শুরু করুন")}</h2>
            {["booking", "warranty"].includes(job.source) && (
              <Field label={t("গ্রাহকের ৪ সংখ্যার কোড")} inputMode="numeric" maxLength={4} value={code} onChange={(e) => setCode(e.target.value)} hint={t("গ্রাহকের অ্যাপে কোডটি দেখানো আছে")} />
            )}
            <PhotoUpload label={t("কাজের আগের ছবি")} value={photos} onChange={setPhotos} purpose="job_photo" max={4} />
            <Button loading={busy} onClick={() => advance("working", { arrival_code: code, photos })}>
              {t("কাজ শুরু")}
            </Button>
          </Card>
        )}

        {job.status === "working" && (
          <Card className="flex flex-col gap-3">
            <h2 className="m-0 text-lg font-bold">{t("কাজ শেষ করুন")}</h2>
            <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
              <legend className="mb-1 font-semibold">{t("চেকলিস্ট")}</legend>
              {checklist.map((item, i) => (
                <label key={item.label} className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    checked={item.done}
                    onChange={() => setChecklist(checklist.map((c, j) => (j === i ? { ...c, done: !c.done } : c)))}
                    className="size-5 accent-brand"
                  />
                  {item.label}
                </label>
              ))}
            </fieldset>
            <PhotoUpload label={t("কাজের পরের ছবি")} value={photos} onChange={setPhotos} purpose="job_photo" max={4} />
            <TextArea label={t("নোট (ঐচ্ছিক)")} value={note} onChange={(e) => setNote(e.target.value)} placeholder={t("কী কী করা হয়েছে, কোনো যন্ত্রাংশ বদলানো হয়েছে কি না")} />
            <Button loading={busy} icon="check" onClick={() => advance("completed", { photos, note, checklist })}>
              {t("কাজ সম্পন্ন")}
            </Button>
          </Card>
        )}

        {["accepted", "on_the_way", "working"].includes(job.status) && <SosButton source="job" sourceId={job.id} className="self-start" />}

        {job.status === "completed" && <RateCustomer job={job} />}

        {["on_the_way", "working"].includes(job.status) && (
          <label className="flex items-center gap-3 text-[15px]">
            <input type="checkbox" checked={sharing} onChange={(e) => setSharing(e.target.checked)} className="size-5 accent-brand" />
            {t("গ্রাহকের সাথে লাইভ লোকেশন শেয়ার করুন")}
          </label>
        )}

        {(job.before_photos.length > 0 || job.after_photos.length > 0) && (
          <Card className="grid gap-3 sm:grid-cols-2">
            {[[t("আগে"), job.before_photos], [t("পরে"), job.after_photos]].map(([label, list]) => (
              <div key={label as string} className="flex flex-col gap-2">
                <span className="font-semibold">{label as string}</span>
                <div className="flex flex-wrap gap-2">
                  {(list as string[]).map((u) => (
                    <img key={u} src={u} alt="" className="size-20 rounded-xl object-cover" />
                  ))}
                </div>
              </div>
            ))}
          </Card>
        )}
      </div>
      {job.logs && (
        <Card className="flex h-fit flex-col gap-4">
          <h2 className="m-0 text-lg font-bold">{t("টাইমলাইন")}</h2>
          <Timeline events={[...job.logs].reverse()} />
        </Card>
      )}
    </div>
  );
}

/** After the job the provider rates the customer too; other providers see the average before accepting. */
function RateCustomer({ job }: { job: Job }) {
  const qc = useQueryClient();
  const [rating, setRating] = useState(0);
  const [feedback, setFeedback] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (job.customer_rating) {
    return (
      <Card className="flex flex-col gap-1">
        <span className="font-semibold">{t("আপনি গ্রাহককে রেটিং দিয়েছেন")}</span>
        <span className="text-alert-strong">{"★".repeat(job.customer_rating)}<span className="text-line">{"★".repeat(5 - job.customer_rating)}</span></span>
      </Card>
    );
  }

  async function submit() {
    setBusy(true);
    setError("");
    try {
      await api.post(`/providers/jobs/${job.id}/rate-customer/`, { rating, feedback });
      qc.invalidateQueries({ queryKey: ["job", String(job.id)] });
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="flex flex-col gap-3">
      <h2 className="m-0 text-lg font-bold">{t("গ্রাহককে রেটিং দিন")}</h2>
      <div className="flex gap-1" role="radiogroup" aria-label={t("রেটিং")}>
        {[1, 2, 3, 4, 5].map((n) => (
          <button key={n} type="button" role="radio" aria-checked={rating === n} onClick={() => setRating(n)} className={`text-3xl ${n <= rating ? "text-alert-strong" : "text-line"}`}>
            ★
          </button>
        ))}
      </div>
      <TextArea label={t("মন্তব্য (ঐচ্ছিক)")} value={feedback} onChange={(e) => setFeedback(e.target.value)} />
      <ErrorNote>{error}</ErrorNote>
      <Button loading={busy} disabled={!rating} onClick={submit} className="self-start">{t("রেটিং দিন")}</Button>
    </Card>
  );
}
