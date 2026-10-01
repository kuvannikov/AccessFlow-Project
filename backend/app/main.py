import secrets
import time

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth import require_hr
from app.db import get_session
from app.logging_config import configure_logging, logger, request_id
from app.routes.employees import router as employees_router

configure_logging()
app = FastAPI(title="AccessFlow API", docs_url=None, redoc_url=None)
app.include_router(employees_router)


@app.exception_handler(RequestValidationError)
async def invalid_request(_request: Request, exc: RequestValidationError) -> JSONResponse:
    # Raw inputs may contain invalid Unicode or non-finite numbers, which cannot
    # be rendered as JSON. Keep field diagnostics without echoing submitted data.
    details = [{key: error[key] for key in ("type", "loc", "msg")} for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": details})


@app.middleware("http")
async def log_request(request: Request, call_next):
    identifier = secrets.token_hex(12)
    token = request_id.set(identifier)
    started = time.monotonic()
    try:
        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001 - final API boundary for safe client responses
            logger.error("unhandled_request_error", exc_info=True)
            response = JSONResponse(
                status_code=500,
                content={"detail": "Внутренняя ошибка сервера", "request_id": identifier},
            )
        response.headers["X-Request-ID"] = identifier
        route = request.scope.get("route")
        route_name = route.path if route is not None else "<unmatched>"
        logger.info(
            "request method=%s route=%s status=%s duration_ms=%.1f",
            request.method,
            route_name,
            response.status_code,
            (time.monotonic() - started) * 1000,
        )
        return response
    finally:
        request_id.reset(token)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/api/ready")
def ready(session: Session = Depends(get_session)) -> JSONResponse:
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.warning("database_unavailable")
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return JSONResponse(content={"status": "ready"})


@app.get("/api/me")
def me(claims: dict = Depends(require_hr)) -> dict[str, str]:
    return {"name": claims.get("name") or claims.get("preferred_username") or "HR"}
