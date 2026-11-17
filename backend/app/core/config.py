"""Read deployment configuration without embedding credentials."""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Define configuration shared by the API and seed process."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    mongodb_uri: str = "mongodb://localhost:27017/?replicaSet=rs0"
    mongodb_db: str = "ketsip"
    jwt_secret: str = Field(min_length=32)
    jwt_minutes: int = Field(default=480, ge=1, le=1440)
    cors_origins: str = "http://localhost:5173"
    seed_on_startup: bool = True
    bootstrap_password: str = ""

    @field_validator("jwt_secret")
    @classmethod
    def validate_secret(cls, value: str) -> str:
        """Reject example secrets and weak signing keys."""
        if "replace" in value.lower() or "change" in value.lower():
            raise ValueError("JWT_SECRET must be a private random secret")
        return value
