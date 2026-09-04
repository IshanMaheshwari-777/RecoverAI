import { CheckCircle2 } from "lucide-react";
import type { PipelineReport } from "../../types";
import { inr, pct } from "../../lib/format";
import { Card, Stat } from "../ui";
import { RecoveryFunnel } from "../RecoveryFunnel";
import { DiagnosisSplitCard } from "../Breakdowns";
import { CompliancePanel, FailurePanel, IncidentBanner } from "../Panels";
import { WebhookPanel } from "../WebhookPanel";
import { RunHistoryCard } from "../RunHistoryCard";
import { CausalLiftCard } from "./LearningTab";

export function OverviewTab({ report }: { report: PipelineReport }) {
  const s = report.summary;

  if (report.data_source === "razorpay" && s.needing_attention === 0) {
    return <LiveDataEmptyState />;
  }

  return (
    <div className="space-y-5">
      {report.data_source === "razorpay" && (
        <p className="max-w-4xl rounded-lg border border-good/30 bg-good/5 px-3 py-2 text-xs text-good">
          This run diagnosed {s.needing_attention} real failed payments read from your connected
          Razorpay account — not generated data.
        </p>
      )}
      {/* the one-sentence story */}
      <p className="max-w-4xl text-sm leading-relaxed text-ink-secondary">
        Of <strong className="text-ink">{s.total_transactions}</strong> transactions,{" "}
        <strong className="text-ink">{s.needing_attention}</strong> failed or were abandoned —{" "}
        <strong className="text-ink">{inr(s.at_risk)}</strong> of revenue at risk. The agent
        diagnosed every one, executed <strong className="text-ink">{s.executed_actions}</strong>{" "}
        recoveries, refused <strong className="text-ink">{s.blocked_actions}</strong>, and held{" "}
        <strong className="text-ink">{s.held_out_actions}</strong> back as a control —{" "}
        {report.learning?.experiment.control_n ? (
          <>
            a measured{" "}
            <strong className="text-good">
              {pct(report.learning.experiment.incremental_rate)}
            </strong>{" "}
            incremental lift
          </>
        ) : (
          <>
            projecting <strong className="text-good">{inr(s.projected_recovered)}</strong> recovered
          </>
        )}{" "}
        — with{" "}
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
        {(() => {
          const x = report.learning?.experiment;
          return x && x.control_n ? (
            <Stat
              label="Incremental lift"
              value={pct(x.incremental_rate)}
              hint={`measured vs ${x.control_n.toLocaleString("en-IN")} untouched controls`}
              tone="good"
              emphasis
              explain="Measured, not modelled: a random holdout of would-act transactions is left untouched and accrued across runs. Treatment recovery rate minus the control's is the true causal effect."
            />
          ) : (
            <Stat
              label="Projected recovered"
              value={inr(s.projected_recovered)}
              hint={`${pct(s.recovery_rate)} of at-risk · learned estimate`}
              tone="good"
              emphasis
              explain="A learned estimate: each action carries a conversion probability from the learning loop, drawn per transaction so re-runs match."
            />
          );
        })()}
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

      <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <MiniStat label="Actions executed" value={s.executed_actions} />
        <MiniStat label="Correctly blocked" value={s.blocked_actions} />
        <MiniStat label="Held out (control)" value={s.held_out_actions} />
        <MiniStat label="Skipped · low EV" value={s.economics.skipped_negative_ev} />
        <MiniStat label="Escalated" value={s.escalated_actions} />
        <MiniStat
          label="Failed, contained"
          value={s.failed}
          tone={s.failed ? "critical" : undefined}
        />
      </div>

      <IncidentBanner report={report} />
      <FailurePanel report={report} />

      <div className="grid items-start gap-5 lg:grid-cols-2">
        <RecoveryFunnel report={report} />
        <DiagnosisSplitCard report={report} />
      </div>

      <div className="grid items-start gap-5 lg:grid-cols-2">
        <CausalLiftCard report={report} />
        <CompliancePanel report={report} />
      </div>
      <WebhookPanel report={report} />
      <RunHistoryCard />
    </div>
  );
}

function LiveDataEmptyState() {
  return (
    <div className="space-y-5">
      <Card className="border-good/30 bg-good/5">
        <div className="flex items-start gap-3">
          <CheckCircle2 className="size-5 shrink-0 text-good" />
          <div>
            <h2 className="text-sm font-semibold text-ink">
              Connected to your real Razorpay account — no failed payments right now
            </h2>
            <p className="mt-1 max-w-2xl text-xs leading-relaxed text-ink-muted">
              This wasn't generated: the agent just made a live, read-only call to your account
              and found zero payments with <code className="text-ink-secondary">status=failed</code>{" "}
              in the most recent page. That's a real result, not an error — switch the header's
              data source to <strong className="text-ink-secondary">Synthetic</strong> to see the
              full pipeline run, or come back once a real payment has failed.
            </p>
          </div>
        </div>
      </Card>
      <RunHistoryCard />
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
