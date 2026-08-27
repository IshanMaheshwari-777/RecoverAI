"""Adapters: concrete implementations of the ports, plus the composition root."""

from revenue_recovery.adapters.anthropic_llm import AnthropicLLM
from revenue_recovery.adapters.factory import build_llm, build_payment_gateway
from revenue_recovery.adapters.null_llm import NullLLM
from revenue_recovery.adapters.razorpay_gateway import RazorpayGateway
from revenue_recovery.adapters.simulated_gateway import SimulatedGateway
from revenue_recovery.adapters.synthetic import generate_batch

__all__ = [
    "AnthropicLLM",
    "NullLLM",
    "RazorpayGateway",
    "SimulatedGateway",
    "build_llm",
    "build_payment_gateway",
    "generate_batch",
]
