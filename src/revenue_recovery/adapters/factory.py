"""Build concrete ports from Settings -- the composition root."""

from __future__ import annotations

from revenue_recovery.adapters.anthropic_llm import AnthropicLLM
from revenue_recovery.adapters.null_llm import NullLLM
from revenue_recovery.adapters.razorpay_gateway import RazorpayGateway
from revenue_recovery.adapters.simulated_gateway import SimulatedGateway
from revenue_recovery.config import Settings
from revenue_recovery.ports.llm import LLMPort
from revenue_recovery.ports.payments import PaymentGatewayPort


def build_llm(settings: Settings) -> LLMPort:
    if settings.anthropic_available and settings.anthropic_api_key is not None:
        return AnthropicLLM(
            api_key=settings.anthropic_api_key.get_secret_value(),
            model=settings.llm_model,
        )
    return NullLLM()


def build_payment_gateway(settings: Settings) -> PaymentGatewayPort:
    if (
        settings.razorpay_available
        and settings.razorpay_key_id is not None
        and settings.razorpay_key_secret is not None
    ):
        return RazorpayGateway(
            key_id=settings.razorpay_key_id.get_secret_value(),
            key_secret=settings.razorpay_key_secret.get_secret_value(),
            live_link_budget=settings.live_link_budget,
        )
    return SimulatedGateway()
