import { Fragment, useMemo, useState } from "react";
import { ChevronRight, Search } from "lucide-react";
import type { PipelineReport, TransactionResult } from "../../types";
import { inr, label, relativeTime } from "../../lib/format";
import { Badge, Card, SectionLead } from "../ui";

type OutcomeFilter = "all" | "recovered" | "not_recovered" | "blocked" | "confirmed" | "failed";

const FILTERS: { key: OutcomeFilter; text: string }[] = [
  { key: "all", text: "All" },
  { key: "recovered", text: "Projected recovered" },
  { key: "not_recovered", text: "Not recovered" },
  { key: "blocked", text: "Blocked" },
  { key: "confirmed", text: "Confirmed paid" },
  { key: "failed", text: "Failed" },
];

function outcomeBadge(r: TransactionResult) {
  if (r.stage_reached === "failed") return <Badge tone="critical">failed · contained</Badge>;
  const e = r.audit_entry;
  if (!e.executed) return <Badge tone="warn">blocked</Badge>;
  if (e.confirmed_outcome === "recovered") return <Badge tone="good">confirmed paid</Badge>;
  return e.projected_outcome === "recovered" ? (
    <Badge tone="series-1">projected recovered</Badge>
  ) : (
    <Badge tone="neutral">not recovered</Badge>
  );
}

function methodTone(m: string) {
  if (m === "razorpay_api" || m === "razorpay_order" || m === "llm_message")
    return "series-1" as const;
  if (m === "razorpay_api_ratelimited" || m === "pipeline_error") return "warn" as const;
  return "neutral" as const;
}

