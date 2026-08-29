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

### 3. Budgeted live Razorpay calls, with a payment-link → order fallback

Razorpay's test mode caps **payment-link** creation at 30 per account (ever)
and rate-limits the endpoint hard. So the gateway:
1. spends a bounded budget of genuine creations (default 12, backing off on
   429, circuit-breaking after 3 consecutive limits);
2. once payment links are capped, creates a live **Order** instead — no
   30-cap, still a real Razorpay object, reported as `RAZORPAY_ORDER`;
3. only then falls back to a labelled `razorpay_api_simulated` /
   `razorpay_api_ratelimited` link.

The dashboard shows the exact split — it never claims more was live than was.
A merchant's real integration would use payment links throughout; the order
path exists so the demo stays genuinely live against a capped test account.

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

### 8. Three-phase concurrent pipeline

With a live LLM, a 180-transaction batch is ~55 model calls plus ~35
payment-gateway calls. Run sequentially that's ~100 s — unusable in a demo
or a webhook handler. `Pipeline.run` splits into three phases: **diagnose**
(parallel, transactions are independent), **decide** (strictly sequential
in chronological order — the recovery engine's per-customer contact
history must see events as they happened), **execute** (parallel again).
Same result, ~8 s. The mutable adapters (`RazorpayGateway` budget,
`AnthropicLLM` lazy client) carry a lock; everything else is stateless.
The containment boundary moved into `_concurrent` — one transaction's
raise is captured and never touches the pool's other work.

### 9. React SPA + JSON API over a static HTML file

An earlier cut rendered a self-contained HTML file. A real API + SPA is worth
the build step: the webhook flow is interactive, runs are triggerable, the
audit trail is filterable, and the JSON API is the actual integration surface
a merchant would consume. `recover-ai serve` hosts both from one
process; the Docker image ships the built dashboard.
