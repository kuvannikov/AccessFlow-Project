from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read from environment variables.

    Every variable has the ACCESSFLOW_ prefix. A missing or invalid value
    stops the application at startup.
    """

    # Validation errors would otherwise echo every value read, including the password.
    model_config = SettingsConfigDict(
        env_prefix="ACCESSFLOW_", frozen=True, hide_input_in_errors=True
    )

    environment: Literal["development", "test", "production"]
    database_host: str
    database_port: int = Field(default=5432, ge=1, le=65535)
    database_name: str
    database_user: str
    database_password: SecretStr
