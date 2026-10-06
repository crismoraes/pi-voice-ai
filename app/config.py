"""Environment-backed application settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Settings used by the Phase 1 HTTP foundation."""

    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, ge=1, le=65535, alias="APP_PORT")
    app_graceful_shutdown_seconds: float = Field(
        default=5, ge=1, le=30, alias="APP_GRACEFUL_SHUTDOWN_SECONDS"
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    audio_mode: Literal["webrtc", "usb"] = Field(
        default="webrtc", alias="AUDIO_MODE"
    )
    usb_capture_device: str = Field(
        default="plughw:CARD=P10S,DEV=0", alias="USB_CAPTURE_DEVICE", min_length=1
    )
    usb_playback_device: str = Field(
        default="plughw:CARD=P10S,DEV=0", alias="USB_PLAYBACK_DEVICE", min_length=1
    )
    usb_capture_period_frames: int = Field(
        default=512, ge=128, le=4096, alias="USB_CAPTURE_PERIOD_FRAMES"
    )
    usb_capture_retry_seconds: float = Field(
        default=3, ge=0.1, le=60, alias="USB_CAPTURE_RETRY_SECONDS"
    )
    usb_zero_stream_seconds: float = Field(
        default=10, ge=0, le=300, alias="USB_ZERO_STREAM_SECONDS"
    )
    usb_mixer_card: str = Field(
        default="P10S", alias="USB_MIXER_CARD", min_length=1
    )
    usb_playback_volume_percent: int = Field(
        default=75, ge=0, le=100, alias="USB_PLAYBACK_VOLUME_PERCENT"
    )
    usb_capture_volume_percent: int = Field(
        default=100, ge=0, le=100, alias="USB_CAPTURE_VOLUME_PERCENT"
    )
    usb_error_message: str = Field(
        default="Desculpe, não consegui concluir a resposta. Tente novamente.",
        alias="USB_ERROR_MESSAGE",
        min_length=1,
        max_length=300,
    )
    usb_enable_barge_in: bool = Field(default=False, alias="USB_ENABLE_BARGE_IN")
    openai_api_key: SecretStr | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-6-luna", alias="OPENAI_MODEL")
    openai_models: str = Field(default="gpt-6-luna", alias="OPENAI_MODELS")
    openai_max_output_tokens: int = Field(
        default=300, ge=16, le=4096, alias="OPENAI_MAX_OUTPUT_TOKENS"
    )
    openai_timeout_seconds: float = Field(
        default=30, ge=1, le=120, alias="OPENAI_TIMEOUT_SECONDS"
    )
    llm_provider: Literal["openai", "llama.cpp"] = Field(
        default="openai", alias="LLM_PROVIDER"
    )
    llm_selection_path: Path = Field(
        default=PROJECT_ROOT / "data" / "llm-selection.json",
        alias="LLM_SELECTION_PATH",
    )
    assistant_enabled: bool = Field(default=True, alias="ASSISTANT_ENABLED")
    assistant_state_path: Path = Field(
        default=PROJECT_ROOT / "data" / "assistant-state.json",
        alias="ASSISTANT_STATE_PATH",
    )
    voice_pipeline: Literal["chained", "openai-realtime"] = Field(
        default="chained", alias="VOICE_PIPELINE"
    )
    pipeline_selection_path: Path = Field(
        default=PROJECT_ROOT / "data" / "pipeline-selection.json",
        alias="PIPELINE_SELECTION_PATH",
    )
    realtime_model: str = Field(
        default="gpt-realtime-2.1", alias="REALTIME_MODEL"
    )
    realtime_models: str = Field(
        default="gpt-realtime-2.1,gpt-realtime-2.1-mini",
        alias="REALTIME_MODELS",
    )
    realtime_voice: str = Field(default="marin", alias="REALTIME_VOICE")
    realtime_voices: str = Field(
        default="marin,cedar,coral,alloy,ash,ballad,echo,sage,shimmer,verse",
        alias="REALTIME_VOICES",
    )
    realtime_timeout_seconds: float = Field(
        default=45, ge=5, le=180, alias="REALTIME_TIMEOUT_SECONDS"
    )
    realtime_max_output_tokens: int = Field(
        default=2048, ge=64, le=32768, alias="REALTIME_MAX_OUTPUT_TOKENS"
    )
    realtime_text_input_price_per_million: float = Field(
        default=4.00, ge=0, alias="REALTIME_TEXT_INPUT_PRICE_PER_MILLION"
    )
    realtime_text_cached_input_price_per_million: float = Field(
        default=0.40, ge=0, alias="REALTIME_TEXT_CACHED_INPUT_PRICE_PER_MILLION"
    )
    realtime_text_output_price_per_million: float = Field(
        default=24.00, ge=0, alias="REALTIME_TEXT_OUTPUT_PRICE_PER_MILLION"
    )
    realtime_audio_input_price_per_million: float = Field(
        default=32.00, ge=0, alias="REALTIME_AUDIO_INPUT_PRICE_PER_MILLION"
    )
    realtime_audio_cached_input_price_per_million: float = Field(
        default=0.40, ge=0, alias="REALTIME_AUDIO_CACHED_INPUT_PRICE_PER_MILLION"
    )
    realtime_audio_output_price_per_million: float = Field(
        default=64.00, ge=0, alias="REALTIME_AUDIO_OUTPUT_PRICE_PER_MILLION"
    )
    realtime_mini_text_input_price_per_million: float = Field(
        default=0.60, ge=0, alias="REALTIME_MINI_TEXT_INPUT_PRICE_PER_MILLION"
    )
    realtime_mini_text_cached_input_price_per_million: float = Field(
        default=0.06,
        ge=0,
        alias="REALTIME_MINI_TEXT_CACHED_INPUT_PRICE_PER_MILLION",
    )
    realtime_mini_text_output_price_per_million: float = Field(
        default=2.40, ge=0, alias="REALTIME_MINI_TEXT_OUTPUT_PRICE_PER_MILLION"
    )
    realtime_mini_audio_input_price_per_million: float = Field(
        default=10.00, ge=0, alias="REALTIME_MINI_AUDIO_INPUT_PRICE_PER_MILLION"
    )
    realtime_mini_audio_cached_input_price_per_million: float = Field(
        default=0.30,
        ge=0,
        alias="REALTIME_MINI_AUDIO_CACHED_INPUT_PRICE_PER_MILLION",
    )
    realtime_mini_audio_output_price_per_million: float = Field(
        default=20.00, ge=0, alias="REALTIME_MINI_AUDIO_OUTPUT_PRICE_PER_MILLION"
    )
    realtime_pricing_date: str = Field(
        default="2026-10-05", alias="REALTIME_PRICING_DATE"
    )
    local_llm_base_url: str = Field(
        default="http://127.0.0.1:8081/v1", alias="LOCAL_LLM_BASE_URL"
    )
    local_llm_model: str = Field(
        default="qwen3.5-2b-q4_k_m", alias="LOCAL_LLM_MODEL"
    )
    local_llm_models: str = Field(
        default="qwen3.5-2b-q4_k_m", alias="LOCAL_LLM_MODELS"
    )
    local_llm_max_output_tokens: int = Field(
        default=180, ge=16, le=2048, alias="LOCAL_LLM_MAX_OUTPUT_TOKENS"
    )
    local_llm_timeout_seconds: float = Field(
        default=90, ge=1, le=300, alias="LOCAL_LLM_TIMEOUT_SECONDS"
    )
    usage_db_path: Path = Field(
        default=PROJECT_ROOT / "data" / "usage.db", alias="USAGE_DB_PATH"
    )
    usage_pricing_model: str = Field(default="gpt-6-luna", alias="USAGE_PRICING_MODEL")
    usage_input_price_per_million: float = Field(
        default=0.10, ge=0, alias="USAGE_INPUT_PRICE_PER_MILLION"
    )
    usage_cached_input_price_per_million: float = Field(
        default=0.01, ge=0, alias="USAGE_CACHED_INPUT_PRICE_PER_MILLION"
    )
    usage_output_price_per_million: float = Field(
        default=0.50, ge=0, alias="USAGE_OUTPUT_PRICE_PER_MILLION"
    )
    usage_pricing_date: str = Field(default="2026-09-26", alias="USAGE_PRICING_DATE")
    llm_instructions: str = Field(
        default=(
            "Responda em português brasileiro, de forma natural, concisa e sem Markdown."
        ),
        alias="LLM_INSTRUCTIONS",
    )
    prompt_state_path: Path = Field(
        default=PROJECT_ROOT / "data" / "prompt-state.json",
        alias="PROMPT_STATE_PATH",
    )
    prompt_max_characters: int = Field(
        default=8000, ge=100, le=20000, alias="PROMPT_MAX_CHARACTERS"
    )
    tls_cert_file: Path | None = Field(default=None, alias="TLS_CERT_FILE")
    tls_key_file: Path | None = Field(default=None, alias="TLS_KEY_FILE")
    stt_engine: str = Field(default="sherpa-whisper", alias="STT_ENGINE")
    stt_model_dir: Path = Field(
        default=PROJECT_ROOT / "models" / "sherpa-onnx-whisper-small",
        alias="STT_MODEL_DIR",
    )
    stt_small_model_dir: Path = Field(
        default=PROJECT_ROOT / "models" / "sherpa-onnx-whisper-small",
        alias="STT_SMALL_MODEL_DIR",
    )
    stt_tiny_model_dir: Path = Field(
        default=PROJECT_ROOT / "models" / "sherpa-onnx-whisper-tiny",
        alias="STT_TINY_MODEL_DIR",
    )
    stt_selection_path: Path = Field(
        default=PROJECT_ROOT / "data" / "stt-selection.json",
        alias="STT_SELECTION_PATH",
    )
    stt_language: str = Field(default="pt", alias="STT_LANGUAGE")
    stt_num_threads: int = Field(default=3, ge=1, le=16, alias="STT_NUM_THREADS")
    stt_model_precision: Literal["int8", "fp32"] = Field(
        default="int8", alias="STT_MODEL_PRECISION"
    )
    stt_normalize_audio: bool = Field(default=True, alias="STT_NORMALIZE_AUDIO")
    stt_target_peak: float = Field(
        default=0.8, ge=0.1, le=0.95, alias="STT_TARGET_PEAK"
    )
    stt_max_gain: float = Field(default=12, ge=1, le=30, alias="STT_MAX_GAIN")
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
    vad_threshold: float = Field(default=0.4, ge=0.05, le=0.95, alias="VAD_THRESHOLD")
    vad_min_silence_seconds: float = Field(
        default=1.2, ge=0.1, le=5, alias="VAD_MIN_SILENCE_SECONDS"
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
    enable_barge_in: bool = Field(default=True, alias="ENABLE_BARGE_IN")
    tts_engine: str = Field(default="sherpa-piper", alias="TTS_ENGINE")
    tts_model_dir: Path = Field(
        default=PROJECT_ROOT / "models" / "vits-piper-pt_BR-jeff-medium",
        alias="TTS_MODEL_DIR",
    )
    tts_english_model_dir: Path = Field(
        default=PROJECT_ROOT / "models" / "vits-piper-en_US-lessac-medium",
        alias="TTS_ENGLISH_MODEL_DIR",
    )
    tts_spanish_model_dir: Path = Field(
        default=PROJECT_ROOT / "models" / "vits-piper-es_ES-sharvard-medium",
        alias="TTS_SPANISH_MODEL_DIR",
    )
    tts_selection_path: Path = Field(
        default=PROJECT_ROOT / "data" / "tts-selection.json",
        alias="TTS_SELECTION_PATH",
    )
    tts_num_threads: int = Field(default=3, ge=1, le=8, alias="TTS_NUM_THREADS")
    tts_speed: float = Field(default=1.0, ge=0.5, le=2.0, alias="TTS_SPEED")
    tts_max_text_characters: int = Field(
        default=2000, ge=100, le=10000, alias="TTS_MAX_TEXT_CHARACTERS"
    )
    tts_chunk_characters: int = Field(
        default=240, ge=40, le=1000, alias="TTS_CHUNK_CHARACTERS"
    )
    story_library_enabled: bool = Field(default=True, alias="STORY_LIBRARY_ENABLED")
    story_library_root: Path = Field(
        default=PROJECT_ROOT / "data" / "story_library", alias="STORY_LIBRARY_ROOT"
    )
    story_cloud_enabled: bool = Field(default=False, alias="STORY_CLOUD_ENABLED")
    story_local_llm_provider: Literal["llama.cpp"] = Field(
        default="llama.cpp", alias="STORY_LOCAL_LLM_PROVIDER"
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
        if not self.stt_small_model_dir.is_absolute():
            self.stt_small_model_dir = PROJECT_ROOT / self.stt_small_model_dir
        if not self.stt_tiny_model_dir.is_absolute():
            self.stt_tiny_model_dir = PROJECT_ROOT / self.stt_tiny_model_dir
        if not self.stt_selection_path.is_absolute():
            self.stt_selection_path = PROJECT_ROOT / self.stt_selection_path
        if self.stt_min_audio_seconds >= self.stt_max_audio_seconds:
            raise ValueError(
                "STT_MIN_AUDIO_SECONDS must be lower than STT_MAX_AUDIO_SECONDS"
            )
        return self

    @model_validator(mode="after")
    def resolve_usage_db_path(self) -> "Settings":
        if not self.usage_db_path.is_absolute():
            self.usage_db_path = PROJECT_ROOT / self.usage_db_path
        return self

    @property
    def openai_model_options(self) -> tuple[str, ...]:
        return self._model_options(self.openai_models, self.openai_model)

    @property
    def local_llm_model_options(self) -> tuple[str, ...]:
        return self._model_options(self.local_llm_models, self.local_llm_model)

    @property
    def realtime_model_options(self) -> tuple[str, ...]:
        return self._model_options(self.realtime_models, self.realtime_model)

    @property
    def realtime_voice_options(self) -> tuple[str, ...]:
        return self._model_options(self.realtime_voices, self.realtime_voice)

    @staticmethod
    def _model_options(value: str, configured: str) -> tuple[str, ...]:
        models = tuple(
            dict.fromkeys(item.strip() for item in value.split(",") if item.strip())
        )
        return models if configured in models else (configured, *models)

    @model_validator(mode="after")
    def resolve_llm_selection_path(self) -> "Settings":
        if not self.llm_selection_path.is_absolute():
            self.llm_selection_path = PROJECT_ROOT / self.llm_selection_path
        if not self.assistant_state_path.is_absolute():
            self.assistant_state_path = PROJECT_ROOT / self.assistant_state_path
        if not self.pipeline_selection_path.is_absolute():
            self.pipeline_selection_path = PROJECT_ROOT / self.pipeline_selection_path
        if not self.prompt_state_path.is_absolute():
            self.prompt_state_path = PROJECT_ROOT / self.prompt_state_path
        return self

    @model_validator(mode="after")
    def resolve_tts_model_dir(self) -> "Settings":
        if not self.tts_model_dir.is_absolute():
            self.tts_model_dir = PROJECT_ROOT / self.tts_model_dir
        if not self.tts_selection_path.is_absolute():
            self.tts_selection_path = PROJECT_ROOT / self.tts_selection_path
        if not self.tts_english_model_dir.is_absolute():
            self.tts_english_model_dir = PROJECT_ROOT / self.tts_english_model_dir
        if not self.tts_spanish_model_dir.is_absolute():
            self.tts_spanish_model_dir = PROJECT_ROOT / self.tts_spanish_model_dir
        if not self.story_library_root.is_absolute():
            self.story_library_root = PROJECT_ROOT / self.story_library_root
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
