"""The recovery policy -- every tunable number in one versioned object.

Caps, conversion priors, channel economics, the holdout fraction, the
incident thresholds: none of these are business logic, they are
*configuration*, and a merchant's risk appetite differs from the next
merchant's. They live here as a frozen, versioned model with defaults
baked in, optionally overridden by a `policy.toml` next to the data
directory. Every decision records the `policy.version` it was made
under, so a policy change is always attributable.
"""

from __future__ import annotations

import tomllib
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from recover_ai.domain.enums import DiagnosisAction

POLICY_FILENAME = "policy.toml"


class ConversionPriors(BaseModel):
    """Prior belief about how often each action converts, before the
    learning loop has seen any real outcomes. Expressed as a mean rate
    plus a pseudo-count (how many observations the prior is 'worth')."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    retry_now: float = 0.45
    retry_later: float = 0.30
    send_reminder: float = 0.20
    request_update: float = 0.15
    prior_strength: float = 40.0  # pseudo-observations; higher = slower to move

    def mean_for(self, action: DiagnosisAction) -> float:
        return float(getattr(self, action.value, 0.0))


class ChannelEconomics(BaseModel):
    """What it costs to reach a customer, and the risk of doing so. All
    values in rupees except the rate, which is a fraction of the amount."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    payment_link: float = 0.0  # a link creation is free
    in_app: float = 0.0
    whatsapp: float = 0.35
    sms: float = 0.18
    email: float = 0.01
    support_contact_cost: float = 22.0  # expected cost if the nudge drives a support ticket
    support_ticket_rate: float = 0.04  # P(a message generates a ticket)
    chargeback_risk_rate: float = 0.0009  # P(chargeback | retry) ...
    chargeback_cost_rate: float = 1.75  # ... costing this multiple of the amount


class IncidentThresholds(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    min_events: int = 6  # don't cry incident on a handful
    share_threshold: float = 0.28  # this fraction of the batch on one (reason, rail)
    window_minutes: int = 45  # concentrated within this span


class Policy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str = "builtin/1"
    contact_cap_per_window: int = 2
    contact_window_hours: int = 48
    holdout_fraction: float = Field(default=0.10, ge=0.0, le=0.5)
    organic_recovery_rate: float = 0.06  # P(customer completes with no nudge) -- control baseline
    min_net_expected_value: float = 1.0  # rupees; act only if NEV clears this
    amount_bands: list[tuple[int, int]] = Field(
        default_factory=lambda: [(0, 999), (1000, 4999), (5000, 11999), (12000, 10**9)]
    )
    conversion_priors: ConversionPriors = Field(default_factory=ConversionPriors)
    channels: ChannelEconomics = Field(default_factory=ChannelEconomics)
    incidents: IncidentThresholds = Field(default_factory=IncidentThresholds)

    # -- derived helpers ------------------------------------------------
    def amount_band(self, amount: Decimal | float | int) -> str:
        """A stable label for the band an amount falls in -- a feature
        key for the learning models."""
        rupees = float(amount)
        for low, high in self.amount_bands:
            if low <= rupees <= high:
                return f"{low}+" if high >= 10**8 else f"{low}-{high}"
        return "unbanded"

    @classmethod
    def load(cls, data_dir: str | Path = "data") -> Policy:
        """Built-in defaults, overlaid with `policy.toml` if one exists."""
        path = Path(data_dir) / POLICY_FILENAME
        if not path.exists():
            return cls()
        raw: dict[str, Any] = tomllib.loads(path.read_text())
        merged = _deep_merge(cls().model_dump(), raw)
        return cls.model_validate(merged)


def _deep_merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out
