from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from codex_video_use.cli import grade_main
from codex_video_use.utils import run


def _make_clip(path: Path) -> None:
    webm = path.suffix.lower() == ".webm"
    run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=blue:s=64x64:r=10:d=0.2",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=0.2",
            "-c:v", "libvpx-vp9" if webm else "libx264",
            "-c:a", "libopus" if webm else "aac",
            str(path),
        ],
        capture_output=True,
        quiet=True,
    )


def _assert_graded_clip(path: Path, audio_codec: str) -> None:
    result = run(
        [
            "ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name",
            "-of", "json", str(path),
        ],
        capture_output=True,
        quiet=True,
    )
    streams = json.loads(result.stdout)["streams"]
    assert [(stream["codec_type"], stream["codec_name"]) for stream in streams] == [
        ("video", "h264"), ("audio", audio_codec),
    ]
    # Decode the complete result to catch container headers with no usable media.
    run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"], capture_output=True, quiet=True)


@pytest.mark.parametrize("suffix", [".webm", ".WEBM"])
def test_grade_cli_defaults_webm_input_to_playable_mp4(tmp_path: Path, monkeypatch, suffix: str) -> None:
    source = tmp_path / f"source{suffix}"
    _make_clip(source)
    original = source.read_bytes()
    monkeypatch.setattr(sys, "argv", ["codex-video-use-grade", str(source)])

    assert grade_main() == 0

    _assert_graded_clip(tmp_path / "source.graded.mp4", "opus")
    assert source.read_bytes() == original
    assert not (tmp_path / f"source.graded{suffix}").exists()


def test_grade_cli_keeps_mp4_default_output(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.mp4"
    _make_clip(source)
    original = source.read_bytes()
    monkeypatch.setattr(sys, "argv", ["codex-video-use-grade", str(source)])

    assert grade_main() == 0

    _assert_graded_clip(tmp_path / "source.graded.mp4", "aac")
    assert source.read_bytes() == original


def test_grade_cli_keeps_explicit_output_for_webm_input(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.webm"
    _make_clip(source)
    original = source.read_bytes()
    destination = tmp_path / "selected.mkv"
    monkeypatch.setattr(sys, "argv", ["codex-video-use-grade", str(source), "-o", str(destination)])

    assert grade_main() == 0

    _assert_graded_clip(destination, "opus")
    assert source.read_bytes() == original
    assert not (tmp_path / "source.graded.mp4").exists()
