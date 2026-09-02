"""Typed configuration, loaded once from the environment and `.env`.

Only three things ever need to be set, and none are required -- the agent
runs fully without them:

    RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET   live payment links (else simulated)
    ANTHROPIC_API_KEY                       LLM diagnosis + copy (else fallback)

Everything else has a sane default and is only there for tuning.

Placeholder scrubbing: `.env.example` ships with obviously-fake values
(`sk-ant-xxxx...`). If someone copies it without filling every field we
must not hand those to the real SDKs -- a bogus key yields a confusing
401 instead of the clean "no credential -> deterministic fallback"
behaviour. Any credential still matching a placeholder pattern is treated
as unset.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_MARKERS = ("xxxx", "your-", "changeme", "<", "example", "placeholder")


def _is_placeholder(value: str | None) -> bool:
    if not value:
        return True
    low = value.strip().lower()
    return any(marker in low for marker in _PLACEHOLDER_MARKERS)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="",
    )

    # -- the only three that matter (all optional) ----------------------
    razorpay_key_id: SecretStr | None = None
    razorpay_key_secret: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None

    # Razorpay webhook signing secret. When set, `/api/webhooks/razorpay`
    # rejects any request whose HMAC signature does not verify.
    razorpay_webhook_secret: SecretStr | None = None

    # -- tuning (defaults are fine; override via env if you want) -------
    # Claude Haiku 4.5 -- the two LLM calls are tiny (a short JSON decision
    # and a 2-3 sentence message), so the cheapest capable model is the
    # right default: ~$1 / $5 per Mtok, a few hundredths of a cent per run.
    llm_model: str = Field(default="claude-haiku-4-5", alias="RECOVERY_LLM_MODEL")
    live_link_budget: int = Field(
        default=12,
        alias="RAZORPAY_LIVE_LINK_BUDGET",
        description="Genuinely-live Razorpay retry-object creations per run "
        "(payment link, or an order once the test account's 30-link cap is "
        "hit) before labelled simulation takes over.",
    )
    data_dir: str = Field(default="data", alias="RECOVERY_DATA_DIR")
    log_json: bool = Field(default=False, alias="RECOVERY_LOG_JSON")
    log_level: str = Field(default="INFO", alias="RECOVERY_LOG_LEVEL")

    # Extra browser origins allowed to call the API, comma-separated. Only
    # needed when the dashboard is hosted apart from the API (e.g. the SPA
    # on Vercel, this service on Render). The bundled single-service deploy
    # serves the SPA same-origin and needs nothing here.
    cors_origins: str = Field(default="", alias="RECOVERY_CORS_ORIGINS")

    @field_validator(
        "razorpay_key_id",
        "razorpay_key_secret",
        "anthropic_api_key",
        "razorpay_webhook_secret",
        mode="before",
    )
    @classmethod
    def _scrub_placeholder(cls, v: object) -> object:
        if isinstance(v, str) and _is_placeholder(v):
            return None
        return v

    # -- derived --------------------------------------------------------
    @property
    def razorpay_available(self) -> bool:
        return self.razorpay_key_id is not None and self.razorpay_key_secret is not None

    @property
    def anthropic_available(self) -> bool:
        return self.anthropic_api_key is not None

    @property
    def allowed_origins(self) -> list[str]:
        """Local dev origins, plus any set via RECOVERY_CORS_ORIGINS."""
        base = ["http://localhost:5173", "http://127.0.0.1:5173"]
        extra = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return base + extra

    def credential_banner(self) -> str:
        rp = "live" if self.razorpay_available else "simulated (no keys)"
        an = f"live ({self.llm_model})" if self.anthropic_available else "deterministic fallback"
        return f"Razorpay = {rp}   |   Anthropic = {an}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
