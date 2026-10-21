import { Empty, Loading, api, type Paginated } from "@shohor/web-core";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";

export type Column<T> = { label: string; render: (row: T) => ReactNode; className?: string };

export function DataTable<T extends { id: number | string }>({
  rows,
  columns,
  onRowClick,
  loading,
  empty = "কিছু পাওয়া যায়নি",
}: {
  rows: T[] | undefined;
  columns: Column<T>[];
  onRowClick?: (row: T) => void;
  loading?: boolean;
  empty?: string;
}) {
  if (loading) return <Loading />;
  if (!rows?.length) return <Empty title={empty} />;
  return (
    <div className="overflow-x-auto rounded-[20px] border border-line bg-surface">
      <table className="w-full min-w-[720px] border-collapse text-[15px]">
        <thead>
          <tr className="text-left text-[13px] text-muted">
            {columns.map((c) => (
              <th key={c.label} className="border-b border-line px-4 py-3 font-semibold">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.id}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              onKeyDown={onRowClick ? (e) => e.key === "Enter" && onRowClick(row) : undefined}
              tabIndex={onRowClick ? 0 : undefined}
              className={onRowClick ? "cursor-pointer hover:bg-brand-tint focus:bg-brand-tint focus:outline-none" : ""}
            >
              {columns.map((c) => (
                <td key={c.label} className={`border-b border-subtle px-4 py-3 align-middle ${c.className ?? ""}`}>
                  {c.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function usePaged<T>(key: unknown[], url: string, params: Record<string, unknown> = {}) {
  return useQuery({
    queryKey: [...key, params],
    queryFn: async () => (await api.get<Paginated<T>>(url, { params })).data,
  });
}

/** Private uploads (NID) need the auth header, so they are fetched as blobs rather than linked. */
export function PrivateImage({ url, alt }: { url: string; alt: string }) {
  const [src, setSrc] = useState<string>();
  useEffect(() => {
    if (!url) return;
    if (!url.startsWith("/api/")) return setSrc(url);
    let revoke = "";
    api.get(url.replace(/^\/api/, ""), { responseType: "blob" }).then((res) => {
      revoke = URL.createObjectURL(res.data);
      setSrc(revoke);
    }).catch(() => setSrc(undefined));
    return () => {
      if (revoke) URL.revokeObjectURL(revoke);
    };
  }, [url]);
  if (!url) return <span className="text-sm text-muted">দেওয়া হয়নি</span>;
  return src ? (
    <a href={src} target="_blank" rel="noreferrer">
      <img src={src} alt={alt} className="h-32 w-48 rounded-xl border border-line object-cover" />
    </a>
  ) : (
    <span className="flex h-32 w-48 items-center justify-center rounded-xl bg-subtle text-sm text-muted">লোড হচ্ছে…</span>
  );
}

export function FilterChips({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: { value: string; label: string }[] }) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
          className={`h-10 rounded-full border px-4 text-sm font-semibold ${value === o.value ? "border-ink bg-ink text-white" : "border-line bg-surface"}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
