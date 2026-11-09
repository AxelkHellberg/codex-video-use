from pathlib import Path
from unittest.mock import Mock

import pytest

from codex_video_use.timeline import render_timeline_image


@pytest.mark.parametrize("start,end", [
    (0, 0), (2, 1), (-1, 1), (float("nan"), 1),
    (0, float("nan")), (0, float("inf")), (float("-inf"), 1),
])
def test_invalid_range_fails_before_extracting_media(tmp_path, monkeypatch, start, end):
    extract = Mock(side_effect=AssertionError("media extraction must not start"))
    monkeypatch.setattr("codex_video_use.timeline._extract_frames", extract)
    destination = tmp_path / "timeline.png"
    with pytest.raises(ValueError, match="finite.*0 <= start < end"):
        render_timeline_image(Path("unused.mp4"), start, end, output_path=destination)
    extract.assert_not_called()
    assert not destination.exists()


@pytest.mark.parametrize("frames", [0, -1, 1.5, True])
def test_invalid_frame_count_fails_before_extracting_media(tmp_path, monkeypatch, frames):
    extract = Mock(side_effect=AssertionError("media extraction must not start"))
    monkeypatch.setattr("codex_video_use.timeline._extract_frames", extract)
    with pytest.raises(ValueError, match="positive integer"):
        render_timeline_image(Path("unused.mp4"), 0, 1, output_path=tmp_path / "timeline.png", frame_count=frames)
    extract.assert_not_called()


def test_single_frame_uses_the_range_midpoint(tmp_path, monkeypatch):
    from codex_video_use.timeline import _extract_frames

    run = Mock()
    monkeypatch.setattr("codex_video_use.timeline.run", run)
    paths = _extract_frames(Path("clip.mp4"), 2, 4, 1, tmp_path)
    assert paths == [tmp_path / "frame-000.jpg"]
    command = run.call_args.args[0]
    assert command[command.index("-ss") + 1] == "3.000"
