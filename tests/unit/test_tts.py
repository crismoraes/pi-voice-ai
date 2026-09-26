import asyncio
from pathlib import Path

import numpy as np
import pytest

from app.tts.base import SynthesisResult, TextToSpeechUnavailableError
from app.tts.sherpa_piper import SherpaPiperTextToSpeech


def test_synthesis_result_calculates_real_time_factor() -> None:
    result = SynthesisResult(
        samples=np.zeros(22_050, dtype=np.float32),
        sample_rate=22_050,
        processing_seconds=0.25,
    )

    assert result.audio_seconds == 1.0
    assert result.real_time_factor == 0.25


def test_missing_tts_model_is_reported_when_synthesis_is_requested(
    tmp_path: Path,
) -> None:
    service = SherpaPiperTextToSpeech(
        model_dir=tmp_path,
        num_threads=1,
        speed=1.0,
        max_text_characters=100,
    )

    with pytest.raises(TextToSpeechUnavailableError, match="model is incomplete"):
        asyncio.run(service.synthesize("teste"))
