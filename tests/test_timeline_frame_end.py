from pathlib import Path

import pytest
from PIL import Image

from codex_video_use.timeline import _extract_frames
from codex_video_use.utils import run


@pytest.mark.parametrize("start,end,frame_count", [(0.0, 1.0, 3), (0.5, 1.0, 4), (0.0, 1.0, 1)])
def test_frame_sampling_excludes_video_end(tmp_path: Path, start: float, end: float, frame_count: int) -> None:
    source = tmp_path / "source.mp4"
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=160x90:rate=10", "-t", "1",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)], quiet=True)
    output_dir = tmp_path / "frames"
    output_dir.mkdir()
    paths = _extract_frames(source, start, end, frame_count, output_dir)
    assert len(paths) == frame_count
    for path in paths:
        with Image.open(path) as image:
            assert image.width == 300
            assert image.height > 0
