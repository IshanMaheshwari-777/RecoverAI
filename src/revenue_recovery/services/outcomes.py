"""Projecting whether a recovery action converts.

Whether a retried or reminded customer actually completes checkout cannot
be known in a batch demo -- there is no real customer on the other end.
So we *project* it: each action type gets a fixed, published conversion
probability, and the draw is seeded on the transaction id, so re-running
the batch reproduces identical outcomes.

This is an explicit modelling assumption, labelled as such everywhere it
surfaces. In production the projection is replaced by real webhook
confirmations -- see `confirmed_outcome` on the audit entry and the
`/api/webhooks/razorpay` endpoint.
"""

from __future__ import annotations

import random

from revenue_recovery.domain.enums import DiagnosisAction, RecoveryOutcome

PROJECTED_CONVERSION_RATE: dict[DiagnosisAction, float] = {
    DiagnosisAction.RETRY_NOW: 0.45,
    DiagnosisAction.RETRY_LATER: 0.30,
    DiagnosisAction.SEND_REMINDER: 0.20,
    DiagnosisAction.REQUEST_UPDATE: 0.15,
}


def project_outcome(action: DiagnosisAction, transaction_id: str) -> RecoveryOutcome:
    rate = PROJECTED_CONVERSION_RATE.get(action, 0.0)
    draw = random.Random(transaction_id).random()
    return RecoveryOutcome.RECOVERED if draw < rate else RecoveryOutcome.NOT_RECOVERED
