import { Button, ErrorNote, Modal, SuccessNote, TextArea, api, errorMessage, openJobChat, t } from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import type { Booking } from "../api/orders";

/** Review and chat for one booking; live map comes with the city layer. */
export function BookingExtras({ booking }: { booking: Booking }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { data: review } = useQuery({
    queryKey: ["review", "booking", booking.id],
    queryFn: async () => (await api.get<{ rating: number; comment: string } | null>("/providers/reviews/", { params: { source: "booking", source_id: booking.id } })).data,
    enabled: booking.status === "completed",
  });
  const [open, setOpen] = useState(false);
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");

  async function submit() {
    setError("");
    try {
      await api.post("/providers/reviews/", { source: "booking", source_id: booking.id, rating, comment });
      setOpen(false);
      qc.invalidateQueries({ queryKey: ["review", "booking", booking.id] });
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function chat() {
    try {
      navigate(`/chat/${await openJobChat("booking", booking.id)}`);
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {booking.provider_id && !["cancelled"].includes(booking.status) && (
        <Button variant="ghost" icon="chat" onClick={chat}>{t("প্রোভাইডারকে বার্তা")}</Button>
      )}
      {booking.status === "completed" && !review && (
        <Button variant="secondary" icon="star" onClick={() => setOpen(true)}>{t("রিভিউ দিন")}</Button>
      )}
      {review && <SuccessNote>{t("আপনার রেটিং:")} {"★".repeat(review.rating)}</SuccessNote>}
      <ErrorNote>{!open && error}</ErrorNote>
      <Modal title={t("প্রোভাইডারকে রেটিং দিন")} open={open} onClose={() => setOpen(false)}>
        <div className="flex gap-1" role="radiogroup" aria-label={t("রেটিং")}>
          {[1, 2, 3, 4, 5].map((n) => (
            <button key={n} type="button" role="radio" aria-checked={rating === n} aria-label={`${n}`} onClick={() => setRating(n)} className={`text-3xl ${n <= rating ? "text-alert" : "text-line"}`}>★</button>
          ))}
        </div>
        <TextArea label={t("মন্তব্য (ঐচ্ছিক)")} value={comment} onChange={(e) => setComment(e.target.value)} />
        <ErrorNote>{error}</ErrorNote>
        <Button disabled={!rating} onClick={submit}>{t("জমা দিন")}</Button>
      </Modal>
    </div>
  );
}

type Payment = { tran_id: string; status: string; amount: string; refunded_amount: string };

/** Refund/complaint request for an online-paid order. */
export function RefundRequest({ orderId }: { orderId: number }) {
  const { data: payments } = useQuery({
    queryKey: ["payments", "order", orderId],
    queryFn: async () => (await api.get<{ results: Payment[] }>("/payments/mine/", { params: { purpose: "order", reference_id: orderId } })).data.results,
  });
  const paid = payments?.find((p) => ["held", "released"].includes(p.status));
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [done, setDone] = useState("");
  const [error, setError] = useState("");
  if (!paid) return null;

  async function submit() {
    setError("");
    try {
      await api.post(`/payments/mine/${paid!.tran_id}/refund-request/`, { reason });
      setDone(t("অভিযোগ/রিফান্ড অনুরোধ জমা হয়েছে। অ্যাডমিন দেখে জানাবেন।"));
      setOpen(false);
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <>
      <SuccessNote>{done}</SuccessNote>
      {!done && <Button variant="ghost" icon="alert" onClick={() => setOpen(true)} className="self-start">{t("অভিযোগ / রিফান্ড চাই")}</Button>}
      <Modal title={t("অভিযোগ / রিফান্ড")} open={open} onClose={() => setOpen(false)}>
        <TextArea label={t("কী সমস্যা হয়েছে?")} value={reason} onChange={(e) => setReason(e.target.value)} required />
        <ErrorNote>{error}</ErrorNote>
        <Button disabled={!reason.trim()} onClick={submit}>{t("জমা দিন")}</Button>
      </Modal>
    </>
  );
}
