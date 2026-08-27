import { useMemo, useState } from "react";
import type { PipelineReport, TransactionResult } from "../types";
import { label } from "../lib/format";
import { Card } from "./ui";

/* A three-stage Sankey: how each transaction flowed from its diagnosis
   method, through the action the recovery layer allowed, to a projected
   outcome. Layout is computed from the run — no chart library. */

const W = 900;
const H = 330;
const PAD = 6;
const NODE_W = 12;
const STAGE_X = [PAD, (W - NODE_W) / 2, W - NODE_W - PAD];

interface FlowNode {
  key: string;
  label: string;
  color: string;
  stage: 0 | 1 | 2;
  value: number;
  y0: number;
  y1: number;
}

const METHOD_COLOR: Record<string, string> = {
  rule: "var(--color-series-1)",
  llm: "var(--color-series-2)",
  llm_fallback: "var(--color-series-4)",
  unhandled: "var(--color-ink-muted)",
};
const OUTCOME_COLOR: Record<string, string> = {
  recovered: "var(--color-series-3)",
  not_recovered: "var(--color-ink-muted)",
  blocked: "var(--color-series-4)",
  failed: "var(--color-critical)",
};

function outcomeKey(r: TransactionResult): string {
  if (r.stage_reached === "failed") return "failed";
  if (!r.audit_entry.executed) return "blocked";
  return r.audit_entry.projected_outcome === "recovered" ? "recovered" : "not_recovered";
}

function actionKey(r: TransactionResult): string {
  if (!r.decision || r.decision.blocked || !r.decision.final_action) return "blocked";
  return r.decision.final_action;
}

const METHOD_ROWS = [
  { key: "rule", label: "Rule" },
  { key: "llm", label: "LLM" },
  { key: "llm_fallback", label: "LLM fallback" },
  { key: "unhandled", label: "Unhandled" },
];
const ACTION_ROWS = [
  { key: "retry_now", label: "Retry now" },
  { key: "retry_later", label: "Retry later" },
  { key: "request_update", label: "Request update" },
  { key: "send_reminder", label: "Send reminder" },
  { key: "blocked", label: "Blocked" },
];
const OUTCOME_ROWS = [
  { key: "recovered", label: "Recovered" },
  { key: "not_recovered", label: "Not recovered" },
  { key: "blocked", label: "Blocked" },
  { key: "failed", label: "Failed (contained)" },
];

function layoutStage(
  stage: 0 | 1 | 2,
  rows: { key: string; label: string }[],
  counts: Map<string, number>,
  colorOf: (k: string) => string,
): FlowNode[] {
  const present = rows.filter((r) => (counts.get(r.key) ?? 0) > 0);
  const total = present.reduce((a, r) => a + (counts.get(r.key) ?? 0), 0) || 1;
  const gapCount = Math.max(0, present.length - 1);
  const gap = gapCount ? Math.min(10, (H - 2 * PAD) * 0.03) : 0;
  const usable = H - 2 * PAD - gap * gapCount;
  let y = PAD;
  return present.map((r) => {
    const value = counts.get(r.key) ?? 0;
    const h = (value / total) * usable;
    const node: FlowNode = { ...r, color: colorOf(r.key), stage, value, y0: y, y1: y + h };
    y += h + gap;
    return node;
  });
}

interface FlowLink {
  from: FlowNode;
  to: FlowNode;
  value: number;
  sy: number;
  ty: number;
  width: number;
}

