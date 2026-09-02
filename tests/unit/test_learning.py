from __future__ import annotations

from recover_ai.domain.enums import DiagnosisAction, FailureReason, PaymentMethod
from recover_ai.domain.policy import Policy
from recover_ai.services.learning import (
    LearningStore,
    conversion_key,
    load_learning,
    save_learning,
)


def _key() -> str:
    return conversion_key(
        DiagnosisAction.RETRY_NOW, PaymentMethod.CARD, FailureReason.NETWORK_ISSUE, "1000-4999"
    )


def test_posterior_starts_at_the_policy_prior() -> None:
    store = LearningStore(Policy())
    assert abs(store.rate(_key()) - 0.45) < 1e-6  # retry_now prior


def test_observations_move_the_posterior_toward_reality() -> None:
    store = LearningStore(Policy())
    key = _key()
    for _ in range(200):
        store.observe_conversion(key, converted=True)
    assert store.rate(key) > 0.6  # moved well above the 0.45 prior
    assert store.observations(key) == 200


def test_credible_interval_tightens_with_data() -> None:
    store = LearningStore(Policy())
    key = _key()
    lo0, hi0 = store.interval(key)
    for i in range(300):
        store.observe_conversion(key, converted=i % 2 == 0)
    lo1, hi1 = store.interval(key)
    assert (hi1 - lo1) < (hi0 - lo0)


def test_brier_score_is_recorded_and_persists(tmp_path) -> None:
    policy = Policy()
    store = LearningStore(policy)
    key = _key()
    for i in range(50):
        store.observe_conversion(key, converted=i % 3 == 0, predicted=0.33)
    assert store.calibration.count == 50
    assert 0.0 <= store.calibration.brier_score <= 1.0

    save_learning(store, tmp_path)
    reloaded = load_learning(policy, tmp_path)
    assert reloaded.calibration.count == 50
    assert abs(reloaded.rate(key) - store.rate(key)) < 1e-9


def test_deliverability_defaults_open_then_learns() -> None:
    store = LearningStore(Policy())
    assert store.deliverable("cust_1", "sms") is True
    store.observe_delivery("cust_1", "sms", delivered=False)
    store.observe_delivery("cust_1", "sms", delivered=False)
    assert store.deliverable("cust_1", "sms") is False


def test_retry_timing_needs_evidence_before_it_overrides() -> None:
    store = LearningStore(Policy())
    assert store.suggested_retry_hours(FailureReason.INSUFFICIENT_FUNDS, 24.0) == 24.0
    for _ in range(5):
        store.observe_retry_landing(FailureReason.INSUFFICIENT_FUNDS, 12.0)
    assert store.suggested_retry_hours(FailureReason.INSUFFICIENT_FUNDS, 24.0) < 20.0
