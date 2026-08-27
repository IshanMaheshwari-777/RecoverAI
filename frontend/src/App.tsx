import { AlertCircle } from "lucide-react";
import { useReport } from "./hooks/useReport";
import { inr, pct } from "./lib/format";
import { Header } from "./components/Header";
import { Stat, Skeleton, Card } from "./components/ui";
import { FlowDiagram } from "./components/FlowDiagram";
import { RecoveryFunnel } from "./components/RecoveryFunnel";
import {
  ActionBreakdownCard,
  DiagnosisSplitCard,
  ExecutionMethodCard,
} from "./components/Breakdowns";
import { AuditTable } from "./components/AuditTable";
import { CompliancePanel, FailurePanel } from "./components/Panels";
import { RunControl, WebhookSimulator } from "./components/Controls";

export default function App() {
  const { data: report, isLoading, error } = useReport();

  return (
    <div className="min-h-full">
      <Header report={report} />
      <main className="mx-auto max-w-[1240px] px-6 py-6">
        {isLoading && <LoadingState />}
        {error && !report && <ErrorState message={(error as Error).message} />}
        {report && (
          <div className="space-y-5">
            {/* headline stat row */}
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Stat
                label="Revenue at risk"
                value={inr(report.summary.at_risk)}
                hint={`${report.summary.needing_attention} of ${report.summary.total_transactions} transactions`}
              />
              <Stat
                label="Projected recovered"
                value={inr(report.summary.projected_recovered)}
                hint={`${pct(report.summary.recovery_rate)} of at-risk · modelled`}
                tone="good"
                emphasis
              />
              <Stat
                label="Confirmed recovered"
                value={inr(report.summary.confirmed_recovered)}
                hint="via Razorpay webhook"
              />
              <Stat
                label="Compliance"
                value={report.summary.compliance_violations === 0 ? "0 violations" : `${report.summary.compliance_violations} violations`}
                hint="do_not_contact never overridden"
                tone={report.summary.compliance_violations === 0 ? "good" : "critical"}
              />
            </div>

            <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
              <MiniStat label="Executed" value={report.summary.executed_actions} />
              <MiniStat label="Blocked" value={report.summary.blocked_actions} />
              <MiniStat label="Escalated" value={report.summary.escalated_actions} />
              <MiniStat
                label="Rule / AI"
                value={`${report.summary.diagnosis_split.rule} / ${
                  report.summary.diagnosis_split.llm + report.summary.diagnosis_split.llm_fallback
                }`}
              />
              <MiniStat
                label="Failed (contained)"
                value={report.summary.failed}
                tone={report.summary.failed ? "critical" : undefined}
              />
              <MiniStat
                label="Transactions"
                value={report.summary.total_transactions}
                muted
              />
            </div>

            <FailurePanel report={report} />
            <FlowDiagram report={report} />

            <div className="grid items-start gap-5 lg:grid-cols-2">
              <RecoveryFunnel report={report} />
              <DiagnosisSplitCard report={report} />
              <ExecutionMethodCard report={report} />
              <ActionBreakdownCard report={report} />
            </div>

            <CompliancePanel report={report} />

            <div className="grid items-start gap-5 lg:grid-cols-2">
              <RunControl report={report} />
              <WebhookSimulator report={report} />
            </div>

            <AuditTable report={report} />

            <footer className="pb-8 pt-2 text-center text-[11px] text-ink-muted">
              Deterministic rules move money; the LLM only reasons and drafts. “Projected recovered”
              is a labelled modelling assumption — production uses webhook confirmations.
            </footer>
          </div>
        )}
      </main>
    </div>
  );
}

function MiniStat({
  label,
  value,
  tone,
  muted,
}: {
  label: string;
  value: React.ReactNode;
  tone?: "critical";
  muted?: boolean;
}) {
  return (
    <div className="rounded-lg border border-border bg-surface px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-ink-muted">{label}</div>
      <div
        className={`mt-0.5 text-sm font-semibold tabular ${
          tone === "critical" ? "text-critical" : muted ? "text-ink-muted" : "text-ink"
        }`}
      >
        {value}
      </div>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
      <Skeleton className="h-80" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Skeleton className="h-64" />
        <Skeleton className="h-64" />
      </div>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <Card className="mx-auto max-w-md text-center">
      <AlertCircle className="mx-auto size-6 text-warn" />
      <h2 className="mt-2 text-sm font-semibold text-ink">No pipeline run found</h2>
      <p className="mt-1 text-xs text-ink-muted">{message}</p>
      <p className="mt-3 text-xs text-ink-muted">
        Start one from the terminal: <code className="text-ink-secondary">revenue-recovery run</code>
        , or the API will seed one on first load.
      </p>
    </Card>
  );
}
