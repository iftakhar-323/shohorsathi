import { api, Badge, Button, errorMessage, ErrorNote, Field, Modal, PageHeader, Select, t, TextArea, useCategories, localName } from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { DataTable } from "../components";

type QuizQuestion = {
  q: { bn: string; en: string };
  options: { bn: string; en: string }[];
  answer: number;
};

type TrainingModule = {
  id: number;
  slug: string;
  title_bn: string;
  title_en: string;
  body_bn: string;
  body_en: string;
  video_url: string;
  category_slug: string;
  questions: QuizQuestion[];
  pass_percent: number;
  is_active: boolean;
  sort_order: number;
};

export default function Training() {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<TrainingModule | null>(null);
  const [creating, setCreating] = useState(false);

  const { data: modules, isPending } = useQuery({
    queryKey: ["admin-training-modules"],
    queryFn: async () => (await api.get<TrainingModule[]>("/admin/training-modules/")).data,
  });

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t("ট্রেনিং মডিউল এডিটর")}
        subtitle={t("প্রোভাইডারদের জন্য প্রশিক্ষণ পাঠ্যক্রম ও কুইজ প্রশ্ন তৈরি এবং পরিচালনা")}
        actions={
          <Button icon="plus" onClick={() => setCreating(true)}>
            {t("নতুন মডিউল তৈরি করুন")}
          </Button>
        }
      />

      <DataTable
        loading={isPending}
        rows={modules}
        onRowClick={(row) => setEditing(row)}
        columns={[
          { label: t("স্লাগ"), render: (m) => <code className="text-xs">{m.slug}</code> },
          {
            label: t("শিরোনাম"),
            render: (m) => (
              <div className="flex flex-col">
                <span className="font-semibold">{m.title_bn}</span>
                <span className="text-xs text-muted">{m.title_en}</span>
              </div>
            ),
          },
          {
            label: t("ক্যাটাগরি"),
            render: (m) => m.category_slug ? <Badge>{m.category_slug}</Badge> : <Badge tone="muted">{t("সবার জন্য")}</Badge>,
          },
          { label: t("পাস মার্ক"), render: (m) => `${m.pass_percent}%` },
          { label: t("প্রশ্ন সংখ্যা"), render: (m) => m.questions.length },
          {
            label: t("অবস্থা"),
            render: (m) => (
              <Badge tone={m.is_active ? "ok" : "muted"}>
                {m.is_active ? t("সক্রিয়") : t("নিষ্ক্রিয়")}
              </Badge>
            ),
          },
        ]}
      />

      {(creating || editing) && (
        <ModuleFormModal
          module={editing}
          onClose={() => {
            setCreating(false);
            setEditing(null);
          }}
          onSaved={() => {
            setCreating(false);
            setEditing(null);
            qc.invalidateQueries({ queryKey: ["admin-training-modules"] });
          }}
        />
      )}
    </div>
  );
}

