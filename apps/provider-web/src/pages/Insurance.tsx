import { api, Badge, Button, Card, Empty, errorMessage, ErrorNote, formatDate, formatTaka, Loading, Modal, PageHeader, PhotoUpload, StatusBadge, SuccessNote, t, TextArea, useLang } from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

type InsurancePlan = {
  id: number;
  name_bn: string;
  name_en: string;
  partner: string;
  weekly_premium: string;
  coverage_bn: string;
  coverage_en: string;
  is_active: boolean;
};

type Enrollment = {
  id: number;
  plan: InsurancePlan;
  provider_name: string;
  status: string;
  last_premium_week: string;
  started_at: string;
};

type InsuranceClaim = {
  id: number;
  provider_name: string;
  plan_name: string;
  description: string;
  photo_urls: string[];
  status: "submitted" | "forwarded" | "paid" | "rejected";
  amount: string | null;
  note: string;
  created_at: string;
};

type InsuranceResponse = {
  plans: InsurancePlan[];
  enrollment: Enrollment | null;
  claims: InsuranceClaim[];
};

export default function Insurance() {
  const { lang } = useLang();
  const qc = useQueryClient();

  const { data, isPending } = useQuery({
    queryKey: ["provider-insurance"],
    queryFn: async () => (await api.get<InsuranceResponse>("/providers/insurance/")).data,
  });

  const [claimOpen, setClaimOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  if (isPending) return <Loading />;

  const enrollment = data?.enrollment;
  const isEnrolled = enrollment && enrollment.status === "active";

  async function handleEnroll(planId: number) {
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await api.post("/providers/insurance/", { plan: planId });
      setSuccess(t("বিমায় সফলভাবে যুক্ত হয়েছেন।"));
      qc.invalidateQueries({ queryKey: ["provider-insurance"] });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleCancel() {
    if (!confirm(t("আপনি কি সত্যিই বিমা বাতিল করতে চান?"))) return;
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await api.delete("/providers/insurance/");
      setSuccess(t("বিমা বাতিল করা হয়েছে।"));
      qc.invalidateQueries({ queryKey: ["provider-insurance"] });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t("সুরক্ষা বিমা")}
        subtitle={t("কাজের সময় দুর্ঘটনা ও স্বাস্থ্য সুরক্ষায় পার্টনারদের জন্য বিশেষ বিমা")}
      />

      <SuccessNote>{success}</SuccessNote>
      <ErrorNote>{error}</ErrorNote>

      {/* Active enrollment or available plans */}
      {isEnrolled ? (
        <Card className="flex flex-col gap-4 border-2 border-brand bg-surface p-6">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Badge tone="ok">{t("বর্তমান সক্রিয় বিমা")}</Badge>
              <span className="text-sm text-muted">{t("সহযোগী:")} {enrollment.plan.partner}</span>
            </div>
            <span className="text-sm text-muted">
              {t("শুরুর তারিখ:")} {formatDate(enrollment.started_at)}
            </span>
          </div>

          <div className="flex flex-col gap-1">
            <h2 className="m-0 text-xl font-bold">
              {lang === "en" ? enrollment.plan.name_en || enrollment.plan.name_bn : enrollment.plan.name_bn || enrollment.plan.name_en}
            </h2>
            <span className="text-lg font-semibold text-brand-strong">
              {formatTaka(enrollment.plan.weekly_premium)} / {t("সপ্তাহ")}
            </span>
            <p className="m-0 text-sm text-muted">
              {t("প্রতি সপ্তাহে উপার্জনের পেআউট থেকে প্রিমিয়াম সমন্বয় করা হয়।")}
            </p>
          </div>

          <div className="rounded-xl bg-subtle p-4">
            <h4 className="m-0 mb-2 font-semibold">{t("কভারেজ সুবিধা:")}</h4>
            <p className="m-0 text-sm whitespace-pre-line">
              {lang === "en" ? enrollment.plan.coverage_en || enrollment.plan.coverage_bn : enrollment.plan.coverage_bn || enrollment.plan.coverage_en}
            </p>
          </div>

          <div className="flex flex-wrap gap-3 pt-2">
            <Button icon="plus" onClick={() => setClaimOpen(true)}>
              {t("ক্লেইম জমা দিন")}
            </Button>
            <Button variant="danger" loading={busy} onClick={handleCancel}>
              {t("বিমা বাতিল করুন")}
            </Button>
          </div>
        </Card>
      ) : (
        <div className="flex flex-col gap-4">
          <h2 className="m-0 text-lg font-bold">{t("উপলব্ধ বিমা প্ল্যানসমূহ")}</h2>
          <div className="grid gap-4 md:grid-cols-2">
            {data?.plans.map((p) => {
              const name = lang === "en" ? p.name_en || p.name_bn : p.name_bn || p.name_en;
              const coverage = lang === "en" ? p.coverage_en || p.coverage_bn : p.coverage_bn || p.coverage_en;
              return (
                <Card key={p.id} className="flex flex-col justify-between gap-4 p-5">
                  <div className="flex flex-col gap-2">
                    <div className="flex items-center justify-between">
                      <h3 className="m-0 text-lg font-bold">{name}</h3>
                      <span className="text-sm font-semibold text-brand-strong">
                        {formatTaka(p.weekly_premium)} / {t("সপ্তাহ")}
                      </span>
                    </div>
                    <span className="text-xs font-semibold text-muted">{t("সহযোগী:")} {p.partner}</span>
                    <p className="m-0 text-sm text-muted whitespace-pre-line">{coverage}</p>
                  </div>
                  <Button
                    loading={busy}
                    onClick={() => handleEnroll(p.id)}
                    className="self-start"
                  >
                    {t("যুক্ত হন")}
                  </Button>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {/* Claims History */}
      <div className="flex flex-col gap-3 pt-4">
        <h2 className="m-0 text-lg font-bold">{t("ক্লেইমের ইতিহাস")}</h2>
        {!data?.claims.length ? (
          <Empty icon="shield" title={t("এখনো কোনো ক্লেইম জমা দেওয়া হয়নি")} />
        ) : (
          <div className="flex flex-col gap-3">
            {data.claims.map((c) => (
              <Card key={c.id} className="flex flex-col gap-3 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <StatusBadge status={c.status} />
                    <span className="font-semibold">{c.plan_name}</span>
                  </div>
                  <span className="text-xs text-muted">{formatDate(c.created_at)}</span>
                </div>
                <p className="m-0 text-sm">{c.description}</p>
                {c.photo_urls.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {c.photo_urls.map((u) => (
                      <a key={u} href={u} target="_blank" rel="noreferrer">
                        <img src={u} alt={t("প্রমাণ ছবি")} className="size-16 rounded-lg object-cover" />
                      </a>
                    ))}
                  </div>
                )}
                {c.amount && (
                  <div className="text-sm font-bold text-ok-strong">
                    {t("পরিশোধিত ক্ষতিপূরণ:")} {formatTaka(c.amount)}
                  </div>
                )}
                {c.note && (
                  <div className="rounded-lg bg-subtle p-2 text-xs text-muted">
                    <strong>{t("নোট:")}</strong> {c.note}
                  </div>
                )}
              </Card>
            ))}
          </div>
        )}
      </div>

      {claimOpen && (
        <ClaimModal
          onClose={() => setClaimOpen(false)}
          onSuccess={() => {
            setClaimOpen(false);
            setSuccess(t("ক্লেইম সফলভাবে জমা দেওয়া হয়েছে।"));
            qc.invalidateQueries({ queryKey: ["provider-insurance"] });
          }}
        />
      )}
    </div>
  );
}

function ClaimModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [description, setDescription] = useState("");
  const [photoUrls, setPhotoUrls] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit() {
    if (!description.trim()) {
      setError(t("অনুগ্রহ করে ঘটনার বিবরণ লিখুন।"));
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      await api.post("/providers/insurance/claims/", {
        description: description.trim(),
        photo_urls: photoUrls,
      });
      onSuccess();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal title={t("বিমা ক্লেইম জমা দিন")} open onClose={onClose}>
      <div className="flex flex-col gap-4">
        <TextArea
          label={t("কী ঘটেছিল? বিবরণ লিখুন")}
          required
          rows={4}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder={t("তারিখ, স্থান এবং ক্ষতির স্পষ্ট বিবরণ দিন…")}
        />

        <PhotoUpload
          label={t("প্রমাণস্বরূপ ছবি যুক্ত করুন (ঐচ্ছিক)")}
          purpose="insurance_claim"
          value={photoUrls}
          onChange={setPhotoUrls}
        />

        <ErrorNote>{error}</ErrorNote>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="ghost" onClick={onClose}>{t("বাতিল")}</Button>
          <Button loading={submitting} onClick={handleSubmit}>
            {t("ক্লেইম জমা দিন")}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
