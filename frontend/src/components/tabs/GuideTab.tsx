import { Ban, Bot, Clock, CreditCard, Ruler, Send, ShieldCheck, Wifi } from "lucide-react";
import type { ReactNode } from "react";
import type { PipelineReport } from "../../types";
import { Card, SectionLead } from "../ui";

const CASES: {
  icon: ReactNode;
  reason: string;
  plain: string;
  action: string;
  by: "rule" | "ai";
}[] = [
  {
    icon: <Ruler className="size-3.5" />,
    reason: "invalid_otp",
    plain: "Customer mistyped the OTP. The card itself is fine.",
    action: "Retry now",
    by: "rule",
  },
  {
    icon: <Bot className="size-3.5" />,
    reason: "payment_declined",
    plain:
      "The bank said no, with no reason given. First decline? Probably a transient hold. Third on the same card? The card is the problem.",
    action: "Claude decides",
    by: "ai",
  },
  {
    icon: <Clock className="size-3.5" />,
    reason: "insufficient_funds",
    plain: "Not enough money right now — but salary lands, wallets get topped up.",
    action: "Retry later",
    by: "rule",
  },
  {
    icon: <Wifi className="size-3.5" />,
    reason: "gateway_timeout",
    plain: "The gateway didn't respond in time. Nothing to do with the customer.",
    action: "Retry now",
    by: "rule",
  },
  {
    icon: <Wifi className="size-3.5" />,
    reason: "network_issue",
    plain: "A network blip mid-processing. Transient.",
    action: "Retry now",
    by: "rule",
  },
  {
    icon: <Send className="size-3.5" />,
    reason: "payment_cancelled",
    plain: "Customer hit cancel or closed the tab. Hesitation, not a technical failure.",
    action: "Send a reminder",
    by: "rule",
  },
  {
    icon: <CreditCard className="size-3.5" />,
    reason: "card_expired",
    plain: "The expiry date has passed. No retry will ever succeed.",
    action: "Ask for a new card",
    by: "rule",
  },
  {
    icon: <Ban className="size-3.5" />,
    reason: "risk_check_failed",
    plain:
      "The fraud engine blocked it — a stolen card, a card-testing bot, or a velocity flag. Retrying would help a fraudster and earn the merchant a chargeback.",
    action: "Never contact",
    by: "rule",
  },
  {
    icon: <Send className="size-3.5" />,
    reason: "abandoned checkout",
    plain: "They reached the payment page and never even tried. High intent.",
    action: "Send a reminder",
    by: "rule",
  },
];

