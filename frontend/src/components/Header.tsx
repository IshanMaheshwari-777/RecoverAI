import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Loader2, Moon, Play, Sun, Zap } from "lucide-react";
import { api } from "../api";
import type { PipelineReport } from "../types";
import { relativeTime } from "../lib/format";
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
  const boxRef = useRef<HTMLDivElement>(null);

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
    mutationFn: () => api.run({ count, seed, inject_failure: injectFailure }),
    onSuccess: (data) => {
      qc.setQueryData(["report"], data);
      setOpen(false);
      const s = data.summary;
      toast(
        `Processed ${s.needing_attention} transactions in ${(data.duration_ms / 1000).toFixed(1)}s` +
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
          <p className="mb-3 text-[11px] leading-relaxed text-ink-muted">
            Generates a fresh batch of transactions and runs the full agent over it. Same seed →
            identical batch, so results are reproducible.
          </p>
          <div className="flex gap-3">
            <label className="flex-1">
              <span className="text-[10px] font-medium uppercase tracking-wide text-ink-muted">
                Transactions
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
          </div>
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
                <StatusPill
                  live={report.razorpay_live}
                  label="Razorpay"
                  detail="Creating real payment objects against Razorpay's test-mode API"
                />
                <StatusPill
                  live={report.anthropic_live}
                  label="Claude"
                  detail={report.llm_model ?? "no model configured"}
                />
              </div>
              <span className="hidden text-[11px] text-ink-muted lg:inline">
                {relativeTime(report.finished_at)} · {(report.duration_ms / 1000).toFixed(1)}s
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
