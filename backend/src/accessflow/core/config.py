from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read from environment variables.

    Every variable has the ACCESSFLOW_ prefix. A missing or invalid value
    stops the application at startup.
    """

    model_config = SettingsConfigDict(env_prefix="ACCESSFLOW_", frozen=True)

    environment: Literal["development", "test", "production"]
