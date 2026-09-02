"""Projecting whether a recovery action converts.

Whether a retried or reminded customer actually completes checkout cannot
be known in a batch demo -- there is no real customer on the other end.
So we *project* it: a Bernoulli draw seeded on the transaction id (so a
re-run reproduces identical outcomes) against a conversion probability.

That probability is no longer a hard-coded constant -- it comes from the
learning loop (`services/learning.py`), which starts at the policy prior
and moves with every real webhook confirmation. In production the
projection is replaced outright by those confirmations -- see
`confirmed_outcome` on the audit entry and `/api/webhooks/razorpay`.
"""

from __future__ import annotations

import random

from recover_ai.domain.enums import DiagnosisAction, RecoveryOutcome

# Prior conversion rates, kept only as a zero-dependency fallback for
# callers without a learning store. The live values live in
# `Policy.conversion_priors` and the posteriors in the learning store.
PRIOR_CONVERSION_RATE: dict[DiagnosisAction, float] = {
    DiagnosisAction.RETRY_NOW: 0.45,
    DiagnosisAction.RETRY_LATER: 0.30,
    DiagnosisAction.SEND_REMINDER: 0.20,
    DiagnosisAction.REQUEST_UPDATE: 0.15,
}


def project_outcome(*, rate: float, transaction_id: str) -> RecoveryOutcome:
    """A seeded draw against ``rate`` -- deterministic per transaction."""
    draw = random.Random(transaction_id).random()
    return RecoveryOutcome.RECOVERED if draw < rate else RecoveryOutcome.NOT_RECOVERED


def prior_rate(action: DiagnosisAction) -> float:
    return PRIOR_CONVERSION_RATE.get(action, 0.0)
