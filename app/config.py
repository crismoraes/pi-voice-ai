"""Environment-backed application settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Settings used by the Phase 1 HTTP foundation."""

    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, ge=1, le=65535, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    openai_api_key: SecretStr | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-6-luna", alias="OPENAI_MODEL")
    openai_max_output_tokens: int = Field(
        default=300, ge=16, le=4096, alias="OPENAI_MAX_OUTPUT_TOKENS"
    )
    openai_timeout_seconds: float = Field(
        default=30, ge=1, le=120, alias="OPENAI_TIMEOUT_SECONDS"
    )
    llm_instructions: str = Field(
        default="Responda em português brasileiro, de forma natural e concisa.",
        alias="LLM_INSTRUCTIONS",
    )
    tls_cert_file: Path | None = Field(default=None, alias="TLS_CERT_FILE")
    tls_key_file: Path | None = Field(default=None, alias="TLS_KEY_FILE")
    stt_engine: str = Field(default="sherpa-whisper", alias="STT_ENGINE")
    stt_model_dir: Path = Field(
        default=PROJECT_ROOT / "models" / "sherpa-onnx-whisper-tiny",
        alias="STT_MODEL_DIR",
    )
    stt_language: str = Field(default="pt", alias="STT_LANGUAGE")
    stt_num_threads: int = Field(default=4, ge=1, le=16, alias="STT_NUM_THREADS")
    stt_min_audio_seconds: float = Field(
        default=0.5, ge=0.1, le=5, alias="STT_MIN_AUDIO_SECONDS"
    )
    stt_max_audio_seconds: float = Field(
        default=30, ge=1, le=120, alias="STT_MAX_AUDIO_SECONDS"
    )

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

    @model_validator(mode="after")
    def resolve_stt_model_dir(self) -> "Settings":
        if not self.stt_model_dir.is_absolute():
            self.stt_model_dir = PROJECT_ROOT / self.stt_model_dir
        if self.stt_min_audio_seconds >= self.stt_max_audio_seconds:
            raise ValueError(
                "STT_MIN_AUDIO_SECONDS must be lower than STT_MAX_AUDIO_SECONDS"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Load and cache settings for the current process."""
    return Settings()
