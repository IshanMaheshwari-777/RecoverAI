"""Adapters: concrete implementations of the ports, plus the composition root."""

from recover_ai.adapters.anthropic_llm import AnthropicLLM
from recover_ai.adapters.factory import build_llm, build_payment_gateway
from recover_ai.adapters.null_llm import NullLLM
from recover_ai.adapters.razorpay_gateway import RazorpayGateway
from recover_ai.adapters.simulated_gateway import SimulatedGateway
from recover_ai.adapters.synthetic import generate_batch

__all__ = [
    "AnthropicLLM",
    "NullLLM",
    "RazorpayGateway",
    "SimulatedGateway",
    "build_llm",
    "build_payment_gateway",
    "generate_batch",
]
