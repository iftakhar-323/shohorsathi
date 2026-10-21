import { api, Button, Card, errorMessage, formatTaka, PageHeader, PhotoUpload, t } from "@shohor/web-core";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAddToCart } from "../api/orders";
import { VoiceSearchButton } from "../components/VoiceSearchButton";

interface DiagnosisResult {
  id: number;
  detected_category: string;
  detected_issue: string;
  recommended_service_slug: string;
  recommended_service_name_bn: string;
  estimated_min_price: string;
  estimated_max_price: string;
  confidence: string;
  severity: "low" | "medium" | "high" | "critical";
  suggested_action: string;
  engine: "claude" | "keywords";
}

export default function AiQuote() {
  const [description, setDescription] = useState("");
  const [photos, setPhotos] = useState<string[]>([]);
  const photoUrl = photos[0] ?? "";
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DiagnosisResult | null>(null);
  const [error, setError] = useState("");
  const addToCart = useAddToCart();
  const navigate = useNavigate();

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!photoUrl && !description.trim()) {
      setError(t("অনুগ্রহ করে সমস্যার একটি ছবি দিন অথবা বিস্তারিত বর্ণনা লিখুন।"));
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const res = await api.post("/custom-requests/ai-quote/", {
        photo_url: photoUrl,
        description: description.trim(),
      });
      setResult(res.data);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleBookNow = async () => {
    if (!result?.recommended_service_slug) return;
    try {
      await addToCart.mutateAsync({
        item_type: "service",
        slug: result.recommended_service_slug,
        quantity: 1,
      });
      navigate("/checkout");
    } catch {
      navigate(`/services/${result.recommended_service_slug}`);
    }
  };

  return (
    <div className="mx-auto max-w-[800px] px-4 py-8 sm:px-6">
      <PageHeader
        title={t("AI ফটো কোট ও সমস্যা নির্ণয়")}
        subtitle={t("বাসার কোনো ফাটল, লিকেজ বা নষ্ট যন্ত্রপাতির ছবি তুলুন — এআই তাৎক্ষণিক খরচ ও সমাধান দেবে")}
      />

      <div className="mt-6 grid gap-6">
        <Card className="p-6">
          <form onSubmit={handleAnalyze} className="space-y-5">
            <PhotoUpload label={t("সমস্যার ছবি আপলোড করুন")} value={photos} onChange={setPhotos} purpose="problem_photo" max={1} />

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-sm font-semibold text-ink">
                  {t("সমস্যার বিবরণ (লিখুন বা মুখে বলুন)")}
                </label>
                <VoiceSearchButton
                  onTranscript={(text) => setDescription((prev) => (prev ? `${prev} ${text}` : text))}
                />
              </div>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                placeholder={t("যেমন: বেসিনের নিচের পাইপ ফেটে পানি পড়ছে, অথবা এসি চালু করলেও ঠান্ডা বাতাস দিচ্ছে না...")}
                className="w-full rounded-xl border border-line bg-surface px-3 py-2 text-sm text-ink focus:border-brand focus:outline-none"
              />
            </div>

            {error && <div className="text-sm font-medium text-rose-600">{error}</div>}

            <Button type="submit" loading={loading} className="w-full justify-center text-base py-2.5">
              ✨ {t("এআই দিয়ে বিশ্লেষণ ও কোট দেখুন")}
            </Button>
          </form>
        </Card>

        {result && (
          <Card className="p-6 border-2 border-brand/30 bg-gradient-to-br from-emerald-50/40 via-surface to-teal-50/20 shadow-md">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-4">
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-brand">
                  {t("এআই রোগ নির্ণয় ফলাফল")}
                </span>
                <h3 className="text-lg font-bold text-ink mt-0.5">{result.detected_issue}</h3>
              </div>
              <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${
                result.severity === "critical" || result.severity === "high"
                  ? "bg-rose-100 text-rose-800"
                  : result.severity === "medium"
                  ? "bg-amber-100 text-amber-800"
                  : "bg-emerald-100 text-emerald-800"
              }`}>
                {result.severity === "critical"
                  ? t("জরুরি মেরামত প্রয়োজন")
                  : result.severity === "high"
                  ? t("উচ্চ সতর্কতা")
                  : result.severity === "medium"
                  ? t("মাঝারি অগ্রাধিকার")
                  : t("স্বাভাবিক")}
              </span>
            </div>

            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div className="rounded-xl border border-line bg-surface p-3.5">
                <div className="text-xs font-medium text-ink-muted">{t("আনুমানিক খরচ সীমা")}</div>
                <div className="mt-1 text-2xl font-black text-brand">
                  {formatTaka(result.estimated_min_price)} – {formatTaka(result.estimated_max_price)}
                </div>
                <div className="text-xs text-ink-muted mt-0.5">
                  {result.engine === "claude"
                    ? `${t("এআই-এর আস্থা:")} ${Math.round(parseFloat(result.confidence) * 100)}%`
                    : t("বিবরণের শব্দ মিলিয়ে আনুমানিক হিসাব")}
                </div>
              </div>

              <div className="rounded-xl border border-line bg-surface p-3.5">
                <div className="text-xs font-medium text-ink-muted">{t("প্রস্তাবিত সার্ভিস")}</div>
                <div className="mt-1 text-base font-bold text-ink">
                  {result.recommended_service_name_bn}
                </div>
                <div className="text-xs text-ink-muted mt-0.5 capitalize">
                  {t("ক্যাটাগরি:")} {result.detected_category}
                </div>
              </div>
            </div>

            <div className="mt-4 rounded-xl bg-brand/5 border border-brand/15 p-3.5 text-sm text-ink">
              <span className="font-semibold text-brand-strong">{t("বিশেষজ্ঞ পরামর্শ:")} </span>
              {result.suggested_action}
            </div>

            <div className="mt-6 flex gap-3">
              <Button onClick={handleBookNow} className="flex-1 justify-center py-2.5 text-base">
                ⚡ {t("এই সার্ভিসটি এখনই বুক করুন")}
              </Button>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
