import { api, Badge, Button, errorMessage, ErrorNote, Field, formatTaka, localName, Modal, PageHeader, PhotoUpload, Select, t, Tabs, TextArea, type Category, type Product, type Service, useAreas } from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { DataTable, usePaged } from "../components";

type Kind = "services" | "products" | "categories";
type Row = Record<string, unknown> & { id: number; slug: string };

const slugify = (s: string) => s.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

function ItemForm({ kind, item, onDone }: { kind: Kind; item: Row | null; onDone: () => void }) {
  const { data: categories } = useQuery({
    queryKey: ["admin-categories"],
    queryFn: async () => (await api.get<Category[]>("/categories/")).data,
  });
  const { data: areas } = useAreas();
  const blank: Row =
    kind === "categories"
      ? { id: 0, slug: "", kind: "service", name_en: "", name_bn: "", sort_order: 0, is_active: true, parent: null }
      : kind === "services"
        ? { id: 0, slug: "", category: "", name_en: "", name_bn: "", description: "", image_url: "", area_ids: [], is_active: true, base_price: "", price_note: "", duration_minutes: 60, warranty_days: 7, emergency_available: false }
        : { id: 0, slug: "", category: "", name_en: "", name_bn: "", description: "", image_url: "", area_ids: [], is_active: true, price: "", unit: "pcs", stock: 0, shop_name: "" };
  const [f, setF] = useState<Row>(item ?? blank);
  const [error, setError] = useState("");
  const set = (k: string, v: unknown) => setF({ ...f, [k]: v });
  const str = (k: string) => String(f[k] ?? "");
  const wantKind = kind === "products" ? "product" : "service";

  async function save(e: FormEvent) {
    e.preventDefault();
    setError("");
    const body = { ...f, slug: f.slug || slugify(str("name_en")) };
    try {
      if (item) await api.patch(`/${kind}/${item.slug}/`, body);
      else await api.post(`/${kind}/`, body);
      onDone();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <form onSubmit={save} className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3">
        <Field label={t("নাম (বাংলা)")} required value={str("name_bn")} onChange={(e) => set("name_bn", e.target.value)} />
        <Field label={t("নাম (English)")} required value={str("name_en")} onChange={(e) => set("name_en", e.target.value)} />
        <Field label="Slug" value={str("slug")} onChange={(e) => set("slug", e.target.value)} hint={t("খালি রাখলে ইংরেজি নাম থেকে")} disabled={!!item} />
        {kind === "categories" ? (
          <Select label={t("ধরন")} value={str("kind")} onChange={(e) => set("kind", e.target.value)} options={[{ value: "service", label: t("সার্ভিস") }, { value: "product", label: t("পণ্য") }]} />
        ) : (
          <Select
            label={t("ক্যাটাগরি")}
            required
            value={str("category")}
            onChange={(e) => set("category", Number(e.target.value))}
            options={[{ value: "", label: t("বাছুন") }, ...(categories ?? []).filter((c) => c.kind === wantKind).map((c) => ({ value: c.id, label: localName(c) }))]}
          />
        )}
      </div>
      {kind === "services" && (
        <div className="grid grid-cols-2 gap-3">
          <Field label={t("শুরুর দাম (৳)")} type="number" min={0} required value={str("base_price")} onChange={(e) => set("base_price", e.target.value)} />
          <Field label={t("দামের নোট")} value={str("price_note")} onChange={(e) => set("price_note", e.target.value)} />
          <Field label={t("সময় (মিনিট)")} type="number" min={1} value={str("duration_minutes")} onChange={(e) => set("duration_minutes", Number(e.target.value))} />
          <Field label={t("ওয়ারেন্টি (দিন)")} type="number" min={0} max={30} value={str("warranty_days")} onChange={(e) => set("warranty_days", Number(e.target.value))} />
          <label className="col-span-2 flex items-center gap-2">
            <input type="checkbox" checked={!!f.emergency_available} onChange={(e) => set("emergency_available", e.target.checked)} className="size-5 accent-brand" />
            {t("জরুরি সেবা হিসেবে পাওয়া যাবে")}
          </label>
        </div>
      )}
      {kind === "products" && (
        <div className="grid grid-cols-2 gap-3">
          <Field label={t("দাম (৳)")} type="number" min={0} required value={str("price")} onChange={(e) => set("price", e.target.value)} />
          <Field label={t("একক")} value={str("unit")} onChange={(e) => set("unit", e.target.value)} />
          <Field label={t("স্টক")} type="number" min={0} value={str("stock")} onChange={(e) => set("stock", Number(e.target.value))} />
          <Field label={t("দোকান")} value={str("shop_name")} onChange={(e) => set("shop_name", e.target.value)} />
        </div>
      )}
      {kind !== "categories" && (
        <>
          <TextArea label={t("বিবরণ")} value={str("description")} onChange={(e) => set("description", e.target.value)} />
          <PhotoUpload label={t("ছবি")} value={str("image_url") ? [str("image_url")] : []} onChange={(u) => set("image_url", u[0] ?? "")} purpose="catalog" max={1} />
          <fieldset className="m-0 flex flex-wrap gap-2 border-0 p-0">
            <legend className="mb-2 text-[15px] font-semibold">{t("এলাকা (কিছু না বাছলে সব এলাকায়)")}</legend>
            {areas?.map((a) => {
              const ids = (f.area_ids as number[]) ?? [];
              const on = ids.includes(a.id);
              return (
                <button key={a.id} type="button" aria-pressed={on} onClick={() => set("area_ids", on ? ids.filter((x) => x !== a.id) : [...ids, a.id])} className={`h-9 rounded-full border px-3 text-sm ${on ? "border-brand bg-brand text-white" : "border-line"}`}>
                  {localName(a)}
                </button>
              );
            })}
          </fieldset>
        </>
      )}
      <label className="flex items-center gap-2">
        <input type="checkbox" checked={!!f.is_active} onChange={(e) => set("is_active", e.target.checked)} className="size-5 accent-brand" />
        {t("চালু (গ্রাহকরা দেখতে পাবেন)")}
      </label>
      <ErrorNote>{error}</ErrorNote>
      <Button type="submit">{t("সেভ করুন")}</Button>
    </form>
  );
}

export default function Catalog() {
  const [kind, setKind] = useState<Kind>("services");
  const qc = useQueryClient();
  const paged = usePaged<Row>(["admin-catalog", kind], `/${kind}/`, {});
  const { data: categories, isPending: catPending } = useQuery({
    queryKey: ["admin-categories"],
    queryFn: async () => (await api.get<Row[]>("/categories/")).data,
    enabled: kind === "categories",
  });
  const rows = kind === "categories" ? categories : paged.data?.results;
  const [editing, setEditing] = useState<Row | null | "new">(null);

  function done() {
    setEditing(null);
    qc.invalidateQueries({ queryKey: ["admin-catalog"] });
    qc.invalidateQueries({ queryKey: ["admin-categories"] });
    qc.invalidateQueries({ queryKey: ["categories"] });
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t("ক্যাটালগ")} subtitle={t("ফিক্সড দামের সার্ভিস, পণ্য ও ক্যাটাগরি")} actions={<Button icon="plus" onClick={() => setEditing("new")}>{t("নতুন যোগ করুন")}</Button>} />
      <Tabs value={kind} onChange={setKind} tabs={[{ value: "services", label: t("সার্ভিস") }, { value: "products", label: t("পণ্য") }, { value: "categories", label: t("ক্যাটাগরি") }]} />
      <DataTable
        loading={kind === "categories" ? catPending : paged.isPending}
        rows={rows}
        onRowClick={setEditing}
        columns={[
          { label: t("নাম"), render: (r) => <><span className="font-semibold">{String(r.name_bn)}</span><span className="block text-[13px] text-muted">{String(r.name_en)}</span></> },
          { label: "Slug", render: (r) => <code className="text-sm">{r.slug}</code> },
          kind === "categories"
            ? { label: t("ধরন"), render: (r) => (r.kind === "service" ? t("সার্ভিস") : t("পণ্য")) }
            : { label: t("দাম"), render: (r) => formatTaka((r as unknown as Service).base_price ?? (r as unknown as Product).price) },
          ...(kind === "products" ? [{ label: t("স্টক"), render: (r: Row) => String(r.stock) }] : []),
          { label: t("অবস্থা"), render: (r) => (r.is_active ? <Badge tone="ok">{t("চালু")}</Badge> : <Badge>{t("বন্ধ")}</Badge>) },
        ]}
      />
      <Modal title={editing === "new" ? t("নতুন যোগ করুন") : t("এডিট")} open={editing !== null} onClose={() => setEditing(null)}>
        {editing !== null && <ItemForm key={editing === "new" ? "new" : editing.id} kind={kind} item={editing === "new" ? null : editing} onDone={done} />}
      </Modal>
    </div>
  );
}
