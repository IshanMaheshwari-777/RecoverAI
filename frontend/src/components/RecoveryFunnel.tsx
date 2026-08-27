import type { PipelineReport } from "../types";
import { inr, pct } from "../lib/format";
import { Card } from "./ui";

/* An ordinal funnel: at-risk revenue narrowing down to what we project
   (and confirm) as recovered. Ordinal blue ramp, lightest step clears 2:1
   on both surfaces per the palette's --ordinal rule. */

const STEP = ["#5598e7", "#3987e5", "#2a78d6", "#1c5cab", "#184f95"];

export function RecoveryFunnel({ report }: { report: PipelineReport }) {
  const s = report.summary;
  const actioned =
    s.at_risk *
    (s.needing_attention ? (s.executed_actions + s.blocked_actions) / s.needing_attention : 0);
  const executedValue =
    s.needing_attention ? s.at_risk * (s.executed_actions / s.needing_attention) : 0;

  const stages = [
    { label: "Revenue at risk", value: s.at_risk, note: `${s.needing_attention} transactions` },
    { label: "Reached a decision", value: actioned, note: `${s.executed_actions + s.blocked_actions} decided` },
    { label: "Action executed", value: executedValue, note: `${s.executed_actions} executed · ${s.blocked_actions} correctly blocked` },
    { label: "Projected recovered", value: s.projected_recovered, note: pct(s.recovery_rate) + " of at-risk" },
    { label: "Confirmed recovered", value: s.confirmed_recovered, note: "via webhook (simulate below)" },
  ];
  const max = stages[0].value || 1;

  return (
    <Card
      title="Recovery funnel"
      subtitle="At-risk revenue narrowing to projected — then webhook-confirmed — recovery"
    >
      <div className="space-y-2">
        {stages.map((st, i) => {
          const w = Math.max(2, (st.value / max) * 100);
          return (
            <div key={st.label} className="grid grid-cols-[150px_1fr] items-center gap-3">
              <div className="text-xs text-ink-secondary">{st.label}</div>
              <div className="flex items-center gap-3">
                <div
                  className="h-9 rounded-md"
                  style={{ width: `${w}%`, background: STEP[i], minWidth: 4 }}
                />
                <div className="whitespace-nowrap text-xs">
                  <span className="tabular font-semibold text-ink">{inr(st.value)}</span>{" "}
                  <span className="text-ink-muted">· {st.note}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <p className="mt-4 border-t border-border pt-3 text-[11px] text-ink-muted">
        “Projected recovered” applies a fixed, published conversion probability per action type
        (45% immediate retry … 15% update request), seeded per transaction. It is an explicit
        modelling assumption — production replaces it with the webhook confirmations shown as the
        final bar.
      </p>
    </Card>
  );
}
