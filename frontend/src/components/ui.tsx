import clsx from "clsx";
import type { ReactNode } from "react";

export function Card({
  children,
  className,
  title,
  subtitle,
  action,
}: {
  children: ReactNode;
  className?: string;
  title?: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <section
      className={clsx(
        "rounded-xl border border-border bg-surface p-5 animate-in",
        className,
      )}
    >
      {(title || action) && (
        <header className="mb-4 flex items-start justify-between gap-4">
          <div>
            {title && <h2 className="text-sm font-semibold text-ink">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs text-ink-muted">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

type Tone = "neutral" | "good" | "warn" | "critical" | "series-1" | "series-2";

const TONE: Record<Tone, string> = {
  neutral: "bg-surface-2 text-ink-secondary",
  good: "bg-good/15 text-good",
  warn: "bg-warn/15 text-warn",
  critical: "bg-critical/15 text-critical",
  "series-1": "bg-series-1/15 text-series-1",
  "series-2": "bg-series-2/15 text-series-2",
};

export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium",
        TONE[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function Button({
  children,
  onClick,
  variant = "primary",
  disabled,
  type = "button",
  className,
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "ghost" | "outline";
  disabled?: boolean;
  type?: "button" | "submit";
  className?: string;
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={clsx(
        "inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition",
        "disabled:cursor-not-allowed disabled:opacity-50",
        variant === "primary" &&
          "bg-series-1 text-white hover:brightness-110 active:brightness-95",
        variant === "outline" &&
          "border border-border text-ink hover:bg-surface-2",
        variant === "ghost" && "text-ink-secondary hover:bg-surface-2 hover:text-ink",
        className,
      )}
    >
      {children}
    </button>
  );
}

export function Stat({
  label,
  value,
  hint,
  tone,
  emphasis,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: "good" | "critical" | "warn";
  emphasis?: boolean;
}) {
  return (
    <div
      className={clsx(
        "rounded-xl border border-border bg-surface p-4 animate-in",
        emphasis && "ring-1 ring-series-1/30",
      )}
    >
      <div className="text-[11px] font-medium uppercase tracking-wide text-ink-muted">
        {label}
      </div>
      <div
        className={clsx(
          "mt-1.5 text-2xl font-semibold tabular tracking-tight",
          tone === "good" && "text-good",
          tone === "critical" && "text-critical",
          tone === "warn" && "text-warn",
        )}
      >
        {value}
      </div>
      {hint && <div className="mt-1 text-[11px] text-ink-muted">{hint}</div>}
    </div>
  );
}

export function BarRow({
  label,
  value,
  total,
  color,
}: {
  label: string;
  value: number;
  total: number;
  color: string;
}) {
  const pct = total ? (value / total) * 100 : 0;
  return (
    <div className="grid grid-cols-[minmax(120px,1fr)_2fr_auto] items-center gap-3 text-xs">
      <span className="truncate text-ink-secondary">{label}</span>
      <span className="h-2 overflow-hidden rounded-full bg-surface-2">
        <span
          className="block h-full rounded-full"
          style={{ width: `${pct}%`, background: color }}
        />
      </span>
      <span className="tabular text-ink-muted">
        {value} · {pct.toFixed(0)}%
      </span>
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("animate-pulse rounded-lg bg-surface-2", className)} />;
}
