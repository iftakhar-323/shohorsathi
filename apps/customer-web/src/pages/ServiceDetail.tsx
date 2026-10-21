import { Button, Card, ErrorNote, Icon, Loading, PhotoUpload, SLOTS, TextArea, api, errorMessage, formatTaka, todayISO, useAuth, type Service } from "@shohor/web-core";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { useAddToCart } from "../api/orders";
import { saveDraft } from "../lib/bookingDraft";

export default function ServiceDetail() {
  const { slug } = useParams();
  const [params] = useSearchParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const addToCart = useAddToCart();
  const { data: service, isPending, isError } = useQuery({
    queryKey: ["service", slug],
    queryFn: async () => (await api.get<Service>(`/services/${slug}/`)).data,
  });

  const emergency = params.get("emergency") === "1";
  const [date, setDate] = useState(todayISO(emergency ? 0 : 1));
  const [slot, setSlot] = useState(SLOTS[0].value);
  const [problem, setProblem] = useState("");
  const [photos, setPhotos] = useState<string[]>([]);
  const [error, setError] = useState("");

  if (isPending) return <Loading />;
  if (isError || !service) return <div className="mx-auto max-w-[1200px] p-6"><ErrorNote>সার্ভিসটি পাওয়া যায়নি।</ErrorNote></div>;

  async function book() {
    if (!user) {
      navigate(`/login?next=/services/${slug}`);
      return;
    }
    setError("");
    try {
      const item = await addToCart.mutateAsync({ item_type: "service", slug: service!.slug });
      saveDraft(item.id, { scheduled_date: date, slot, problem_description: problem, photo_urls: photos, is_emergency: emergency });
      navigate("/cart");
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <section className="mx-auto grid max-w-[1200px] gap-6 px-4 py-8 sm:px-6 lg:grid-cols-[1.2fr_1fr]">
      <div className="flex flex-col gap-5">
        {service.image_url ? (
          <img src={service.image_url} alt="" className="h-64 w-full rounded-3xl object-cover" />
        ) : (
          <div className="flex h-64 items-center justify-center rounded-3xl bg-brand-soft text-brand-strong">
            <Icon name="wrench" size={56} />
          </div>
        )}
        <div className="flex flex-col gap-2">
          <h1 className="m-0 text-3xl font-bold">{service.name_bn}</h1>
          <p className="m-0 text-lg leading-relaxed text-muted">{service.description}</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          {[
            ["shield", `${service.warranty_days} দিনের ওয়ারেন্টি`, "কাজে সমস্যা হলে ফ্রি রি-ওয়ার্ক"],
            ["check", "যাচাইকৃত প্রোভাইডার", "NID ও দক্ষতা যাচাই করা"],
            ["clock", `প্রায় ${service.duration_minutes} মিনিট`, "সময়মতো পৌঁছানোর নিশ্চয়তা"],
          ].map(([icon, title, body]) => (
            <Card key={title} className="flex flex-col gap-1 p-4">
              <Icon name={icon as "shield"} className="text-brand" />
              <span className="font-semibold">{title}</span>
              <span className="text-sm text-muted">{body}</span>
            </Card>
          ))}
        </div>
      </div>

      <Card className="flex h-fit flex-col gap-4 lg:sticky lg:top-24">
        <div className="flex items-baseline justify-between">
          <span className="text-muted">শুরু</span>
          <span className="text-2xl font-bold">{formatTaka(service.base_price)}</span>
        </div>
        {service.price_note && <p className="m-0 text-sm text-muted">{service.price_note}</p>}
        {emergency && (
          <p className="m-0 rounded-xl bg-alert-soft px-3 py-2 text-sm font-semibold text-alert-strong">জরুরি বুকিং: কাছের অনলাইন প্রোভাইডারদের এখনই জানানো হবে।</p>
        )}

        <div className="flex flex-col gap-1.5">
          <label htmlFor="date" className="text-[15px] font-semibold">
            তারিখ
          </label>
          <input id="date" type="date" min={todayISO()} value={date} onChange={(e) => setDate(e.target.value)} className="h-11 rounded-xl border border-line px-3" />
        </div>

        <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
          <legend className="mb-2 text-[15px] font-semibold">সময়</legend>
          <div className="grid grid-cols-3 gap-2">
            {SLOTS.map((s) => (
              <button
                key={s.value}
                type="button"
                aria-pressed={slot === s.value}
                onClick={() => setSlot(s.value)}
                className={`h-11 rounded-xl border text-sm font-semibold ${slot === s.value ? "border-brand bg-brand text-white" : "border-line bg-surface"}`}
              >
                {s.label}
              </button>
            ))}
          </div>
        </fieldset>

        <TextArea label="সমস্যা লিখুন" placeholder="যেমন: বেডরুমের ফ্যান ঘুরছে না" value={problem} onChange={(e) => setProblem(e.target.value)} />
        <PhotoUpload label="সমস্যার ছবি (ঐচ্ছিক)" value={photos} onChange={setPhotos} purpose="problem_photo" max={3} />

        <ErrorNote>{error}</ErrorNote>
        <Button onClick={book} loading={addToCart.isPending} className="h-12 text-base" variant={emergency ? "alert" : "primary"}>
          কার্টে যোগ করুন
        </Button>
        <span className="flex items-center gap-2 text-sm text-muted">
          <Icon name="money" size={16} /> ক্যাশ অন ডেলিভারি · কাজ শেষে টাকা দিন
        </span>
      </Card>
    </section>
  );
}
