import { Activity, AlertTriangle, ShieldCheck } from "lucide-react";
import type { PipelineReport } from "../types";
import { Card } from "./ui";

export function IncidentBanner({ report }: { report: PipelineReport }) {
  if (!report.incidents.length) return null;
  return (
    <Card className="border-warn/40 bg-warn/5">
      <div className="flex items-start gap-3">
        <Activity className="size-5 shrink-0 text-warn" />
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-ink">
            {report.incidents.length} degraded rail{report.incidents.length > 1 ? "s" : ""} detected
            — retries deferred
          </h2>
          <p className="text-xs text-ink-muted">
            A cluster of failures on one rail in a short window looks like an infrastructure
            incident, not individual recoveries. Retries against it are held so we don&rsquo;t pile
            onto a struggling gateway.
          </p>
          <div className="mt-3 space-y-2">
            {report.incidents.map((inc, i) => (
              <div key={i} className="rounded-lg bg-surface-2 px-3 py-2 text-[11px]">
                <span className="font-medium text-ink">
                  {inc.method} · {inc.reason.replace(/_/g, " ")}
                </span>{" "}
                <span className="text-ink-muted">
                  — {inc.count} failures ({(inc.share * 100).toFixed(0)}% of the batch) within{" "}
                  {inc.window_minutes} min. {inc.action_taken}.
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Card>
  );
}

export function FailurePanel({ report }: { report: PipelineReport }) {
  const failed = report.results.filter((r) => r.stage_reached === "failed");

  if (failed.length === 0) {
    return (
      <Card>
        <div className="flex items-center gap-3">
          <ShieldCheck className="size-5 shrink-0 text-good" />
          <div>
            <h2 className="text-sm font-semibold text-ink">No processing failures this run</h2>
            <p className="text-xs leading-relaxed text-ink-muted">
              Every transaction reached a decision. Open the arrow next to{" "}
              <span className="text-ink-secondary">Run agent</span> and tick{" "}
              <span className="text-ink-secondary">Inject a corrupt record</span> to watch one bad
              row fail on its own without stopping the batch.
            </p>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card className="border-critical/40 bg-critical/5">
      <div className="flex items-start gap-3">
        <AlertTriangle className="size-5 shrink-0 text-critical" />
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-ink">
            Failure containment · {failed.length} record{failed.length > 1 ? "s" : ""} caught
          </h2>
          <p className="text-xs text-ink-muted">
            The malformed record failed in isolation. The other {report.summary.completed}{" "}
            transactions were processed normally — the failure did not stop the run.
          </p>
          <div className="mt-3 space-y-2">
            {failed.map((r) => (
              <div key={r.transaction_id} className="rounded-lg bg-surface-2 px-3 py-2">
                <div className="font-mono text-[11px] text-critical">{r.transaction_id}</div>
                <div className="mt-0.5 break-all text-[11px] text-ink-secondary">
                  {r.error?.split("\n")[0]}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Card>
  );
}

export function CompliancePanel({ report }: { report: PipelineReport }) {
  const s = report.summary;
  const rules = [
    {
      title: "Fraud stops are absolute",
      body: "A risk-check failure can never become an action. Retrying would complete a fraudulent charge and earn the merchant a chargeback.",
      metric: `${s.compliance_violations} violations`,
      ok: s.compliance_violations === 0,
    },
    {
      title: "Retries capped per method",
      body: "Card networks fine merchants for retry abuse. Past the cap we stop retrying that rail and ask the customer to switch.",
      metric: `${s.escalated_actions} escalations`,
      ok: true,
    },
    {
      title: "Contact capped per customer",
      body: "At most 2 messages to one person in a rolling 48 h, across all their transactions. Silent retries don't count.",
      metric: `${s.blocked_actions} held back`,
      ok: true,
    },
  ];

  return (
    <Card
      title="Compliance &amp; stopping rules"
      subtitle="Hard limits enforced in code, with a test that regenerates a fresh batch on a new seed and proves the first one holds"
    >
      <div className="grid gap-3 sm:grid-cols-3">
        {rules.map((r) => (
          <div key={r.title} className="rounded-lg border border-border bg-surface-2/50 p-3">
            <div className="flex items-center gap-1.5">
              <span
                className={`inline-block size-1.5 rounded-full ${r.ok ? "bg-good" : "bg-critical"}`}
              />
              <span className="text-xs font-semibold text-ink">{r.title}</span>
            </div>
            <p className="mt-1.5 text-[11px] leading-relaxed text-ink-muted">{r.body}</p>
            <p className="mt-2 text-[11px] font-medium text-ink-secondary tabular">{r.metric}</p>
          </div>
        ))}
      </div>
    </Card>
  );
}
