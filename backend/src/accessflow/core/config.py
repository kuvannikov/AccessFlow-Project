from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database connection settings, read from environment variables.

    Every variable has the ACCESSFLOW_ prefix. A missing, empty or invalid value
    stops the application at startup.
    """

    # Validation errors would otherwise echo every value read, including the password.
    # An empty value is rejected rather than dropped: libpq would fall back to its own
    # defaults and PG* variables and connect somewhere else.
    model_config = SettingsConfigDict(
        env_prefix="ACCESSFLOW_", frozen=True, hide_input_in_errors=True
    )

    database_host: str = Field(min_length=1)
    database_port: int = Field(default=5432, ge=1, le=65535)
    database_name: str = Field(min_length=1)
    database_user: str = Field(min_length=1)
    database_password: SecretStr = Field(min_length=1)


class Settings(DatabaseSettings):
    # Compared with the "iss" claim character for character, so it is not
    # normalized as a URL.
    auth_issuer: str = Field(min_length=1)
    auth_audience: str = Field(default="accessflow-api", min_length=1)
    auth_jwks_url: HttpUrl
