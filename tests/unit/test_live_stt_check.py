from pathlib import Path

from scripts import live_stt_check


class FakeContainer:
    duration = 6_625_000

    def __enter__(self) -> "FakeContainer":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_audio_duration_converts_av_time_base_to_seconds(monkeypatch) -> None:
    monkeypatch.setattr(live_stt_check.av, "time_base", 1_000_000)
    monkeypatch.setattr(
        live_stt_check.av,
        "open",
        lambda _path: FakeContainer(),
    )

    assert live_stt_check.audio_duration(Path("sample.wav")) == 6.625
