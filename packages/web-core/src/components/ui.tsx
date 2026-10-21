import { t } from "../lib/i18n";
import { useId, useState, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";

import { upload } from "../lib/api";
import { getCity, setCity, useCities } from "../lib/shared-api";
import { formatDateTime, statusInfo, type Tone } from "../lib/format";
import Icon, { type IconName } from "./Icon";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "alert";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-brand text-white hover:bg-brand-strong",
  secondary: "border border-brand bg-surface text-brand-strong hover:bg-brand-tint",
  ghost: "border border-line bg-surface text-ink hover:bg-subtle",
  danger: "border border-bad bg-surface text-bad hover:bg-bad-soft",
  alert: "bg-alert text-ink hover:brightness-95",
};

export function Button({
  variant = "primary",
  icon,
  loading,
  className = "",
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; icon?: IconName; loading?: boolean }) {
  return (
    <button
      type="button"
      {...props}
      disabled={props.disabled || loading}
      className={`inline-flex h-11 items-center justify-center gap-2 rounded-xl px-4 text-[15px] font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${VARIANTS[variant]} ${className}`}
    >
      {loading ? <Spinner size={16} /> : icon ? <Icon name={icon} size={18} /> : null}
      {children}
    </button>
  );
}

type FieldProps = { label: string; hint?: string; error?: string };

function FieldShell({ id, label, hint, error, children }: FieldProps & { id: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-[15px] font-semibold">
        {label}
      </label>
      {children}
      {hint && !error && <span className="text-[13px] text-muted">{hint}</span>}
      {error && <span className="text-[13px] font-medium text-bad">{error}</span>}
    </div>
  );
}

const INPUT = "w-full rounded-xl border border-line bg-surface px-3 text-[15px] text-ink outline-none focus:border-brand focus:ring-2 focus:ring-brand-soft";

export function Field({ label, hint, error, ...props }: FieldProps & InputHTMLAttributes<HTMLInputElement>) {
  const id = useId();
  return (
    <FieldShell id={id} label={label} hint={hint} error={error}>
      <input id={id} {...props} className={`h-11 ${INPUT} ${props.className ?? ""}`} />
    </FieldShell>
  );
}

export function TextArea({ label, hint, error, ...props }: FieldProps & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const id = useId();
  return (
    <FieldShell id={id} label={label} hint={hint} error={error}>
      <textarea id={id} rows={3} {...props} className={`py-2.5 ${INPUT}`} />
    </FieldShell>
  );
}

export function Select({
  label,
  hint,
  error,
  options,
  ...props
}: FieldProps & SelectHTMLAttributes<HTMLSelectElement> & { options: { value: string | number; label: string }[] }) {
  const id = useId();
  return (
    <FieldShell id={id} label={label} hint={hint} error={error}>
      <select id={id} {...props} className={`h-11 ${INPUT}`}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </FieldShell>
  );
}

const TONES: Record<Tone, string> = {
  ok: "bg-brand-soft text-brand-strong",
  info: "bg-info-soft text-info-strong",
  warn: "bg-alert-soft text-alert-strong",
  bad: "bg-bad-soft text-bad",
  muted: "bg-subtle text-muted",
};

export function StatusBadge({ status, className = "" }: { status: string; className?: string }) {
  const { label, tone } = statusInfo(status);
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-[13px] font-semibold ${TONES[tone]} ${className}`}>{label}</span>;
}

export function Badge({ tone = "muted", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-[13px] font-semibold ${TONES[tone]}`}>{children}</span>;
}

