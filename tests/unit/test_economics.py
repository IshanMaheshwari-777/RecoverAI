from __future__ import annotations

from recover_ai.domain.enums import Channel, DiagnosisAction
from recover_ai.domain.policy import Policy
from recover_ai.services.economics import best_channel, evaluate


def test_tiny_amount_low_odds_is_not_worth_pursuing() -> None:
    r = evaluate(
        policy=Policy(),
        action=DiagnosisAction.SEND_REMINDER,
        amount=30.0,
        p_recover=0.03,
        channel=Channel.WHATSAPP,
    )
    assert r.net_expected_value < 1.0
    assert not r.worth_pursuing


def test_large_amount_good_odds_clears_easily() -> None:
    r = evaluate(
        policy=Policy(),
        action=DiagnosisAction.RETRY_NOW,
        amount=9000.0,
        p_recover=0.5,
        channel=Channel.PAYMENT_LINK,
    )
    assert r.worth_pursuing
    assert r.net_expected_value > 4000


def test_channel_ladder_prefers_the_cheapest_that_clears() -> None:
    result = best_channel(
        policy=Policy(),
        action=DiagnosisAction.SEND_REMINDER,
        amount=3000.0,
        p_recover=0.2,
        deliverable=lambda _c: True,
    )
    # in_app is free and effective -> chosen over paid SMS/WhatsApp
    assert result.channel is Channel.IN_APP
    assert result.channel_cost == 0.0


def test_channel_ladder_skips_undeliverable_channels() -> None:
    result = best_channel(
        policy=Policy(),
        action=DiagnosisAction.SEND_REMINDER,
        amount=3000.0,
        p_recover=0.2,
        deliverable=lambda c: c is not Channel.IN_APP,
    )
    assert result.channel is not Channel.IN_APP
