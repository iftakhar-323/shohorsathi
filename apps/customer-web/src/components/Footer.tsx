import { t } from "@shohor/web-core";
export default function Footer() {
  return (
    <footer className="bg-night text-night-text">
      <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-5 px-6 py-10">
        <div className="flex flex-col gap-1.5">
          <span className="text-[22px] font-bold text-white">{t("আপনি কি দক্ষ কারিগর বা হোম শেফ?")}</span>
          <span>{t("শহরসাথীতে যোগ দিন, নিজের সময়ে কাজ করুন, সাপ্তাহিক পেমেন্ট বিকাশ/নগদে।")}</span>
        </div>
        <a href="/provider" className="rounded-2xl bg-white px-6 py-3.5 font-bold text-ink no-underline">
          {t("প্রোভাইডার হিসেবে যোগ দিন")}
        </a>
      </div>
      <div className="mx-auto flex max-w-[1200px] gap-5 px-6 pb-8 text-sm">
        <a href="/privacy" className="text-night-text">{t("প্রাইভেসি নীতি")}</a>
        <a href="/terms" className="text-night-text">{t("ব্যবহারের শর্ত")}</a>
      </div>
    </footer>
  );
}