function ModuleFormModal({
  module,
  onClose,
  onSaved,
}: {
  module: TrainingModule | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { data: categories } = useCategories("service");
  const isNew = !module;

  const [slug, setSlug] = useState(module?.slug ?? "");
  const [titleBn, setTitleBn] = useState(module?.title_bn ?? "");
  const [titleEn, setTitleEn] = useState(module?.title_en ?? "");
  const [bodyBn, setBodyBn] = useState(module?.body_bn ?? "");
  const [bodyEn, setBodyEn] = useState(module?.body_en ?? "");
  const [videoUrl, setVideoUrl] = useState(module?.video_url ?? "");
  const [categorySlug, setCategorySlug] = useState(module?.category_slug ?? "");
  const [passPercent, setPassPercent] = useState(module?.pass_percent ?? 70);
  const [sortOrder, setSortOrder] = useState(module?.sort_order ?? 0);
  const [isActive, setIsActive] = useState(module?.is_active ?? true);

  const [questions, setQuestions] = useState<QuizQuestion[]>(
    module?.questions?.length
      ? module.questions
      : [
          {
            q: { bn: "", en: "" },
            options: [
              { bn: "", en: "" },
              { bn: "", en: "" },
            ],
            answer: 0,
          },
        ]
  );

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  function addQuestion() {
    setQuestions([
      ...questions,
      {
        q: { bn: "", en: "" },
        options: [
          { bn: "", en: "" },
          { bn: "", en: "" },
        ],
        answer: 0,
      },
    ]);
  }

  function removeQuestion(idx: number) {
    setQuestions(questions.filter((_, i) => i !== idx));
  }

  function updateQuestionText(idx: number, lang: "bn" | "en", text: string) {
    const next = [...questions];
    next[idx] = { ...next[idx], q: { ...next[idx].q, [lang]: text } };
    setQuestions(next);
  }

  function addOption(qIdx: number) {
    const next = [...questions];
    next[qIdx] = { ...next[qIdx], options: [...next[qIdx].options, { bn: "", en: "" }] };
    setQuestions(next);
  }

  function removeOption(qIdx: number, oIdx: number) {
    const next = [...questions];
    const opts = next[qIdx].options.filter((_, i) => i !== oIdx);
    const ans = next[qIdx].answer >= opts.length ? Math.max(0, opts.length - 1) : next[qIdx].answer;
    next[qIdx] = { ...next[qIdx], options: opts, answer: ans };
    setQuestions(next);
  }

  function updateOptionText(qIdx: number, oIdx: number, lang: "bn" | "en", text: string) {
    const next = [...questions];
    const opts = [...next[qIdx].options];
    opts[oIdx] = { ...opts[oIdx], [lang]: text };
    next[qIdx] = { ...next[qIdx], options: opts };
    setQuestions(next);
  }

  function setAnswer(qIdx: number, ansIdx: number) {
    const next = [...questions];
    next[qIdx] = { ...next[qIdx], answer: ansIdx };
    setQuestions(next);
  }

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    if (!slug.trim()) {
      setError(t("অনুগ্রহ করে স্লাগ লিখুন।"));
      return;
    }
    for (let i = 0; i < questions.length; i++) {
      const q = questions[i];
      if (!q.q.bn.trim() && !q.q.en.trim()) {
        setError(t("প্রশ্ন #{num}-এর লেখা দিন।", { num: i + 1 }));
        return;
      }
      if (q.options.length < 2) {
        setError(t("প্রশ্ন #{num}-এ কমপক্ষে ২টি বিকল্প থাকতে হবে।", { num: i + 1 }));
        return;
      }
    }

    setError("");
    setSubmitting(true);
    const payload = {
      slug: slug.trim(),
      title_bn: titleBn,
      title_en: titleEn,
      body_bn: bodyBn,
      body_en: bodyEn,
      video_url: videoUrl,
      category_slug: categorySlug,
      questions,
      pass_percent: Number(passPercent),
      is_active: isActive,
      sort_order: Number(sortOrder),
    };

    try {
      if (isNew) {
        await api.post("/admin/training-modules/", payload);
      } else {
        await api.patch(`/admin/training-modules/${module.slug}/`, payload);
      }
      onSaved();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete() {
    if (!module || !confirm(t("আপনি কি এই মডিউলটি মুছে ফেলতে চান?"))) return;
    setSubmitting(true);
    try {
      await api.delete(`/admin/training-modules/${module.slug}/`);
      onSaved();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      title={isNew ? t("নতুন ট্রেনিং মডিউল") : t("ট্রেনিং মডিউল সম্পাদনা")}
      open
      onClose={onClose}
    >
      <form onSubmit={handleSave} className="flex flex-col gap-5 max-h-[80vh] overflow-y-auto px-1">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field
            label={t("স্লাগ (ইউনিক আইডি)")}
            required
            disabled={!isNew}
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            placeholder="e.g. electrical-safety"
          />
          <Select
            label={t("প্রোভাইডার ক্যাটাগরি")}
            value={categorySlug}
            onChange={(e) => setCategorySlug(e.target.value)}
            options={[
              { value: "", label: t("সবার জন্য প্রযোজ্য") },
              ...(categories ?? []).map((c) => ({ value: c.slug, label: localName(c) })),
            ]}
          />
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <Field
            label={t("শিরোনাম (বাংলা)")}
            required
            value={titleBn}
            onChange={(e) => setTitleBn(e.target.value)}
            placeholder={t("যেমন: প্রাথমিক নিরাপত্তা ও আচরণবিধি")}
          />
          <Field
            label={t("শিরোনাম (ইংরেজি)")}
            required
            value={titleEn}
            onChange={(e) => setTitleEn(e.target.value)}
            placeholder="e.g. Safety & Conduct Protocol"
          />
        </div>

        <TextArea
          label={t("পাঠ্যক্রমের বিবরণ / নির্দেশিকা (বাংলা)")}
          rows={3}
          value={bodyBn}
          onChange={(e) => setBodyBn(e.target.value)}
          placeholder={t("কাজের সময় অবশ্যই সেফটি গ্লাভস ব্যবহার করতে হবে…")}
        />

        <TextArea
          label={t("পাঠ্যক্রমের বিবরণ / নির্দেশিকা (ইংরেজি)")}
          rows={3}
          value={bodyEn}
          onChange={(e) => setBodyEn(e.target.value)}
          placeholder="Always wear safety gloves when handling circuits..."
        />

        <div className="grid gap-3 sm:grid-cols-3">
          <Field
            label={t("ভিডিও টিউটোরিয়াল লিংক")}
            type="url"
            value={videoUrl}
            onChange={(e) => setVideoUrl(e.target.value)}
            placeholder="https://youtu.be/..."
          />
          <Field
            label={t("পাস মার্ক (%)")}
            type="number"
            min={10}
            max={100}
            required
            value={passPercent}
            onChange={(e) => setPassPercent(Number(e.target.value))}
          />
          <Field
            label={t("ক্রম (Sort Order)")}
            type="number"
            value={sortOrder}
            onChange={(e) => setSortOrder(Number(e.target.value))}
          />
        </div>

        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
            className="size-5 accent-brand"
          />
          <span className="font-semibold text-sm">{t("মডিউলটি সক্রিয় রাখুন")}</span>
        </label>

        {/* Question editor section */}
        <div className="flex flex-col gap-4 border-t border-line pt-4">
          <div className="flex items-center justify-between">
            <h4 className="m-0 text-base font-bold">{t("কুইজ প্রশ্নসমূহ")}</h4>
            <Button variant="ghost" type="button" icon="plus" onClick={addQuestion}>
              {t("নতুন প্রশ্ন যোগ করুন")}
            </Button>
          </div>

          {questions.map((q, qIdx) => (
            <div key={qIdx} className="flex flex-col gap-3 rounded-xl border border-line bg-subtle/50 p-4">
              <div className="flex items-center justify-between">
                <span className="font-bold text-sm text-brand-strong">{t("প্রশ্ন #{num}", { num: qIdx + 1 })}</span>
                {questions.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeQuestion(qIdx)}
                    className="text-xs text-bad-strong font-semibold hover:underline"
                  >
                    {t("প্রশ্ন মুছুন")}
                  </button>
                )}
              </div>

              <div className="grid gap-2 sm:grid-cols-2">
                <Field
                  label={t("প্রশ্ন (বাংলা)")}
                  value={q.q.bn}
                  onChange={(e) => updateQuestionText(qIdx, "bn", e.target.value)}
                  placeholder={t("যেমন: কাজের শুরুতে কী করা উচিত?")}
                />
                <Field
                  label={t("প্রশ্ন (ইংরেজি)")}
                  value={q.q.en}
                  onChange={(e) => updateQuestionText(qIdx, "en", e.target.value)}
                  placeholder="e.g. What is the first safety step?"
                />
              </div>

              <div className="flex flex-col gap-2 pt-1">
                <span className="text-xs font-semibold text-muted">
                  {t("বিকল্প উত্তরসমূহ (সঠিক উত্তরের পাশের রেডিও বোতাম চিহ্নিত করুন):")}
                </span>

                {q.options.map((opt, oIdx) => (
                  <div key={oIdx} className="flex items-center gap-2">
                    <input
                      type="radio"
                      name={`answer-q-${qIdx}`}
                      checked={q.answer === oIdx}
                      onChange={() => setAnswer(qIdx, oIdx)}
                      className="size-4 accent-brand cursor-pointer"
                      title={t("সঠিক উত্তর হিসেবে চিহ্নিত করুন")}
                    />
                    <div className="grid flex-1 gap-2 sm:grid-cols-2">
                      <input
                        type="text"
                        placeholder={t("বিকল্প (বাংলা)")}
                        value={opt.bn}
                        onChange={(e) => updateOptionText(qIdx, oIdx, "bn", e.target.value)}
                        className="h-9 rounded-lg border border-line bg-surface px-2.5 text-sm"
                      />
                      <input
                        type="text"
                        placeholder="Option (English)"
                        value={opt.en}
                        onChange={(e) => updateOptionText(qIdx, oIdx, "en", e.target.value)}
                        className="h-9 rounded-lg border border-line bg-surface px-2.5 text-sm"
                      />
                    </div>
                    {q.options.length > 2 && (
                      <button
                        type="button"
                        onClick={() => removeOption(qIdx, oIdx)}
                        className="text-muted hover:text-bad-strong px-1"
                        title={t("বিকল্প মুছুন")}
                      >
                        ✕
                      </button>
                    )}
                  </div>
                ))}

                <button
                  type="button"
                  onClick={() => addOption(qIdx)}
                  className="self-start text-xs font-semibold text-brand-strong hover:underline pt-1"
                >
                  {t("+ আরেকটি বিকল্প যোগ করুন")}
                </button>
              </div>
            </div>
          ))}
        </div>

        <ErrorNote>{error}</ErrorNote>

        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line pt-4">
          {!isNew ? (
            <Button variant="danger" type="button" onClick={handleDelete} loading={submitting}>
              {t("মডিউল মুছুন")}
            </Button>
          ) : <span />}

          <div className="flex gap-2">
            <Button variant="ghost" type="button" onClick={onClose}>{t("বাতিল")}</Button>
            <Button loading={submitting} type="submit">
              {t("সংরক্ষণ করুন")}
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  );
}
