import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, Webhook } from "lucide-react";
import { api } from "../api";
import type { PipelineReport } from "../types";
import { inr } from "../lib/format";
import { Button, Card } from "./ui";
import { toast } from "./Toast";

/**
 * Simulates Razorpay's `payment_link.paid` webhook.
 *
 * This is the bridge between the two money numbers on the dashboard:
 * *projected* recovery (a modelled estimate) becomes *confirmed* recovery
 * (measured). Each confirmation moves one transaction across.
 */
export function WebhookPanel({ report }: { report: PipelineReport }) {
  const qc = useQueryClient();
  const [linkId, setLinkId] = useState("");

  const { pending, confirmed, total } = useMemo(() => {
    const withLink = report.results
      .map((r) => r.audit_entry)
      .filter((e) => e.payment_link_id);
    return {
      pending: withLink.filter((e) => e.confirmed_outcome !== "recovered"),
      confirmed: withLink.filter((e) => e.confirmed_outcome === "recovered").length,
      total: withLink.length,
    };
  }, [report]);

  const mutation = useMutation({
    mutationFn: (id: string) => api.confirmWebhook(id),
    onSuccess: (_d, id) => {
      qc.invalidateQueries({ queryKey: ["report"] });
      setLinkId("");
      toast(`Confirmed ${id} — moved from projected to confirmed`);
    },
    onError: (e) => toast((e as Error).message, "critical"),
  });

  const selected = linkId || pending[0]?.payment_link_id || "";

  return (
    <Card
      title="Webhook simulator"
      subtitle="Stands in for Razorpay's real payment_link.paid event"
      action={<Webhook className="size-4 text-ink-muted" />}
    >
      <p className="mb-3 rounded-lg bg-surface-2 px-3 py-2.5 text-[11px] leading-relaxed text-ink-muted">
        <span className="font-medium text-ink-secondary">Projected</span> recovery is an
        estimate — each action is scored with the conversion rate the learning loop has settled
        on for that segment.{" "}
        <span className="font-medium text-ink-secondary">Confirmed</span> recovery is measured: a
        customer actually paid, and each confirmation here also moves the posterior. Confirm one
        below to watch a transaction move across.
      </p>

      {total === 0 ? (
        <p className="text-xs text-ink-muted">
          No retry links in this run — every action was a message, which has nothing to confirm.
        </p>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={selected}
              onChange={(e) => setLinkId(e.target.value)}
              disabled={pending.length === 0}
              className="min-w-[230px] flex-1 rounded-lg border border-border bg-surface-2 px-2 py-1.5 text-xs outline-none focus:border-series-1 disabled:opacity-50"
            >
              {pending.length === 0 ? (
                <option>All confirmed</option>
              ) : (
                pending.map((e) => (
                  <option key={e.payment_link_id} value={e.payment_link_id!}>
                    {e.payment_link_id} · {inr(e.amount)}
                  </option>
                ))
              )}
            </select>
            <Button
              variant="outline"
              onClick={() => selected && mutation.mutate(selected)}
              disabled={mutation.isPending || pending.length === 0}
            >
              {mutation.isPending ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <CheckCircle2 className="size-3.5" />
              )}
              Mark as paid
            </Button>
          </div>

          <div className="mt-3 flex items-center gap-3">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2">
              <div
                className="h-full rounded-full bg-good transition-[width] duration-500"
                style={{ width: `${total ? (confirmed / total) * 100 : 0}%` }}
              />
            </div>
            <span className="tabular whitespace-nowrap text-[11px] text-ink-muted">
              {confirmed} of {total} confirmed
            </span>
          </div>

          {confirmed === total && total > 0 && (
            <p className="mt-2 text-[11px] leading-relaxed text-warn">
              Every retry marked paid — that's the theoretical ceiling ({inr(report.summary.confirmed_recovered)}),
              not a realistic outcome. The projected number assumes only a fraction convert.
            </p>
          )}
        </>
      )}
    </Card>
  );
}
