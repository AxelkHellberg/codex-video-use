from pathlib import Path
import shutil
import subprocess

import pytest

from codex_video_use.rendering import _has_subtitles_filter, composite_output
from codex_video_use.utils import ffprobe_json


def ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True, capture_output=True)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")
@pytest.mark.parametrize("with_audio", [False, True])
@pytest.mark.parametrize("composition", ["subtitles", "overlay"])
def test_composition_preserves_available_base_streams(tmp_path: Path, with_audio: bool, composition: str) -> None:
    if composition == "subtitles" and not _has_subtitles_filter():
        pytest.skip("ffmpeg subtitles filter is required")
    base = tmp_path / "base.mp4"
    args = ["-f", "lavfi", "-i", "color=black:s=160x90:r=10:d=0.5"]
    if with_audio:
        args += ["-f", "lavfi", "-i", "sine=frequency=440:duration=0.5", "-shortest", "-c:a", "aac"]
    ffmpeg(*args, "-c:v", "libx264", str(base))
    subtitles = None
    overlays = []
    if composition == "subtitles":
        subtitles = tmp_path / "caption.srt"
        subtitles.write_text("1\n00:00:00,000 --> 00:00:00,500\nHELLO\n", encoding="utf-8")
    else:
        overlay = tmp_path / "overlay.mp4"
        ffmpeg("-f", "lavfi", "-i", "color=red:s=160x90:r=10:d=0.5", "-c:v", "libx264", str(overlay))
        overlays = [{"file": str(overlay), "start": 0, "duration": 0.5}]
    output = tmp_path / "output.mp4"
    composite_output(base, overlays=overlays, subtitles_path=subtitles, output_path=output, edit_dir=tmp_path)
    streams = ffprobe_json(output)["streams"]
    assert any(stream["codec_type"] == "video" for stream in streams)
    assert any(stream["codec_type"] == "audio" for stream in streams) == with_audio
    frame = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(output), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        check=True, capture_output=True,
    ).stdout
    assert max(frame) > 100  # Captions/overlay must actually appear on the black base.
