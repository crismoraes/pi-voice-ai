import asyncio
from pathlib import Path

import numpy as np
import pytest

from app.conversation.manager import ConversationManager
from app.llm.base import ConversationMessage, LanguageModel
from app.stt.base import SpeechToText, TranscriptionResult
from app.tts.base import SynthesisResult, TextToSpeech
from app.vad.base import VoiceActivityDetectionUnavailableError
from app.vad.sherpa_silero import SherpaSileroVoiceActivityDetector


class FakeSpeechToText(SpeechToText):
    def __init__(self) -> None:
        self.calls = 0

    async def transcribe(self, samples: np.ndarray) -> TranscriptionResult:
        self.calls += 1
        return TranscriptionResult(
            text="Meu nome é Ana." if self.calls == 1 else "Qual é o meu nome?",
            audio_seconds=len(samples) / self.sample_rate,
            processing_seconds=0.1,
        )


class ContextAwareLanguageModel(LanguageModel):
    model = "context-test"

    def __init__(self) -> None:
        self.histories: list[tuple[ConversationMessage, ...]] = []

    async def stream_response(
        self,
        text: str,
        *,
        history: tuple[ConversationMessage, ...] = (),
    ):
        self.histories.append(history)
        yield "Olá, Ana." if not history else "Seu nome é Ana."


class FakeTextToSpeech(TextToSpeech):
    async def synthesize(self, text: str) -> SynthesisResult:
        return SynthesisResult(
            samples=np.ones(8_000, dtype=np.float32) * 0.1,
            sample_rate=16_000,
            processing_seconds=0.05,
        )


async def run_two_turns() -> tuple[list[tuple[str, dict[str, object]]], ContextAwareLanguageModel]:
    model = ContextAwareLanguageModel()
    manager = ConversationManager(
        speech_to_text=FakeSpeechToText(),
        language_model=model,
        text_to_speech=FakeTextToSpeech(),
        max_turns=2,
    )
    events: list[tuple[str, dict[str, object]]] = []

    async def emit(event: str, payload: dict[str, object]) -> None:
        events.append((event, payload))

    samples = np.zeros(16_000, dtype=np.float32)
    first = await manager.process("peer", samples, emit)
    second = await manager.process("peer", samples, emit)
    assert first is not None and first.response_text == "Olá, Ana."
    assert second is not None and second.response_text == "Seu nome é Ana."
    return events, model


def test_conversation_pipeline_streams_events_and_keeps_context() -> None:
    events, model = asyncio.run(run_two_turns())

    assert model.histories[0] == ()
    assert model.histories[1] == (
        ConversationMessage(role="user", content="Meu nome é Ana."),
        ConversationMessage(role="assistant", content="Olá, Ana."),
    )
    assert [event for event, _ in events].count("transcript") == 2
    assert [event for event, _ in events].count("assistant_delta") == 2
    assert [event for event, _ in events].count("tts_done") == 2


def test_missing_vad_model_is_reported(tmp_path: Path) -> None:
    with pytest.raises(VoiceActivityDetectionUnavailableError, match="VAD model"):
        SherpaSileroVoiceActivityDetector(
            model_path=tmp_path / "silero_vad.onnx",
            threshold=0.5,
            min_silence_seconds=0.8,
            min_speech_seconds=0.3,
            max_speech_seconds=30,
            num_threads=1,
        )
