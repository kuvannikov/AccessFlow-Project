import secrets
import time

from fastapi import Depends, FastAPI, HTTPException
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth import require_hr
from app.db import get_session
from app.logging_config import configure_logging, logger, request_id
from app.models import Employee
from app.schemas import EmployeeCreate, EmployeeRead, NameInput, SlugSuggestion
from app.slug import base_slug

configure_logging()
app = FastAPI(title="AccessFlow API", docs_url=None, redoc_url=None)


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


@app.get("/api/me", dependencies=[Depends(require_hr)])
def me(claims: dict = Depends(require_hr)) -> dict[str, str]:
    return {"name": claims.get("name") or claims.get("preferred_username") or "HR"}


@app.get("/api/employees", response_model=list[EmployeeRead], dependencies=[Depends(require_hr)])
def list_employees(session: Session = Depends(get_session)) -> list[Employee]:
    return list(
        session.scalars(select(Employee).order_by(Employee.created_at.desc(), Employee.id.desc()))
    )


@app.post(
    "/api/employees/slug-suggestion",
    response_model=SlugSuggestion,
    dependencies=[Depends(require_hr)],
)
def suggest_slug(data: NameInput, session: Session = Depends(get_session)) -> SlugSuggestion:
    logger.debug("slug_suggestion_requested")
    try:
        root = base_slug(data.first_name, data.last_name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    candidate = root
    number = 2
    while session.scalar(select(Employee.id).where(Employee.slug == candidate)) is not None:
        candidate = f"{root}-{number}"
        number += 1
    return SlugSuggestion(slug=candidate)


@app.post(
    "/api/employees",
    response_model=EmployeeRead,
    status_code=201,
    dependencies=[Depends(require_hr)],
)
def create_employee(data: EmployeeCreate, session: Session = Depends(get_session)) -> Employee:
    employee = Employee(**data.model_dump())
    employee.email = employee.email.lower()
    session.add(employee)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if session.scalar(select(Employee.id).where(Employee.slug == data.slug)) is not None:
            logger.warning("employee_create_conflict field=slug")
            raise HTTPException(
                status_code=409,
                detail={"code": "slug_conflict", "message": "Этот slug уже занят"},
            ) from exc
        logger.warning("employee_create_conflict field=email")
        raise HTTPException(
            status_code=409,
            detail={"code": "email_conflict", "message": "Сотрудник с таким email уже существует"},
        ) from exc
    session.refresh(employee)
    return employee


@app.delete("/api/employees/{employee_id}", status_code=204, dependencies=[Depends(require_hr)])
def delete_employee(employee_id: int, session: Session = Depends(get_session)) -> None:
    employee = session.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    session.delete(employee)
    session.commit()
