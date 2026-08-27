"""HTTP layer: FastAPI JSON API + static SPA hosting."""

from revenue_recovery.api.main import app, create_app

__all__ = ["app", "create_app"]
