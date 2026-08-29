import type { PipelineReport } from "../../types";
import { inr, pct } from "../../lib/format";
import { Stat } from "../ui";
import { RecoveryFunnel } from "../RecoveryFunnel";
import { DiagnosisSplitCard } from "../Breakdowns";
import { CompliancePanel, FailurePanel } from "../Panels";
import { WebhookPanel } from "../WebhookPanel";

export function OverviewTab({ report }: { report: PipelineReport }) {
  const s = report.summary;

  return (
    <div className="space-y-5">
      {/* the one-sentence story */}
      <p className="max-w-4xl text-sm leading-relaxed text-ink-secondary">
        Of <strong className="text-ink">{s.total_transactions}</strong> transactions,{" "}
        <strong className="text-ink">{s.needing_attention}</strong> failed or were abandoned —{" "}
        <strong className="text-ink">{inr(s.at_risk)}</strong> of revenue at risk. The agent
        diagnosed every one, took <strong className="text-ink">{s.executed_actions}</strong>{" "}
        recovery actions, correctly refused{" "}
        <strong className="text-ink">{s.blocked_actions}</strong>, and projects{" "}
        <strong className="text-good">{inr(s.projected_recovered)}</strong> recovered — with{" "}
        <strong className={s.compliance_violations ? "text-critical" : "text-good"}>
          {s.compliance_violations} compliance violations
        </strong>
        .
      </p>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Revenue at risk"
          value={inr(s.at_risk)}
          hint={`${s.needing_attention} failed or abandoned payments`}
          explain="Every payment that failed or was abandoned, added up. This is the money that leaks if nobody follows up."
        />
        <Stat
          label="Projected recovered"
          value={inr(s.projected_recovered)}
          hint={`${pct(s.recovery_rate)} of at-risk · modelled estimate`}
          tone="good"
          emphasis
          explain="A modelled estimate: each recovery action carries a published conversion rate (immediate retry ~45%, update request ~15%), drawn per transaction so re-runs match."
        />
        <Stat
          label="Confirmed recovered"
          value={inr(s.confirmed_recovered)}
          hint="Measured via Razorpay webhook"
          explain="Money a customer actually paid, confirmed by a payment_link.paid webhook. Starts at ₹0 — use the webhook simulator below."
        />
        <Stat
          label="Compliance"
          value={s.compliance_violations === 0 ? "0 violations" : `${s.compliance_violations}`}
          hint="do_not_contact never overridden"
          tone={s.compliance_violations === 0 ? "good" : "critical"}
          explain="Counts every time a compliance stop was turned into an action. Must always be zero — a test proves it across a fresh 400-transaction batch."
        />
      </div>

      <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <MiniStat label="Actions executed" value={s.executed_actions} />
        <MiniStat label="Correctly blocked" value={s.blocked_actions} />
        <MiniStat label="Escalated" value={s.escalated_actions} />
        <MiniStat label="Rule / AI" value={`${s.diagnosis_split.rule} / ${s.diagnosis_split.llm + s.diagnosis_split.llm_fallback}`} />
        <MiniStat
          label="Failed, contained"
          value={s.failed}
          tone={s.failed ? "critical" : undefined}
        />
      </div>

      <FailurePanel report={report} />

      <div className="grid items-start gap-5 lg:grid-cols-2">
        <RecoveryFunnel report={report} />
        <DiagnosisSplitCard report={report} />
      </div>

      <CompliancePanel report={report} />
      <WebhookPanel report={report} />
    </div>
  );
}

function MiniStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: React.ReactNode;
  tone?: "critical";
}) {
  return (
    <div className="rounded-lg border border-border bg-surface px-3 py-2.5">
      <div className="text-[10px] uppercase tracking-wide text-ink-muted">{label}</div>
      <div
        className={`mt-0.5 text-base font-semibold tabular ${
          tone === "critical" ? "text-critical" : "text-ink"
        }`}
      >
        {value}
      </div>
    </div>
  );
}
