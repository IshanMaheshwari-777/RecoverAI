"""The learning loop: turn real recovery outcomes into better predictions.

Nothing here calls an LLM or an API. It is bookkeeping -- Beta-Bernoulli
posteriors over "did this kind of action convert", updated one webhook at
a time, persisted as plain counts.

    ConversionModel   P(recover | action, method, reason, amount band)
    RetryTimingModel  how many hours after a failure a retry actually lands
    Calibration       predicted vs. observed, with a Brier score

In the batch demo there is no real customer to convert, so predictions
still drive a seeded projection -- but the *rates* they use are the
learned posteriors, not hard-coded constants, and every webhook
confirmation (or its N-day absence) moves them.
"""

from __future__ import annotations

import contextlib
import json
import math
import threading
from dataclasses import dataclass, field
from pathlib import Path

from recover_ai.domain.enums import DiagnosisAction, FailureReason, PaymentMethod
from recover_ai.domain.policy import Policy

LEARNING_FILENAME = "learning_state.json"


def conversion_key(
    action: DiagnosisAction,
    method: PaymentMethod,
    reason: FailureReason | None,
    amount_band: str,
) -> str:
    return f"{action.value}|{method.value}|{(reason or FailureReason.UNKNOWN).value}|{amount_band}"


@dataclass(slots=True)
class _Beta:
    alpha: float
    beta: float

    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    @property
    def n(self) -> float:
        return self.alpha + self.beta

    def interval(self) -> tuple[float, float]:
        """A normal approximation to the 95% credible interval -- good
        enough for a dashboard, and it never needs scipy."""
        m, total = self.mean, self.alpha + self.beta
        sd = math.sqrt(m * (1 - m) / (total + 1))
        return (max(0.0, m - 1.96 * sd), min(1.0, m + 1.96 * sd))


@dataclass(slots=True)
class Calibration:
    """Reliability of the predictions: bucket the predicted probability,
    compare to the observed conversion rate in that bucket."""

    brier_sum: float = 0.0
    count: int = 0
    buckets: dict[str, list[float]] = field(default_factory=dict)  # label -> [pred_sum, hits, n]

    def record(self, predicted: float, converted: bool) -> None:
        self.brier_sum += (predicted - (1.0 if converted else 0.0)) ** 2
        self.count += 1
        lo = int(min(predicted, 0.999) * 10) * 10
        label = f"{lo}-{lo + 10}%"
        slot = self.buckets.setdefault(label, [0.0, 0.0, 0.0])
        slot[0] += predicted
        slot[1] += 1.0 if converted else 0.0
        slot[2] += 1.0

    @property
    def brier_score(self) -> float:
        return self.brier_sum / self.count if self.count else 0.0

    def table(self) -> list[dict[str, float | str]]:
        rows: list[dict[str, float | str]] = []
        for label, (psum, hits, n) in sorted(self.buckets.items()):
            rows.append(
                {
                    "bucket": label,
                    "predicted": round(psum / n, 4) if n else 0.0,
                    "observed": round(hits / n, 4) if n else 0.0,
                    "n": int(n),
                }
            )
        return rows


