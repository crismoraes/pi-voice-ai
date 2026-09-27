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


def test_quiet_audio_is_normalized_with_a_limited_gain(tmp_path: Path) -> None:
    class FakeStream:
        def __init__(self) -> None:
            self.samples = np.empty(0, dtype=np.float32)
            self.result = type("Result", (), {"text": "teste"})()

        def accept_waveform(self, _: int, samples: np.ndarray) -> None:
            self.samples = samples

    class FakeRecognizer:
        def __init__(self) -> None:
            self.stream = FakeStream()

        def create_stream(self) -> FakeStream:
            return self.stream

        def decode_stream(self, _: FakeStream) -> None:
            return None

    service = SherpaWhisperSpeechToText(
        model_dir=tmp_path,
        language="pt",
        num_threads=1,
        normalize_audio=True,
        target_peak=0.8,
        max_gain=12,
    )
    recognizer = FakeRecognizer()
    service._recognizer = recognizer

    result = asyncio.run(
        service.transcribe(np.array([-0.02, 0.01, 0.02], dtype=np.float32))
    )

    assert result.text == "teste"
    assert np.max(np.abs(recognizer.stream.samples)) == pytest.approx(0.24)
