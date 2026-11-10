from pathlib import Path
import wave

import numpy as np
import pytest

import codex_video_use.timeline as timeline


@pytest.mark.parametrize("pcm, expected", [
    ([0, 0, 0, 0, 0, 0, 30000], [0, 0, 0, 1]),
    ([10000, -10000], [0, 1, 0, 1]),
    ([0] * 7, [0, 0, 0, 0]),
    ([], [0, 0, 0, 0]),
])
def test_waveform_covers_the_full_audio_interval(monkeypatch, pcm: list[int], expected: list[int]) -> None:
    def extract(command: list[str], **kwargs: object) -> None:
        with wave.open(str(Path(command[-1])), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(np.asarray(pcm, dtype=np.int16).tobytes())

    monkeypatch.setattr(timeline, "run", extract)
    actual = timeline._extract_waveform(Path("clip.mp4"), 0, 1, samples=4)

    np.testing.assert_allclose(actual, expected)
