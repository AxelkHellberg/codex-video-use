from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from codex_video_use.rendering import render_edl
from codex_video_use.timeline import render_timeline_image
from codex_video_use.utils import ffprobe_json, run


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")
def test_render_preview_and_timeline(tmp_path: Path) -> None:
    edit_dir = tmp_path / "edit"
    edit_dir.mkdir()
    source = tmp_path / "source.mp4"
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=1280x720:rate=24",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=880:sample_rate=48000",
            "-t",
            "2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(source),
        ],
        quiet=True,
    )
    transcripts = edit_dir / "transcripts"
    transcripts.mkdir()
    (transcripts / "demo.json").write_text(
        json.dumps(
            {
                "words": [
                    {"text": "demo", "start": 0.1, "end": 0.4, "type": "word"},
                    {"text": "clip", "start": 0.45, "end": 0.8, "type": "word"}
                ]
            }
        ),
        encoding="utf-8",
    )
    edl_path = edit_dir / "edl.json"
    edl_path.write_text(
        json.dumps(
            {
                "sources": {"demo": str(source)},
                "segments": [{"source": "demo", "start": 0.0, "end": 2.0, "label": "intro"}],
                "overlays": []
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    preview = edit_dir / "preview.mp4"
    render_edl(edl_path, output_path=preview, preview=True, build_subtitles_flag=True)
    assert preview.exists()
    info = ffprobe_json(preview)
    video_streams = [stream for stream in info["streams"] if stream["codec_type"] == "video"]
    assert video_streams
    timeline = edit_dir / "verify" / "timeline.png"
    render_timeline_image(preview, 0.0, 1.0, output_path=timeline, transcript_path=transcripts / "demo.json")
    assert timeline.exists()

