import clsx from "clsx";
import { Info } from "lucide-react";
import type { ReactNode } from "react";

/* ---------------------------------------------------------------- Card */

export function Card({
  children,
  className,
  title,
  subtitle,
  action,
  tone,
}: {
  children: ReactNode;
  className?: string;
  title?: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  tone?: "critical" | "good";
}) {
  return (
    <section
      className={clsx(
        "rounded-xl border bg-surface p-5 animate-in",
        tone === "critical" && "border-critical/40 bg-critical/5",
        tone === "good" && "border-good/30",
        !tone && "border-border",
        className,
      )}
    >
      {(title || action) && (
        <header className="mb-4 flex items-start justify-between gap-4">
          <div className="min-w-0">
            {title && <h2 className="text-sm font-semibold text-ink">{title}</h2>}
            {subtitle && (
              <p className="mt-1 text-xs leading-relaxed text-ink-muted">{subtitle}</p>
            )}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

/* --------------------------------------------------------------- Badge */

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
        "inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium",
        TONE[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/* -------------------------------------------------------------- Button */

export function Button({
  children,
  onClick,
  variant = "primary",
  size = "md",
  disabled,
  type = "button",
  className,
  title,
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "ghost" | "outline";
  size?: "sm" | "md";
  disabled?: boolean;
  type?: "button" | "submit";
  className?: string;
  title?: string;
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={clsx(
        "inline-flex items-center justify-center gap-1.5 rounded-lg font-semibold transition",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-series-1",
        "disabled:cursor-not-allowed disabled:opacity-50",
        size === "sm" ? "px-2.5 py-1 text-[11px]" : "px-3.5 py-2 text-xs",
        variant === "primary" && "bg-series-1 text-white hover:brightness-110 active:brightness-95",
        variant === "outline" && "border border-border text-ink hover:bg-surface-2",
        variant === "ghost" && "text-ink-secondary hover:bg-surface-2 hover:text-ink",
        className,
      )}
    >
      {children}
    </button>
  );
}

/* ------------------------------------------------------------- Tooltip */

/** A hover explainer for a term the reader may not know. */
export function Explain({ children }: { children: ReactNode }) {
  return (
    <span className="group relative inline-flex align-middle">
      <Info className="size-3 cursor-help text-ink-muted" />
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 z-30 mb-1.5 w-56 -translate-x-1/2
                   rounded-lg border border-border bg-surface-2 px-2.5 py-2 text-[11px] leading-relaxed
                   text-ink-secondary opacity-0 shadow-lg transition group-hover:opacity-100"
      >
        {children}
      </span>
    </span>
  );
}

/* ----------------------------------------------------------- Stat tile */

export function Stat({
  label,
  value,
  hint,
  tone,
  emphasis,
  explain,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: "good" | "critical" | "warn";
  emphasis?: boolean;
  explain?: ReactNode;
}) {
  return (
    <div
      className={clsx(
        "rounded-xl border bg-surface p-4 animate-in",
        emphasis ? "border-series-1/40 ring-1 ring-series-1/20" : "border-border",
      )}
    >
      <div className="flex items-center gap-1.5">
        <span className="text-[11px] font-medium uppercase tracking-wide text-ink-muted">
          {label}
        </span>
        {explain && <Explain>{explain}</Explain>}
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
      {hint && <div className="mt-1 text-[11px] leading-snug text-ink-muted">{hint}</div>}
    </div>
  );
}

/* -------------------------------------------------------------- BarRow */

export function BarRow({
  label,
  value,
  total,
  color,
  suffix,
}: {
  label: ReactNode;
  value: number;
  total: number;
  color: string;
  suffix?: string;
}) {
  const pct = total ? (value / total) * 100 : 0;
  return (
    <div className="grid grid-cols-[minmax(110px,1.1fr)_2fr_auto] items-center gap-3 text-xs">
      <span className="truncate text-ink-secondary">{label}</span>
      <span className="h-2 overflow-hidden rounded-full bg-surface-2">
        <span
          className="block h-full rounded-full transition-[width] duration-500"
          style={{ width: `${pct}%`, background: color }}
        />
      </span>
      <span className="tabular whitespace-nowrap text-ink-muted">
        {value}
        {suffix ?? ""} · {pct.toFixed(0)}%
      </span>
    </div>
  );
}

/* ------------------------------------------------------------ Skeleton */

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("animate-pulse rounded-xl bg-surface-2", className)} />;
}

/* ------------------------------------------------------- Section intro */

/** A short plain-English lead-in above a group of cards. */
export function SectionLead({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mb-1">
      <h2 className="text-[13px] font-semibold text-ink">{title}</h2>
      <p className="mt-0.5 max-w-3xl text-xs leading-relaxed text-ink-muted">{children}</p>
    </div>
  );
}
