from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # a fresh store per test, bound to the tmp cwd from _hermetic_env
    import importlib

    from revenue_recovery.api import store as store_mod

    importlib.reload(store_mod)
    from revenue_recovery.api import main as main_mod

    importlib.reload(main_mod)
    return TestClient(main_mod.app)


def test_health(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["razorpay_live"] is False
    assert body["anthropic_live"] is False


def test_report_404_before_any_run(client: TestClient) -> None:
    assert client.get("/api/report").status_code == 404


def test_run_then_report(client: TestClient) -> None:
    run = client.post("/api/runs", json={"count": 90, "seed": 42, "inject_failure": False})
    assert run.status_code == 200
    report = run.json()
    assert report["summary"]["compliance_violations"] == 0
    assert client.get("/api/report").json()["run_id"] == report["run_id"]


def test_webhook_confirms_a_pending_payment(client: TestClient) -> None:
    report = client.post(
        "/api/runs", json={"count": 120, "seed": 42, "inject_failure": False}
    ).json()
    link_id = next(
        r["audit_entry"]["payment_link_id"]
        for r in report["results"]
        if r["audit_entry"]["payment_link_id"]
    )
    before = client.get("/api/report").json()["summary"]["confirmed_recovered"]

    res = client.post(
        "/api/webhooks/razorpay",
        json={"event": "payment_link.paid", "payment_link_id": link_id},
    )
    assert res.status_code == 200

    after = client.get("/api/report").json()["summary"]["confirmed_recovered"]
    assert after > before


def test_webhook_unknown_link_is_404(client: TestClient) -> None:
    client.post("/api/runs", json={"count": 60, "seed": 1, "inject_failure": False})
    res = client.post(
        "/api/webhooks/razorpay",
        json={"event": "payment_link.paid", "payment_link_id": "plink_does_not_exist"},
    )
    assert res.status_code == 404
