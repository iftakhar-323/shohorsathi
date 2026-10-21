import { api, Badge, Button, Card, Empty, errorMessage, ErrorNote, Loading, Modal, PageHeader, t, useLang } from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { useProvider } from "../api";

type QuizQuestion = {
  q: { bn: string; en: string };
  options: { bn: string; en: string }[];
};

type TrainingModule = {
  id: number;
  slug: string;
  title_bn: string;
  title_en: string;
  body_bn: string;
  body_en: string;
  video_url: string;
  pass_percent: number;
  questions: QuizQuestion[];
  result: { score: number; passed: boolean; certificate_code: string; attempts: number } | null;
};

export default function Training() {
  const { lang } = useLang();
  const { data: provider } = useProvider();
  const qc = useQueryClient();

  const { data: modules, isPending } = useQuery({
    queryKey: ["provider-training"],
    queryFn: async () => (await api.get<TrainingModule[]>("/providers/training/")).data,
  });

  const [activeQuiz, setActiveQuiz] = useState<TrainingModule | null>(null);
  const [activeCert, setActiveCert] = useState<{ module: TrainingModule; code: string; score: number } | null>(null);

  if (isPending) return <Loading />;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t("প্রশিক্ষণ ও দক্ষতা সনদ")}
        subtitle={t("কুইজ পাস করে সার্টিফিকেশন নিন এবং গ্রাহকের আস্থা অর্জন করুন")}
      />

      {modules?.length === 0 ? (
        <Empty icon="sparkle" title={t("বর্তমানে কোনো প্রশিক্ষণ মডিউল উপলব্ধ নেই")} />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {modules?.map((m) => {
            const title = lang === "en" ? m.title_en || m.title_bn : m.title_bn || m.title_en;
            const body = lang === "en" ? m.body_en || m.body_bn : m.body_bn || m.body_en;
            const res = m.result;

            return (
              <Card key={m.id} className="flex flex-col justify-between gap-4 p-5">
                <div className="flex flex-col gap-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-xs font-semibold uppercase tracking-wider text-muted">{m.slug}</span>
                    {res?.passed ? (
                      <Badge tone="ok">{t("উত্তীর্ণ")} ({res.score}%)</Badge>
                    ) : res ? (
                      <Badge tone="bad">{t("অকৃতকার্য")} ({res.score}%)</Badge>
                    ) : (
                      <Badge tone="muted">{t("নতুন")}</Badge>
                    )}
                  </div>
                  <h3 className="m-0 text-lg font-bold">{title}</h3>
                  {body && <p className="m-0 text-sm text-muted whitespace-pre-line">{body}</p>}
                  {m.video_url && (
                    <a
                      href={m.video_url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-1 self-start text-sm font-semibold text-brand-strong"
                    >
                      {t("টিউটোরিয়াল ভিডিও দেখুন")}
                    </a>
                  )}
                  <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted">
                    <span>{t("প্রশ্ন সংখ্যা:")} {m.questions.length}</span>
                    <span>·</span>
                    <span>{t("পাস মার্ক:")} {m.pass_percent}%</span>
                    {res && (
                      <>
                        <span>·</span>
                        <span>{t("চেষ্টা:")} {res.attempts} {t("বার")}</span>
                      </>
                    )}
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2 pt-2">
                  {res?.passed ? (
                    <Button
                      variant="secondary"
                      icon="sparkle"
                      onClick={() => setActiveCert({ module: m, code: res.certificate_code, score: res.score })}
                    >
                      {t("সার্টিফিকেট দেখুন")}
                    </Button>
                  ) : res ? (
                    <Button onClick={() => setActiveQuiz(m)}>
                      {t("আবার পরীক্ষা দিন")}
                    </Button>
                  ) : (
                    <Button onClick={() => setActiveQuiz(m)}>
                      {t("পরীক্ষা শুরু করুন")}
                    </Button>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {activeQuiz && (
        <QuizModal
          module={activeQuiz}
          onClose={() => {
            setActiveQuiz(null);
            qc.invalidateQueries({ queryKey: ["provider-training"] });
            qc.invalidateQueries({ queryKey: ["provider-me"] });
          }}
        />
      )}

      {activeCert && (
        <CertificateModal
          cert={activeCert}
          providerName={provider?.full_name ?? ""}
          onClose={() => setActiveCert(null)}
        />
      )}
    </div>
  );
}

function QuizModal({ module, onClose }: { module: TrainingModule; onClose: () => void }) {
  const { lang } = useLang();
  const [answers, setAnswers] = useState<number[]>(new Array(module.questions.length).fill(-1));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ score: number; passed: boolean; certificate_code: string } | null>(null);

  const title = lang === "en" ? module.title_en || module.title_bn : module.title_bn || module.title_en;

  function selectOption(qIdx: number, oIdx: number) {
    const next = [...answers];
    next[qIdx] = oIdx;
    setAnswers(next);
  }

  async function handleSubmit() {
    if (answers.some((a) => a === -1)) {
      setError(t("অনুগ্রহ করে সব প্রশ্নের উত্তর দিন।"));
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      const res = await api.post<{ score: number; passed: boolean; certificate_code: string; attempts: number }>(
        `/providers/training/${module.slug}/submit/`,
        { answers }
      );
      setResult(res.data);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal title={title} open onClose={onClose}>
      <div className="flex flex-col gap-5">
        {result ? (
          <div className="flex flex-col items-center gap-3 py-4 text-center">
            {result.passed ? (
              <>
                <span className="text-4xl">🎉</span>
                <h3 className="m-0 text-xl font-bold text-ok-strong">{t("অভিনন্দন! আপনি উত্তীর্ণ হয়েছেন")}</h3>
                <p className="m-0 text-muted">
                  {t("আপনার প্রাপ্ত স্কোর:")} {result.score}% ({t("পাস মার্ক:")} {module.pass_percent}%)
                </p>
                <div className="my-2 rounded-xl bg-subtle p-3 text-sm">
                  {t("আপনার সার্টিফিকেট কোড:")} <strong>{result.certificate_code}</strong>
                </div>
                <Button onClick={onClose}>{t("সম্পন্ন করুন")}</Button>
              </>
            ) : (
              <>
                <span className="text-4xl">⚠️</span>
                <h3 className="m-0 text-xl font-bold text-bad-strong">{t("আপনি উত্তীর্ণ হতে পারেননি")}</h3>
                <p className="m-0 text-muted">
                  {t("আপনার প্রাপ্ত স্কোর:")} {result.score}% ({t("পাস মার্ক:")} {module.pass_percent}%)
                </p>
                <div className="flex gap-2">
                  <Button
                    onClick={() => {
                      setResult(null);
                      setAnswers(new Array(module.questions.length).fill(-1));
                    }}
                  >
                    {t("আবার চেষ্টা করুন")}
                  </Button>
                  <Button variant="ghost" onClick={onClose}>{t("বন্ধ করুন")}</Button>
                </div>
              </>
            )}
          </div>
        ) : (
          <>
            <p className="m-0 text-sm text-muted">
              {t("পাস করতে হলে কমপক্ষে {percent}% সঠিক উত্তর দিতে হবে।", { percent: module.pass_percent })}
            </p>

            <div className="flex flex-col gap-6">
              {module.questions.map((q, qIdx) => {
                const questionText = lang === "en" ? q.q.en || q.q.bn : q.q.bn || q.q.en;
                return (
                  <div key={qIdx} className="flex flex-col gap-2 rounded-xl border border-line p-4">
                    <span className="font-semibold">
                      {qIdx + 1}. {questionText}
                    </span>
                    <div className="flex flex-col gap-2 pt-1">
                      {q.options.map((opt, oIdx) => {
                        const optText = lang === "en" ? opt.en || opt.bn : opt.bn || opt.en;
                        const isSelected = answers[qIdx] === oIdx;
                        return (
                          <label
                            key={oIdx}
                            className={`flex cursor-pointer items-center gap-3 rounded-lg border p-2.5 text-sm transition-colors ${
                              isSelected ? "border-brand bg-brand-soft font-semibold text-brand-strong" : "border-line bg-surface hover:bg-subtle"
                            }`}
                          >
                            <input
                              type="radio"
                              name={`q-${qIdx}`}
                              checked={isSelected}
                              onChange={() => selectOption(qIdx, oIdx)}
                              className="size-4 accent-brand"
                            />
                            <span>{optText}</span>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>

            <ErrorNote>{error}</ErrorNote>

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="ghost" onClick={onClose}>{t("বাতিল")}</Button>
              <Button loading={submitting} onClick={handleSubmit}>
                {t("উত্তর জমা দিন")}
              </Button>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}

function CertificateModal({
  cert,
  providerName,
  onClose,
}: {
  cert: { module: TrainingModule; code: string; score: number };
  providerName: string;
  onClose: () => void;
}) {
  const { lang } = useLang();
  const moduleTitle = lang === "en" ? cert.module.title_en || cert.module.title_bn : cert.module.title_bn || cert.module.title_en;

  return (
    <Modal title={t("প্রশিক্ষণ সনদপত্র")} open onClose={onClose}>
      <div className="flex flex-col gap-4">
        <div className="relative flex flex-col items-center gap-3 rounded-2xl border-4 border-double border-brand bg-surface p-6 text-center shadow-sm">
          <div className="flex items-center gap-2">
            <span className="text-xl font-bold text-brand-strong">{t("শহরসাথী")}</span>
            <span className="rounded-full bg-brand-soft px-2 py-0.5 text-xs font-semibold text-brand-strong">
              {t("ভেরিফায়েড পার্টনার")}
            </span>
          </div>

          <h2 className="m-0 text-xl font-bold">{t("প্রশিক্ষণ সনদ")}</h2>
          <p className="m-0 text-xs tracking-wider text-muted uppercase">{t("সনদ নম্বর:")} {cert.code}</p>

          <div className="my-2 flex flex-col items-center gap-1">
            <span className="text-sm text-muted">{t("এই মর্মে প্রত্যয়ন করা যাচ্ছে যে")}</span>
            <span className="text-xl font-bold text-ink">{providerName}</span>
            <span className="text-sm text-muted">{t("সফলভাবে সমাপ্ত করেছেন")}</span>
            <span className="text-base font-semibold text-brand-strong">{moduleTitle}</span>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-4 text-xs text-muted">
            <span>{t("প্রাপ্ত নম্বর:")} <strong>{cert.score}%</strong></span>
            <span>·</span>
            <span>{t("অনলাইন যাচাই:")} <code>{cert.code}</code></span>
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="ghost" onClick={onClose}>{t("বন্ধ করুন")}</Button>
          <Button onClick={() => window.print()}>{t("প্রিন্ট করুন")}</Button>
        </div>
      </div>
    </Modal>
  );
}
