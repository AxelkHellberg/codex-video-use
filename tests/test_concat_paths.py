from pathlib import Path
import shutil

import pytest

from codex_video_use.rendering import concat_segments
from codex_video_use.utils import media_duration, run


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")
def test_concat_paths_with_apostrophes_and_backslashes(tmp_path: Path) -> None:
    edit = tmp_path / "editor's footage"
    edit.mkdir()
    first = edit / "take's one.mp4"
    second = edit / "take\\two.mp4"
    run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=size=64x48:rate=10",
        "-t", "0.3", "-c:v", "libx264", str(first),
    ], quiet=True)
    shutil.copyfile(first, second)
    output = edit / "combined.mp4"

    concat_segments([first, second], output, edit)

    assert media_duration(output) == pytest.approx(0.6, abs=0.05)
    assert not (edit / "_concat.txt").exists()


@pytest.mark.parametrize("separator", ["\n", "\r"])
def test_concat_rejects_line_breaks_before_writing_list(tmp_path: Path, separator: str) -> None:
    with pytest.raises(ValueError, match="line break"):
        concat_segments([tmp_path / f"take{separator}one.mp4"], tmp_path / "out.mp4", tmp_path)
    assert not (tmp_path / "_concat.txt").exists()
