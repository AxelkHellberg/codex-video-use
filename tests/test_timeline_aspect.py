from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image
import pytest

from codex_video_use.timeline import _extract_frames, render_timeline_image
from codex_video_use.utils import run


pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg and ffprobe are required",
)


def _make_source(tmp_path: Path, *, size: str = "320x240", sar: str = "1/1") -> Path:
    source = tmp_path / "source.mp4"
    run(
        [
            "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
            f"color=red:size={size}:rate=5:duration=1",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000:duration=1",
            "-vf", f"setsar={sar}", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", str(source),
        ],
        quiet=True,
    )
    return source


@pytest.mark.parametrize(
    ("size", "sar", "display_aspect"),
    [
        ("320x240", "2/1", 8 / 3),
        ("320x240", "1/2", 2 / 3),
        ("320x240", "1/1", 4 / 3),
        ("240x320", "2/1", 3 / 2),
    ],
)
def test_timeline_thumbnails_use_square_pixels_at_display_aspect(
    tmp_path: Path, size: str, sar: str, display_aspect: float
) -> None:
    source = _make_source(tmp_path, size=size, sar=sar)
    frame = _extract_frames(source, 0.0, 0.5, 1, tmp_path)[0]

    with Image.open(frame) as image:
        assert image.width == 300
        assert image.height % 2 == 0
        assert image.width / image.height == pytest.approx(display_aspect, rel=0.01)

    result = run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
            "stream=sample_aspect_ratio", "-of", "json", str(frame),
        ],
        capture_output=True,
        quiet=True,
    )
    assert json.loads(result.stdout)["streams"][0]["sample_aspect_ratio"] == "1:1"


@pytest.mark.parametrize(("sar", "display_aspect"), [("1/1", 3 / 4), ("2/1", 3 / 8)])
def test_timeline_thumbnails_preserve_rotated_display_aspect(
    tmp_path: Path, sar: str, display_aspect: float
) -> None:
    source = _make_source(tmp_path, sar=sar)
    rotated = tmp_path / "rotated.mp4"
    run(
        [
            "ffmpeg", "-v", "error", "-display_rotation:v:0", "90", "-i", str(source),
            "-c", "copy", str(rotated),
        ],
        quiet=True,
    )
    frame = _extract_frames(rotated, 0.0, 0.5, 1, tmp_path)[0]

    with Image.open(frame) as image:
        assert image.width == 300
        assert image.height % 2 == 0
        assert image.width / image.height == pytest.approx(display_aspect, rel=0.01)


def test_timeline_ribbon_displays_anamorphic_frame_at_its_display_width(tmp_path: Path) -> None:
    source = _make_source(tmp_path, sar="2/1")
    output = tmp_path / "timeline.png"
    render_timeline_image(source, 0.0, 0.5, output_path=output, frame_count=1)

    with Image.open(output) as image:
        red_columns = [
            x for x in range(image.width)
            if (pixel := image.getpixel((x, 100)))[0] > 200 and pixel[1] < 40 and pixel[2] < 40
        ]
    assert min(red_columns) == 40
    assert len(red_columns) == pytest.approx(180 * 8 / 3, abs=3)
