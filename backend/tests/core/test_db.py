from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, MetaData, Table, Text

from accessflow.core.db import NAMING_CONVENTION


def test_constraint_names_follow_convention() -> None:
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    Table("teams", metadata, Column("id", Integer, primary_key=True))
    members = Table(
        "members",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("email", Text, unique=True),
        Column("team_id", ForeignKey("teams.id"), index=True),
        CheckConstraint("id > 0", name="id_positive"),
    )

    names = {constraint.name for constraint in members.constraints}
    names |= {index.name for index in members.indexes}

    assert names == {
        "pk_members",
        "uq_members_email",
        "fk_members_team_id_teams",
        "ck_members_id_positive",
        "ix_members_team_id",
    }
