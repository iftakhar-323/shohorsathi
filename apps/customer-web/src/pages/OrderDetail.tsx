import { api, Button, Card, errorMessage, ErrorNote, Field, formatDate, formatTaka, Icon, Loading, Modal, PageHeader, payOnline, PhotoUpload, Select, slotOptions, StatusBadge, SuccessNote, t, TextArea, Timeline, todayISO } from "@shohor/web-core";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router-dom";

import { useOrder, useTracking, type Booking } from "../api/orders";
import { BookingExtras, RefundRequest } from "../components/BookingExtras";

function BookingCard({ booking, onChanged }: { booking: Booking; onChanged: () => void }) {
  const [dialog, setDialog] = useState<"reschedule" | "warranty" | null>(null);
  const [date, setDate] = useState(booking.scheduled_date);
  const [slot, setSlot] = useState(booking.slot);
  const [claim, setClaim] = useState("");
  const [photos, setPhotos] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const active = ["pending", "confirmed"].includes(booking.status);
  const underWarranty = booking.warranty_until && new Date(booking.warranty_until) > new Date();

  async function act(fn: () => Promise<unknown>, done: string) {
    setBusy(true);
    setError("");
    try {
      await fn();
      setNotice(done);
      setDialog(null);
      onChanged();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <span className="text-lg font-bold">{booking.service_name}</span>
          <span className="flex items-center gap-2 text-muted">
            <Icon name="calendar" size={16} /> {formatDate(booking.scheduled_date)} · {booking.slot_label}
          </span>
        </div>
        <StatusBadge status={booking.status} />
      </div>

      {booking.provider_name ? (
        <div className="flex flex-wrap items-center gap-3 rounded-xl bg-subtle p-3">
          <span className="flex size-10 items-center justify-center rounded-full bg-brand-soft text-brand-strong">
            <Icon name="user" />
          </span>
          <div className="flex flex-1 flex-col">
            <span className="font-semibold">{booking.provider_name}</span>
            <span className="text-sm text-muted">{t("আপনার প্রোভাইডার")}</span>
          </div>
          {booking.provider_phone && (
            <a href={`tel:${booking.provider_phone}`} className="flex h-11 items-center gap-2 rounded-xl border border-line bg-surface px-3 font-semibold text-ink no-underline">
              <Icon name="phone" size={16} /> {t("কল করুন")}
            </a>
          )}
        </div>
      ) : (
        booking.status === "pending" && <p className="m-0 text-muted">{t("আপনার এলাকার একজন যাচাইকৃত প্রোভাইডার খোঁজা হচ্ছে…")}</p>
      )}

      {["confirmed", "on_the_way"].includes(booking.status) && (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-dashed border-brand p-3">
          <Icon name="shield" className="text-brand" />
          <span className="flex-1 text-[15px]">{t("প্রোভাইডার এলে এই কোডটি বলুন, তাহলেই কাজ শুরু হবে:")}</span>
          <span className="rounded-lg bg-brand px-3 py-1 font-mono text-2xl font-bold tracking-[0.3em] text-white">{booking.arrival_code}</span>
        </div>
      )}

      {booking.status === "completed" && booking.warranty_until && (
        <p className="m-0 flex items-center gap-2 text-sm text-brand-strong">
          <Icon name="shield" size={16} /> {t("ওয়ারেন্টি")} {formatDate(booking.warranty_until)} {t("পর্যন্ত")}
        </p>
      )}

      <BookingExtras booking={booking} />

      <SuccessNote>{notice}</SuccessNote>
      <ErrorNote>{!dialog && error}</ErrorNote>

      <div className="flex flex-wrap gap-2">
        {active && (
          <>
            <Button variant="ghost" icon="calendar" onClick={() => setDialog("reschedule")}>
              {t("সময় বদলান")}
            </Button>
            <Button variant="danger" loading={busy} onClick={() => confirm(t("বুকিং বাতিল করবেন?")) && act(() => api.post(`/bookings/${booking.id}/cancel/`), t("বুকিং বাতিল হয়েছে।"))}>
              {t("বাতিল করুন")}
            </Button>
          </>
        )}
        {booking.status === "completed" && underWarranty && (
          <Button variant="secondary" icon="refresh" onClick={() => setDialog("warranty")}>
            {t("ওয়ারেন্টি দাবি")}
          </Button>
        )}
      </div>

      <Modal title={t("সময় বদলান")} open={dialog === "reschedule"} onClose={() => setDialog(null)}>
        <Field label={t("নতুন তারিখ")} type="date" min={todayISO()} value={date} onChange={(e) => setDate(e.target.value)} />
        <Select label={t("সময়")} value={slot} onChange={(e) => setSlot(e.target.value)} options={slotOptions()} />
        <ErrorNote>{error}</ErrorNote>
        <Button loading={busy} onClick={() => act(() => api.patch(`/bookings/${booking.id}/reschedule/`, { scheduled_date: date, slot }), t("সময় বদলানো হয়েছে।"))}>
          {t("সেভ করুন")}
        </Button>
      </Modal>

      <Modal title={t("ওয়ারেন্টি দাবি")} open={dialog === "warranty"} onClose={() => setDialog(null)}>
        <p className="m-0 text-muted">{t("একই সমস্যা আবার হলে আমরা বিনা খরচে ঠিক করে দেব।")}</p>
        <TextArea label={t("কী সমস্যা হচ্ছে?")} value={claim} onChange={(e) => setClaim(e.target.value)} required />
        <PhotoUpload label={t("ছবি (ঐচ্ছিক)")} value={photos} onChange={setPhotos} purpose="problem_photo" max={3} />
        <ErrorNote>{error}</ErrorNote>
        <Button
          loading={busy}
          disabled={!claim.trim()}
          onClick={() => act(() => api.post(`/bookings/${booking.id}/warranty/`, { description: claim, photo_urls: photos }), t("ওয়ারেন্টি দাবি জমা হয়েছে। অ্যাডমিন শীঘ্রই যোগাযোগ করবেন।"))}
        >
          {t("জমা দিন")}
        </Button>
      </Modal>
    </Card>
  );
}

export default function OrderDetail() {
  const { id } = useParams();
  const qc = useQueryClient();
  const { data: order, isPending } = useOrder(id);
  const { data: tracking } = useTracking(id);
  const [error, setError] = useState("");

  if (isPending || !order) return <Loading />;

  const refresh = () => qc.invalidateQueries({ queryKey: ["orders", id] });

  async function cancelOrder() {
    if (!confirm(t("পুরো অর্ডার বাতিল করবেন?"))) return;
    try {
      await api.post(`/orders/${order!.id}/cancel/`);
      refresh();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <section className="mx-auto grid max-w-[1100px] gap-6 px-4 py-8 sm:px-6 lg:grid-cols-[1.5fr_1fr]">
      <div className="flex flex-col gap-5">
        <PageHeader
          title={t("অর্ডার {number}", { number: order.number })}
          subtitle={`${formatDate(order.created_at)} · ${order.address_line}, ${order.area_name}`}
          actions={<StatusBadge status={order.status} className="text-base" />}
        />
        {order.bookings.map((b) => (
          <BookingCard key={b.id} booking={b} onChanged={refresh} />
        ))}
        {order.items.length > 0 && (
          <Card className="flex flex-col gap-3">
            <h2 className="m-0 text-lg font-bold">{t("পণ্য")}</h2>
            {order.items.map((i) => (
              <div key={i.slug} className="flex justify-between">
                <span>
                  {i.name} × {i.quantity}
                </span>
                <span className="font-semibold">{formatTaka(i.line_total)}</span>
              </div>
            ))}
          </Card>
        )}
        <ErrorNote>{error}</ErrorNote>
        {order.status === "pending" && (
          <Button variant="danger" onClick={cancelOrder} className="self-start">
            {t("পুরো অর্ডার বাতিল করুন")}
          </Button>
        )}
      </div>

      <div className="flex flex-col gap-5">
        <Card className="flex flex-col gap-2">
          <h2 className="m-0 text-lg font-bold">{t("পেমেন্ট")}</h2>
          <div className="flex justify-between text-muted">
            <span>{t("সাবটোটাল")}</span>
            <span>{formatTaka(order.subtotal)}</span>
          </div>
          {Number(order.delivery_fee) > 0 && (
            <div className="flex justify-between text-muted">
              <span>{t("ডেলিভারি")}</span>
              <span>{formatTaka(order.delivery_fee)}</span>
            </div>
          )}
          {Number(order.discount) > 0 && (
            <div className="flex justify-between text-brand-strong">
              <span>{t("ছাড়")}</span>
              <span>− {formatTaka(order.discount)}</span>
            </div>
          )}
          <div className="flex justify-between border-t border-line pt-2 text-lg font-bold">
            <span>{t("মোট")}</span>
            <span>{formatTaka(order.total)}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted">{order.payment_method === "cod" ? t("ক্যাশ অন ডেলিভারি") : t("অনলাইন পেমেন্ট")}</span>
            <StatusBadge status={order.payment_status} />
          </div>
          {order.payment_method === "online" && order.payment_status === "unpaid" && order.status !== "cancelled" && (
            <Button onClick={() => payOnline("order", order.id)}>{t("এখনই পরিশোধ করুন")}</Button>
          )}
          {order.payment_method === "online" && <RefundRequest orderId={order.id} />}
        </Card>
        <Card className="flex flex-col gap-4">
          <h2 className="m-0 text-lg font-bold">{t("টাইমলাইন")}</h2>
          {tracking && <Timeline events={[...tracking.events].reverse()} />}
        </Card>
      </div>
    </section>
  );
}
