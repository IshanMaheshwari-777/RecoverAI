import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Loader2, Moon, Play, Sun, Zap } from "lucide-react";
import { api } from "../api";
import type { PipelineReport } from "../types";
import { relativeTime } from "../lib/format";
import { useHealth } from "../hooks/useHealth";
import { Button } from "./ui";
import { toast } from "./Toast";

/* ---------------------------------------------------------- theme */

function ThemeToggle() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    try {
      localStorage.setItem("recover-ai-theme", dark ? "dark" : "light");
    } catch {
      /* private mode — fine */
    }
  }, [dark]);
  return (
    <button
      onClick={() => setDark((d) => !d)}
      className="rounded-lg border border-border p-1.5 text-ink-secondary transition hover:bg-surface-2 hover:text-ink"
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
    >
      {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </button>
  );
}

/* --------------------------------------------------- live status pill */

function StatusPill({ live, label, detail }: { live: boolean; label: string; detail?: string }) {
  return (
    <span
      title={detail}
      className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-2 px-2 py-1 text-[11px] text-ink-secondary"
    >
      <span
        className={`size-1.5 rounded-full ${live ? "bg-good" : "bg-ink-muted"}`}
        aria-hidden
      />
      {label}
      <span className={live ? "text-good" : "text-ink-muted"}>{live ? "live" : "offline"}</span>
    </span>
  );
}

/* --------------------------------------------------------- run popover */

function RunControl({ report }: { report: PipelineReport | undefined }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [count, setCount] = useState(report?.count ?? 180);
  const [seed, setSeed] = useState(report?.seed ?? 42);
  const [injectFailure, setInjectFailure] = useState(false);
  const [shadow, setShadow] = useState(false);
  const [source, setSource] = useState<"synthetic" | "razorpay">("synthetic");
  const boxRef = useRef<HTMLDivElement>(null);
  const { data: health } = useHealth();
  // the server's *current* credentials, not whatever a stale/synthetic
  // report happened to record at the time it was generated
  const liveDataAvailable = health?.razorpay_live ?? report?.razorpay_live ?? false;

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!boxRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onEsc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onEsc);
    };
  }, [open]);

  const mutation = useMutation({
    mutationFn: () =>
      api.run({
        count,
        seed,
        inject_failure: source === "synthetic" && injectFailure,
        mode: shadow ? "shadow" : "live",
        source,
      }),
    onSuccess: (data) => {
      qc.setQueryData(["report"], data);
      if (data.mode === "live") void qc.invalidateQueries({ queryKey: ["runHistory"] });
      setOpen(false);
      const s = data.summary;
      const sourceLabel = data.data_source === "razorpay" ? "live Razorpay data · " : "";
      if (data.data_source === "razorpay" && s.needing_attention === 0) {
        toast(`${sourceLabel}connected, but no failed payments found right now`);
        return;
      }
      toast(
        (data.mode === "shadow" ? "Shadow run · " : "") +
          sourceLabel +
          `${s.needing_attention} transactions in ${(data.duration_ms / 1000).toFixed(1)}s` +
          (s.failed ? ` · ${s.failed} contained` : ""),
      );
    },
    onError: (e) => toast((e as Error).message, "critical"),
  });

  return (
    <div className="relative" ref={boxRef}>
      <div className="flex">
        <Button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className="rounded-r-none"
        >
          {mutation.isPending ? (
            <>
              <Loader2 className="size-3.5 animate-spin" /> Running…
            </>
          ) : (
            <>
              <Play className="size-3.5" /> Run agent
            </>
          )}
        </Button>
        <button
          onClick={() => setOpen((o) => !o)}
          disabled={mutation.isPending}
          aria-label="Run options"
          className="rounded-r-lg border-l border-white/25 bg-series-1 px-1.5 text-white transition hover:brightness-110 disabled:opacity-50"
        >
          <ChevronDown className="size-3.5" />
        </button>
      </div>

      {open && (
        <div className="absolute right-0 top-full z-40 mt-2 w-72 rounded-xl border border-border bg-surface p-4 shadow-2xl">
          <span className="text-[10px] font-medium uppercase tracking-wide text-ink-muted">
            Data source
          </span>
          <div className="mt-1.5 grid grid-cols-2 gap-1.5">
            <button
              type="button"
              onClick={() => setSource("synthetic")}
              className={`rounded-lg border px-2 py-1.5 text-[11px] font-medium transition ${
                source === "synthetic"
                  ? "border-series-1 bg-series-1/10 text-ink"
                  : "border-border text-ink-secondary hover:bg-surface-2"
              }`}
            >
              Synthetic
            </button>
            <button
              type="button"
              disabled={!liveDataAvailable}
              title={
                liveDataAvailable
                  ? "Read-only: pulls your account's recent failed payments"
                  : "No Razorpay credentials configured"
              }
              onClick={() => setSource("razorpay")}
              className={`rounded-lg border px-2 py-1.5 text-[11px] font-medium transition disabled:cursor-not-allowed disabled:opacity-40 ${
                source === "razorpay"
                  ? "border-series-1 bg-series-1/10 text-ink"
                  : "border-border text-ink-secondary hover:bg-surface-2"
              }`}
            >
              Live Razorpay
            </button>
          </div>
          <p className="mb-3 mt-2 text-[11px] leading-relaxed text-ink-muted">
            {source === "synthetic" ? (
              <>Generates a fresh batch and runs the full agent over it. Same seed → identical batch.</>
            ) : (
              <>
                Reads your account's most recent failed payments — read-only, no charges. Same
                pipeline, real data.
              </>
            )}
          </p>
          <div className="flex gap-3">
            <label className="flex-1">
              <span className="text-[10px] font-medium uppercase tracking-wide text-ink-muted">
                {source === "synthetic" ? "Transactions" : "Payments to check"}
              </span>
              <input
                type="number"
                min={10}
                max={2000}
                value={count}
                onChange={(e) => setCount(+e.target.value)}
                className="mt-1 w-full rounded-lg border border-border bg-surface-2 px-2 py-1.5 text-xs tabular outline-none focus:border-series-1"
              />
            </label>
            {source === "synthetic" && (
              <label className="w-20">
                <span className="text-[10px] font-medium uppercase tracking-wide text-ink-muted">
                  Seed
                </span>
                <input
                  type="number"
                  min={0}
                  value={seed}
                  onChange={(e) => setSeed(+e.target.value)}
                  className="mt-1 w-full rounded-lg border border-border bg-surface-2 px-2 py-1.5 text-xs tabular outline-none focus:border-series-1"
                />
              </label>
            )}
          </div>
          {source === "synthetic" && (
            <label className="mt-3 flex cursor-pointer items-start gap-2 rounded-lg bg-surface-2 p-2.5">
              <input
                type="checkbox"
                checked={injectFailure}
                onChange={(e) => setInjectFailure(e.target.checked)}
                className="mt-0.5 accent-series-1"
              />
              <span className="text-[11px] leading-relaxed text-ink-secondary">
                <span className="font-medium text-ink">Inject a corrupt record</span>
                <br />
                Adds one malformed transaction to prove it fails alone without stopping the batch.
              </span>
            </label>
          )}
          <label className="mt-2 flex cursor-pointer items-start gap-2 rounded-lg bg-surface-2 p-2.5">
            <input
              type="checkbox"
              checked={shadow}
              onChange={(e) => setShadow(e.target.checked)}
              className="mt-0.5 accent-series-1"
            />
            <span className="text-[11px] leading-relaxed text-ink-secondary">
              <span className="font-medium text-ink">Shadow run</span>
              <br />
              Decide everything, execute nothing. The result is shown but not saved.
            </span>
          </label>
          <Button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
            className="mt-3 w-full"
          >
            {mutation.isPending ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Zap className="size-3.5" />
            )}
            Run with these settings
          </Button>
        </div>
      )}
    </div>
  );
}

