import { useEffect, useState } from "react";
import { Activity, Moon, Sun } from "lucide-react";
import type { PipelineReport } from "../types";
import { relativeTime } from "../lib/format";

function ThemeToggle() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    try {
      localStorage.setItem("rra-theme", dark ? "dark" : "light");
    } catch {
      /* ignore */
    }
  }, [dark]);
  return (
    <button
      onClick={() => setDark((d) => !d)}
      className="rounded-lg border border-border p-1.5 text-ink-secondary hover:bg-surface-2"
      aria-label="Toggle theme"
    >
      {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </button>
  );
}

function Dot({ live, label }: { live: boolean; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] text-ink-secondary">
      <span className={`size-1.5 rounded-full ${live ? "bg-good" : "bg-ink-muted"}`} />
      {label} {live ? "live" : "fallback"}
    </span>
  );
}

export function Header({ report }: { report: PipelineReport | undefined }) {
  return (
    <header className="sticky top-0 z-10 border-b border-border bg-bg">
      <div className="mx-auto flex max-w-[1240px] items-center gap-4 px-6 py-3">
        <div className="flex items-center gap-2.5">
          <span className="grid size-8 place-items-center rounded-lg bg-series-1 text-white">
            <Activity className="size-4" />
          </span>
          <div>
            <div className="text-sm font-semibold leading-tight text-ink">Revenue Recovery Agent</div>
            <div className="text-[11px] text-ink-muted">Razorpay Buildathon · Track 03</div>
          </div>
        </div>
        {report && (
          <div className="ml-auto flex items-center gap-4">
            <Dot live={report.razorpay_live} label="Razorpay" />
            <Dot live={report.anthropic_live} label="Anthropic" />
            <span className="hidden text-[11px] text-ink-muted sm:inline">
              run {report.run_id.slice(4, 12)} · {relativeTime(report.finished_at)} ·{" "}
              {report.duration_ms} ms
            </span>
            <ThemeToggle />
          </div>
        )}
        {!report && (
          <div className="ml-auto">
            <ThemeToggle />
          </div>
        )}
      </div>
    </header>
  );
}
