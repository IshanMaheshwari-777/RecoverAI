# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
[Semantic Versioning](https://semver.org/).

## [1.1.0] — 2026-08-29

### Changed
- Default LLM is now **Claude Haiku 4.5** (was Opus 5) — the two calls are tiny;
  ~₹1 per full run. `output_config.effort` is sent only on tiers that accept it.
- **Concurrent pipeline**: diagnose + execute run on a thread pool (default 16
  workers), decide stays sequential/chronological. A live 180-txn run drops
  from ~100 s to ~8 s. Adapters carry a lock; containment moved into the pool.
- `.env` reduced to three optional keys.

### Added
- `RazorpayGateway` recognises the test-account 30-link lifetime cap and stops
  attempting live immediately (was retrying + backing off pointlessly).
- Unit tests for the gateway degradation logic (budget / backoff / circuit /
  quota). 68 tests, 93% coverage.

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
- `revenue-recovery` CLI (`run`, `report`, `serve`, `demo`).
- FastAPI JSON API + OpenAPI docs.
- React + Vite dashboard: KPI tiles, decision-flow Sankey, recovery funnel,
  breakdowns, compliance panel, filterable audit trail, run + webhook
  controls; light/dark.
- CI (lint, types, tests on 3.11/3.12, frontend build, Docker smoke test),
  pre-commit, multi-stage Dockerfile, compose.
