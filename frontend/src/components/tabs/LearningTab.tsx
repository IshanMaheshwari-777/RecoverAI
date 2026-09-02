import { useState } from "react";
import { TrendingUp } from "lucide-react";
import type { CalibrationRow, PipelineReport } from "../../types";
import { inr, pct } from "../../lib/format";
import { label as fmt } from "../../lib/format";
import { Badge, Card, Explain, SectionLead, Stat } from "../ui";

export function LearningTab({ report }: { report: PipelineReport }) {
  const L = report.learning;
  const s = report.summary;

  if (!L) {
    return (
      <Card>
        <p className="text-xs text-ink-muted">
          No learning state yet. Run the agent, then confirm a few payments in the webhook
          simulator on the Overview tab — each confirmation moves the model.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-5">
      <SectionLead title="The learning loop">
        Conversion isn&rsquo;t a constant. Every recovery action is a bet with a probability, and
        every webhook confirmation (or its absence) is a labelled outcome. The model holds a
        Beta&nbsp;posterior per <em>action × method × failure reason × amount band</em>, starts at
        the policy prior, and moves toward reality — so the projected number becomes a{" "}
        <em>calibrated</em> one, and the decision engine can pick the action with the highest
        expected value.
      </SectionLead>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Observations"
          value={L.observations.toLocaleString("en-IN")}
          hint="labelled outcomes the model has seen"
          explain="Warm-started from a synthetic outcome log so a fresh install has a curve; in production these are all real webhook events."
        />
        <Stat
          label="Brier score"
          value={L.brier_score.toFixed(3)}
          hint="lower is better · 0 = perfect, 0.25 = coin flip"
          tone={L.brier_score < 0.2 ? "good" : L.brier_score < 0.25 ? "warn" : "critical"}
          explain="Mean squared error of the predicted probabilities against what actually happened. The headline measure of whether the model is calibrated."
          emphasis
        />
        <Stat
          label="Incremental lift"
          value={L.experiment.control_n ? pct(L.experiment.incremental_rate) : "—"}
          hint={
            L.experiment.control_n
              ? `treated ${pct(L.experiment.treatment_rate)} vs control ${pct(L.experiment.control_rate)}`
              : "no control data yet"
          }
          tone="good"
          explain="Measured, not modelled: a random holdout of would-act transactions is left untouched, accrued across runs. Treatment rate minus control rate is the true causal effect."
        />
        <Stat
          label="Net expected value"
          value={inr(s.economics.net_expected_value)}
          hint={`after ${inr(s.economics.total_channel_cost)} channel cost`}
          explain="Sum over executed actions of p(recover)·amount minus channel cost minus chargeback/support risk. What the run is worth in expectation."
        />
      </div>

      <div className="grid items-start gap-5 lg:grid-cols-2">
        <CalibrationCard rows={L.calibration_table} brier={L.brier_score} />
        <CausalLiftCard report={report} />
      </div>

      <ConversionTable report={report} />

      <div className="grid items-start gap-5 lg:grid-cols-2">
        <EconomicsCard report={report} />
        <RetryTimingCard report={report} />
      </div>
    </div>
  );
}

/* ---------------------------------------------------- reliability plot */

function CalibrationCard({ rows, brier }: { rows: CalibrationRow[]; brier: number }) {
  const W = 260;
  const H = 200;
  const pad = 28;
  const x = (v: number) => pad + v * (W - 2 * pad);
  const y = (v: number) => H - pad - v * (H - 2 * pad);
  const withData = rows.filter((r) => r.n > 0);

  return (
    <Card
      title="Calibration"
      subtitle="Predicted probability vs. what actually happened. Points on the diagonal mean the model's confidence matches reality."
    >
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-sm" role="img" aria-label="Reliability diagram">
        {[0.25, 0.5, 0.75, 1].map((g) => (
          <g key={g}>
            <line x1={x(g)} y1={y(0)} x2={x(g)} y2={y(1)} stroke="var(--color-border)" strokeOpacity={0.4} />
            <line x1={x(0)} y1={y(g)} x2={x(1)} y2={y(g)} stroke="var(--color-border)" strokeOpacity={0.4} />
          </g>
        ))}
        {/* axes */}
        <line x1={pad} y1={H - pad} x2={W - pad} y2={H - pad} stroke="var(--color-border)" />
        <line x1={pad} y1={pad} x2={pad} y2={H - pad} stroke="var(--color-border)" />
        {/* perfect-calibration diagonal */}
        <line
          x1={x(0)}
          y1={y(0)}
          x2={x(1)}
          y2={y(1)}
          stroke="var(--color-ink-muted)"
          strokeDasharray="3 3"
        />
        {[0, 0.5, 1].map((t) => (
          <g key={t} className="fill-ink-muted text-[8px]">
            <text x={x(t)} y={H - pad + 10} textAnchor="middle">{t}</text>
            <text x={pad - 6} y={y(t) + 3} textAnchor="end">{t}</text>
          </g>
        ))}
        {/* observed vs predicted, sized by n */}
        {withData.map((r) => (
          <circle
            key={r.bucket}
            cx={x(r.predicted)}
            cy={y(r.observed)}
            r={Math.max(3, Math.min(9, Math.sqrt(r.n)))}
            fill="var(--color-series-1)"
            fillOpacity={0.75}
            stroke="var(--color-surface)"
          />
        ))}
        <text x={W / 2} y={H - 4} textAnchor="middle" className="fill-ink-muted text-[9px]">
          predicted
        </text>
        <text x={9} y={H / 2} textAnchor="middle" transform={`rotate(-90 9 ${H / 2})`} className="fill-ink-muted text-[9px]">
          observed
        </text>
      </svg>
      <p className="mt-2 text-[11px] leading-relaxed text-ink-muted">
        Brier score <strong className="text-ink-secondary tabular">{brier.toFixed(3)}</strong>. Dot
        size is the number of observations in that bucket.
      </p>
    </Card>
  );
}

/* ------------------------------------------------------- causal lift */

export function CausalLiftCard({ report }: { report: PipelineReport }) {
  const x = report.learning?.experiment;
  const run = report.summary.causal;
  if (!x || !x.control_n) {
    return (
      <Card title="Causal lift" subtitle="Accrues across every run that holds out a control group.">
        <p className="text-xs text-ink-muted">No control data yet.</p>
      </Card>
    );
  }
  const bar = (rate: number, tone: string) => (
    <div className="h-2.5 overflow-hidden rounded-full bg-surface-2">
      <div className="h-full rounded-full" style={{ width: `${rate * 100}%`, background: tone }} />
    </div>
  );
  const sig = x.ci_low > 0;
  return (
    <Card
      title="Causal lift — measured, not modelled"
      subtitle={`${x.treatment_n.toLocaleString("en-IN")} treated vs ${x.control_n.toLocaleString("en-IN")} untouched controls, accrued across runs.`}
    >
      <div className="space-y-3">
        <div>
          <div className="flex items-baseline justify-between text-xs">
            <span className="text-ink-secondary">Treated</span>
            <span className="tabular font-semibold text-ink">{pct(x.treatment_rate)}</span>
          </div>
          <div className="mt-1">{bar(x.treatment_rate, "var(--color-series-3)")}</div>
        </div>
        <div>
          <div className="flex items-baseline justify-between text-xs">
            <span className="text-ink-secondary">Control — no action taken</span>
            <span className="tabular font-semibold text-ink">{pct(x.control_rate)}</span>
          </div>
          <div className="mt-1">{bar(x.control_rate, "var(--color-ink-muted)")}</div>
        </div>
        <div className="border-t border-border pt-2.5">
          <div className="flex items-baseline justify-between">
            <span className="text-xs font-medium text-ink">
              Incremental lift{" "}
              <Explain>
                The part of recovery that would not have happened on its own. This is the number a
                CFO signs off on.
              </Explain>
            </span>
            <span className="tabular text-lg font-semibold text-series-3">
              {pct(x.incremental_rate)}
            </span>
          </div>
          <p className={`mt-1 text-[11px] ${sig ? "text-ink-muted" : "text-warn"}`}>
            95% CI {pct(x.ci_low)} – {pct(x.ci_high)}
            {sig ? " · significant" : " · not yet significant"}
            {run.control_n ? ` · +${run.control_n} controls this run` : ""}
          </p>
        </div>
      </div>
    </Card>
  );
}

/* --------------------------------------------------- posteriors table */

function ConversionTable({ report }: { report: PipelineReport }) {
  const rows = report.learning?.conversion_rates ?? [];
  const [all, setAll] = useState(false);
  const shown = all ? rows : rows.slice(0, 10);
  const prior: Record<string, number> = {
    retry_now: 0.45,
    retry_later: 0.3,
    send_reminder: 0.2,
    request_update: 0.15,
  };

  return (
    <Card
      title="Learned conversion rates"
      subtitle="Posterior mean and 95% credible interval per segment, most-observed first. Compare against the flat prior it started from."
    >
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border text-left text-[10px] uppercase tracking-wide text-ink-muted">
              <th className="py-1.5 pr-3">Action</th>
              <th className="py-1.5 pr-3">Method</th>
              <th className="py-1.5 pr-3">Failure reason</th>
              <th className="py-1.5 pr-3">Band</th>
              <th className="py-1.5 pr-3 text-right">Prior</th>
              <th className="py-1.5 pr-3 text-right">Learned</th>
              <th className="py-1.5 pr-3">95% CI</th>
              <th className="py-1.5 text-right">n</th>
            </tr>
          </thead>
          <tbody className="text-ink-secondary">
            {shown.map((r, i) => {
              const p = prior[r.action] ?? 0;
              const moved = r.rate - p;
              return (
                <tr key={i} className="border-b border-border/50">
                  <td className="py-1.5 pr-3">{fmt.action(r.action)}</td>
                  <td className="py-1.5 pr-3">{r.method}</td>
                  <td className="py-1.5 pr-3">{r.reason.replace(/_/g, " ")}</td>
                  <td className="py-1.5 pr-3 tabular text-ink-muted">₹{r.amount_band}</td>
                  <td className="py-1.5 pr-3 text-right tabular text-ink-muted">{pct(p)}</td>
                  <td className="py-1.5 pr-3 text-right tabular font-medium text-ink">
                    {pct(r.rate)}
                    <span
                      className={`ml-1 text-[10px] ${moved >= 0 ? "text-series-3" : "text-series-2"}`}
                    >
                      {moved >= 0 ? "▲" : "▼"}
                    </span>
                  </td>
                  <td className="py-1.5 pr-3 tabular text-ink-muted">
                    {pct(r.ci_low)}–{pct(r.ci_high)}
                  </td>
                  <td className="py-1.5 text-right tabular">{r.observations}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {rows.length > 10 && (
        <button
          onClick={() => setAll((a) => !a)}
          className="mt-2 text-[11px] text-series-1 hover:underline"
        >
          {all ? "Show top 10" : `Show all ${rows.length} segments`}
        </button>
      )}
    </Card>
  );
}

/* ------------------------------------------------------- economics */

export function EconomicsCard({ report }: { report: PipelineReport }) {
  const e = report.summary.economics;
  const total = Object.values(e.channel_mix).reduce((a, b) => a + b, 0) || 1;
  const COLORS: Record<string, string> = {
    payment_link: "var(--color-series-1)",
    in_app: "var(--color-series-3)",
    email: "var(--color-series-4)",
    sms: "var(--color-series-2)",
    whatsapp: "var(--color-ink-secondary)",
  };
  return (
    <Card
      title="Recovery economics"
      subtitle="Every action is priced. A recovery whose net expected value is below the policy floor is skipped, not sent."
    >
      <div className="grid grid-cols-2 gap-3 text-xs">
        <Metric label="Actions taken" value={String(e.positive_ev_actions)} />
        <Metric
          label="Skipped (negative EV)"
          value={String(e.skipped_negative_ev)}
          tone={e.skipped_negative_ev ? "warn" : undefined}
        />
        <Metric label="Channel cost" value={inr(e.total_channel_cost)} />
        <Metric label="Net expected value" value={inr(e.net_expected_value)} tone="good" />
      </div>
      <div className="mt-4">
        <div className="mb-1.5 text-[10px] uppercase tracking-wide text-ink-muted">Channel mix</div>
        <div className="flex h-2.5 overflow-hidden rounded-full bg-surface-2">
          {Object.entries(e.channel_mix).map(([ch, n]) => (
            <div
              key={ch}
              title={`${ch}: ${n}`}
              style={{ width: `${(n / total) * 100}%`, background: COLORS[ch] ?? "var(--color-ink-muted)" }}
            />
          ))}
        </div>
        <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1">
          {Object.entries(e.channel_mix).map(([ch, n]) => (
            <span key={ch} className="inline-flex items-center gap-1 text-[10px] text-ink-muted">
              <span
                className="size-2 rounded-full"
                style={{ background: COLORS[ch] ?? "var(--color-ink-muted)" }}
              />
              {ch.replace(/_/g, " ")} {n}
            </span>
          ))}
        </div>
      </div>
    </Card>
  );
}

function RetryTimingCard({ report }: { report: PipelineReport }) {
  const timing = report.learning?.retry_timing_hours ?? {};
  const entries = Object.entries(timing);
  return (
    <Card
      title="Learned retry timing"
      subtitle="When a delayed retry actually lands, by failure reason — learned from outcomes, replacing the hard-coded delay."
    >
      {entries.length === 0 ? (
        <p className="text-xs text-ink-muted">
          Not enough confirmed retries yet to override the policy defaults.
        </p>
      ) : (
        <div className="space-y-2">
          {entries.map(([reason, hours]) => (
            <div key={reason} className="flex items-center justify-between text-xs">
              <span className="text-ink-secondary">{reason.replace(/_/g, " ")}</span>
              <Badge tone="series-1">
                <TrendingUp className="size-3" /> {hours}h
              </Badge>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

/* ----------------------------------------------------------- helpers */

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "good" | "warn";
}) {
  return (
    <div className="rounded-lg border border-border bg-surface-2/40 p-2.5">
      <div className="text-[10px] uppercase tracking-wide text-ink-muted">{label}</div>
      <div
        className={`mt-0.5 text-sm font-semibold tabular ${
          tone === "good" ? "text-good" : tone === "warn" ? "text-warn" : "text-ink"
        }`}
      >
        {value}
      </div>
    </div>
  );
}
