import { LEGAL_PRIVACY, LEGAL_TERMS, PageHeader, getLang, t, type LegalSection } from "@shohor/web-core";

function LegalPage({ title, sections }: { title: string; sections: LegalSection[] }) {
  const lang = getLang();
  return (
    <section className="mx-auto flex max-w-[760px] flex-col gap-5 px-4 py-8 sm:px-6">
      <PageHeader title={title} subtitle={t("সংস্করণ {v}", { v: "2026-10" })} />
      {sections.map((s) => (
        <div key={s.title.en} className="flex flex-col gap-1.5">
          <h2 className="m-0 text-lg font-bold">{s.title[lang]}</h2>
          <p className="m-0 leading-relaxed text-muted">{s.body[lang]}</p>
        </div>
      ))}
    </section>
  );
}

export function Privacy() {
  return <LegalPage title={t("প্রাইভেসি নীতি")} sections={LEGAL_PRIVACY} />;
}

export function Terms() {
  return <LegalPage title={t("ব্যবহারের শর্ত")} sections={LEGAL_TERMS} />;
}