export function Card({ className = "", children }: { className?: string; children: ReactNode }) {
  return <div className={`rounded-[20px] border border-line bg-surface p-5 ${className}`}>{children}</div>;
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="flex flex-col gap-1">
        <h1 className="m-0 text-[28px] leading-tight font-bold">{title}</h1>
        {subtitle && <p className="m-0 text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Spinner({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className="animate-spin" aria-hidden="true">
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export function Loading({ label = t("লোড হচ্ছে…") }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-3 py-10 text-muted">
      <Spinner /> {label}
    </div>
  );
}

export function Empty({ icon = "list", title, children }: { icon?: IconName; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-[20px] border border-dashed border-line bg-surface px-6 py-12 text-center">
      <span className="flex size-12 items-center justify-center rounded-2xl bg-subtle text-muted">
        <Icon name={icon} size={24} />
      </span>
      <p className="m-0 text-lg font-semibold">{title}</p>
      {children && <div className="text-muted">{children}</div>}
    </div>
  );
}

export function ErrorNote({ children }: { children: ReactNode }) {
  if (!children) return null;
  return (
    <p role="alert" className="m-0 rounded-xl bg-bad-soft px-4 py-3 text-[15px] font-medium text-bad">
      {children}
    </p>
  );
}

export function SuccessNote({ children }: { children: ReactNode }) {
  if (!children) return null;
  return <p role="status" className="m-0 rounded-xl bg-brand-soft px-4 py-3 text-[15px] font-medium text-brand-strong">{children}</p>;
}

export function Tabs<T extends string>({ value, onChange, tabs }: { value: T; onChange: (v: T) => void; tabs: { value: T; label: string }[] }) {
  return (
    <div role="tablist" className="flex flex-wrap gap-2">
      {tabs.map((t) => (
        <button
          key={t.value}
          type="button"
          role="tab"
          aria-selected={value === t.value}
          onClick={() => onChange(t.value)}
          className={`h-11 rounded-full border px-4 text-[15px] font-semibold ${value === t.value ? "border-ink bg-ink text-white" : "border-line bg-surface text-ink"}`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function Timeline({ events }: { events: { status: string; note?: string; created_at: string }[] }) {
  return (
    <ol className="m-0 flex list-none flex-col gap-0 p-0">
      {events.map((e, i) => (
        <li key={i} className="relative flex gap-3 pb-5 last:pb-0">
          {i < events.length - 1 && <span className="absolute top-6 left-[9px] h-full w-0.5 bg-line" aria-hidden="true" />}
          <span className="mt-1 size-5 shrink-0 rounded-full border-4 border-brand-soft bg-brand" aria-hidden="true" />
          <div className="flex flex-col">
            <span className="font-semibold">{statusInfo(e.status).label}</span>
            {e.note && <span className="text-sm text-muted">{e.note}</span>}
            <span className="text-[13px] text-muted">{formatDateTime(e.created_at)}</span>
          </div>
        </li>
      ))}
    </ol>
  );
}

export function PhotoUpload({
  label,
  value,
  onChange,
  purpose,
  max = 5,
  visibility = "public",
}: {
  label: string;
  value: string[];
  onChange: (urls: string[]) => void;
  purpose: string;
  max?: number;
  visibility?: "public" | "private";
}) {
  const id = useId();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function pick(files: FileList | null) {
    if (!files?.length) return;
    setBusy(true);
    setError("");
    try {
      const urls = [];
      for (const f of Array.from(files).slice(0, max - value.length)) urls.push(await upload(f, purpose, visibility));
      onChange([...value, ...urls]);
    } catch {
      setError(t("ছবি আপলোড করা যায়নি। ১০ MB-এর ছোট JPG/PNG দিন।"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <span className="text-[15px] font-semibold">{label}</span>
      <div className="flex flex-wrap gap-2">
        {value.map((url) => (
          <div key={url} className="relative">
            {visibility === "public" ? (
              <img src={url} alt="" className="size-20 rounded-xl border border-line object-cover" />
            ) : (
              <span className="flex size-20 items-center justify-center rounded-xl border border-line bg-subtle text-xs text-muted">{t("আপলোড হয়েছে")}</span>
            )}
            <button
              type="button"
              aria-label={t("ছবি সরান")}
              onClick={() => onChange(value.filter((u) => u !== url))}
              className="absolute -top-2 -right-2 flex size-7 items-center justify-center rounded-full border border-line bg-surface"
            >
              <Icon name="x" size={14} />
            </button>
          </div>
        ))}
        {value.length < max && (
          <label
            htmlFor={id}
            className="flex size-20 cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-[1.5px] border-dashed border-brand/50 bg-surface text-xs text-brand-strong"
          >
            {busy ? <Spinner size={18} /> : <Icon name="camera" />}
            {t("ছবি দিন")}
          </label>
        )}
        <input id={id} type="file" accept="image/*" multiple={max > 1} className="sr-only" onChange={(e) => pick(e.target.files)} />
      </div>
      {error && <span className="text-[13px] font-medium text-bad">{error}</span>}
    </div>
  );
}

export function Stat({ label, value, icon }: { label: string; value: ReactNode; icon?: IconName }) {
  return (
    <div className="flex flex-col gap-1.5 rounded-2xl border border-line bg-surface p-4">
      <span className="flex items-center gap-2 text-sm text-muted">
        {icon && <Icon name={icon} size={16} />}
        {label}
      </span>
      <span className="text-[26px] font-bold">{value}</span>
    </div>
  );
}

export function Modal({ title, open, onClose, children }: { title: string; open: boolean; onClose: () => void; children: ReactNode }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 sm:items-center" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="flex max-h-[90vh] w-full max-w-lg flex-col gap-4 overflow-auto rounded-3xl bg-surface p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-4">
          <h2 className="m-0 text-xl font-bold">{title}</h2>
          <button type="button" aria-label={t("বন্ধ করুন")} onClick={onClose} className="flex size-10 items-center justify-center rounded-xl border border-line">
            <Icon name="x" size={18} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

/** City switcher; picking a city reloads so every area list and filter follows it. */
export function CitySelect({ className = "" }: { className?: string }) {
  const { data: cities } = useCities();
  if (!cities || cities.length < 2) return null;
  return (
    <label className={`flex items-center gap-1 ${className}`}>
      <span className="sr-only">{t("শহর")}</span>
      <Icon name="pin" size={16} />
      <select
        value={getCity()}
        onChange={(e) => {
          setCity(e.target.value);
          window.location.reload();
        }}
        className="h-11 rounded-full border border-line bg-surface px-3 text-[15px]"
      >
        <option value="">{t("সব শহর")}</option>
        {cities.map((c) => <option key={c} value={c}>{t(c)}</option>)}
      </select>
    </label>
  );
}
