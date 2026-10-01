import json
from datetime import date

import pytest
from fastapi import HTTPException
from psycopg.errors import CheckViolation, UniqueViolation
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import employee_data
from app.db import Base
from app.models import Employee
from app.routes.employees import create_employee
from app.schemas import EmployeeCreate, NameInput
from app.slug import base_slug


def headers(token):
    return {"Authorization": f"Bearer {token()}"}


def employee(**changes):
    data = {
        "first_name": "Вася",
        "last_name": "Иванов",
        "middle_name": None,
        "email": "vasya@example.org",
        "position": "Разработчик",
        "department": "Разработка",
        "start_date": "2026-10-12",
        "slug": "vasya.ivanov",
    }
    data.update(changes)
    return data


def test_cyrillic_slug_and_repeated_name(client):
    http, token = client
    assert base_slug("Вася", "Иванов") == "vasya.ivanov"
    assert len(base_slug("Щ" * 80, "Щ" * 80)) <= 180
    response = http.post(
        "/api/employees/slug-suggestion",
        json={"first_name": "Вася", "last_name": "Иванов"},
        headers=headers(token),
    )
    assert response.json() == {"slug": "vasya.ivanov"}
    assert http.post("/api/employees", json=employee(), headers=headers(token)).status_code == 201
    response = http.post(
        "/api/employees/slug-suggestion",
        json={"first_name": "Вася", "last_name": "Иванов"},
        headers=headers(token),
    )
    assert response.json() == {"slug": "vasya.ivanov-2"}
    assert (
        http.post(
            "/api/employees",
            json=employee(email="second@example.org", slug="vasya.ivanov-2"),
            headers=headers(token),
        ).status_code
        == 201
    )


def test_slug_suggestion_bounds_queries_for_long_occupied_sequence():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    root = "anna.ivanova"
    employees = [
        Employee(
            first_name="Анна",
            last_name="Иванова",
            email=f"anna{number}@example.org",
            position="HR",
            department="People",
            start_date=date(2026, 10, 1),
            slug=root if number == 1 else f"{root}-{number}",
        )
        for number in range(1, 1001)
    ]
    statements: list[str] = []
    parameter_counts: list[int] = []

    def count_selects(_connection, _cursor, statement, parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)
            parameter_counts.append(len(parameters))

    with Session(engine) as session:
        session.add_all(employees)
        session.commit()
        event.listen(engine, "before_cursor_execute", count_selects)
        try:
            with pytest.raises(employee_data.SlugSuggestionExhausted):
                employee_data.find_available_slug(session, root)
        finally:
            event.remove(engine, "before_cursor_execute", count_selects)
    engine.dispose()

    assert len(statements) == 10
    assert parameter_counts == [100] * 10


