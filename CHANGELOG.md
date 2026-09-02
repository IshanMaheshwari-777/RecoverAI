# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
[Semantic Versioning](https://semver.org/).

## [1.3.0] — 2026-09-03

### Added
- **Versioned policy** (`domain/policy.py`, optional `data/policy.toml`) —
  every tunable in one frozen object: caps, conversion priors, channel costs,
  the holdout fraction, incident thresholds. Each audit entry records the
  `policy_version` it was decided under.
- **Learning loop** (`services/learning.py`) — Beta-Bernoulli posteriors for
  `P(recover | action, method, reason, amount band)`, a credible interval, and
  a Brier-scored calibration table. Starts at the policy prior; every webhook
  confirmation moves it. `project_outcome` now draws against the learned
  posterior, not a constant. New **Learning** dashboard tab: reliability
  diagram, posteriors table (prior vs learned), calibration score.
- **Causal holdout** — a seeded fraction of would-execute decisions are decided
  identically but not executed. Treatment-vs-control recovery is a **measured
  incremental lift** with a 95% CI, accrued across runs — not a projection.
- **Recovery economics** (`services/economics.py`) — net expected value =
  `p·amount − channel cost − chargeback/support risk`. A recovery below the
  policy floor is skipped, not sent. Messages walk a cheapest-first channel
  ladder (in-app → email → SMS → WhatsApp).
- **Incident detection** (`services/incidents.py`) — a large, time-concentrated
  cluster of failures on one rail is flagged; retries against it are deferred.
- **Trust layer** — webhook HMAC-SHA256 verification
  (`services/webhooks.py`, gated on `RAZORPAY_WEBHOOK_SECRET`); idempotency
  keys + a dedupe store (`services/idempotency.py`).
- **Shadow mode** — `recover-ai run --shadow` and the Run popover: decide
  everything, execute nothing, don't save.
- **`recover-ai backtest <csv>`** — replay the policy over a historical outcome
  log and report projected recovery, organic baseline, incremental revenue,
  and the calibration score. **`recover-ai policy-diff`** diffs two policies in
  shadow over one batch.
- `GET /api/learning`; `POST /api/runs` takes `mode`.

### Changed
- 93 tests (was 69). The pipeline threads a `Policy` and a `LearningStore`
  through every layer; adapters are unchanged.

## [1.2.0] — 2026-08-29

### Changed
- **Renamed to Recover AI.** Python package `revenue_recovery` → `recover_ai`,
  CLI `revenue-recovery` → `recover-ai`, product name throughout.
- **Dashboard rebuilt around four tabs** — Overview · Decision flow · Audit
  trail · How it works — replacing a single 2,700 px scroll. Everything a
  reader needs is now one screen deep.
- **Run agent** moved into the header as the primary action, with a settings
  popover (batch size / seed / inject a corrupt record) and a completion toast.
- Audit rows are **expandable**: the message Claude wrote, the Razorpay object
  created, the model + latency + confidence, the strategy applied, and why the
  compliance layer allowed it.
- Plain-English copy throughout; hover explainers on every metric that needs
  one. Jargon (`llm_fallback`, `razorpay_api_simulated`) is now secondary.

### Added
- **How it works** tab: the nine failure cases in plain English, the stopping
  rules and the real-world penalty behind each, and a side-by-side explanation
  of projected vs. confirmed recovery.
- Webhook simulator shows an `n of m confirmed` meter and warns when every
  retry is marked paid (the theoretical ceiling, not a realistic outcome).

## [1.1.0] — 2026-08-29

### Changed
- Default LLM is now **Claude Haiku 4.5** (was Opus 5) — the two calls are tiny;
  ~₹1 per full run. `output_config.effort` is sent only on tiers that accept it.
- **Concurrent pipeline**: diagnose + execute run on a thread pool (default 16
  workers), decide stays sequential/chronological. A live 180-txn run drops
  from ~100 s to ~8 s. Adapters carry a lock; containment moved into the pool.
- `.env` reduced to three optional keys.

### Added
- `RazorpayGateway` now falls back **payment link → live order → simulated**:
  once the test account's 30-payment-link cap is hit it creates a real Order
  instead (`RAZORPAY_ORDER`), so the demo stays genuinely live. New
  `ExecutionMethod.RAZORPAY_ORDER`, surfaced on the dashboard.
- Unit tests for the gateway fallback chain (budget / backoff / circuit / cap
  / order). 69 tests, 93% coverage.

## [1.0.0] — 2026-08-27

First complete cut for the Razorpay AI Buildathon, Track 03.

### Architecture
- Hexagonal layout: `domain` (pure) → `ports` (Protocols) → `adapters`
  (Razorpay, Anthropic, synthetic data) → `services` (diagnosis, recovery,
  execution, pipeline) → `api` / `cli` (delivery).
- Strict-typed Pydantic domain models; `Money` value type with Indian digit
  grouping and exact paise arithmetic.
- Typed settings with placeholder-credential scrubbing; structured logging.

### Agent behaviour
- **Diagnosis** — 7/8 failure reasons resolved by a deterministic rule table;
  confidence-weighted routing sends the genuinely ambiguous bare-decline case
  to the LLM, which recommends but never executes.
- **Recovery** — three hard limits enforced in code: `do_not_contact` is
  absolute, retries capped per method, contact capped per customer per 48 h.
  Per-method playbooks (card / UPI / net-banking / wallet) and a
  cause-aware retry-scheduling model.
- **Execution** — live Razorpay payment-links with a budgeted, backing-off
  live path and honest `simulated` / `rate-limited` labelling; LLM-drafted or
  templated customer messages.
- **Containment** — one malformed record fails in isolation; the batch
  continues, with an audit entry for the failure.
- **Outcomes** — projected conversion (published per-action probabilities,
  seeded) plus a `/api/webhooks/razorpay` path that turns a projection into a
  confirmed recovery.

### Delivery
- `recover-ai` CLI (`run`, `report`, `serve`, `demo`).
- FastAPI JSON API + OpenAPI docs.
- React + Vite dashboard: KPI tiles, decision-flow Sankey, recovery funnel,
  breakdowns, compliance panel, filterable audit trail, run + webhook
  controls; light/dark.
- CI (lint, types, tests on 3.11/3.12, frontend build, Docker smoke test),
  pre-commit, multi-stage Dockerfile, compose.
