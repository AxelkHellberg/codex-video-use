import shutil
import json
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from codex_video_use import timeline
from codex_video_use.utils import run


@pytest.mark.parametrize("stream,container,expected", [
    ("1.125", "3", 1.125), ("N/A", "2.25", 2.25), (None, "0.0009", 0.0009),
])
def test_duration_prefers_video_stream_then_container(monkeypatch, stream, container, expected):
    monkeypatch.setattr(timeline, "run", lambda command, **kw: CompletedProcess(
        command, 0, stdout=json.dumps({"streams": [{"duration": stream}],
                                      "format": {"duration": container}})))
    assert timeline._timeline_video_duration(Path("source.mkv")) == expected


@pytest.mark.parametrize("metadata", [
    {"streams": [], "format": {"duration": "10"}},
    {"streams": [{}]},
    {"streams": [{"duration": "nan"}], "format": {"duration": "inf"}},
])
def test_no_video_or_unknown_duration_stops(monkeypatch, metadata):
    monkeypatch.setattr(timeline, "run", lambda command, **kw: CompletedProcess(
        command, 0, stdout=json.dumps(metadata)))
    with pytest.raises(ValueError, match="video stream|video duration"):
        timeline._timeline_video_duration(Path("source.mkv"))


@pytest.mark.parametrize("start,end", [(0, 2), (1, 2), (2, 3)])
def test_range_beyond_video_fails_before_extraction(tmp_path, monkeypatch, start, end):
    monkeypatch.setattr(timeline, "_timeline_video_duration", lambda path: 1.0, raising=False)
    monkeypatch.setattr(timeline, "_extract_frames", lambda *a: pytest.fail("frame extraction started"))
    monkeypatch.setattr(timeline, "_extract_waveform", lambda *a: pytest.fail("audio extraction started"))
    output = tmp_path / "new" / "timeline.png"
    with pytest.raises(ValueError, match="video duration"):
        timeline.render_timeline_image(Path("video.mp4"), start, end, output_path=output)
    assert not output.parent.exists()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg is required")
def test_real_video_range_rejected_and_exact_end_accepted(tmp_path):
    video = tmp_path / "source.mp4"
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=black:s=64x64:r=10",
         "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=16000", "-t", "1",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(video)], quiet=True)
    output = tmp_path / "timeline.png"
    with pytest.raises(ValueError, match="video duration"):
        timeline.render_timeline_image(video, 1.0, 2.0, output_path=output, frame_count=1)
    assert not output.exists()
    timeline.render_timeline_image(video, 0, 1, output_path=output, frame_count=1)
    assert output.is_file()
