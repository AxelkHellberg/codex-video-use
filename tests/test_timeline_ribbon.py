from pathlib import Path

import numpy as np
from PIL import Image
import pytest

from codex_video_use import timeline


@pytest.mark.parametrize("frame_count", [1, 10, 30, 70])
def test_timeline_keeps_every_thumbnail_inside_the_image(tmp_path, monkeypatch, frame_count):
    paths = []
    for index in range(frame_count):
        path = tmp_path / f"frame-{index}.png"
        color = (255, 0, 0) if index == frame_count - 1 else (0, 255, 0)
        Image.new("RGB", (64, 64), color).save(path)
        paths.append(path)

    monkeypatch.setattr(timeline, "_extract_frames", lambda *args: paths)
    monkeypatch.setattr(timeline, "_extract_waveform", lambda *args: np.zeros(8))
    monkeypatch.setattr(timeline, "_default_transcript_path", lambda *args: None)
    output = tmp_path / "timeline.png"

    timeline.render_timeline_image(
        Path("source.mp4"), 0, 10, output_path=output, frame_count=frame_count,
    )

    with Image.open(output) as image:
        row = [image.getpixel((x, 100)) for x in range(image.width)]
        assert row.count((255, 0, 0)) == 180, "the final thumbnail was cropped"
        assert row.count((0, 255, 0)) == (frame_count - 1) * 180
        assert row[:40] == [timeline.BG] * 40
        assert row[-40:] == [timeline.BG] * 40