def test_slug_suggestion_reports_conflict_when_candidate_range_is_exhausted(client, monkeypatch):
    http, token = client

    def exhausted(_session, _root):
        raise employee_data.SlugSuggestionExhausted

    monkeypatch.setattr(employee_data, "find_available_slug", exhausted)
    response = http.post(
        "/api/employees/slug-suggestion",
        json={"first_name": "Анна", "last_name": "Иванова"},
        headers=headers(token),
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "slug_suggestion_exhausted"


@pytest.mark.parametrize(
    ("first", "last", "expected"),
    [
        ("Вася", "Иванов", "vasya.ivanov"),
        (" ANNA ", "VAN DER BERG", "anna.van-der-berg"),
        ("Аліна", "Коваль", "alina.koval"),
        ("Їжак", "Ґанна", "yizhak.ganna"),
        ("Жан-Поль", "Де Виль", "zhan-pol.de-vil"),
        ("Мар'яна", "Іванова", "mar-yana.ivanova"),
    ],
)
def test_supported_names_keep_their_letters(first, last, expected):
    assert base_slug(first, last) == expected
    assert NameInput(first_name=first, last_name=last)


@pytest.mark.parametrize("first", ["李", "Émile", "Анна!", "Анна.", "---"])
def test_unsupported_or_empty_names_are_rejected(first):
    with pytest.raises(ValueError):
        base_slug(first, "Иванов")
    with pytest.raises(ValidationError):
        NameInput(first_name=first, last_name="Иванов")


def test_create_employee_persists_for_next_request(client):
    http, token = client
    response = http.post(
        "/api/employees", json=employee(middle_name="Петрович"), headers=headers(token)
    )
    assert response.status_code == 201
    assert response.json()["slug"] == "vasya.ivanov"
    rows = http.get("/api/employees", headers=headers(token)).json()
    assert len(rows) == 1
    assert rows[0]["middle_name"] == "Петрович"
    assert rows[0]["email"] == "vasya@example.org"


def test_duplicate_slug_and_email_get_conflict(client):
    http, token = client
    assert http.post("/api/employees", json=employee(), headers=headers(token)).status_code == 201
    slug_conflict = http.post(
        "/api/employees", json=employee(email="new@example.org"), headers=headers(token)
    )
    assert slug_conflict.status_code == 409
    assert slug_conflict.json()["detail"]["code"] == "slug_conflict"
    email_conflict = http.post(
        "/api/employees",
        json=employee(email="VASYA@example.org", slug="different.slug"),
        headers=headers(token),
    )
    assert email_conflict.status_code == 409
    assert email_conflict.json()["detail"]["code"] == "email_conflict"
    assert len(http.get("/api/employees", headers=headers(token)).json()) == 1


def test_creation_conflict_rolls_back_and_leaves_session_usable():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        create_employee(EmployeeCreate(**employee()), session)
        with pytest.raises(HTTPException) as conflict:
            create_employee(EmployeeCreate(**employee(slug="different.slug")), session)
        assert conflict.value.status_code == 409
        assert conflict.value.detail["code"] == "email_conflict"

        created = create_employee(
            EmployeeCreate(**employee(email="another@example.org", slug="another.slug")), session
        )
        assert created.id is not None
        assert {row.email for row in employee_data.list_employees(session)} == {
            "vasya@example.org",
            "another@example.org",
        }
    engine.dispose()


@pytest.mark.parametrize(
    ("database_error", "constraint", "expected_status", "expected_code"),
    [
        (UniqueViolation, "uq_employees_slug", 409, "slug_conflict"),
        (UniqueViolation, "uq_employees_email", 409, "email_conflict"),
        (UniqueViolation, "unknown_unique_constraint", 500, None),
        (CheckViolation, "unknown_check_constraint", 500, None),
        (CheckViolation, "uq_employees_slug", 500, None),
    ],
)
def test_postgres_conflict_uses_failed_constraint_without_racy_lookup(
    client, monkeypatch, database_error, constraint, expected_status, expected_code
):
    http, token = client
    rollbacks: list[Session] = []
    original_rollback = Session.rollback

    def rollback(session):
        rollbacks.append(session)
        original_rollback(session)

    def failed_save(_session, _employee):
        # Psycopg's real diagnostic interface, without connecting to PostgreSQL.
        original = database_error("private-db-error-marker", info={ord("n"): constraint.encode()})
        raise IntegrityError("INSERT employees", {}, original)

    def unexpected_lookup(_session, *_args, **_kwargs):
        pytest.fail("Conflict classification must not query rows after rollback")

    monkeypatch.setattr(Session, "rollback", rollback)
    monkeypatch.setattr(Session, "scalar", unexpected_lookup)
    monkeypatch.setattr(employee_data, "save_employee", failed_save)
    response = http.post("/api/employees", json=employee(), headers=headers(token))

    assert response.status_code == expected_status
    assert len(rollbacks) == 1
    assert "private-db-error-marker" not in response.text
    if expected_code is not None:
        assert response.json()["detail"]["code"] == expected_code
    else:
        assert response.json()["detail"] == "Внутренняя ошибка сервера"


def test_form_validation_and_access_to_creation(client):
    http, token = client
    assert http.post("/api/employees", json=employee()).status_code == 401
    assert (
        http.post(
            "/api/employees",
            json=employee(),
            headers={"Authorization": f"Bearer {token(roles=())}"},
        ).status_code
        == 403
    )
    assert (
        http.post(
            "/api/employees", json=employee(email="wrong-email"), headers=headers(token)
        ).status_code
        == 422
    )
    assert (
        http.post("/api/employees", json=employee(position=" "), headers=headers(token)).status_code
        == 422
    )
    assert (
        http.post("/api/employees", json=employee(slug="Вася"), headers=headers(token)).status_code
        == 422
    )


@pytest.mark.parametrize("field", ["middle_name", "position", "department"])
@pytest.mark.parametrize("invalid_character", ["\x00", "\ud800"])
def test_text_invalid_for_postgresql_is_rejected_before_persistence(
    client, field, invalid_character
):
    http, token = client
    response = http.post(
        "/api/employees",
        content=json.dumps(employee(**{field: f"Text{invalid_character}"})),
        headers={**headers(token), "Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", field]
    assert set(response.json()["detail"][0]) == {"type", "loc", "msg"}
    assert http.get("/api/employees", headers=headers(token)).json() == []


def test_large_json_number_produces_validation_error_without_echoing_input(client):
    http, token = client
    payload = json.dumps(employee(position=float("inf"))).replace("Infinity", "1e999")
    response = http.post(
        "/api/employees",
        content=payload,
        headers={**headers(token), "Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "position"]
    assert set(response.json()["detail"][0]) == {"type", "loc", "msg"}
    assert http.get("/api/employees", headers=headers(token)).json() == []


def test_delete_employee_requires_hr_and_removes_record(client):
    http, token = client
    created = http.post("/api/employees", json=employee(), headers=headers(token))
    employee_id = created.json()["id"]
    path = f"/api/employees/{employee_id}"

    assert http.delete(path).status_code == 401
    assert (
        http.delete(path, headers={"Authorization": f"Bearer {token(roles=())}"}).status_code == 403
    )
    assert len(http.get("/api/employees", headers=headers(token)).json()) == 1
    assert http.delete(path, headers=headers(token)).status_code == 204
    assert http.get("/api/employees", headers=headers(token)).json() == []
    assert http.delete(path, headers=headers(token)).status_code == 404
