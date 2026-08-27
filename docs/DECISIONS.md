# Design decisions

Short ADRs — the *why* behind choices a reviewer would otherwise have to ask about.

### 1. Deterministic rules move money; the LLM only advises

The LLM is on the path for two things: diagnosing a bare bank decline, and
drafting customer message copy. It is never the thing that decides whether a
retry fires or a customer is contacted. That boundary is structural — the LLM
port returns a `Diagnosis` recommendation, and `RecoveryEngine` (pure, tested)
is what turns it into an allowed action. Rationale: a wrong message is cheap;
a wrong "charge them again" is not.

### 2. It must run with zero credentials

Every port has a no-op adapter (`NullLLM`, `SimulatedGateway`). A cold `git
clone && make demo` produces a full dashboard with labelled simulation. Real
keys upgrade paths in place — no code change, no separate "demo mode". This
also keeps the test suite hermetic.

### 3. Budgeted live Razorpay calls, not all-or-nothing

Razorpay's test-mode API rate-limits at a few link-creates per minute.
Creating a real link for all ~40 retries in a batch would take minutes and
mostly 429. The gateway spends a small budget of genuine creations (default 8,
backing off on 429, with a circuit breaker after 3 consecutive limits), then
labels the rest `razorpay_api_simulated` / `razorpay_api_ratelimited`. The
dashboard shows the split — it never claims more was live than was.

### 4. Per-method recovery strategies

A second card decline and a net-banking timeout are not the same situation.
`services/strategies.py` encodes small, defensible differences: UPI retries in
minutes (instant rails, free), net-banking waits hours (likely a bank
outage), card escalates to UPI after 3 tries. This is the judgement a
merchant's ops team applies by hand.

### 5. `Money`, not `float`

Payments are money. `float` rupees accumulate error and misformat for an
Indian audience. `Money` is an exact `Decimal`, converts to/from integer
paise for the wire, and groups digits the Indian way everywhere.

### 6. Pydantic strict models, and a deliberate way past them

Domain models reject malformed input at the boundary. The failure-containment
demo needs a bad record to reach deep into the pipeline, so it uses
`Transaction.model_construct` to bypass validation on that one record —
modelling data that slipped past ingestion (a legacy export, a bad
migration). It blows up in the executor's arithmetic, is caught per
transaction, and the batch continues.

### 7. One report object

The pipeline produces a single `PipelineReport`. Every headline number is a
`@staticmethod` derivation from `results` — never stored twice, never able to
drift. The CLI, the API, the SPA, and the tests all read the same object.

### 8. React SPA + JSON API over a static HTML file

An earlier cut rendered a self-contained HTML file. A real API + SPA is worth
the build step: the webhook flow is interactive, runs are triggerable, the
audit trail is filterable, and the JSON API is the actual integration surface
a merchant would consume. `revenue-recovery serve` hosts both from one
process; the Docker image ships the built dashboard.
