from __future__ import annotations

from recover_ai.domain.enums import DiagnosisAction
from recover_ai.services.idempotency import (
    IdempotencyStore,
    execution_key,
    load_idempotency,
    save_idempotency,
)
from recover_ai.services.webhooks import expected_signature, verify_signature


def test_execution_key_is_stable_and_policy_scoped() -> None:
    a = execution_key("pay_1", DiagnosisAction.RETRY_NOW, "builtin/1")
    b = execution_key("pay_1", DiagnosisAction.RETRY_NOW, "builtin/1")
    c = execution_key("pay_1", DiagnosisAction.RETRY_NOW, "builtin/2")
    assert a == b
    assert a != c


def test_idempotency_store_round_trips(tmp_path) -> None:
    store = IdempotencyStore()
    key = execution_key("pay_1", DiagnosisAction.SEND_REMINDER, "builtin/1")
    assert not store.seen(key)
    store.mark(key)
    assert store.seen(key)
    save_idempotency(store, tmp_path)
    assert load_idempotency(tmp_path).seen(key)


def test_webhook_signature_roundtrip() -> None:
    body = b'{"event":"payment_link.paid","payment_link_id":"plink_x"}'
    sig = expected_signature(body, "shh")
    assert verify_signature(body, sig, "shh")
    assert not verify_signature(body, sig, "wrong-secret")
    assert not verify_signature(body, None, "shh")
    assert not verify_signature(b"tampered", sig, "shh")
