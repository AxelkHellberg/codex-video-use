from __future__ import annotations

import hashlib
from pathlib import Path
import shutil

import pytest

from codex_video_use.grading import apply_grade
from codex_video_use.utils import ffprobe_json, run


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg and ffprobe are required",
)
@pytest.mark.parametrize(
    ("width", "height", "filter_string", "expected_dimensions"),
    [
        (321, 240, "neutral", (322, 240)),
        (320, 241, "neutral", (320, 242)),
        (321, 241, "neutral", (322, 242)),
        (320, 240, "neutral", (320, 240)),
        (321, 241, "", (322, 242)),
        (320, 240, "crop=319:239:exact=1", (320, 240)),
    ],
)
def test_grade_encodes_dimensions_after_applying_filter(
    tmp_path: Path,
    width: int,
    height: int,
    filter_string: str,
    expected_dimensions: tuple[int, int],
) -> None:
    source = tmp_path / "source.mkv"
    output = tmp_path / "graded.mp4"
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=size={width}x{height}:rate=12",
            "-t",
            "0.25",
            "-c:v",
            "ffv1",
            str(source),
        ],
        quiet=True,
    )
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()

    assert apply_grade(source, output, filter_string=filter_string) == output

    stream = next(
        stream
        for stream in ffprobe_json(output)["streams"]
        if stream["codec_type"] == "video"
    )
    assert (stream["width"], stream["height"]) == expected_dimensions
    run(
        ["ffmpeg", "-v", "error", "-i", str(output), "-f", "null", "-"],
        quiet=True,
    )
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
