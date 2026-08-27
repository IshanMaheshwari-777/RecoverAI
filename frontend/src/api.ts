import type { PipelineReport, RunRequest } from "./types";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}${body ? ` – ${body}` : ""}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getReport: () => fetch("/api/report").then((r) => json<PipelineReport>(r)),

  run: (body: RunRequest) =>
    fetch("/api/runs", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    }).then((r) => json<PipelineReport>(r)),

  confirmWebhook: (payment_link_id: string) =>
    fetch("/api/webhooks/razorpay", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ event: "payment_link.paid", payment_link_id }),
    }).then((r) => json<{ status: string; transaction_id: string }>(r)),
};
