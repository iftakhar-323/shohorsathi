import { Card, Icon, t } from "@shohor/web-core";
import { Link, useSearchParams } from "react-router-dom";

const TARGET: Record<string, (id: string) => string> = {
  order: (id) => `/orders/${id}`,
  subscription: (id) => `/subscriptions/${id}`,
  custom_request_advance: (id) => `/custom-requests/${id}`,
  wallet_topup: () => "/wallet",
};

/** The gateway sends customers here after paying (status = held), failing or cancelling. */
export default function PaymentResult() {
  const [params] = useSearchParams();
  const status = params.get("status") ?? "";
  const ok = status === "held" || status === "released";
  const back = TARGET[params.get("purpose") ?? ""]?.(params.get("reference_id") ?? "") ?? "/";

  return (
    <section className="mx-auto flex max-w-[560px] flex-col gap-4 px-4 py-16">
      <Card className="flex flex-col items-center gap-3 text-center">
        <span className={`flex size-14 items-center justify-center rounded-full ${ok ? "bg-brand-soft text-brand-strong" : "bg-bad-soft text-bad"}`}>
          <Icon name={ok ? "check" : "x"} size={28} />
        </span>
        <h1 className="m-0 text-2xl font-bold">{ok ? t("পেমেন্ট সফল") : status === "cancelled" ? t("পেমেন্ট বাতিল করেছেন") : t("পেমেন্ট হয়নি")}</h1>
        <p className="m-0 text-muted">
          {ok ? t("টাকা আমাদের কাছে নিরাপদে জমা আছে; কাজ শেষ হওয়ার পর প্রোভাইডার পাবেন।") : t("কোনো টাকা কাটা হয়নি। আবার চেষ্টা করতে পারেন।")}
        </p>
        {params.get("tran_id") && <span className="text-sm text-muted">TxID: {params.get("tran_id")}</span>}
        <Link to={back} className="flex h-12 items-center rounded-xl bg-brand px-6 font-semibold text-white no-underline">{t("ফিরে যান")}</Link>
      </Card>
    </section>
  );
}
