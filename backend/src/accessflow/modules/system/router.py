from fastapi import APIRouter

from accessflow.modules.system.schemas import HealthResponse

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health() -> HealthResponse:
    """Liveness check: the process is up and can answer requests."""
    return HealthResponse(status="ok")