class LearningStore:
    """All the learned state, persisted together as counts."""

    def __init__(self, policy: Policy) -> None:
        self._policy = policy
        self._lock = threading.Lock()
        self._conv: dict[str, _Beta] = {}
        self._timing: dict[str, list[float]] = {}  # reason -> [ewma_hours, weight]
        self._deliver: dict[str, list[float]] = {}  # "cust|channel" -> [ok, n]
        self.calibration = Calibration()

    # -- conversion ----------------------------------------------------
    def _prior(self, action: DiagnosisAction) -> _Beta:
        strength = self._policy.conversion_priors.prior_strength
        mean = self._policy.conversion_priors.mean_for(action)
        return _Beta(alpha=max(mean * strength, 1e-3), beta=max((1 - mean) * strength, 1e-3))

    def _bucket(self, key: str) -> _Beta:
        if key not in self._conv:
            action = DiagnosisAction(key.split("|", 1)[0])
            self._conv[key] = self._prior(action)
        return self._conv[key]

    def rate(self, key: str) -> float:
        with self._lock:
            return self._bucket(key).mean

    def interval(self, key: str) -> tuple[float, float]:
        with self._lock:
            return self._bucket(key).interval()

    def observations(self, key: str) -> int:
        with self._lock:
            b = self._bucket(key)
            prior_n = self._prior(DiagnosisAction(key.split("|", 1)[0])).n
            return round(b.n - prior_n)

    def observe_conversion(
        self, key: str, *, converted: bool, predicted: float | None = None
    ) -> None:
        with self._lock:
            b = self._bucket(key)
            if converted:
                b.alpha += 1.0
            else:
                b.beta += 1.0
            if predicted is not None:
                self.calibration.record(predicted, converted)

    # -- retry timing ------------------------------------------------
    def suggested_retry_hours(self, reason: FailureReason | None, fallback_hours: float) -> float:
        key = (reason or FailureReason.UNKNOWN).value
        with self._lock:
            slot = self._timing.get(key)
            if slot is None or slot[1] < 3:  # too few real observations to trust
                return fallback_hours
            return slot[0]

    def observe_retry_landing(self, reason: FailureReason | None, hours: float) -> None:
        key = (reason or FailureReason.UNKNOWN).value
        with self._lock:
            slot = self._timing.setdefault(key, [hours, 0.0])
            weight = min(slot[1], 20.0)
            slot[0] = (slot[0] * weight + hours) / (weight + 1)
            slot[1] += 1

    # -- deliverability --------------------------------------------
    def deliverable(self, customer_id: str, channel: str) -> bool:
        with self._lock:
            slot = self._deliver.get(f"{customer_id}|{channel}")
            if slot is None or slot[1] < 2:
                return True  # no bad history -> assume fine
            return slot[0] / slot[1] >= 0.5

    def observe_delivery(self, customer_id: str, channel: str, *, delivered: bool) -> None:
        with self._lock:
            slot = self._deliver.setdefault(f"{customer_id}|{channel}", [0.0, 0.0])
            slot[0] += 1.0 if delivered else 0.0
            slot[1] += 1.0

    # -- persistence ----------------------------------------------
    def to_dict(self) -> dict[str, object]:
        with self._lock:
            return {
                "policy_version": self._policy.version,
                "conversion": {k: [v.alpha, v.beta] for k, v in self._conv.items()},
                "timing": self._timing,
                "deliverability": self._deliver,
                "calibration": {
                    "brier_sum": self.calibration.brier_sum,
                    "count": self.calibration.count,
                    "buckets": self.calibration.buckets,
                },
            }

    def load_dict(self, raw: dict[str, object]) -> None:
        with self._lock:
            conv = raw.get("conversion", {})
            if isinstance(conv, dict):
                self._conv = {
                    str(k): _Beta(alpha=float(v[0]), beta=float(v[1])) for k, v in conv.items()
                }
            timing = raw.get("timing", {})
            if isinstance(timing, dict):
                self._timing = {str(k): [float(x) for x in v] for k, v in timing.items()}
            deliver = raw.get("deliverability", {})
            if isinstance(deliver, dict):
                self._deliver = {str(k): [float(x) for x in v] for k, v in deliver.items()}
            cal = raw.get("calibration", {})
            if isinstance(cal, dict):
                self.calibration = Calibration(
                    brier_sum=float(cal.get("brier_sum", 0.0)),
                    count=int(cal.get("count", 0)),
                    buckets={
                        str(k): [float(x) for x in v]
                        for k, v in dict(cal.get("buckets", {})).items()
                    },
                )

    def summary(self) -> dict[str, object]:
        """Compact view for the API/dashboard."""
        with self._lock:
            rows = []
            for key, b in sorted(self._conv.items(), key=lambda kv: -kv[1].n):
                action, method, reason, band = key.split("|")
                lo, hi = b.interval()
                rows.append(
                    {
                        "action": action,
                        "method": method,
                        "reason": reason,
                        "amount_band": band,
                        "rate": round(b.mean, 4),
                        "ci_low": round(lo, 4),
                        "ci_high": round(hi, 4),
                        "observations": round(b.n - self._prior(DiagnosisAction(action)).n),
                    }
                )
            return {
                "policy_version": self._policy.version,
                "conversion_rates": rows,
                "brier_score": round(self.calibration.brier_score, 4),
                "calibration_table": self.calibration.table(),
                "observations": self.calibration.count,
                "retry_timing_hours": {
                    k: round(v[0], 1) for k, v in self._timing.items() if v[1] >= 3
                },
            }


def learning_path(data_dir: str | Path) -> Path:
    return Path(data_dir) / LEARNING_FILENAME


def load_learning(policy: Policy, data_dir: str | Path) -> LearningStore:
    store = LearningStore(policy)
    path = learning_path(data_dir)
    if path.exists():
        with contextlib.suppress(json.JSONDecodeError, KeyError, ValueError, TypeError):
            store.load_dict(json.loads(path.read_text()))
    return store


def save_learning(store: LearningStore, data_dir: str | Path) -> Path:
    path = learning_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store.to_dict(), indent=2))
    return path
