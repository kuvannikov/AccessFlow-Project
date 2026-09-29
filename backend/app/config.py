from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://accessflow:accessflow@localhost:5432/accessflow"
    oidc_issuer: str = "http://localhost:8081/auth/realms/accessflow"
    oidc_jwks_url: str = (
        "http://localhost:8081/auth/realms/accessflow/protocol/openid-connect/certs"
    )
    oidc_audience: str = "accessflow-api"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
