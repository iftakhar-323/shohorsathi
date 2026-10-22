import { t } from "@shohor/web-core";
import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <section className="mx-auto flex max-w-[1200px] flex-col items-start gap-4 px-6 py-20">
      <h1 className="m-0 text-3xl font-bold">{t("পেজটি খুঁজে পাওয়া যায়নি")}</h1>
      <p className="m-0 text-muted">{t("লিংকটি ভুল অথবা পেজটি সরানো হয়েছে।")}</p>
      <Link to="/" className="font-semibold text-brand">
        {t("হোমে ফিরে যান")}
      </Link>
    </section>
  );
}