/* -------------------------------------------------------------- header */

export function Header({ report }: { report: PipelineReport | undefined }) {
  const { data: health } = useHealth();
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-bg">
      <div className="mx-auto flex max-w-[1280px] flex-wrap items-center gap-x-4 gap-y-2 px-6 py-3">
        <div className="flex items-center gap-2.5">
          <span className="grid size-8 place-items-center rounded-lg bg-series-1 text-white">
            <Zap className="size-4" strokeWidth={2.5} />
          </span>
          <div>
            <div className="text-sm font-semibold leading-tight text-ink">Recover AI</div>
            <div className="text-[11px] leading-tight text-ink-muted">
              Razorpay Buildathon · Track 03
            </div>
          </div>
        </div>

        <div className="ml-auto flex items-center gap-2.5">
          {report && (
            <>
              <div className="hidden items-center gap-2 md:flex">
                <span
                  title={
                    report.data_source === "razorpay"
                      ? "This run diagnosed real failed payments read from your Razorpay account"
                      : "This run used generated demo transactions"
                  }
                  className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-[11px] font-medium ${
                    report.data_source === "razorpay"
                      ? "border-good/40 bg-good/10 text-good"
                      : "border-border bg-surface-2 text-ink-secondary"
                  }`}
                >
                  <span
                    className={`size-1.5 rounded-full ${report.data_source === "razorpay" ? "bg-good" : "bg-ink-muted"}`}
                    aria-hidden
                  />
                  {report.data_source === "razorpay" ? "Live Razorpay data" : "Synthetic data"}
                </span>
                <StatusPill
                  live={health?.razorpay_live ?? report.razorpay_live}
                  label="Razorpay"
                  detail="Creating real payment objects against Razorpay's test-mode API"
                />
                <StatusPill
                  live={health?.anthropic_live ?? report.anthropic_live}
                  label="Claude"
                  detail={report.llm_model ?? "no model configured"}
                />
              </div>
              <span className="hidden text-[11px] text-ink-muted lg:inline">
                {relativeTime(report.finished_at)} · {(report.duration_ms / 1000).toFixed(1)}s ·{" "}
                <span title="Active policy version">{report.policy_version}</span>
              </span>
            </>
          )}
          <RunControl report={report} />
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
