import { Empty, ErrorNote, formatTaka, Icon, Loading, localName, PageHeader, Select, t, type Service, useAreas, useCategories, useServices } from "@shohor/web-core";
import { Link, useSearchParams } from "react-router-dom";

import { useSelectedArea } from "../lib/area";

export function ServiceCard({ service, emergency = false }: { service: Service; emergency?: boolean }) {
  return (
    <article className="flex flex-col overflow-hidden rounded-[20px] border border-line bg-surface">
      {service.image_url ? (
        <img src={service.image_url} alt="" className="h-[132px] w-full object-cover" />
      ) : (
        <div className="flex h-[132px] items-center justify-center bg-brand-soft text-brand-strong">
          <Icon name="wrench" size={36} />
        </div>
      )}
      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex flex-wrap items-center gap-1.5 text-[13px] font-semibold text-brand-strong">
          <Icon name="shield" size={14} />
          {service.warranty_days} {t("দিনের ওয়ারেন্টি")}
          {service.emergency_available && <span className="rounded-full bg-alert-soft px-2 text-alert-strong">{t("জরুরি সেবা")}</span>}
        </div>
        <h3 className="m-0 text-lg font-bold">{localName(service)}</h3>
        <p className="m-0 line-clamp-2 text-sm leading-normal text-muted">{service.description}</p>
        <div className="mt-auto flex items-center justify-between gap-2 pt-2">
          <span className="font-bold">{formatTaka(service.base_price)} {t("থেকে")}</span>
          <Link
            to={`/services/${service.slug}${emergency ? "?emergency=1" : ""}`}
            className="flex h-11 items-center rounded-xl border border-brand px-4 text-[15px] font-semibold text-brand-strong no-underline"
          >
            {t("বুক করুন")}
          </Link>
        </div>
      </div>
    </article>
  );
}

export default function Services() {
  const [params, setParams] = useSearchParams();
  const [area, setArea] = useSelectedArea();
  const { data: areas } = useAreas();
  const { data: categories } = useCategories("service");
  const q = params.get("q") ?? "";
  const category = params.get("category") ?? "";
  const ordering = params.get("ordering") ?? "";
  const { data, isPending, isError } = useServices({
    q: q || undefined,
    category: category || undefined,
    ordering: ordering || undefined,
    area,
    emergency: params.get("emergency") ?? undefined,
  });

  function set(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  }

  return (
    <section className="mx-auto flex max-w-[1200px] flex-col gap-6 px-4 py-8 sm:px-6">
      <PageHeader title={t("সার্ভিস")} subtitle={t("নির্দিষ্ট দাম, যাচাইকৃত প্রোভাইডার, কাজের ওয়ারেন্টি")} />

      <div className="grid gap-3 rounded-[20px] border border-line bg-surface p-4 sm:grid-cols-[2fr_1fr_1fr]">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="q" className="text-[15px] font-semibold">
            {t("খুঁজুন")}
          </label>
          <input
            id="q"
            type="search"
            defaultValue={q}
            placeholder={t("যেমন: ফ্যান, পাইপ, এসি")}
            onKeyDown={(e) => e.key === "Enter" && set("q", e.currentTarget.value)}
            onBlur={(e) => set("q", e.currentTarget.value)}
            className="h-11 rounded-xl border border-line px-3 outline-none focus:border-brand"
          />
        </div>
        <Select
          label={t("এলাকা")}
          value={area ?? ""}
          onChange={(e) => setArea(e.target.value ? Number(e.target.value) : undefined)}
          options={[{ value: "", label: t("সব এলাকা") }, ...(areas ?? []).map((a) => ({ value: a.id, label: localName(a) }))]}
        />
        <Select
          label={t("সাজান")}
          value={ordering}
          onChange={(e) => set("ordering", e.target.value)}
          options={[
            { value: "", label: t("নতুন আগে") },
            { value: "price", label: t("দাম: কম থেকে বেশি") },
            { value: "-price", label: t("দাম: বেশি থেকে কম") },
          ]}
        />
      </div>

      <div className="flex flex-wrap gap-2">
        {[{ slug: "", name_bn: t("সব"), name_en: t("সব") }, ...(categories ?? [])].map((c) => (
          <button
            key={c.slug}
            type="button"
            onClick={() => set("category", c.slug)}
            className={`h-11 rounded-full border px-4 text-[15px] ${category === c.slug ? "border-brand bg-brand text-white" : "border-line bg-surface"}`}
          >
            {localName(c)}
          </button>
        ))}
      </div>

      {isPending && <Loading />}
      {isError && <ErrorNote>{t("সার্ভিস লোড করা যায়নি।")}</ErrorNote>}
      {data && data.results.length === 0 && (
        <Empty icon="wrench" title={t("কোনো সার্ভিস পাওয়া যায়নি")}>
          {t("অন্য কিছু খুঁজুন, অথবা")} <Link to="/custom-requests/new">{t("কাস্টম রিকোয়েস্ট")}</Link> {t("পাঠান।")}
        </Empty>
      )}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-4">
        {data?.results.map((s) => <ServiceCard key={s.id} service={s} emergency={params.get("emergency") === "1"} />)}
      </div>
    </section>
  );
}
