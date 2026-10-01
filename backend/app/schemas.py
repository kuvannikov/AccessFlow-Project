from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.slug import slug_part


def clean(value: str) -> str:
    if "\x00" in value:
        raise ValueError("Поле содержит недопустимые символы")
    return " ".join(value.strip().split())


class NameInput(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = clean(value)
        if not value or not any(char.isalpha() for char in value):
            raise ValueError("Укажите имя или фамилию буквами")
        if not slug_part(value):
            raise ValueError("Из имени или фамилии нельзя создать slug")
        return value


class EmployeeCreate(NameInput):
    middle_name: str | None = Field(default=None, max_length=80)
    email: EmailStr
    position: str = Field(min_length=1, max_length=120)
    department: str = Field(min_length=1, max_length=120)
    start_date: date
    slug: str = Field(min_length=3, max_length=180, pattern=r"^[a-z0-9]+(?:[-.][a-z0-9]+)*$")

    @field_validator("middle_name", "position", "department")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = clean(value)
        if not value:
            return None
        return value

    @field_validator("position", "department")
    @classmethod
    def required_text(cls, value: str | None) -> str:
        if not value:
            raise ValueError("Заполните поле")
        return value


class EmployeeRead(EmployeeCreate):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SlugSuggestion(BaseModel):
    slug: str
