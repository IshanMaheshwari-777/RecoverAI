import type { PipelineReport } from "../types";
import { label } from "../lib/format";
import { BarRow, Card } from "./ui";

const SERIES = [
  "var(--color-series-1)",
  "var(--color-series-2)",
  "var(--color-series-3)",
  "var(--color-series-4)",
  "var(--color-ink-muted)",
];

function sortedEntries(rec: Record<string, number>): [string, number][] {
  return Object.entries(rec).sort((a, b) => b[1] - a[1]);
}

export function DiagnosisSplitCard({ report }: { report: PipelineReport }) {
  const s = report.summary.diagnosis_split;
  const rows: [string, number, string][] = [
    ["Deterministic rule", s.rule, "var(--color-series-1)"],
    ["LLM (Claude)", s.llm, "var(--color-series-2)"],
    ["LLM fallback", s.llm_fallback, "var(--color-series-4)"],
    ["Unhandled", s.unhandled, "var(--color-ink-muted)"],
  ].filter((r) => (r[1] as number) > 0) as [string, number, string][];
  const total = report.summary.diagnosis_split.rule + s.llm + s.llm_fallback + s.unhandled;
  const aiPct = total ? ((s.llm + s.llm_fallback) / total) * 100 : 0;

  return (
    <Card
      title="Diagnosis — rule vs. AI"
      subtitle={`${(100 - aiPct).toFixed(0)}% resolved by deterministic rule; the LLM is consulted only for genuinely ambiguous declines`}
    >
      <div className="space-y-2.5">
        {rows.map(([name, value, color]) => (
          <BarRow key={name} label={name} value={value} total={total} color={color} />
        ))}
      </div>
      {!report.anthropic_live && (
        <p className="mt-3 rounded-lg bg-surface-2 px-3 py-2 text-[11px] text-ink-muted">
          No Anthropic key set — ambiguous cases took the conservative fallback rule instead of a
          live model call. Add <code className="text-ink-secondary">ANTHROPIC_API_KEY</code> to see
          the <span className="text-series-2">LLM</span> path light up.
        </p>
      )}
    </Card>
  );
}

export function ExecutionMethodCard({ report }: { report: PipelineReport }) {
  const entries = sortedEntries(report.summary.execution_methods);
  const total = entries.reduce((a, [, v]) => a + v, 0);
  return (
    <Card title="Execution method" subtitle="How each recovery action was actually carried out">
      <div className="space-y-2.5">
        {entries.map(([k, v], i) => (
          <BarRow key={k} label={label.method(k)} value={v} total={total} color={SERIES[i % SERIES.length]} />
        ))}
      </div>
    </Card>
  );
}

export function ActionBreakdownCard({ report }: { report: PipelineReport }) {
  const entries = sortedEntries(report.summary.action_breakdown);
  const total = entries.reduce((a, [, v]) => a + v, 0);
  return (
    <Card title="Recovery actions taken" subtitle="Final action after the stopping rules were applied">
      <div className="space-y-2.5">
        {entries.map(([k, v], i) => (
          <BarRow key={k} label={label.action(k)} value={v} total={total} color={SERIES[i % SERIES.length]} />
        ))}
      </div>
    </Card>
  );
}
