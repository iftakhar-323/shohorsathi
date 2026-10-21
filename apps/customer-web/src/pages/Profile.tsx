import {
  api,
  Button,
  Card,
  errorMessage,
  ErrorNote,
  Field,
  Icon,
  localName,
  MapPicker,
  PageHeader,
  Select,
  SuccessNote,
  t,
  useAreas,
  useAuth,
} from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";

import { useAddresses } from "../api/orders";

type Me = { id: number; phone: string; email: string; full_name: string; role: string };

export default function Profile() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: async () => (await api.get<Me>("/me/")).data });
  const { data: addresses } = useAddresses();
  const { data: areas } = useAreas();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [saved, setSaved] = useState("");
  const [error, setError] = useState("");
  const [address, setAddress] = useState({ label: t("বাসা"), area: "", line: "" });
  const [pin, setPin] = useState<{ lat: number; lng: number } | null>(null);

  useEffect(() => {
    if (me) {
      setName(me.full_name);
      setEmail(me.email);
    }
  }, [me]);

  async function saveProfile(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.patch("/me/", { full_name: name, email });
      setSaved(t("প্রোফাইল সেভ হয়েছে।"));
      qc.invalidateQueries({ queryKey: ["me"] });
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function addAddress(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.post("/me/addresses/", {
        ...address,
        area: Number(address.area),
        is_default: !addresses?.length,
        latitude: pin ? pin.lat.toFixed(6) : null,
        longitude: pin ? pin.lng.toFixed(6) : null,
      });
      setAddress({ label: t("বাসা"), area: "", line: "" });
      setPin(null);
      qc.invalidateQueries({ queryKey: ["addresses"] });
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function update(id: number, body: object | null) {
    await (body ? api.patch(`/me/addresses/${id}/`, body) : api.delete(`/me/addresses/${id}/`));
    qc.invalidateQueries({ queryKey: ["addresses"] });
  }

  return (
    <section className="mx-auto flex max-w-[760px] flex-col gap-6 px-4 py-8 sm:px-6">
      <PageHeader title={t("প্রোফাইল")} subtitle={user?.phone} />
      <ErrorNote>{error}</ErrorNote>
      <Card>
        <form onSubmit={saveProfile} className="flex flex-col gap-4">
          <Field label={t("নাম")} value={name} onChange={(e) => setName(e.target.value)} required />
          <Field label={t("ইমেইল (ঐচ্ছিক)")} type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <SuccessNote>{saved}</SuccessNote>
          <Button type="submit" className="self-start">
            {t("সেভ করুন")}
          </Button>
        </form>
      </Card>

      <Card className="flex flex-col gap-4">
        <h2 className="m-0 text-lg font-bold">{t("সেভ করা ঠিকানা")}</h2>
        {addresses?.map((a) => (
          <div key={a.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-line p-3">
            <Icon name="pin" className="text-brand" />
            <div className="flex flex-1 flex-col">
              <span className="font-semibold">
                {a.label} {a.is_default && <span className="text-sm font-normal text-brand-strong">{t("· ডিফল্ট")}</span>}
              </span>
              <span className="text-sm text-muted">
                {a.line}, {localName(a.area_detail)}
              </span>
            </div>
            {!a.is_default && (
              <Button variant="ghost" onClick={() => update(a.id, { is_default: true })}>
                {t("ডিফল্ট করুন")}
              </Button>
            )}
            <button type="button" aria-label={t("ঠিকানা মুছুন")} onClick={() => update(a.id, null)} className="flex size-10 items-center justify-center rounded-xl text-bad hover:bg-bad-soft">
              <Icon name="trash" size={18} />
            </button>
          </div>
        ))}
        <form onSubmit={addAddress} className="grid gap-3 border-t border-line pt-4 sm:grid-cols-3">
          <Field label={t("লেবেল")} value={address.label} onChange={(e) => setAddress({ ...address, label: e.target.value })} />
          <Select
            label={t("এলাকা")}
            required
            value={address.area}
            onChange={(e) => setAddress({ ...address, area: e.target.value })}
            options={[{ value: "", label: t("বাছুন") }, ...(areas ?? []).map((a) => ({ value: a.id, label: localName(a) }))]}
          />
          <Field label={t("বাসা ও রাস্তা")} required value={address.line} onChange={(e) => setAddress({ ...address, line: e.target.value })} />
          <div className="flex flex-col gap-1 sm:col-span-3">
            <span className="text-[15px] font-semibold">{t("ম্যাপে বাসা (ঐচ্ছিক, প্রোভাইডার সহজে খুঁজে পাবেন)")}</span>
            <MapPicker value={pin} onChange={setPin} height={220} />
          </div>
          <Button type="submit" variant="secondary" icon="plus" className="sm:col-span-3 sm:justify-self-start">
            {t("ঠিকানা যোগ করুন")}
          </Button>
        </form>
      </Card>
    </section>
  );
}
