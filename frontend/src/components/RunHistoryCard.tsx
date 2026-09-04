import { Database } from "lucide-react";
import { useRunHistory } from "../hooks/useRunHistory";
import { inr, pct, relativeTime } from "../lib/format";
import { Badge, Card, Skeleton } from "./ui";

/** Proof this isn't one file that overwrites itself: a real SQLite ledger
 * (data/recover.db), one row per run, queried live from `/api/runs/history`. */
export function RunHistoryCard() {
  const { data, isLoading } = useRunHistory();

  return (
    <Card
      title="Run history"
      subtitle="Every run, persisted to a real database (data/recover.db) — not just the latest snapshot"
      action={<Database className="size-4 text-ink-muted" />}
    >
      {isLoading && <Skeleton className="h-24" />}
      {!isLoading && (!data || data.length === 0) && (
        <p className="text-xs text-ink-muted">No runs recorded yet.</p>
      )}
      {!isLoading && data && data.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-ink-muted">
              <tr className="[&>th]:whitespace-nowrap [&>th]:pb-2 [&>th]:pr-4 [&>th]:font-medium">
                <th>When</th>
                <th>Source</th>
                <th>Mode</th>
                <th className="text-right">Failures</th>
                <th className="text-right">Projected</th>
                <th className="text-right">Lift</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data.map((r) => (
                <tr key={r.run_id}>
                  <td className="py-1.5 pr-4 text-ink-secondary">
                    {relativeTime(r.finished_at)}
                  </td>
                  <td className="py-1.5 pr-4">
                    <Badge tone={r.data_source === "razorpay" ? "good" : "neutral"}>
                      {r.data_source === "razorpay" ? "live" : "synthetic"}
                    </Badge>
                  </td>
                  <td className="py-1.5 pr-4 text-ink-secondary">{r.mode}</td>
                  <td className="py-1.5 pr-4 text-right tabular text-ink">
                    {r.needing_attention}
                  </td>
                  <td className="py-1.5 pr-4 text-right tabular text-ink">
                    {inr(r.projected_recovered_rupees)}
                  </td>
                  <td className="py-1.5 text-right tabular text-ink">
                    {r.incremental_lift ? pct(r.incremental_lift) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
