import { Button, Card, Empty, formatTaka, Icon, Loading, PageHeader, slotLabel, t } from "@shohor/web-core";
import { Link } from "react-router-dom";

import { useCart, useUpdateCartItem } from "../api/orders";
import { getDraft } from "../lib/bookingDraft";

export default function Cart() {
  const { data: cart, isPending } = useCart();
  const update = useUpdateCartItem();

  if (isPending) return <Loading />;

  return (
    <section className="mx-auto flex max-w-[960px] flex-col gap-6 px-4 py-8 sm:px-6">
      <PageHeader title={t("কার্ট")} subtitle={t("পণ্য আর সার্ভিস এক অর্ডারে")} />
      {!cart?.items.length ? (
        <Empty icon="cart" title={t("কার্ট খালি")}>
          <Link to="/services">{t("সার্ভিস দেখুন")}</Link> {t("বা")} <Link to="/shop">{t("শপে যান")}</Link>
        </Empty>
      ) : (
        <>
          <Card className="flex flex-col divide-y divide-line p-0">
            {cart.items.map((item) => {
              const draft = item.item_type === "service" ? getDraft(item.id) : undefined;
              return (
                <div key={item.id} className="flex flex-wrap items-center gap-4 p-4">
                  <span className="flex size-12 items-center justify-center rounded-xl bg-brand-soft text-brand-strong">
                    <Icon name={item.item_type === "service" ? "wrench" : "bag"} />
                  </span>
                  <div className="flex min-w-0 flex-1 flex-col">
                    <span className="font-semibold">{item.name}</span>
                    <span className="text-sm text-muted">
                      {item.item_type === "service"
                        ? draft
                          ? `${draft.scheduled_date} · ${slotLabel(draft.slot)}`
                          : t("সময় চেকআউটে বাছবেন")
                        : `${formatTaka(item.unit_price)} × ${item.quantity}`}
                    </span>
                  </div>
                  {item.item_type === "product" && (
                    <div className="flex items-center gap-1" role="group" aria-label={t("পরিমাণ")}>
                      <button type="button" aria-label={t("কমান")} onClick={() => update.mutate({ id: item.id, quantity: item.quantity - 1 })} className="flex size-10 items-center justify-center rounded-xl border border-line">
                        <Icon name="minus" size={16} />
                      </button>
                      <span className="w-8 text-center font-semibold">{item.quantity}</span>
                      <button type="button" aria-label={t("বাড়ান")} onClick={() => update.mutate({ id: item.id, quantity: item.quantity + 1 })} className="flex size-10 items-center justify-center rounded-xl border border-line">
                        <Icon name="plus" size={16} />
                      </button>
                    </div>
                  )}
                  <span className="w-24 text-right font-bold">{formatTaka(item.line_total)}</span>
                  <button type="button" aria-label={t("{name} সরান", { name: item.name })} onClick={() => update.mutate({ id: item.id, quantity: 0 })} className="flex size-10 items-center justify-center rounded-xl text-bad hover:bg-bad-soft">
                    <Icon name="trash" size={18} />
                  </button>
                </div>
              );
            })}
          </Card>
          <Card className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-col">
              <span className="text-muted">{t("সাবটোটাল")}</span>
              <span className="text-2xl font-bold">{formatTaka(cart.subtotal)}</span>
            </div>
            <Link to="/checkout" className="flex h-12 items-center gap-2 rounded-xl bg-brand px-6 font-semibold text-white no-underline">
              {t("চেকআউট")} <Icon name="next" size={18} />
            </Link>
          </Card>
        </>
      )}
      {update.isPending && <span className="sr-only">{t("আপডেট হচ্ছে")}</span>}
      <Button variant="ghost" icon="plus" onClick={() => history.back()} className="self-start">
        {t("আরও যোগ করুন")}
      </Button>
    </section>
  );
}
