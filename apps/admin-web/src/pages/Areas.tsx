import { api, Button, errorMessage, ErrorNote, Field, PageHeader, t, type Area } from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { DataTable } from "../components";

export default function Areas() {
  const qc = useQueryClient();
  const { data, isPending } = useQuery({ queryKey: ["admin-areas"], queryFn: async () => (await api.get<Area[]>("/admin/areas/")).data });
  const [form, setForm] = useState({ city: "Dhaka", name_en: "", name_bn: "", ward: "" });
  const [error, setError] = useState("");

  async function add(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.post("/admin/areas/", form);
      setForm({ ...form, name_en: "", name_bn: "", ward: "" });
      qc.invalidateQueries({ queryKey: ["admin-areas"] });
      qc.invalidateQueries({ queryKey: ["areas"] });
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t("এলাকা")} subtitle={t("শহর ও এলাকা যোগ করুন; নতুন শহরে চালু করতে শুধু এলাকা যোগ করলেই হবে")} />
      <form onSubmit={add} className="grid items-end gap-3 rounded-[20px] border border-line bg-surface p-4 sm:grid-cols-5">
        <Field label={t("শহর")} required value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} />
        <Field label={t("নাম (বাংলা)")} required value={form.name_bn} onChange={(e) => setForm({ ...form, name_bn: e.target.value })} />
        <Field label={t("নাম (English)")} required value={form.name_en} onChange={(e) => setForm({ ...form, name_en: e.target.value })} />
        <Field label={t("ওয়ার্ড")} value={form.ward} onChange={(e) => setForm({ ...form, ward: e.target.value })} />
        <Button type="submit" icon="plus">{t("যোগ করুন")}</Button>
      </form>
      <ErrorNote>{error}</ErrorNote>
      <DataTable
        loading={isPending}
        rows={data}
        columns={[
          { label: t("শহর"), render: (a) => a.city },
          { label: t("এলাকা"), render: (a) => <><span className="font-semibold">{a.name_bn}</span> <span className="text-muted">({a.name_en})</span></> },
          { label: t("ওয়ার্ড"), render: (a) => a.ward || "—" },
          { label: "ID", render: (a) => a.id },
        ]}
      />
    </div>
  );
}
