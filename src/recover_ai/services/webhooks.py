"""Razorpay webhook signature verification.

Razorpay signs every webhook with HMAC-SHA256 over the raw request body,
using the endpoint's configured secret, and sends it as the
`X-Razorpay-Signature` header. An endpoint that acts on an unverified
body will happily mark a payment 'paid' for anyone who can POST to it.
"""

from __future__ import annotations

import hashlib
import hmac


def expected_signature(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def verify_signature(body: bytes, signature: str | None, secret: str) -> bool:
    if not signature:
        return False
    return hmac.compare_digest(expected_signature(body, secret), signature)
