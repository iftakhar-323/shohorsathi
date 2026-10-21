import { Field, PhotoUpload, Select, TextArea, useAreas, useCategories } from "@shohor/web-core";

import { DAYS, PROVIDER_TYPES, type Provider } from "../api";

export type ProviderForm = Pick<
  Provider,
  | "provider_type" | "skills" | "area_ids" | "bio" | "experience_years" | "nid_number" | "photo_url" | "nid_front_url"
  | "nid_back_url" | "kitchen_photo_urls" | "gender" | "working_days" | "work_start" | "work_end" | "payout_method" | "payout_account"
>;

export const EMPTY_FORM: ProviderForm = {
  provider_type: "electrician",
  skills: [],
  area_ids: [],
  bio: "",
  experience_years: 0,
  nid_number: "",
  photo_url: "",
  nid_front_url: "",
  nid_back_url: "",
  kitchen_photo_urls: [],
  gender: "",
  working_days: [0, 1, 2, 3, 4, 5],
  work_start: "09:00",
  work_end: "20:00",
  payout_method: "bkash",
  payout_account: "",
};

function Chips<T extends string | number>({ label, options, value, onChange }: { label: string; options: { value: T; label: string }[]; value: T[]; onChange: (v: T[]) => void }) {
  return (
    <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
      <legend className="mb-2 text-[15px] font-semibold">{label}</legend>
      <div className="flex flex-wrap gap-2">
        {options.map((o) => {
          const on = value.includes(o.value);
          return (
            <button
              key={String(o.value)}
              type="button"
              aria-pressed={on}
              onClick={() => onChange(on ? value.filter((v) => v !== o.value) : [...value, o.value])}
              className={`h-10 rounded-full border px-3.5 text-sm ${on ? "border-brand bg-brand text-white" : "border-line bg-surface"}`}
            >
              {o.label}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

export default function ProviderFields({ form, setForm, identity = true }: { form: ProviderForm; setForm: (f: ProviderForm) => void; identity?: boolean }) {
  const { data: areas } = useAreas();
  const { data: categories } = useCategories("service");
  const set = <K extends keyof ProviderForm>(k: K, v: ProviderForm[K]) => setForm({ ...form, [k]: v });

  return (
    <div className="flex flex-col gap-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <Select label="কাজের ধরন" value={form.provider_type} onChange={(e) => set("provider_type", e.target.value)} options={PROVIDER_TYPES} />
        <Field label="অভিজ্ঞতা (বছর)" type="number" min={0} max={60} value={form.experience_years} onChange={(e) => set("experience_years", Number(e.target.value))} />
      </div>
      <Chips label="কোন কোন কাজ পারেন" options={(categories ?? []).map((c) => ({ value: c.slug, label: c.name_bn }))} value={form.skills} onChange={(v) => set("skills", v)} />
      <Chips label="কোন এলাকায় কাজ করবেন" options={(areas ?? []).map((a) => ({ value: a.id, label: a.name_bn }))} value={form.area_ids} onChange={(v) => set("area_ids", v)} />
      <TextArea label="নিজের সম্পর্কে" value={form.bio} onChange={(e) => set("bio", e.target.value)} placeholder="কী কী কাজে দক্ষ, কোথায় কাজ করেছেন" />

      {identity && (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="NID নম্বর" required value={form.nid_number} onChange={(e) => set("nid_number", e.target.value)} inputMode="numeric" />
            <Select label="লিঙ্গ (ঐচ্ছিক)" value={form.gender} onChange={(e) => set("gender", e.target.value)} options={[{ value: "", label: "বলতে চাই না" }, { value: "female", label: "মহিলা" }, { value: "male", label: "পুরুষ" }]} />
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <PhotoUpload label="নিজের ছবি" value={form.photo_url ? [form.photo_url] : []} onChange={(u) => set("photo_url", u[0] ?? "")} purpose="profile_photo" max={1} />
            <PhotoUpload label="NID সামনের দিক" value={form.nid_front_url ? [form.nid_front_url] : []} onChange={(u) => set("nid_front_url", u[0] ?? "")} purpose="nid" max={1} visibility="private" />
            <PhotoUpload label="NID পেছনের দিক" value={form.nid_back_url ? [form.nid_back_url] : []} onChange={(u) => set("nid_back_url", u[0] ?? "")} purpose="nid" max={1} visibility="private" />
          </div>
          {form.provider_type === "home_chef" && (
            <PhotoUpload label="রান্নাঘরের ছবি (হাইজিন চেকের জন্য)" value={form.kitchen_photo_urls} onChange={(u) => set("kitchen_photo_urls", u)} purpose="kitchen" max={5} />
          )}
        </>
      )}

      <Chips label="কাজের দিন" options={DAYS.map((d, i) => ({ value: i, label: d }))} value={form.working_days} onChange={(v) => set("working_days", v)} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="কাজ শুরু" type="time" value={form.work_start.slice(0, 5)} onChange={(e) => set("work_start", e.target.value)} />
        <Field label="কাজ শেষ" type="time" value={form.work_end.slice(0, 5)} onChange={(e) => set("work_end", e.target.value)} />
        <Select label="পেমেন্ট নেবেন" value={form.payout_method} onChange={(e) => set("payout_method", e.target.value)} options={[{ value: "bkash", label: "বিকাশ" }, { value: "nagad", label: "নগদ" }]} />
        <Field label="বিকাশ/নগদ নম্বর" pattern="01[3-9][0-9]{8}" value={form.payout_account} onChange={(e) => set("payout_account", e.target.value)} />
      </div>
    </div>
  );
}
