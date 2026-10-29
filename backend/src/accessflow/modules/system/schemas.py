from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class StatusResponse(BaseModel):
    status: Literal["ok"]


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, validate_by_name=True)

    display_name: str
    roles: list[str]