export function AuditTab({ report }: { report: PipelineReport }) {
  const [q, setQ] = useState("");
  const [outcome, setOutcome] = useState<OutcomeFilter>("all");
  const [method, setMethod] = useState("all");
  const [openId, setOpenId] = useState<string | null>(null);

  const methods = useMemo(
    () => ["all", ...Object.keys(report.summary.execution_methods)],
    [report],
  );

  const rows = useMemo(
    () =>
      report.results.filter((r) => {
        const e = r.audit_entry;
        if (method !== "all" && e.execution_method !== method) return false;
        if (outcome === "recovered" && !(e.executed && e.projected_outcome === "recovered"))
          return false;
        if (outcome === "not_recovered" && !(e.executed && e.projected_outcome === "not_recovered"))
          return false;
        if (outcome === "blocked" && e.executed) return false;
        if (outcome === "confirmed" && e.confirmed_outcome !== "recovered") return false;
        if (outcome === "failed" && r.stage_reached !== "failed") return false;
        if (q) {
          const hay =
            `${r.transaction_id} ${e.customer_id} ${e.reason} ${e.detail}`.toLowerCase();
          if (!hay.includes(q.toLowerCase())) return false;
        }
        return true;
      }),
    [report, q, outcome, method],
  );

  return (
    <div className="space-y-4">
      <SectionLead title="Every decision, executed or blocked">
        The complete record: what was diagnosed, what the compliance layer allowed, how it was
        carried out, and why. Click any row to see the full detail — the message Claude wrote, the
        Razorpay object created, or the reason it was refused.
      </SectionLead>

      <Card className="p-4">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => setOutcome(f.key)}
              className={`rounded-full px-2.5 py-1 text-[11px] font-medium transition ${
                outcome === f.key
                  ? "bg-series-1 text-white"
                  : "bg-surface-2 text-ink-secondary hover:text-ink"
              }`}
            >
              {f.text}
            </button>
          ))}

          <div className="ml-auto flex items-center gap-2">
            <select
              value={method}
              onChange={(e) => setMethod(e.target.value)}
              className="rounded-lg border border-border bg-surface-2 px-2 py-1 text-[11px] text-ink-secondary outline-none"
            >
              {methods.map((m) => (
                <option key={m} value={m}>
                  {m === "all" ? "All methods" : label.method(m)}
                </option>
              ))}
            </select>
            <div className="relative">
              <Search className="pointer-events-none absolute left-2 top-1/2 size-3 -translate-y-1/2 text-ink-muted" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search…"
                className="w-44 rounded-lg border border-border bg-surface-2 py-1 pl-7 pr-2 text-[11px] outline-none focus:border-series-1"
              />
            </div>
          </div>
        </div>

        <p className="mb-2 text-[11px] text-ink-muted">
          Showing {rows.length} of {report.results.length} decisions
        </p>

        <div className="max-h-[560px] overflow-auto rounded-lg border border-border">
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 z-10 bg-surface text-ink-muted">
              <tr className="[&>th]:whitespace-nowrap [&>th]:px-3 [&>th]:py-2.5 [&>th]:font-medium">
                <th className="w-6" />
                <th>Transaction</th>
                <th className="text-right">Amount</th>
                <th>Why it failed</th>
                <th>Action taken</th>
                <th>How</th>
                <th>Outcome</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-3 py-8 text-center text-ink-muted">
                    Nothing matches those filters.
                  </td>
                </tr>
              )}
              {rows.map((r) => {
                const e = r.audit_entry;
                const open = openId === r.transaction_id;
                return (
                  <Fragment key={r.transaction_id}>
                    <tr
                      onClick={() => setOpenId(open ? null : r.transaction_id)}
                      className="cursor-pointer align-top hover:bg-surface-2/60"
                    >
                      <td className="px-3 py-2.5">
                        <ChevronRight
                          className={`size-3.5 text-ink-muted transition-transform ${
                            open ? "rotate-90" : ""
                          }`}
                        />
                      </td>
                      <td className="px-3 py-2.5">
                        <div className="font-mono text-[11px] text-ink-secondary">
                          {r.transaction_id}
                        </div>
                        <div className="text-[10px] text-ink-muted">{e.customer_id}</div>
                      </td>
                      <td className="px-3 py-2.5 text-right tabular text-ink">{inr(e.amount)}</td>
                      <td className="px-3 py-2.5 max-w-[230px] text-ink-secondary">
                        {r.diagnosis?.root_cause ?? "—"}
                        <div className="mt-0.5 text-[10px] text-ink-muted">
                          {label.diagnosis(e.diagnosis_method)}
                        </div>
                      </td>
                      <td className="px-3 py-2.5 whitespace-nowrap text-ink-secondary">
                        {label.action(e.final_action)}
                        {e.final_action !== e.diagnosis_action && (
                          <div className="text-[10px] text-warn">
                            was {label.action(e.diagnosis_action)}
                          </div>
                        )}
                      </td>
                      <td className="px-3 py-2.5">
                        <Badge tone={methodTone(e.execution_method)}>
                          {label.method(e.execution_method)}
                        </Badge>
                        {e.scheduled_for && (
                          <div className="mt-0.5 text-[10px] text-ink-muted">
                            fires {relativeTime(e.scheduled_for).replace(" ago", " out")}
                          </div>
                        )}
                      </td>
                      <td className="px-3 py-2.5">{outcomeBadge(r)}</td>
                    </tr>

                    {open && (
                      <tr className="bg-surface-2/40">
                        <td />
                        <td colSpan={6} className="px-3 pb-4 pt-1">
                          <dl className="grid gap-x-6 gap-y-2.5 sm:grid-cols-2">
                            <Detail term="Why this action was allowed">{e.reason}</Detail>
                            <Detail term="What was actually done">{e.detail}</Detail>
                            {r.diagnosis?.reasoning && (
                              <Detail term="Diagnosis reasoning">{r.diagnosis.reasoning}</Detail>
                            )}
                            {r.diagnosis?.model_name && (
                              <Detail term="Model">
                                {r.diagnosis.model_name} · {r.diagnosis.latency_ms} ms ·
                                confidence {(r.diagnosis.confidence * 100).toFixed(0)}%
                              </Detail>
                            )}
                            {r.decision && (
                              <Detail term="Strategy">
                                {r.decision.strategy} playbook
                                {r.decision.scheduled_for &&
                                  ` · scheduled ${new Date(r.decision.scheduled_for).toLocaleString()}`}
                              </Detail>
                            )}
                            {r.error && <Detail term="Error">{r.error.split("\n")[0]}</Detail>}
                          </dl>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function Detail({ term, children }: { term: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-[10px] font-medium uppercase tracking-wide text-ink-muted">{term}</dt>
      <dd className="mt-0.5 text-[11px] leading-relaxed text-ink-secondary">{children}</dd>
    </div>
  );
}
