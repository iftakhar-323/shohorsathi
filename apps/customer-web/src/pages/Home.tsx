import { Icon, t, type IconName, useServices } from "@shohor/web-core";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ServiceCard } from "./Services";

const quickSearches = ["ইলেকট্রিশিয়ান", "প্লাম্বার", "এসি সার্ভিস", "হোম ক্লিনিং", "পেস্ট কন্ট্রোল"];
const emergencies = [
  { label: "গ্যাস লিক", category: "plumbing" },
  { label: "শর্ট সার্কিট", category: "electrical" },
  { label: "পাইপ ফেটেছে", category: "plumbing" },
  { label: "বিদ্যুৎ নেই", category: "electrical" },
];

const layers: { to: string; icon: IconName; title: string; body: string; tone: string }[] = [
  {
    to: "/shop",
    icon: "bag",
    title: "পণ্য কিনুন",
    body: "ঘরের দরকারি জিনিস, ইলেকট্রিক ও প্লাম্বিং সামগ্রী, লোকাল দোকানের পণ্য",
    tone: "bg-brand-soft text-brand-strong",
  },
  {
    to: "/services",
    icon: "wrench",
    title: "সার্ভিস বুক করুন",
    body: "ফিক্সড দাম, যাচাইকৃত প্রোভাইডার, ৭–৩০ দিনের কাজের ওয়ারেন্টি",
    tone: "bg-brand-soft text-brand-strong",
  },
  {
    to: "/issues",
    icon: "flag",
    title: "সমস্যা রিপোর্ট করুন",
    body: "ময়লা, নষ্ট রাস্তার বাতি, জলাবদ্ধতা — ছবি আর লোকেশন দিয়ে জানান",
    tone: "bg-alert-soft text-alert-strong",
  },
];

export default function Home() {
  return (
    <>
      <Hero />
      <Layers />
      <PopularServices />
      <CustomRequestCta />
    </>
  );
}

function Hero() {
  const [query, setQuery] = useState("");
  const navigate = useNavigate();

  return (
    <section className="mx-auto flex max-w-[1200px] flex-wrap items-stretch gap-8 px-6 pt-12 pb-8">
      <div className="flex min-w-0 flex-[999_1_560px] flex-col justify-center gap-5">
        <span className="self-start rounded-full bg-brand-soft px-3.5 py-1.5 text-sm font-semibold text-brand-strong">
          {t("পণ্য · সার্ভিস · শহরের সমস্যা — এক অ্যাপে")}
        </span>
        <h1 className="m-0 text-4xl leading-tight font-bold tracking-tight sm:text-[52px]">
          {t("শহরের প্রতিদিনের সমস্যার")}
          <br />
          {t("ভরসাযোগ্য সমাধান")}
        </h1>
        <p className="m-0 max-w-[560px] text-lg leading-relaxed text-muted">
          {t("যাচাইকৃত ইলেকট্রিশিয়ান, প্লাম্বার, ক্লিনার — নির্দিষ্ট দামে। ঘরের দরকারি জিনিস কিনুন, আর এলাকার সমস্যা রিপোর্ট করুন।")}
        </p>

        <form
          role="search"
          className="flex max-w-[620px] gap-2 rounded-2xl border border-line bg-surface p-2"
          onSubmit={(e) => {
            e.preventDefault();
            navigate(`/services?q=${encodeURIComponent(query)}`);
          }}
        >
          <label htmlFor="hero-search" className="sr-only">
            {t("সার্ভিস বা পণ্য খুঁজুন")}
          </label>
          <input
            id="hero-search"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("কী সমস্যা? যেমন: ফ্যান চলছে না")}
            className="h-12 min-w-0 flex-auto bg-transparent px-3 text-[17px] outline-none"
          />
          <button
            type="button"
            aria-label={t("ভয়েস সার্চ")}
            className="flex size-12 items-center justify-center rounded-xl bg-brand-soft text-brand-strong"
          >
            <Icon name="mic" />
          </button>
          <button type="submit" className="h-12 rounded-xl bg-brand px-6 font-semibold text-white">
            {t("খুঁজুন")}
          </button>
        </form>

        <div className="flex flex-wrap gap-2">
          {quickSearches.map((label) => (
            <button
              key={label}
              type="button"
              onClick={() => navigate(`/services?q=${encodeURIComponent(t(label))}`)}
              className="rounded-full border border-line bg-surface px-4 py-2.5 text-[15px]"
            >
              {t(label)}
            </button>
          ))}
        </div>
      </div>

      <aside className="flex flex-[1_1_320px] flex-col gap-4 rounded-3xl bg-night p-7 text-white">
        <div className="flex items-center gap-2.5">
          <span className="flex size-10 items-center justify-center rounded-xl bg-alert text-ink">
            <Icon name="alert" size={22} />
          </span>
          <h2 className="m-0 text-[22px] font-bold">{t("জরুরি সাহায্য")}</h2>
        </div>
        <p className="m-0 leading-relaxed text-night-text">{t("এক ট্যাপে কাছের প্রোভাইডারকে অ্যালার্ট। প্রায়োরিটি চার্জ প্রযোজ্য।")}</p>
        <div className="grid grid-cols-2 gap-2.5">
          {emergencies.map((e) => (
            <Link
              key={e.label}
              to={`/services?category=${e.category}&emergency=1`}
              className="flex min-h-13 items-center justify-center rounded-2xl border border-night-line bg-night-raised text-[15px] font-medium text-white no-underline"
            >
              {t(e.label)}
            </Link>
          ))}
        </div>
        <Link to="/services?emergency=1" className="mt-auto flex h-13 items-center justify-center rounded-2xl bg-alert text-[17px] font-bold text-ink no-underline">
          {t("এখনই সাহায্য চাই")}
        </Link>
      </aside>
    </section>
  );
}

