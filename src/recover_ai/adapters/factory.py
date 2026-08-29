"""Build concrete ports from Settings -- the composition root."""

from __future__ import annotations

from recover_ai.adapters.anthropic_llm import AnthropicLLM
from recover_ai.adapters.null_llm import NullLLM
from recover_ai.adapters.razorpay_gateway import RazorpayGateway
from recover_ai.adapters.simulated_gateway import SimulatedGateway
from recover_ai.config import Settings
from recover_ai.ports.llm import LLMPort
from recover_ai.ports.payments import PaymentGatewayPort


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
