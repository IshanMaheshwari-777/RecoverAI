"""FastAPI application: JSON API for the dashboard SPA.

GET  /api/health
GET  /api/report                 -> the current PipelineReport
POST /api/runs                    -> run a fresh pipeline, return the report
POST /api/webhooks/razorpay       -> apply a payment_link.paid confirmation
GET  /                            -> the built SPA (api/static)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from recover_ai import __version__
from recover_ai.api.store import store
from recover_ai.config import get_settings
from recover_ai.domain.results import PipelineReport
from recover_ai.logging import configure
from recover_ai.services.webhooks import verify_signature

_STATIC_DIR = Path(__file__).parent / "static"


class RunRequest(BaseModel):
    count: int = Field(default=180, ge=1, le=2000)
    seed: int = Field(default=42, ge=0)
    inject_failure: bool = False
    mode: Literal["live", "shadow"] = "live"


class RazorpayWebhook(BaseModel):
    """The slice of Razorpay's webhook body we act on."""

    event: Literal["payment_link.paid"]
    payment_link_id: str


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    razorpay_live: bool
    anthropic_live: bool
    webhook_verified: bool


def create_app() -> FastAPI:
    settings = get_settings()
    configure(json_logs=settings.log_json, level=settings.log_level)

    app = FastAPI(
        title="Recover AI",
        version=__version__,
        summary="Diagnose failed Razorpay payments and drive compliant recovery.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health", response_model=HealthResponse, tags=["meta"])
    def health() -> HealthResponse:
        s = get_settings()
        return HealthResponse(
            status="ok",
            version=__version__,
            razorpay_live=s.razorpay_available,
            anthropic_live=s.anthropic_available,
            webhook_verified=s.razorpay_webhook_secret is not None,
        )

    @app.get("/api/report", response_model=PipelineReport, tags=["report"])
    def get_report() -> PipelineReport:
        if store.report is None:
            raise HTTPException(404, "No pipeline run yet -- POST /api/runs first.")
        return store.report

    @app.get("/api/learning", tags=["report"])
    def get_learning() -> dict[str, object]:
        if store.report is None or store.report.learning is None:
            raise HTTPException(404, "No learning state yet.")
        return store.report.learning

    @app.post("/api/runs", response_model=PipelineReport, tags=["report"])
    def create_run(body: RunRequest) -> PipelineReport:
        return store.run(
            count=body.count,
            seed=body.seed,
            inject_failure=body.inject_failure,
            mode=body.mode,
        )

    @app.post("/api/webhooks/razorpay", tags=["webhooks"])
    async def razorpay_webhook(request: Request) -> dict[str, str]:
        raw = await request.body()
        secret = get_settings().razorpay_webhook_secret
        if secret is not None:
            sig = request.headers.get("x-razorpay-signature")
            if not verify_signature(raw, sig, secret.get_secret_value()):
                raise HTTPException(401, "Invalid or missing webhook signature.")
        try:
            body = RazorpayWebhook.model_validate(json.loads(raw))
        except (ValidationError, json.JSONDecodeError) as exc:
            raise HTTPException(422, f"Unprocessable webhook body: {exc}") from exc

        result = store.confirm_payment(body.payment_link_id)
        if result is None:
            raise HTTPException(404, f"No pending action for link {body.payment_link_id}")
        return {"status": "confirmed", "transaction_id": result.transaction_id}

    if _STATIC_DIR.exists():
        app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="spa")

    return app


app = create_app()
