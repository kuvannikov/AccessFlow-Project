from fastapi import APIRouter, HTTPException, status

from accessflow.core.db import SessionDep
from accessflow.core.security import PrincipalDep
from accessflow.modules.system import service
from accessflow.modules.system.schemas import CurrentUserResponse, StatusResponse

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health() -> StatusResponse:
    """Liveness check: the process is up and can answer requests."""
    return StatusResponse(status="ok")


@router.get("/ready")
def ready(session: SessionDep) -> StatusResponse:
    """Readiness check: the API can reach its database."""
    if not service.database_is_available(session):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE)
    return StatusResponse(status="ok")


@router.get("/me")
def me(principal: PrincipalDep) -> CurrentUserResponse:
    """The signed-in user's name and roles. Any authenticated user may call it."""
    return CurrentUserResponse(display_name=principal.display_name, roles=sorted(principal.roles))
