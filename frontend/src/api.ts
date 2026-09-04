import type { HealthResponse, PipelineReport, RunHistoryRow, RunRequest } from "./types";

// Empty by default: the SPA is served same-origin by the API. Set
// VITE_API_URL at build time (e.g. on Vercel) when the API lives elsewhere.
const BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");
const url = (path: string) => `${BASE}${path}`;

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}${body ? ` – ${body}` : ""}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getReport: () => fetch(url("/api/report")).then((r) => json<PipelineReport>(r)),

  getHealth: () => fetch(url("/api/health")).then((r) => json<HealthResponse>(r)),

  run: (body: RunRequest) =>
    fetch(url("/api/runs"), {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    }).then((r) => json<PipelineReport>(r)),

  confirmWebhook: (payment_link_id: string) =>
    fetch(url("/api/webhooks/razorpay"), {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ event: "payment_link.paid", payment_link_id }),
    }).then((r) => json<{ status: string; transaction_id: string }>(r)),

  getRunHistory: () => fetch(url("/api/runs/history")).then((r) => json<RunHistoryRow[]>(r)),
};
