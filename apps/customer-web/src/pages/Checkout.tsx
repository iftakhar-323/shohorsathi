import { api, Button, Card, errorMessage, ErrorNote, Field, formatTaka, Loading, localName, PageHeader, payOnline, Select, slotOptions, SLOTS, t, TextArea, todayISO, useAreas, useAuth } from "@shohor/web-core";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { useAddresses, useCart, type Order } from "../api/orders";
import { clearDrafts, getDraft, type BookingDraft } from "../lib/bookingDraft";

export default function Checkout() {
  const { user } = useAuth();
  const { data: cart, isPending } = useCart();
  const { data: addresses } = useAddresses();
  const { data: areas } = useAreas();
  const qc = useQueryClient();
  const navigate = useNavigate();

  const [addressId, setAddressId] = useState<number | "new">("new");
  const [newArea, setNewArea] = useState<number>();
  const [newLine, setNewLine] = useState("");
  const [contactName, setContactName] = useState(user?.name ?? "");
  const [contactPhone, setContactPhone] = useState(user?.phone ?? "");
  const [note, setNote] = useState("");
  const [payment, setPayment] = useState<"cod" | "online">("cod");
  const [schedules, setSchedules] = useState<Record<number, BookingDraft>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const def = addresses?.find((a) => a.is_default) ?? addresses?.[0];
    if (def) setAddressId(def.id);
  }, [addresses]);

  useEffect(() => {
    if (!cart) return;
    const initial: Record<number, BookingDraft> = {};
    for (const item of cart.items.filter((i) => i.item_type === "service")) {
      initial[item.id] = getDraft(item.id) ?? { scheduled_date: todayISO(1), slot: SLOTS[0].value, problem_description: "", photo_urls: [] };
    }
    setSchedules(initial);
  }, [cart]);

  if (isPending) return <Loading />;
  if (!cart?.items.length) return <Navigate to="/cart" replace />;

  const services = cart.items.filter((i) => i.item_type === "service");

  async function placeOrder(e: FormEvent) {
    e.preventDefault();
    setError("");
    let area_id: number, area_name: string, address_line: string;
    let latitude: string | null = null;
    let longitude: string | null = null;
    if (addressId === "new") {
      const area = areas?.find((a) => a.id === newArea);
      if (!area) return setError(t("এলাকা বাছুন।"));
      area_id = area.id;
      area_name = area.name_bn;
      address_line = newLine;
      // remember the address for next time
      api.post("/me/addresses/", { area: area.id, line: newLine, is_default: !addresses?.length }).then(() => qc.invalidateQueries({ queryKey: ["addresses"] }));
    } else {
      const a = addresses!.find((x) => x.id === addressId)!;
      area_id = a.area;
      area_name = a.area_detail.name_bn;
      address_line = a.line;
      latitude = a.latitude;
      longitude = a.longitude;
    }
    setBusy(true);
    try {
      const { data } = await api.post<Order>("/orders/", {
        contact_name: contactName,
        contact_phone: contactPhone,
        address_line,
        area_id,
        area_name,
        latitude,
        longitude,
        note,
        payment_method: payment,
        service_details: schedules,
      });
      clearDrafts();
      qc.invalidateQueries({ queryKey: ["cart"] });
      qc.invalidateQueries({ queryKey: ["orders"] });
      if (payment === "online") await payOnline("order", data.id);
      else navigate(`/orders/${data.id}`, { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={placeOrder} className="mx-auto grid max-w-[1100px] gap-6 px-4 py-8 sm:px-6 lg:grid-cols-[1.4fr_1fr]">
      <div className="flex flex-col gap-5">
        <PageHeader title={t("চেকআউট")} />

        <Card className="flex flex-col gap-4">
          <h2 className="m-0 text-lg font-bold">{t("ঠিকানা")}</h2>
          {addresses?.map((a) => (
            <label key={a.id} className={`flex items-start gap-3 rounded-xl border p-3 ${addressId === a.id ? "border-brand bg-brand-tint" : "border-line"}`}>
              <input type="radio" name="address" checked={addressId === a.id} onChange={() => setAddressId(a.id)} className="mt-1 accent-brand" />
              <span className="flex flex-col">
                <span className="font-semibold">{a.label}</span>
                <span className="text-sm text-muted">
                  {a.line}, {localName(a.area_detail)}
                </span>
              </span>
            </label>
          ))}
          <label className={`flex items-center gap-3 rounded-xl border p-3 ${addressId === "new" ? "border-brand bg-brand-tint" : "border-line"}`}>
            <input type="radio" name="address" checked={addressId === "new"} onChange={() => setAddressId("new")} className="accent-brand" />
            <span className="font-semibold">{t("নতুন ঠিকানা")}</span>
          </label>
          {addressId === "new" && (
            <div className="grid gap-3 sm:grid-cols-2">
              <Select
                label={t("এলাকা")}
                required
                value={newArea ?? ""}
                onChange={(e) => setNewArea(Number(e.target.value) || undefined)}
                options={[{ value: "", label: t("এলাকা বাছুন") }, ...(areas ?? []).map((a) => ({ value: a.id, label: localName(a) }))]}
              />
              <Field label={t("বাসা ও রাস্তা")} required value={newLine} onChange={(e) => setNewLine(e.target.value)} placeholder={t("বাসা ১২, রোড ৫")} />
            </div>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t("যোগাযোগের নাম")} required value={contactName} onChange={(e) => setContactName(e.target.value)} />
            <Field label={t("মোবাইল")} required pattern="01[3-9][0-9]{8}" value={contactPhone} onChange={(e) => setContactPhone(e.target.value)} />
          </div>
        </Card>

        {services.length > 0 && (
          <Card className="flex flex-col gap-4">
            <h2 className="m-0 text-lg font-bold">{t("সার্ভিসের সময়")}</h2>
            {services.map((item) => {
              const s = schedules[item.id];
              if (!s) return null;
              const set = (patch: Partial<BookingDraft>) => setSchedules({ ...schedules, [item.id]: { ...s, ...patch } });
              return (
                <div key={item.id} className="grid gap-3 rounded-xl border border-line p-3 sm:grid-cols-2">
                  <span className="font-semibold sm:col-span-2">{item.name}</span>
                  <Field label={t("তারিখ")} type="date" min={todayISO()} value={s.scheduled_date} onChange={(e) => set({ scheduled_date: e.target.value })} required />
                  <Select label={t("সময়")} value={s.slot} onChange={(e) => set({ slot: e.target.value })} options={slotOptions()} />
                </div>
              );
            })}
          </Card>
        )}

        <Card>
          <TextArea label={t("নোট (ঐচ্ছিক)")} value={note} onChange={(e) => setNote(e.target.value)} placeholder={t("গেটের পাসওয়ার্ড, কোন তলা ইত্যাদি")} />
        </Card>
      </div>

      <Card className="flex h-fit flex-col gap-3 lg:sticky lg:top-24">
        <h2 className="m-0 text-lg font-bold">{t("অর্ডার সারাংশ")}</h2>
        {cart.items.map((i) => (
          <div key={i.id} className="flex justify-between gap-2 text-[15px]">
            <span className="text-muted">
              {i.name} {i.quantity > 1 && `× ${i.quantity}`}
            </span>
            <span>{formatTaka(i.line_total)}</span>
          </div>
        ))}
        <div className="flex justify-between border-t border-line pt-3 text-lg font-bold">
          <span>{t("সাবটোটাল")}</span>
          <span>{formatTaka(cart.subtotal)}</span>
        </div>
        <p className="m-0 text-sm text-muted">{t("পণ্য থাকলে ডেলিভারি চার্জ যোগ হতে পারে। যন্ত্রাংশ লাগলে আলাদা দেখানো হবে।")}</p>
        {([["cod", "ক্যাশ অন ডেলিভারি", "পণ্য পেয়ে বা কাজ শেষে টাকা দিন"], ["online", "বিকাশ / নগদ / কার্ড", "টাকা কাজ শেষ হওয়া পর্যন্ত নিরাপদে জমা থাকে"]] as const).map(([value, title, hint]) => (
          <label key={value} className={`flex items-start gap-3 rounded-xl border p-3 text-[15px] ${payment === value ? "border-brand bg-brand-tint" : "border-line"}`}>
            <input type="radio" name="payment" checked={payment === value} onChange={() => setPayment(value)} className="mt-1 accent-brand" />
            <span>
              <span className="font-semibold">{t(title)}</span>
              <span className="block text-sm text-muted">{t(hint)}</span>
            </span>
          </label>
        ))}
        <ErrorNote>{error}</ErrorNote>
        <Button type="submit" loading={busy} className="h-12 text-base">
          {t("অর্ডার কনফার্ম করুন")}
        </Button>
      </Card>
    </form>
  );
}