export function FlowDiagram({ report }: { report: PipelineReport }) {
  const [hover, setHover] = useState<string | null>(null);
  const n = Math.max(1, report.results.length);

  const { nodes, links } = useMemo(() => {
    const rows = report.results;
    const count = (fn: (r: TransactionResult) => string) => {
      const m = new Map<string, number>();
      for (const r of rows) m.set(fn(r), (m.get(fn(r)) ?? 0) + 1);
      return m;
    };

    const methods = layoutStage(0, METHOD_ROWS, count((r) => r.diagnosis?.method ?? "unhandled"), (k) => METHOD_COLOR[k] ?? METHOD_COLOR.unhandled);
    const actions = layoutStage(1, ACTION_ROWS, count(actionKey), (k) => (k === "blocked" ? OUTCOME_COLOR.blocked : "var(--color-series-1)"));
    const outcomes = layoutStage(2, OUTCOME_ROWS, count(outcomeKey), (k) => OUTCOME_COLOR[k] ?? OUTCOME_COLOR.not_recovered);

    const idx = (ns: FlowNode[]) => new Map(ns.map((x) => [x.key, x]));
    const mIdx = idx(methods);
    const aIdx = idx(actions);
    const oIdx = idx(outcomes);

    const pairCount = (a: (r: TransactionResult) => string, b: (r: TransactionResult) => string) => {
      const m = new Map<string, number>();
      for (const r of rows) {
        const k = `${a(r)}|${b(r)}`;
        m.set(k, (m.get(k) ?? 0) + 1);
      }
      return m;
    };

    const links: FlowLink[] = [];
    const outCursor = new Map<string, number>();
    const inCursor = new Map<string, number>();
    const connect = (from: FlowNode, to: FlowNode, value: number) => {
      const so = outCursor.get(from.key) ?? from.y0;
      const ti = inCursor.get(to.key) ?? to.y0;
      const sSpan = (value / from.value) * (from.y1 - from.y0);
      const tSpan = (value / to.value) * (to.y1 - to.y0);
      links.push({
        from,
        to,
        value,
        sy: so + sSpan / 2,
        ty: ti + tSpan / 2,
        width: Math.max(1.2, (value / n) * (H - 2 * PAD)),
      });
      outCursor.set(from.key, so + sSpan);
      inCursor.set(to.key, ti + tSpan);
    };

    for (const [k, v] of [...pairCount((r) => r.diagnosis?.method ?? "unhandled", actionKey)].sort()) {
      const [a, b] = k.split("|");
      const f = mIdx.get(a);
      const t = aIdx.get(b);
      if (f && t) connect(f, t, v);
    }
    for (const [k, v] of [...pairCount(actionKey, outcomeKey)].sort()) {
      const [a, b] = k.split("|");
      const f = aIdx.get(`${a}`);
      const t = oIdx.get(b);
      if (f && t) connect(f, t, v);
    }

    return { nodes: [...methods, ...actions, ...outcomes], links };
  }, [report, n]);

  return (
    <Card
      title="Decision flow"
      subtitle="Every transaction · diagnosis method → action allowed → projected outcome"
    >
      <div className="overflow-x-auto">
        <svg viewBox={`0 0 ${W} ${H + 30}`} className="w-full min-w-[640px]" role="img"
          aria-label="Sankey of transaction flow through the agent">
          {links.map((lk, i) => {
            const x1 = STAGE_X[lk.from.stage] + NODE_W;
            const x2 = STAGE_X[lk.to.stage];
            const mx = (x1 + x2) / 2;
            const active = hover === null || hover === lk.from.key || hover === lk.to.key;
            return (
              <path
                key={i}
                d={`M${x1},${lk.sy} C${mx},${lk.sy} ${mx},${lk.ty} ${x2},${lk.ty}`}
                fill="none"
                stroke={lk.from.color}
                strokeWidth={lk.width}
                strokeOpacity={active ? 0.24 : 0.05}
                style={{ transition: "stroke-opacity .2s" }}
              >
                <title>
                  {label.diagnosis(lk.from.key)} → {label.action(lk.to.key)} · {lk.value}
                </title>
              </path>
            );
          })}
          {nodes.map((nd) => (
            <g
              key={`${nd.stage}-${nd.key}`}
              onMouseEnter={() => setHover(nd.key)}
              onMouseLeave={() => setHover(null)}
              style={{ cursor: "default" }}
            >
              <rect
                x={STAGE_X[nd.stage]}
                y={nd.y0}
                width={NODE_W}
                height={Math.max(1.5, nd.y1 - nd.y0)}
                rx={2}
                fill={nd.color}
              />
              <text
                x={nd.stage === 2 ? STAGE_X[nd.stage] - 8 : STAGE_X[nd.stage] + NODE_W + 8}
                y={(nd.y0 + nd.y1) / 2}
                dominantBaseline="middle"
                textAnchor={nd.stage === 2 ? "end" : "start"}
                className="fill-ink-secondary text-[11px]"
              >
                {nd.label}
                <tspan className="fill-ink-muted"> · {nd.value}</tspan>
              </text>
            </g>
          ))}
          {["Diagnosis method", "Action allowed", "Projected outcome"].map((t, i) => (
            <text
              key={t}
              x={i === 0 ? PAD : i === 1 ? W / 2 : W - PAD}
              y={H + 22}
              textAnchor={i === 0 ? "start" : i === 1 ? "middle" : "end"}
              className="fill-ink-muted text-[10px] font-medium uppercase tracking-wide"
            >
              {t}
            </text>
          ))}
        </svg>
      </div>
    </Card>
  );
}
