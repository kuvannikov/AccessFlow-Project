"""Database operations for employee routes."""

from sqlite3 import IntegrityError as SQLiteIntegrityError

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Employee

MAX_SLUG_CANDIDATES = 1000
SLUG_CANDIDATE_BATCH_SIZE = 100


class SlugSuggestionExhausted(Exception):
    """Raised when no free slug is found within the bounded candidate range."""


def list_employees(session: Session) -> list[Employee]:
    return list(
        session.scalars(select(Employee).order_by(Employee.created_at.desc(), Employee.id.desc()))
    )


def conflict_field(error: IntegrityError) -> str | None:
    constraint_name = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
    if constraint_name is not None:
        if getattr(error.orig, "sqlstate", None) != "23505":
            return None
        return {"uq_employees_slug": "slug", "uq_employees_email": "email"}.get(constraint_name)
    if isinstance(error.orig, SQLiteIntegrityError):
        return {
            "UNIQUE constraint failed: employees.slug": "slug",
            "UNIQUE constraint failed: employees.email": "email",
        }.get(str(error.orig))
    return None


def find_available_slug(session: Session, root: str) -> str:
    for start in range(1, MAX_SLUG_CANDIDATES + 1, SLUG_CANDIDATE_BATCH_SIZE):
        end = min(start + SLUG_CANDIDATE_BATCH_SIZE, MAX_SLUG_CANDIDATES + 1)
        candidates = [root if number == 1 else f"{root}-{number}" for number in range(start, end)]
        occupied = set(session.scalars(select(Employee.slug).where(Employee.slug.in_(candidates))))
        for candidate in candidates:
            if candidate not in occupied:
                return candidate
    raise SlugSuggestionExhausted


def save_employee(session: Session, employee: Employee) -> None:
    session.add(employee)
    session.commit()
    session.refresh(employee)


def get_employee(session: Session, employee_id: int) -> Employee | None:
    return session.get(Employee, employee_id)


def delete_employee(session: Session, employee: Employee) -> None:
    session.delete(employee)
    session.commit()
