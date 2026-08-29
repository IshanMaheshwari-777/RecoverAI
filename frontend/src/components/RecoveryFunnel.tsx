import type { PipelineReport } from "../types";
import { inr, pct } from "../lib/format";
import { Card } from "./ui";

/* An ordinal funnel: at-risk revenue narrowing down to what we project
   (and confirm) as recovered. Ordinal blue ramp, lightest step clears 2:1
   on both surfaces per the palette's --ordinal rule.

   Every bar sits in its own full-width rail and is sized as a percentage of
   that rail, so bar length encodes value and nothing else — the amount and
   note live on a separate line and never compete with the bar for width. */

const STEP = ["#5598e7", "#3987e5", "#2a78d6", "#1c5cab", "#184f95"];

export function RecoveryFunnel({ report }: { report: PipelineReport }) {
  const s = report.summary;
  const executedValue = s.needing_attention
    ? s.at_risk * (s.executed_actions / s.needing_attention)
    : 0;

  const stages = [
    {
      label: "Revenue at risk",
      value: s.at_risk,
      note: `${s.needing_attention} failed or abandoned`,
    },
    {
      label: "Action executed",
      value: executedValue,
      note: `${s.executed_actions} executed · ${s.blocked_actions} correctly blocked`,
    },
    {
      label: "Projected recovered",
      value: s.projected_recovered,
      note: `${pct(s.recovery_rate)} of at-risk · modelled`,
    },
    {
      label: "Confirmed recovered",
      value: s.confirmed_recovered,
      note: "via webhook — simulate below",
    },
  ];
  const max = stages[0].value || 1;

  return (
    <Card
      title="Recovery funnel"
      subtitle="At-risk revenue narrowing to what the agent executes, projects, and confirms"
    >
      <div className="space-y-3.5">
        {stages.map((st, i) => {
          const w = st.value <= 0 ? 0 : Math.max(1.5, (st.value / max) * 100);
          return (
            <div key={st.label}>
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-xs font-medium text-ink-secondary">{st.label}</span>
                <span className="whitespace-nowrap text-[11px] text-ink-muted">{st.note}</span>
              </div>
              <div className="mt-1.5 flex items-center gap-2.5">
                <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-surface-2">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${w}%`, background: STEP[i] }}
                  />
                </div>
                <span className="tabular w-[92px] shrink-0 text-right text-xs font-semibold text-ink">
                  {inr(st.value)}
                </span>
              </div>
            </div>
          );
        })}
      </div>
      <p className="mt-4 border-t border-border pt-3 text-[11px] leading-relaxed text-ink-muted">
        “Projected recovered” applies a fixed, published conversion probability per action type
        (45% immediate retry … 15% update request), seeded per transaction. It is an explicit
        modelling assumption — production replaces it with the webhook confirmations shown as the
        final bar.
      </p>
    </Card>
  );
}
