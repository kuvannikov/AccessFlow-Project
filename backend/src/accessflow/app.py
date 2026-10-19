from fastapi import FastAPI

from accessflow.core.config import Settings
from accessflow.modules.system.router import router as system_router


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application. Without explicit settings they are read from the environment."""
    app = FastAPI(title="AccessFlow API")
    app.state.settings = settings if settings is not None else Settings()
    app.include_router(system_router)
    return app