export function GuideTab({ report }: { report: PipelineReport }) {
  const s = report.summary;

  return (
    <div className="space-y-6">
      <SectionLead title="What this solves">
        Razorpay tells a merchant that a payment failed, and why. It does not decide what to do
        about each one — retry now, wait, ask for a new card, send a nudge, or leave it alone
        because it is fraud. Most merchants send one generic “payment failed” email and eat the
        rest. That per-case judgment, done inside hard compliance limits and fully audited, is the
        revenue this agent recovers.
      </SectionLead>

      <div className="grid gap-3 md:grid-cols-3">
        <Step n={1} title="Detect">
          Reads a batch of transactions and finds the failed and abandoned ones — {inrLike(s.at_risk)}{" "}
          at risk here.
        </Step>
        <Step n={2} title="Diagnose">
          Reads Razorpay's structured error to work out the real cause. {s.diagnosis_split.rule} by
          fixed rule, {s.diagnosis_split.llm + s.diagnosis_split.llm_fallback} by Claude.
        </Step>
        <Step n={3} title="Decide &amp; act">
          Picks the right recovery, checks it against the stopping rules, then creates a real
          Razorpay payment object or writes the customer message.
        </Step>
      </div>

      <Card
        title="The nine cases it handles"
        subtitle="Every failure reason, what it actually means, and the agent's response"
      >
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-ink-muted">
              <tr className="[&>th]:whitespace-nowrap [&>th]:pb-2 [&>th]:pr-4 [&>th]:font-medium">
                <th>Failure reason</th>
                <th>What it means</th>
                <th>Recovery</th>
                <th>Decided by</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {CASES.map((c) => (
                <tr key={c.reason} className="align-top">
                  <td className="py-2.5 pr-4">
                    <span className="inline-flex items-center gap-1.5 whitespace-nowrap font-mono text-[11px] text-ink">
                      <span className="text-ink-muted">{c.icon}</span>
                      {c.reason}
                    </span>
                  </td>
                  <td className="max-w-md py-2.5 pr-4 leading-relaxed text-ink-muted">{c.plain}</td>
                  <td className="whitespace-nowrap py-2.5 pr-4 text-ink-secondary">{c.action}</td>
                  <td className="py-2.5">
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                        c.by === "ai"
                          ? "bg-series-2/15 text-series-2"
                          : "bg-series-1/15 text-series-1"
                      }`}
                    >
                      {c.by === "ai" ? "Claude" : "rule"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-4 border-t border-border pt-3 text-[11px] leading-relaxed text-ink-muted">
          Eight of nine have exactly one sane answer regardless of context — an expired card
          <em> always</em> means “ask for a new one”. Sending those to a model would add latency,
          cost and a hallucination surface for zero judgment benefit. Only the bare bank decline is
          genuinely ambiguous, so that is the only case Claude sees. And Claude only{" "}
          <strong className="text-ink-secondary">recommends</strong> — a separate deterministic
          layer decides whether money actually moves.
        </p>
      </Card>

      <Card
        title="The stopping rules"
        subtitle="Not policy documents — limits enforced in code, with a test that proves they hold"
      >
        <div className="grid gap-4 md:grid-cols-3">
          <Rule
            icon={<ShieldCheck className="size-4 text-good" />}
            title="Fraud stops are absolute"
            body="A risk-check failure can never be turned into an action. Retrying would complete a fraudulent charge — the merchant eats a chargeback plus a network fine, and a real person whose card was stolen gets harassed with 'complete your payment' texts."
            stat={`${s.compliance_violations} violations`}
          />
          <Rule
            icon={<CreditCard className="size-4 text-series-1" />}
            title="Retries capped per method"
            body="Card networks fine merchants for retry abuse. Cards get 3 attempts, net-banking 2 (usually a bank outage — retrying is pointless). Past the cap we stop and ask the customer to switch rails."
            stat={`${s.escalated_actions} escalations`}
          />
          <Rule
            icon={<Send className="size-4 text-series-3" />}
            title="Contact capped per customer"
            body="At most 2 messages to one person in a rolling 48 hours, across all of their transactions. Silent retries never count — nobody is being bothered. This is what stops the agent becoming a spam bot."
            stat={`${s.blocked_actions} held back`}
          />
        </div>
      </Card>

      <Card
        title="Projected vs. confirmed recovery"
        subtitle="The two money numbers, and why they differ"
      >
        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-lg border border-border bg-surface-2/50 p-3.5">
            <div className="text-xs font-semibold text-ink">Projected — a realistic estimate</div>
            <p className="mt-1.5 text-[11px] leading-relaxed text-ink-muted">
              Each action carries a published conversion rate: an immediate retry converts ~45% of
              the time, a delayed retry ~30%, a reminder ~20%, an update request ~15%. Applied per
              transaction with a fixed seed, so re-running gives the same answer. It is a labelled
              modelling assumption, not measured data.
            </p>
          </div>
          <div className="rounded-lg border border-border bg-surface-2/50 p-3.5">
            <div className="text-xs font-semibold text-ink">Confirmed — measured</div>
            <p className="mt-1.5 text-[11px] leading-relaxed text-ink-muted">
              A customer actually paid. In production, Razorpay fires a{" "}
              <code className="text-ink-secondary">payment_link.paid</code> webhook and the agent
              moves that transaction from projected to confirmed. The simulator on the Overview tab
              does exactly this. Marking <em>every</em> retry paid gives the theoretical ceiling —
              that is not a realistic outcome, and it is why the two numbers differ.
            </p>
          </div>
        </div>
      </Card>

      <Card title="Where the API keys are used" subtitle="Nothing runs in the background — only a run spends anything">
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <div className="text-xs font-semibold text-ink">Razorpay</div>
            <p className="mt-1.5 text-[11px] leading-relaxed text-ink-muted">
              Creates the actual place to pay, so the customer can complete the payment. You cannot
              silently re-charge a card that already declined — regenerating a payment object is
              the real recovery mechanism. Test accounts cap payment links at 30 forever, so beyond
              that the agent creates live <strong>orders</strong> instead, and labels anything past
              its budget as simulated.
            </p>
          </div>
          <div>
            <div className="text-xs font-semibold text-ink">
              Claude{report.llm_model ? ` (${report.llm_model})` : ""}
            </div>
            <p className="mt-1.5 text-[11px] leading-relaxed text-ink-muted">
              Two small jobs. It diagnoses the ambiguous bank declines — “attempt 3 on ₹5,000 by
              card: retry, wait, or switch method?” — and it writes the customer-facing messages.
              It never decides whether money moves. Idle dashboard = zero API calls; only pressing{" "}
              <strong className="text-ink-secondary">Run agent</strong> spends anything.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}

function inrLike(n: number) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(n);
}

function Step({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="flex items-center gap-2">
        <span className="grid size-5 place-items-center rounded-full bg-series-1 text-[10px] font-bold text-white">
          {n}
        </span>
        <span className="text-xs font-semibold text-ink">{title}</span>
      </div>
      <p className="mt-2 text-[11px] leading-relaxed text-ink-muted">{children}</p>
    </div>
  );
}

function Rule({
  icon,
  title,
  body,
  stat,
}: {
  icon: ReactNode;
  title: string;
  body: string;
  stat: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-surface-2/50 p-3.5">
      <div className="flex items-center gap-2">
        {icon}
        <span className="text-xs font-semibold text-ink">{title}</span>
      </div>
      <p className="mt-2 text-[11px] leading-relaxed text-ink-muted">{body}</p>
      <p className="mt-2.5 tabular text-[11px] font-medium text-ink-secondary">{stat}</p>
    </div>
  );
}
