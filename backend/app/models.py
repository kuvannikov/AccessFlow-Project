from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80), index=True)
    middle_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    position: Mapped[str] = mapped_column(String(120))
    department: Mapped[str] = mapped_column(String(120))
    start_date: Mapped[date] = mapped_column(Date)
    slug: Mapped[str] = mapped_column(String(180), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
