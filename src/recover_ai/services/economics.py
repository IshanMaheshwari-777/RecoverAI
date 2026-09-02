"""Unit economics: is this recovery worth the cost of chasing it?

Not every failed payment should be pursued. A small amount, a low
conversion probability, and a paid messaging channel can add up to a
negative expected value once you price in the chance the nudge generates
a support ticket, or that a retry ends in a chargeback.

    NEV = p_recover * amount
          - channel_cost
          - support_ticket_rate * support_contact_cost      (messages only)
          - chargeback_risk_rate * chargeback_cost_rate * amount   (retries only)

The recovery layer computes NEV for the cheapest workable channel and
only acts when it clears `policy.min_net_expected_value`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from recover_ai.domain.enums import MESSAGING_LADDER, RETRY_ACTIONS, Channel, DiagnosisAction
from recover_ai.domain.policy import Policy

DeliverabilityCheck = Callable[[Channel], bool]

_CHANNEL_COST_FIELD = {
    Channel.PAYMENT_LINK: "payment_link",
    Channel.IN_APP: "in_app",
    Channel.EMAIL: "email",
    Channel.SMS: "sms",
    Channel.WHATSAPP: "whatsapp",
}


def channel_cost(policy: Policy, channel: Channel) -> float:
    return float(getattr(policy.channels, _CHANNEL_COST_FIELD[channel]))


@dataclass(frozen=True, slots=True)
class EVResult:
    channel: Channel
    channel_cost: float
    net_expected_value: float
    worth_pursuing: bool


def evaluate(
    *,
    policy: Policy,
    action: DiagnosisAction,
    amount: float,
    p_recover: float,
    channel: Channel,
) -> EVResult:
    ch = policy.channels
    cost = channel_cost(policy, channel)
    gross = p_recover * amount
    if action in RETRY_ACTIONS:
        risk = ch.chargeback_risk_rate * ch.chargeback_cost_rate * amount
        nev = gross - cost - risk
    else:
        support = ch.support_ticket_rate * ch.support_contact_cost
        nev = gross - cost - support
    return EVResult(
        channel=channel,
        channel_cost=cost,
        net_expected_value=round(nev, 2),
        worth_pursuing=nev >= policy.min_net_expected_value,
    )


def best_channel(
    *,
    policy: Policy,
    action: DiagnosisAction,
    amount: float,
    p_recover: float,
    deliverable: DeliverabilityCheck,
) -> EVResult:
    """For a retry the channel is always the payment link. For a message,
    walk the ladder cheapest-first and take the first channel that is
    both deliverable and positive-NEV; if none clear, return the best
    one found so the caller can record why it was skipped."""
    if action in RETRY_ACTIONS:
        return evaluate(
            policy=policy,
            action=action,
            amount=amount,
            p_recover=p_recover,
            channel=Channel.PAYMENT_LINK,
        )

    best: EVResult | None = None
    for channel in MESSAGING_LADDER:
        if not deliverable(channel):
            continue
        result = evaluate(
            policy=policy, action=action, amount=amount, p_recover=p_recover, channel=channel
        )
        if result.worth_pursuing:
            return result
        if best is None or result.net_expected_value > best.net_expected_value:
            best = result
    return best or evaluate(
        policy=policy,
        action=action,
        amount=amount,
        p_recover=p_recover,
        channel=Channel.EMAIL,
    )
