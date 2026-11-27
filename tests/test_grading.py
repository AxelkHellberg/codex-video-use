from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from codex_video_use import grading
from codex_video_use.cli import grade_main
from codex_video_use.grading import apply_grade
from codex_video_use.utils import CommandFailure, ffprobe_json, run


pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")


@pytest.fixture
def source(tmp_path: Path) -> Path:
    path = tmp_path / "source.mp4"
    run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=64x48:r=12",
            "-t", "0.25", "-c:v", "libx264", str(path),
        ],
        quiet=True,
    )
    return path


def test_failed_grade_preserves_existing_export(source: Path, tmp_path: Path) -> None:
    output = tmp_path / "graded.mp4"
    original = source.read_bytes()
    output.write_bytes(original)
    before = set(tmp_path.iterdir())

    # The filter is valid, but the resulting odd canvas makes libx264 fail after
    # FFmpeg has opened its output. A parser error would not exercise truncation.
    with pytest.raises(CommandFailure):
        apply_grade(source, output, filter_string="scale=1:1")

    assert output.read_bytes() == original
    assert source.read_bytes() == original
    assert set(tmp_path.iterdir()) == before


def test_failed_grade_leaves_no_partial_export(source: Path, tmp_path: Path) -> None:
    output = tmp_path / "graded.mp4"
    before = set(tmp_path.iterdir())

    with pytest.raises(CommandFailure):
        apply_grade(source, output, filter_string="scale=1:1")

    assert not output.exists()
    assert set(tmp_path.iterdir()) == before


@pytest.mark.parametrize("through_symlink", [False, True])
def test_successful_grade_replaces_export_and_cleans_workspace(
    source: Path, tmp_path: Path, through_symlink: bool
) -> None:
    output = tmp_path / "graded.mp4"
    original = source.read_bytes()
    output.write_bytes(original)
    before = set(tmp_path.iterdir())

    output.chmod(0o640)
    if through_symlink:
        target = tmp_path / "target.mp4"
        output.rename(target)
        output.symlink_to(target)
        before = set(tmp_path.iterdir())

    assert apply_grade(source, output, filter_string="scale=32:24") == output

    video = next(stream for stream in ffprobe_json(output)["streams"] if stream["codec_type"] == "video")
    assert (video["width"], video["height"]) == (32, 24)
    assert output.read_bytes() != original
    assert output.stat().st_mode & 0o777 == 0o640
    assert output.is_symlink() == through_symlink
    assert source.read_bytes() == original
    assert set(tmp_path.iterdir()) == before


@pytest.mark.parametrize(
    "alias", ["same-path", "output-symlink", "input-symlink", "parent-symlink", "hardlink"]
)
def test_grade_rejects_input_output_aliases(source: Path, tmp_path: Path, alias: str) -> None:
    input_path = source
    output = source
    if alias == "output-symlink":
        output = tmp_path / "alias.mp4"
        output.symlink_to(source)
    elif alias == "input-symlink":
        input_path = tmp_path / "alias.mp4"
        input_path.symlink_to(source)
    elif alias == "parent-symlink":
        parent_alias = tmp_path / "alias-directory"
        parent_alias.symlink_to(tmp_path, target_is_directory=True)
        output = parent_alias / source.name
    elif alias == "hardlink":
        output = tmp_path / "alias.mp4"
        output.hardlink_to(source)

    original = source.read_bytes()
    before = set(tmp_path.iterdir())
    with pytest.raises(SystemExit, match="output.*different.*input"):
        apply_grade(input_path, output, filter_string="scale=32:24")

    assert source.read_bytes() == original
    assert output.read_bytes() == original
    assert set(tmp_path.iterdir()) == before


def test_grade_alias_rejection_precedes_media_work(source: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected(*args, **kwargs):
        pytest.fail("input/output alias reached media processing or workspace creation")

    monkeypatch.setattr(grading, "run", unexpected)
    monkeypatch.setattr(grading.tempfile, "TemporaryDirectory", unexpected)
    with pytest.raises(SystemExit, match="output.*different.*input"):
        apply_grade(source, source, filter_string="neutral")


def test_grade_cli_preserves_input_when_output_is_same_path(
    source: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = source.read_bytes()
    monkeypatch.setattr(
        sys, "argv",
        ["codex-video-use-grade", str(source), "-o", str(source), "--filter", "scale=32:24"],
    )
    with pytest.raises(SystemExit, match="output.*different.*input"):
        grade_main()
    assert source.read_bytes() == original


def test_successful_grade_creates_separate_export(source: Path, tmp_path: Path) -> None:
    output = tmp_path / "new-grade.mp4"
    original = source.read_bytes()
    assert apply_grade(source, output, filter_string="scale=32:24") == output
    video = next(stream for stream in ffprobe_json(output)["streams"] if stream["codec_type"] == "video")
    assert (video["width"], video["height"]) == (32, 24)
    assert source.read_bytes() == original
    assert set(tmp_path.iterdir()) == {source, output}
