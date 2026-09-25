"""Environment-backed application settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Settings used by the Phase 1 HTTP foundation."""

    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, ge=1, le=65535, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    tls_cert_file: Path | None = Field(default=None, alias="TLS_CERT_FILE")
    tls_key_file: Path | None = Field(default=None, alias="TLS_KEY_FILE")

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        env_ignore_empty=True,
    )

    @property
    def tls_enabled(self) -> bool:
        return self.tls_cert_file is not None and self.tls_key_file is not None

    @model_validator(mode="after")
    def validate_tls_pair(self) -> "Settings":
        if (self.tls_cert_file is None) != (self.tls_key_file is None):
            raise ValueError("TLS_CERT_FILE and TLS_KEY_FILE must be set together")
        return self


@lru_cache
def get_settings() -> Settings:
    """Load and cache settings for the current process."""
    return Settings()
