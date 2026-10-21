import { Badge, Button, Card, ErrorNote, Field, Icon, Loading, PageHeader, Stat, SuccessNote, api, errorMessage, formatDateTime, formatTaka, payOnline, t } from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

export type LoyaltyAccount = {
  points: number;
  points_value: string;
  wallet: string;
  referral_code: string;
  referred: boolean;
  completed_orders: number;
  referrals: number;
  badges: string[];
  rules: { points_per_100_taka: number; point_value_taka: string; max_redeem_percent: number; referral_bonus: string; referral_welcome: string };
  history: { kind: "points" | "wallet"; delta: string; reason: string; ref: string; created_at: string }[];
};

export function useLoyalty(enabled = true) {
  return useQuery({ queryKey: ["loyalty"], queryFn: async () => (await api.get<LoyaltyAccount>("/loyalty/me/")).data, enabled });
}

const BADGES: Record<string, [string, string]> = {
  first_order: ["প্রথম অর্ডার", "star"],
  regular: ["নিয়মিত গ্রাহক", "heart"],
  loyal_subscriber: ["বিশ্বস্ত সাবস্ক্রাইবার", "repeat"],
  referrer: ["বন্ধু এনেছেন", "user"],
  gold: ["গোল্ড মেম্বার", "gift"],
};
const REASONS: Record<string, string> = {
  order: "অর্ডার সম্পন্ন",
  subscription: "সাবস্ক্রিপশন বোনাস",
  subscription_renewal: "রিনিউ বোনাস",
  redeem: "অর্ডারে ব্যবহার",
  redeem_reversed: "বাতিল অর্ডার থেকে ফেরত",
  pay_order: "ওয়ালেট থেকে পেমেন্ট",
  pay_order_reversed: "বাতিল অর্ডার থেকে ফেরত",
  topup: "টপ-আপ",
  referral: "রেফারেল বোনাস",
  referral_welcome: "স্বাগত বোনাস",
};

export default function Wallet() {
  const qc = useQueryClient();
  const { data: acc, isPending } = useLoyalty();
  const [amount, setAmount] = useState("500");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  if (isPending || !acc) return <Loading />;

  async function topUp(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const { data } = await api.post<{ id: number }>("/loyalty/topups/", { amount });
      await payOnline("wallet_topup", data.id);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function applyCode(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.post("/loyalty/referral/", { code });
      setNotice(t("রেফারেল কোড যোগ হয়েছে। প্রথম অর্ডার সম্পন্ন হলে বোনাস পাবেন।"));
      qc.invalidateQueries({ queryKey: ["loyalty"] });
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  const shareText = t("শহরসাথীতে আমার কোড {code} দিয়ে যোগ দিন, প্রথম অর্ডারে {amount} বোনাস!", { code: acc.referral_code, amount: formatTaka(acc.rules.referral_welcome) });

  return (
    <section className="mx-auto flex max-w-[960px] flex-col gap-5 px-4 py-8 sm:px-6">
      <PageHeader title={t("ওয়ালেট ও পয়েন্ট")} subtitle={t("প্রতি ৳১০০-তে {n} পয়েন্ট; চেকআউটে পয়েন্ট দিয়ে ছাড় নিন", { n: acc.rules.points_per_100_taka })} />
      <ErrorNote>{error}</ErrorNote>
      <SuccessNote>{notice}</SuccessNote>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-3">
        <Stat label={t("ওয়ালেট ব্যালেন্স")} value={formatTaka(acc.wallet)} icon="money" />
        <Stat label={t("পয়েন্ট")} value={acc.points} icon="star" />
        <Stat label={t("পয়েন্টের মূল্য")} value={formatTaka(acc.points_value)} icon="gift" />
      </div>
      {acc.badges.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {acc.badges.map((b) => (
            <span key={b} className="flex items-center gap-1.5 rounded-full bg-brand-soft px-3 py-1.5 font-semibold text-brand-strong">
              <Icon name={(BADGES[b]?.[1] ?? "star") as "star"} size={16} /> {t(BADGES[b]?.[0] ?? b)}
            </span>
          ))}
        </div>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <form onSubmit={topUp} className="flex flex-col gap-3">
            <h2 className="m-0 text-lg font-bold">{t("ওয়ালেট টপ-আপ")}</h2>
            <Field label={t("পরিমাণ (৳)")} type="number" min={50} max={20000} value={amount} onChange={(e) => setAmount(e.target.value)} />
            <div className="flex flex-wrap gap-2">
              {["200", "500", "1000", "2000"].map((v) => <button key={v} type="button" onClick={() => setAmount(v)} className="rounded-full border border-line px-3 py-1.5 text-sm">{formatTaka(v)}</button>)}
            </div>
            <Button type="submit" icon="money">{t("বিকাশ/নগদ দিয়ে টপ-আপ")}</Button>
          </form>
        </Card>
        <Card className="flex flex-col gap-3">
          <h2 className="m-0 text-lg font-bold">{t("বন্ধুকে আমন্ত্রণ")}</h2>
          <p className="m-0 text-muted">{t("বন্ধু প্রথম অর্ডার সম্পন্ন করলে আপনি পাবেন {a}, বন্ধু পাবেন {b}।", { a: formatTaka(acc.rules.referral_bonus), b: formatTaka(acc.rules.referral_welcome) })}</p>
          <div className="flex items-center gap-2">
            <span className="rounded-xl bg-subtle px-4 py-2 font-mono text-xl font-bold tracking-widest">{acc.referral_code}</span>
            <Button variant="ghost" icon="send" onClick={() => (navigator.share ? navigator.share({ text: shareText }) : navigator.clipboard?.writeText(shareText).then(() => setNotice(t("কপি হয়েছে"))))}>{t("শেয়ার")}</Button>
          </div>
          {!acc.referred && acc.completed_orders === 0 && (
            <form onSubmit={applyCode} className="flex gap-2">
              <label htmlFor="ref-code" className="sr-only">{t("রেফারেল কোড")}</label>
              <input id="ref-code" value={code} onChange={(e) => setCode(e.target.value)} placeholder={t("বন্ধুর কোড আছে?")} className="h-11 min-w-0 flex-1 rounded-xl border border-line px-3 uppercase" />
              <Button type="submit" variant="secondary">{t("যোগ করুন")}</Button>
            </form>
          )}
        </Card>
      </div>
      <Card className="flex flex-col gap-2">
        <h2 className="m-0 text-lg font-bold">{t("ইতিহাস")}</h2>
        {acc.history.length === 0 && <p className="m-0 text-muted">{t("এখনো কিছু নেই।")}</p>}
        {acc.history.map((h, i) => (
          <div key={i} className="flex items-center gap-3 border-b border-subtle py-2 last:border-0">
            <Badge tone={h.kind === "wallet" ? "info" : "ok"}>{h.kind === "wallet" ? t("ওয়ালেট") : t("পয়েন্ট")}</Badge>
            <span className="flex-1">{t(REASONS[h.reason] ?? h.reason)}<span className="block text-[12px] text-muted">{formatDateTime(h.created_at)}</span></span>
            <span className={`font-bold ${Number(h.delta) < 0 ? "text-bad" : "text-brand-strong"}`}>
              {Number(h.delta) > 0 ? "+" : ""}{h.kind === "wallet" ? formatTaka(h.delta) : Number(h.delta)}
            </span>
          </div>
        ))}
      </Card>
    </section>
  );
}
