import pytest
from pydantic import ValidationError

from app.schemas import NameInput
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
    assert (
        http.post(
            "/api/employees", json=employee(email="new@example.org"), headers=headers(token)
        ).status_code
        == 409
    )
    assert (
        http.post(
            "/api/employees", json=employee(slug="different.slug"), headers=headers(token)
        ).status_code
        == 409
    )


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
