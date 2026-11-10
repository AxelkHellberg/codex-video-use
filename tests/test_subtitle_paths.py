from __future__ import annotations

import shutil
import subprocess

import pytest

from codex_video_use.rendering import _has_subtitles_filter, composite_output


@pytest.fixture(scope="module")
def base_video(tmp_path_factory):
    if not shutil.which("ffmpeg") or not _has_subtitles_filter():
        pytest.skip("FFmpeg with subtitles support is required")
    path = tmp_path_factory.mktemp("subtitle-base") / "base.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=640x360:r=24",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "0.25",
        "-c:v", "libx264", "-c:a", "aac", str(path)], check=True, timeout=30)
    return path


@pytest.mark.parametrize("name", ["captions.srt", "captions'quote.srt", "captions:colon.srt",
    r"captions\slash.srt", "captions,[brackets];=.srt", "captions with spaces.srt",
    "captions'\\:,[all];=.srt"])
def test_subtitles_from_literal_paths_are_actually_burned(tmp_path, base_video, name):
    folder = tmp_path / "parent's folder"
    folder.mkdir()
    subtitles = folder / name
    subtitles.write_text("1\n00:00:00,000 --> 00:00:01,000\nVISIBLE CAPTION\n", encoding="utf-8")
    output = tmp_path / "out.mp4"
    composite_output(base_video, overlays=[], subtitles_path=subtitles, output_path=output, edit_dir=tmp_path)
    frame = subprocess.run(["ffmpeg", "-v", "error", "-i", str(output), "-frames:v", "1",
        "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"], capture_output=True, check=True, timeout=30).stdout
    assert len(frame) == 640 * 360
    assert sum(value > 150 for value in frame) > 50, "caption must appear on the black frame"
