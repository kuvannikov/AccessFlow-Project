from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from anyio import CapacityLimiter
from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker

from accessflow.core.config import Settings
from accessflow.core.db import create_database_engine
from accessflow.core.errors import install_error_handlers
from accessflow.core.logging import configure_logging
from accessflow.core.middleware import RequestMiddleware
from accessflow.core.security import (
    PROVIDER_UNAVAILABLE,
    IdentityProviderUnavailableError,
    create_token_verifier,
)
from accessflow.modules.system.router import router as system_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    app.state.engine.dispose()


# Probes that hang on an unresponsive database may keep this many threads busy.
READINESS_THREADS = 2


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application. Without explicit settings they are read from the environment."""
    settings = settings if settings is not None else Settings()
    engine = create_database_engine(settings)
    app = FastAPI(title="AccessFlow API", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = sessionmaker(engine)
    app.state.readiness_limiter = CapacityLimiter(READINESS_THREADS)
    app.state.token_verifier = create_token_verifier(settings)
    configure_logging()
    install_error_handlers(app)
    app.state.error_registry.register(IdentityProviderUnavailableError, PROVIDER_UNAVAILABLE)
    app.add_middleware(RequestMiddleware)
    app.include_router(system_router)
    return app
