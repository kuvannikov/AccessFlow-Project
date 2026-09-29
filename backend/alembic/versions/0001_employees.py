"""Create employees table.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "employees",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("first_name", sa.String(80), nullable=False),
        sa.Column("last_name", sa.String(80), nullable=False),
        sa.Column("middle_name", sa.String(80), nullable=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("position", sa.String(120), nullable=False),
        sa.Column("department", sa.String(120), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("slug", sa.String(180), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("email", name="uq_employees_email"),
        sa.UniqueConstraint("slug", name="uq_employees_slug"),
    )
    op.create_index("ix_employees_last_name", "employees", ["last_name"])


def downgrade() -> None:
    op.drop_index("ix_employees_last_name", table_name="employees")
    op.drop_table("employees")
