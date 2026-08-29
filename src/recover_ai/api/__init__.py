"""HTTP layer: FastAPI JSON API + static SPA hosting."""

from recover_ai.api.main import app, create_app

__all__ = ["app", "create_app"]