function Layers() {
  return (
    <section className="mx-auto max-w-[1200px] px-6 pt-4 pb-10">
      <div className="grid grid-cols-[repeat(auto-fit,minmax(260px,1fr))] gap-4">
        {layers.map((layer) => (
          <Link
            key={layer.to}
            to={layer.to}
            className="flex flex-col gap-2.5 rounded-[20px] border border-line bg-surface p-6 text-ink no-underline"
          >
            <span className={`flex size-12 items-center justify-center rounded-[14px] ${layer.tone}`}>
              <Icon name={layer.icon} size={24} />
            </span>
            <span className="text-xl font-bold">{t(layer.title)}</span>
            <span className="text-[15px] leading-normal text-muted">{t(layer.body)}</span>
          </Link>
        ))}
      </div>
    </section>
  );
}

function PopularServices() {
  const { data, isPending, isError } = useServices();

  return (
    <section className="mx-auto flex max-w-[1200px] flex-col gap-5 px-6 pt-6 pb-10">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 className="m-0 text-3xl font-bold">{t("জনপ্রিয় সার্ভিস")}</h2>
        <Link to="/services" className="font-semibold text-brand">
          {t("সব সার্ভিস দেখুন")}
        </Link>
      </div>

      {isError && <p className="m-0 text-muted">{t("সার্ভিস লোড করা যায়নি। একটু পরে আবার চেষ্টা করুন।")}</p>}

      <div className="grid grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-4">
        {isPending &&
          Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="h-[280px] animate-pulse rounded-[20px] border border-line bg-surface" />
          ))}
        {data?.results.slice(0, 8).map((service) => <ServiceCard key={service.id} service={service} />)}
      </div>
    </section>
  );
}

function CustomRequestCta() {
  return (
    <section className="mx-auto max-w-[1200px] px-6 pb-12">
      <div className="flex flex-wrap items-center justify-between gap-6 rounded-3xl bg-brand-soft p-7">
        <div className="flex max-w-[640px] flex-col gap-2">
          <h2 className="m-0 text-2xl font-bold text-brand-strong">{t("ক্যাটালগে নেই? কাস্টম রিকোয়েস্ট পাঠান")}</h2>
          <p className="m-0 leading-relaxed text-brand-strong">
            {t("দেয়াল রং, বাসা বদল, বিয়েবাড়ি পরিষ্কার — লিখে পাঠান। অ্যাডমিন দেখে খরচের হিসাবসহ কোট দেবে।")}
          </p>
        </div>
        <Link
          to="/custom-requests/new"
          className="flex h-[50px] items-center rounded-2xl bg-brand px-6 font-semibold text-white no-underline"
        >
          {t("রিকোয়েস্ট পাঠান")}
        </Link>
      </div>
    </section>
  );
}
