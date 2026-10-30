import anyio
from anyio import to_thread
from fastapi import APIRouter, HTTPException, Request, status

from accessflow.core.security import PrincipalDep
from accessflow.modules.system import service
from accessflow.modules.system.schemas import CurrentUserResponse, StatusResponse

READINESS_TIMEOUT_SECONDS = 3

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health() -> StatusResponse:
    """Liveness check: the process is up and can answer requests."""
    return StatusResponse(status="ok")


@router.get("/ready")
async def ready(request: Request) -> StatusResponse:
    """Readiness check: the API can reach its database within a few seconds.

    The check owns its session and runs in a thread that is abandoned when the
    deadline passes: a database that accepts connections but never answers must
    neither hold the request nor use up the threads that serve other requests.
    """
    try:
        with anyio.fail_after(READINESS_TIMEOUT_SECONDS):
            available = await to_thread.run_sync(
                service.database_is_available,
                request.app.state.session_factory,
                abandon_on_cancel=True,
                limiter=request.app.state.readiness_limiter,
            )
    except TimeoutError:
        available = False
    if not available:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE)
    return StatusResponse(status="ok")


@router.get("/me")
def me(principal: PrincipalDep) -> CurrentUserResponse:
    """The signed-in user's name and roles. Any authenticated user may call it."""
    return CurrentUserResponse(display_name=principal.display_name, roles=sorted(principal.roles))
