"""The recovery layer enforces the compliance limits -- these tests are
the proof they hold, so they are explicit, not incidental."""

from __future__ import annotations

from revenue_recovery.domain.diagnosis import Diagnosis
from revenue_recovery.domain.enums import DiagnosisAction, DiagnosisMethod, PaymentMethod
from revenue_recovery.services.recovery import RecoveryEngine


def _diag(txn_id: str, action: DiagnosisAction) -> Diagnosis:
    return Diagnosis(
        transaction_id=txn_id,
        root_cause="x",
        action=action,
        method=DiagnosisMethod.RULE,
        confidence=0.9,
    )


def test_do_not_contact_is_never_overridden(txn_factory) -> None:
    txn = txn_factory()
    d = RecoveryEngine().decide(txn, _diag(txn.id, DiagnosisAction.DO_NOT_CONTACT))
    assert d.blocked
    assert d.final_action is None


def test_retry_within_cap_proceeds_and_is_scheduled(txn_factory) -> None:
    txn = txn_factory(method=PaymentMethod.CARD, attempt_number=1)
    d = RecoveryEngine().decide(txn, _diag(txn.id, DiagnosisAction.RETRY_NOW))
    assert not d.blocked
    assert d.final_action is DiagnosisAction.RETRY_NOW
    assert d.scheduled_for == txn.created_at  # retry_now fires immediately


def test_retry_later_is_scheduled_into_the_future(txn_factory) -> None:
    txn = txn_factory(method=PaymentMethod.CARD, attempt_number=1)
    d = RecoveryEngine().decide(txn, _diag(txn.id, DiagnosisAction.RETRY_LATER))
    assert d.scheduled_for is not None
    assert d.scheduled_for > txn.created_at


def test_per_method_retry_cap_escalates_to_request_update(txn_factory) -> None:
    # netbanking caps at 2 attempts -- a 2nd-attempt retry escalates
    txn = txn_factory(method=PaymentMethod.NETBANKING, attempt_number=2)
    d = RecoveryEngine().decide(txn, _diag(txn.id, DiagnosisAction.RETRY_LATER))
    assert d.final_action is DiagnosisAction.REQUEST_UPDATE
    assert d.escalated
    assert "upi" in d.reason  # netbanking's alternate rail


def test_card_allows_a_third_attempt_that_netbanking_would_not(txn_factory) -> None:
    card = txn_factory(method=PaymentMethod.CARD, attempt_number=2)
    d = RecoveryEngine().decide(card, _diag(card.id, DiagnosisAction.RETRY_NOW))
    assert d.final_action is DiagnosisAction.RETRY_NOW  # card cap is 3


def test_third_contact_in_window_is_blocked() -> None:
    from tests.conftest import make_txn

    engine = RecoveryEngine()
    times = [
        "2026-01-01T00:00:00+00:00",
        "2026-01-01T10:00:00+00:00",
        "2026-01-01T20:00:00+00:00",  # still inside 48h -> 3rd contact blocked
    ]
    results = [
        engine.decide(
            make_txn(id=f"c{i}", customer_id="cust_repeat", created_at=t),
            _diag(f"pay_c{i}", DiagnosisAction.SEND_REMINDER),
        )
        for i, t in enumerate(times)
    ]
    assert [r.blocked for r in results] == [False, False, True]
    assert "48h" in results[2].reason


def test_contact_cap_resets_outside_window() -> None:
    from tests.conftest import make_txn

    engine = RecoveryEngine()
    for t in ("2026-01-01T00:00:00+00:00", "2026-01-01T10:00:00+00:00"):
        engine.decide(
            make_txn(id="x", customer_id="c", created_at=t),
            _diag("pay_x", DiagnosisAction.SEND_REMINDER),
        )
    later = engine.decide(
        make_txn(id="x", customer_id="c", created_at="2026-01-05T00:00:00+00:00"),
        _diag("pay_x", DiagnosisAction.SEND_REMINDER),
    )
    assert not later.blocked


def test_retries_do_not_count_against_contact_cap() -> None:
    from tests.conftest import make_txn

    engine = RecoveryEngine()
    for i in range(5):
        engine.decide(
            make_txn(id=f"r{i}", customer_id="heavy", attempt_number=1),
            _diag(f"pay_r{i}", DiagnosisAction.RETRY_NOW),
        )
    reminder = engine.decide(
        make_txn(id="rf", customer_id="heavy"),
        _diag("pay_rf", DiagnosisAction.SEND_REMINDER),
    )
    assert not reminder.blocked
