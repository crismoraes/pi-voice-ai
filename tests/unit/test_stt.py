import asyncio
from pathlib import Path

import numpy as np
import pytest

from app.stt.base import SpeechToTextUnavailableError, TranscriptionResult
from app.stt.sherpa_whisper import SherpaWhisperSpeechToText


def test_transcription_result_calculates_real_time_factor() -> None:
    result = TranscriptionResult(
        text="olá",
        audio_seconds=2.0,
        processing_seconds=0.5,
    )

    assert result.real_time_factor == 0.25


def test_missing_model_is_reported_only_when_transcription_is_requested(
    tmp_path: Path,
) -> None:
    service = SherpaWhisperSpeechToText(
        model_dir=tmp_path,
        language="pt",
        num_threads=1,
    )

    with pytest.raises(SpeechToTextUnavailableError, match="model is incomplete"):
        asyncio.run(service.transcribe(np.zeros(16_000, dtype=np.float32)))
