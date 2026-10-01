from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import employee_data
from app.auth import require_hr
from app.db import get_session
from app.logging_config import logger
from app.models import Employee
from app.schemas import EmployeeCreate, EmployeeRead, NameInput, SlugSuggestion
from app.slug import base_slug

router = APIRouter(prefix="/api/employees", dependencies=[Depends(require_hr)])


@router.get("", response_model=list[EmployeeRead])
def list_employees(session: Session = Depends(get_session)) -> list[Employee]:
    return employee_data.list_employees(session)


@router.post(
    "/slug-suggestion",
    response_model=SlugSuggestion,
)
def suggest_slug(data: NameInput, session: Session = Depends(get_session)) -> SlugSuggestion:
    logger.debug("slug_suggestion_requested")
    try:
        root = base_slug(data.first_name, data.last_name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        candidate = employee_data.find_available_slug(session, root)
    except employee_data.SlugSuggestionExhausted as exc:
        logger.warning("slug_suggestion_exhausted")
        raise HTTPException(
            status_code=409,
            detail={
                "code": "slug_suggestion_exhausted",
                "message": "Не удалось подобрать свободный slug. Измените имя или укажите slug вручную.",
            },
        ) from exc
    return SlugSuggestion(slug=candidate)


@router.post(
    "",
    response_model=EmployeeRead,
    status_code=201,
)
def create_employee(data: EmployeeCreate, session: Session = Depends(get_session)) -> Employee:
    employee = Employee(**data.model_dump())
    employee.email = employee.email.lower()
    try:
        employee_data.save_employee(session, employee)
    except IntegrityError as exc:
        session.rollback()
        field = employee_data.conflict_field(exc)
        if field == "slug":
            logger.warning("employee_create_conflict field=slug")
            raise HTTPException(
                status_code=409,
                detail={"code": "slug_conflict", "message": "Этот slug уже занят"},
            ) from exc
        if field != "email":
            raise
        logger.warning("employee_create_conflict field=email")
        raise HTTPException(
            status_code=409,
            detail={"code": "email_conflict", "message": "Сотрудник с таким email уже существует"},
        ) from exc
    return employee


@router.delete("/{employee_id}", status_code=204)
def delete_employee(employee_id: int, session: Session = Depends(get_session)) -> None:
    employee = employee_data.get_employee(session, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    employee_data.delete_employee(session, employee)
