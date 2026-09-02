/** ₹ with Indian digit grouping (12,34,567). */
export function inr(amount: number, opts: { decimals?: boolean } = {}): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: opts.decimals ? 2 : 0,
    minimumFractionDigits: opts.decimals ? 2 : 0,
  }).format(amount);
}

export function inrCompact(amount: number): string {
  if (amount >= 1e7) return `₹${(amount / 1e7).toFixed(2)} Cr`;
  if (amount >= 1e5) return `₹${(amount / 1e5).toFixed(2)} L`;
  return inr(amount);
}

export function pct(ratio: number, digits = 1): string {
  return `${(ratio * 100).toFixed(digits)}%`;
}

export function titleCase(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

const ACTION_LABELS: Record<string, string> = {
  retry_now: "Retry now",
  retry_later: "Retry later",
  request_update: "Request update",
  send_reminder: "Send reminder",
  do_not_contact: "Do not contact",
};

const METHOD_LABELS: Record<string, string> = {
  razorpay_api: "Razorpay link · live",
  razorpay_order: "Razorpay order · live",
  razorpay_api_simulated: "Razorpay API · simulated",
  razorpay_api_ratelimited: "Razorpay API · rate-limited",
  llm_message: "LLM-drafted message",
  template_message: "Template message",
  blocked: "Blocked",
  unhandled: "Unhandled",
  pipeline_error: "Processing failed",
  holdout_control: "Holdout control",
  retry_held_incident: "Retry deferred · incident",
  skipped_negative_ev: "Skipped · negative EV",
  shadow: "Shadow · not executed",
};

const DIAG_LABELS: Record<string, string> = {
  rule: "Deterministic rule",
  llm: "LLM",
  llm_fallback: "LLM fallback",
  unhandled: "Unhandled",
};

export const label = {
  action: (k: string | null) => (k ? (ACTION_LABELS[k] ?? titleCase(k)) : "—"),
  method: (k: string) => METHOD_LABELS[k] ?? titleCase(k),
  diagnosis: (k: string) => DIAG_LABELS[k] ?? titleCase(k),
};

export function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  const diff = Date.now() - then;
  const mins = Math.round(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}
