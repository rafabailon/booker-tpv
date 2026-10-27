"""Validated application settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    """Settings sourced from the process environment."""

    model_config = SettingsConfigDict(env_file=None, case_sensitive=False)

    database_url: str = ""
    database_host: str = "db"
    database_port: int = Field(default=5432, ge=1, le=65535)
    database_name: str = "booker_tpv"
    database_user: str = "booker"
    database_password: SecretStr | None = None
    app_secret: SecretStr
    app_env: Literal["production", "development", "test"] = "production"
    app_timezone: str = "Europe/Madrid"
    app_currency: str = "EUR"
    prices_include_tax: bool = True
    cookie_secure: bool = True
    allowed_origin: str = "http://localhost:8080"
    bootstrap_admin_username: str = ""
    bootstrap_admin_password: SecretStr | None = None
    session_max_age_seconds: int = Field(default=28800, ge=60)
    low_stock_threshold: int = Field(default=3, ge=0, le=10000)

    @field_validator("app_secret")
    @classmethod
    def secret_must_be_long(cls, value: SecretStr) -> SecretStr:
        """Reject weak signing secrets before serving requests."""
        if len(value.get_secret_value()) < 32:
            raise ValueError("APP_SECRET debe tener al menos 32 caracteres")
        return value

    @field_validator("allowed_origin")
    @classmethod
    def normalize_origin(cls, value: str) -> str:
        """Store origins without a trailing slash so CORS matches browsers."""
        return value.strip().rstrip("/")

    @field_validator("app_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        """Use the canonical three-letter uppercase currency code."""
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("APP_CURRENCY debe ser un código ISO 4217 de tres letras")
        return normalized

    @model_validator(mode="after")
    def build_database_url(self) -> "Settings":
        """Build an escaped PostgreSQL URL from discrete credentials when needed."""
        if not self.database_url:
            if self.database_password is None:
                raise ValueError("Define DATABASE_URL o DATABASE_PASSWORD")
            self.database_url = URL.create(
                "postgresql+psycopg",
                username=self.database_user,
                password=self.database_password.get_secret_value(),
                host=self.database_host,
                port=self.database_port,
                database=self.database_name,
            ).render_as_string(hide_password=False)
        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached settings for this process."""
    return Settings()