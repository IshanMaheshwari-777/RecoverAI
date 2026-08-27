import { useMemo, useState } from "react";
import type { PipelineReport, TransactionResult } from "../types";
import { inr, label, relativeTime } from "../lib/format";
import { Badge, Card } from "./ui";

type OutcomeFilter = "all" | "recovered" | "not_recovered" | "blocked" | "failed" | "confirmed";

function outcomeBadge(r: TransactionResult) {
  if (r.stage_reached === "failed")
    return <Badge tone="critical">failed · contained</Badge>;
  const e = r.audit_entry;
  if (!e.executed) return <Badge tone="warn">blocked</Badge>;
  if (e.confirmed_outcome === "recovered")
    return <Badge tone="good">confirmed ✓</Badge>;
  return e.projected_outcome === "recovered" ? (
    <Badge tone="series-1">projected recovered</Badge>
  ) : (
    <Badge tone="neutral">not recovered</Badge>
  );
}

function methodTone(m: string) {
  if (m === "razorpay_api" || m === "llm_message") return "series-1" as const;
  if (m === "razorpay_api_ratelimited" || m === "pipeline_error") return "warn" as const;
  return "neutral" as const;
}

export function AuditTable({ report }: { report: PipelineReport }) {
  const [q, setQ] = useState("");
  const [outcome, setOutcome] = useState<OutcomeFilter>("all");
  const [method, setMethod] = useState<string>("all");

  const methods = useMemo(
    () => ["all", ...Object.keys(report.summary.execution_methods)],
    [report],
  );

  const rows = useMemo(() => {
    return report.results.filter((r) => {
      const e = r.audit_entry;
      if (method !== "all" && e.execution_method !== method) return false;
      if (outcome === "recovered" && !(e.executed && e.projected_outcome === "recovered")) return false;
      if (outcome === "not_recovered" && !(e.executed && e.projected_outcome === "not_recovered")) return false;
      if (outcome === "blocked" && e.executed) return false;
      if (outcome === "confirmed" && e.confirmed_outcome !== "recovered") return false;
      if (outcome === "failed" && r.stage_reached !== "failed") return false;
      if (q) {
        const hay = `${r.transaction_id} ${e.customer_id} ${e.reason} ${e.detail}`.toLowerCase();
        if (!hay.includes(q.toLowerCase())) return false;
      }
      return true;
    });
  }, [report, q, outcome, method]);

  return (
    <Card
      title="Audit trail"
      subtitle={`${rows.length} of ${report.results.length} decisions — every one, executed or blocked`}
      action={
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search id, customer, reason…"
          className="w-52 rounded-lg border border-border bg-surface-2 px-2.5 py-1 text-xs outline-none focus:border-series-1"
        />
      }
    >
      <div className="mb-3 flex flex-wrap gap-1.5">
        {(["all", "recovered", "not_recovered", "blocked", "confirmed", "failed"] as OutcomeFilter[]).map((f) => (
          <button
            key={f}
            onClick={() => setOutcome(f)}
            className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium transition ${
              outcome === f
                ? "bg-series-1 text-white"
                : "bg-surface-2 text-ink-secondary hover:text-ink"
            }`}
          >
            {label.action(f) === "—" ? f : f.replace(/_/g, " ")}
          </button>
        ))}
        <select
          value={method}
          onChange={(e) => setMethod(e.target.value)}
          className="ml-auto rounded-lg border border-border bg-surface-2 px-2 py-0.5 text-[11px] text-ink-secondary outline-none"
        >
          {methods.map((m) => (
            <option key={m} value={m}>
              {m === "all" ? "all methods" : label.method(m)}
            </option>
          ))}
        </select>
      </div>

      <div className="max-h-[460px] overflow-auto rounded-lg border border-border">
        <table className="w-full text-left text-xs">
          <thead className="sticky top-0 bg-surface text-ink-muted">
            <tr className="[&>th]:whitespace-nowrap [&>th]:px-3 [&>th]:py-2 [&>th]:font-medium">
              <th>Transaction</th>
              <th className="text-right">Amount</th>
              <th>Diagnosed</th>
              <th>Final action</th>
              <th>Method</th>
              <th>Outcome</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((r) => {
              const e = r.audit_entry;
              return (
                <tr key={r.transaction_id} className="align-top hover:bg-surface-2/60">
                  <td className="px-3 py-2">
                    <div className="font-mono text-[11px] text-ink-secondary">{r.transaction_id}</div>
                    <div className="text-[10px] text-ink-muted">{e.customer_id}</div>
                  </td>
                  <td className="px-3 py-2 text-right tabular text-ink">{inr(e.amount)}</td>
                  <td className="px-3 py-2 whitespace-nowrap text-ink-secondary">
                    {label.action(e.diagnosis_action)}
                    <div className="text-[10px] text-ink-muted">{label.diagnosis(e.diagnosis_method)}</div>
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap text-ink-secondary">{label.action(e.final_action)}</td>
                  <td className="px-3 py-2">
                    <Badge tone={methodTone(e.execution_method)}>{label.method(e.execution_method)}</Badge>
                    {e.scheduled_for && (
                      <div className="mt-0.5 text-[10px] text-ink-muted">
                        fires {relativeTime(e.scheduled_for).replace(" ago", " out")}
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-2">{outcomeBadge(r)}</td>
                  <td className="px-3 py-2 max-w-[280px] text-ink-muted">{e.reason}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
