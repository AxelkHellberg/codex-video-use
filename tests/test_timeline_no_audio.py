from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from codex_video_use.timeline import _extract_waveform, render_timeline_image
from codex_video_use.utils import CommandFailure, run


def make_video(path: Path, *, audio: bool) -> None:
    command = ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=10"]
    if audio:
        command += ["-f", "lavfi", "-i", "sine=frequency=880:sample_rate=16000"]
    run(command + ["-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], quiet=True)


def test_timeline_accepts_video_without_audio(tmp_path: Path) -> None:
    source = tmp_path / "silent.mp4"
    make_video(source, audio=False)
    waveform = _extract_waveform(source, 0.0, 0.8, samples=20)
    np.testing.assert_array_equal(waveform, np.zeros(20))
    output = tmp_path / "timeline.png"
    render_timeline_image(source, 0.0, 0.8, output_path=output, frame_count=1)
    with Image.open(output) as image:
        assert image.width >= 1600
        assert image.height == 520


def test_audio_track_still_produces_waveform(tmp_path: Path) -> None:
    source = tmp_path / "audio.mp4"
    make_video(source, audio=True)
    waveform = _extract_waveform(source, 0.0, 0.8, samples=20)
    assert waveform.shape == (20,)
    assert waveform.max() == pytest.approx(1.0)
    assert np.all(waveform > 0)


def test_invalid_media_is_not_treated_as_silent(tmp_path: Path) -> None:
    source = tmp_path / "invalid.mp4"
    source.write_bytes(b"not media")
    with pytest.raises(CommandFailure):
        _extract_waveform(source, 0.0, 0.8)
