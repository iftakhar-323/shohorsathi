import { Badge, Button, PageHeader, api, errorMessage, formatDate } from "@shohor/web-core";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { DataTable, FilterChips, usePaged } from "../components";

type User = { id: number; phone: string; full_name: string; email: string; role: string; is_active: boolean; date_joined: string };
const ROLES: Record<string, string> = { customer: "গ্রাহক", provider: "প্রোভাইডার", admin: "অ্যাডমিন" };

export default function Users() {
  const [role, setRole] = useState("");
  const [q, setQ] = useState("");
  const { data, isPending } = usePaged<User>(["admin-users"], "/admin/users/", { role: role || undefined, q: q || undefined });
  const qc = useQueryClient();

  async function toggle(u: User) {
    if (!confirm(u.is_active ? `${u.full_name}-কে ব্লক করবেন?` : `${u.full_name}-কে আনব্লক করবেন?`)) return;
    try {
      await api.post(`/admin/users/${u.id}/${u.is_active ? "block" : "unblock"}/`);
      qc.invalidateQueries({ queryKey: ["admin-users"] });
    } catch (e) {
      alert(errorMessage(e));
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title="ইউজার" />
      <div className="flex flex-wrap items-center gap-3">
        <FilterChips value={role} onChange={setRole} options={[{ value: "", label: "সব" }, ...Object.entries(ROLES).map(([value, label]) => ({ value, label }))]} />
        <input type="search" aria-label="নাম বা ফোন" placeholder="নাম বা ফোন" value={q} onChange={(e) => setQ(e.target.value)} className="h-10 rounded-xl border border-line px-3" />
      </div>
      <DataTable
        loading={isPending}
        rows={data?.results}
        columns={[
          { label: "নাম", render: (u) => <span className="font-semibold">{u.full_name}</span> },
          { label: "ফোন", render: (u) => u.phone },
          { label: "ভূমিকা", render: (u) => ROLES[u.role] ?? u.role },
          { label: "যোগদান", render: (u) => formatDate(u.date_joined) },
          { label: "অবস্থা", render: (u) => (u.is_active ? <Badge tone="ok">সক্রিয়</Badge> : <Badge tone="bad">ব্লকড</Badge>) },
          { label: "", render: (u) => <Button variant={u.is_active ? "danger" : "secondary"} onClick={() => toggle(u)}>{u.is_active ? "ব্লক" : "আনব্লক"}</Button> },
        ]}
      />
    </div>
  );
}
