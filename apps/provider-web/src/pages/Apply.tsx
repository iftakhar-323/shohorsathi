import { Button, Card, ErrorNote, Icon, api, errorMessage, refreshTokens, useAuth } from "@shohor/web-core";
import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import type { Provider } from "../api";
import ProviderFields, { EMPTY_FORM, type ProviderForm } from "./ProviderFields";

function pick(p: Provider): ProviderForm {
  return Object.fromEntries(Object.keys(EMPTY_FORM).map((k) => [k, p[k as keyof Provider]])) as ProviderForm;
}

export default function Apply({ provider }: { provider: Provider | null }) {
  const { user, logout } = useAuth();
  const qc = useQueryClient();
  const [form, setForm] = useState<ProviderForm>(provider ? pick(provider) : EMPTY_FORM);
  const [editing, setEditing] = useState(!provider);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!form.skills.length || !form.area_ids.length) return setError("অন্তত একটি কাজ আর একটি এলাকা বাছুন।");
    if (!form.photo_url || !form.nid_front_url) return setError("নিজের ছবি আর NID-এর ছবি দিন।");
    setBusy(true);
    setError("");
    try {
      if (provider) await api.patch("/providers/me/", form);
      else await api.post("/providers/register/", form);
      setEditing(false);
      qc.invalidateQueries({ queryKey: ["provider-me"] });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function checkAgain() {
    await refreshTokens();
    qc.invalidateQueries({ queryKey: ["provider-me"] });
  }

  return (
    <div className="mx-auto flex max-w-[860px] flex-col gap-6 px-4 py-10">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-2xl font-bold">শহরসাথী</span>
          <span className="rounded-full bg-alert px-2 py-0.5 text-xs font-semibold">পার্টনার</span>
        </div>
        <Button variant="ghost" icon="logout" onClick={logout}>
          লগআউট
        </Button>
      </div>

      {provider && !editing ? (
        <Card className="flex flex-col items-start gap-4">
          {provider.status === "pending" && (
            <>
              <Icon name="clock" size={36} className="text-alert-strong" />
              <h1 className="m-0 text-2xl font-bold">আবেদন যাচাই চলছে</h1>
              <p className="m-0 text-muted">অ্যাডমিন আপনার NID ও তথ্য যাচাই করছেন। প্রয়োজনে ফোন করে ছোট একটা দক্ষতা পরীক্ষা নেওয়া হতে পারে।</p>
              <div className="flex flex-wrap gap-2">
                <Button icon="refresh" onClick={checkAgain}>
                  আবার দেখুন
                </Button>
                <Button variant="ghost" onClick={() => setEditing(true)}>
                  তথ্য বদলান
                </Button>
              </div>
            </>
          )}
          {provider.status === "rejected" && (
            <>
              <Icon name="x" size={36} className="text-bad" />
              <h1 className="m-0 text-2xl font-bold">আবেদন গ্রহণ করা হয়নি</h1>
              <ErrorNote>কারণ: {provider.rejection_reason}</ErrorNote>
              <Button onClick={() => setEditing(true)}>তথ্য ঠিক করে আবার জমা দিন</Button>
            </>
          )}
          {provider.status === "suspended" && (
            <>
              <Icon name="alert" size={36} className="text-bad" />
              <h1 className="m-0 text-2xl font-bold">অ্যাকাউন্ট স্থগিত</h1>
              <p className="m-0 text-muted">{provider.rejection_reason || "সাপোর্টে যোগাযোগ করুন।"}</p>
            </>
          )}
        </Card>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-6">
          <div className="flex flex-col gap-2">
            <h1 className="m-0 text-3xl font-bold">পার্টনার হিসেবে যোগ দিন</h1>
            <p className="m-0 text-muted">
              {user?.name}, আপনার তথ্য দিন। যাচাইয়ের পর আপনার এলাকার কাজ পাবেন, সাপ্তাহিক পেমেন্ট বিকাশ/নগদে।
            </p>
          </div>
          <Card>
            <ProviderFields form={form} setForm={setForm} />
          </Card>
          <ErrorNote>{error}</ErrorNote>
          <Button type="submit" loading={busy} className="h-12 self-start px-8 text-base">
            আবেদন জমা দিন
          </Button>
        </form>
      )}
    </div>
  );
}
