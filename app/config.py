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
        default=(
            "Responda em português brasileiro, de forma natural, concisa e sem Markdown."
        ),
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
    vad_engine: str = Field(default="sherpa-silero", alias="VAD_ENGINE")
    vad_model_path: Path = Field(
        default=PROJECT_ROOT / "models" / "silero_vad.onnx",
        alias="VAD_MODEL_PATH",
    )
    vad_threshold: float = Field(default=0.5, ge=0.05, le=0.95, alias="VAD_THRESHOLD")
    vad_min_silence_seconds: float = Field(
        default=0.8, ge=0.1, le=5, alias="VAD_MIN_SILENCE_SECONDS"
    )
    vad_min_speech_seconds: float = Field(
        default=0.3, ge=0.1, le=5, alias="VAD_MIN_SPEECH_SECONDS"
    )
    vad_max_speech_seconds: float = Field(
        default=30, ge=1, le=120, alias="VAD_MAX_SPEECH_SECONDS"
    )
    vad_num_threads: int = Field(default=1, ge=1, le=8, alias="VAD_NUM_THREADS")
    conversation_max_turns: int = Field(
        default=6, ge=1, le=20, alias="CONVERSATION_MAX_TURNS"
    )
    tts_engine: str = Field(default="sherpa-piper", alias="TTS_ENGINE")
    tts_model_dir: Path = Field(
        default=PROJECT_ROOT / "models" / "vits-piper-pt_BR-jeff-medium",
        alias="TTS_MODEL_DIR",
    )
    tts_num_threads: int = Field(default=2, ge=1, le=8, alias="TTS_NUM_THREADS")
    tts_speed: float = Field(default=1.0, ge=0.5, le=2.0, alias="TTS_SPEED")
    tts_max_text_characters: int = Field(
        default=2000, ge=100, le=10000, alias="TTS_MAX_TEXT_CHARACTERS"
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

    @model_validator(mode="after")
    def resolve_tts_model_dir(self) -> "Settings":
        if not self.tts_model_dir.is_absolute():
            self.tts_model_dir = PROJECT_ROOT / self.tts_model_dir
        return self

    @model_validator(mode="after")
    def resolve_vad_model_path(self) -> "Settings":
        if not self.vad_model_path.is_absolute():
            self.vad_model_path = PROJECT_ROOT / self.vad_model_path
        if self.vad_min_speech_seconds >= self.vad_max_speech_seconds:
            raise ValueError(
                "VAD_MIN_SPEECH_SECONDS must be lower than VAD_MAX_SPEECH_SECONDS"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Load and cache settings for the current process."""
    return Settings()
