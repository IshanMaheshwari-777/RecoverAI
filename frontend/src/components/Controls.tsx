import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, Play, Webhook } from "lucide-react";
import { api } from "../api";
import type { PipelineReport } from "../types";
import { inr } from "../lib/format";
import { Button, Card } from "./ui";

export function RunControl({ report }: { report: PipelineReport }) {
  const qc = useQueryClient();
  const [count, setCount] = useState(report.count);
  const [seed, setSeed] = useState(report.seed);
  const [injectFailure, setInjectFailure] = useState(report.failure_injected);

  const mutation = useMutation({
    mutationFn: () => api.run({ count, seed, inject_failure: injectFailure }),
    onSuccess: (data) => qc.setQueryData(["report"], data),
  });

  return (
    <Card title="Run the pipeline" subtitle="Generate a fresh batch and process it end-to-end">
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Batch size">
          <input
            type="number"
            value={count}
            min={10}
            max={2000}
            onChange={(e) => setCount(+e.target.value)}
            className="w-24 rounded-lg border border-border bg-surface-2 px-2 py-1 text-xs tabular outline-none focus:border-series-1"
          />
        </Field>
        <Field label="Seed">
          <input
            type="number"
            value={seed}
            min={0}
            onChange={(e) => setSeed(+e.target.value)}
            className="w-20 rounded-lg border border-border bg-surface-2 px-2 py-1 text-xs tabular outline-none focus:border-series-1"
          />
        </Field>
        <label className="flex cursor-pointer items-center gap-2 text-xs text-ink-secondary">
          <input
            type="checkbox"
            checked={injectFailure}
            onChange={(e) => setInjectFailure(e.target.checked)}
            className="accent-series-1"
          />
          Inject a malformed record
        </label>
        <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>
          {mutation.isPending ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : (
            <Play className="size-3.5" />
          )}
          Run pipeline
        </Button>
      </div>
      {mutation.isError && (
        <p className="mt-2 text-[11px] text-critical">{(mutation.error as Error).message}</p>
      )}
      <p className="mt-3 text-[11px] text-ink-muted">
        Same seed → byte-identical batch. Live Razorpay link creation is budgeted (test-mode API
        rate-limits hard); the rest is labelled simulation.
      </p>
    </Card>
  );
}

export function WebhookSimulator({ report }: { report: PipelineReport }) {
  const qc = useQueryClient();
  const [linkId, setLinkId] = useState<string>("");

  const pending = useMemo(
    () =>
      report.results
        .map((r) => r.audit_entry)
        .filter((e) => e.payment_link_id && e.confirmed_outcome !== "recovered"),
    [report],
  );

  const mutation = useMutation({
    mutationFn: (id: string) => api.confirmWebhook(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["report"] }),
  });

  const selected = linkId || pending[0]?.payment_link_id || "";

  return (
    <Card
      title="Webhook simulator"
      subtitle="POST /api/webhooks/razorpay — turn a projected recovery into a confirmed one"
      action={<Webhook className="size-4 text-ink-muted" />}
    >
      {pending.length === 0 ? (
        <p className="text-xs text-ink-muted">No payment links awaiting confirmation in this run.</p>
      ) : (
        <div className="flex flex-wrap items-center gap-3">
          <select
            value={selected}
            onChange={(e) => setLinkId(e.target.value)}
            className="min-w-[220px] rounded-lg border border-border bg-surface-2 px-2 py-1 text-xs outline-none"
          >
            {pending.map((e) => (
              <option key={e.payment_link_id} value={e.payment_link_id!}>
                {e.payment_link_id} · {inr(e.amount)} · {e.transaction_id.slice(0, 12)}
              </option>
            ))}
          </select>
          <Button
            variant="outline"
            onClick={() => selected && mutation.mutate(selected)}
            disabled={mutation.isPending || !selected}
          >
            {mutation.isPending ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <CheckCircle2 className="size-3.5" />
            )}
            Mark as paid
          </Button>
          <span className="text-[11px] text-ink-muted">
            {report.summary.confirmed_recovered > 0 && (
              <>confirmed so far: <span className="text-good">{inr(report.summary.confirmed_recovered)}</span></>
            )}
          </span>
        </div>
      )}
    </Card>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] font-medium uppercase tracking-wide text-ink-muted">{label}</span>
      {children}
    </label>
  );
}
