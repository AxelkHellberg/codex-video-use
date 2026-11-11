import json
from pathlib import Path
import shutil
import subprocess

import pytest

from codex_video_use.rendering import render_edl
from codex_video_use.utils import ffprobe_json


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")
@pytest.mark.parametrize("portrait_first", [False, True])
def test_mixed_orientation_edit_has_one_canvas(tmp_path: Path, portrait_first: bool) -> None:
    sources = {}
    for name, size in [("landscape", "160x90"), ("portrait", "90x160")]:
        source = tmp_path / f"{name}.mp4"
        subprocess.run([
            "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=red:s={size}:r=10:d=0.3",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=0.3", "-shortest",
            "-c:v", "libx264", "-c:a", "aac", str(source),
        ], check=True, capture_output=True)
        sources[name] = str(source)
    order = ["portrait", "landscape"] if portrait_first else ["landscape", "portrait"]
    edl = tmp_path / "edl.json"
    edl.write_text(json.dumps({
        "sources": sources,
        "segments": [{"source": name, "start": 0, "end": 0.3} for name in order],
    }), encoding="utf-8")
    output = tmp_path / "preview.mp4"
    render_edl(edl, output_path=output, preview=True, no_subtitles=True, no_normalize=True)
    expected = (720, 1280) if portrait_first else (1280, 720)
    for clip in sorted((tmp_path / "clips-preview").glob("*.mp4")):
        video = next(s for s in ffprobe_json(clip)["streams"] if s["codec_type"] == "video")
        assert (video["width"], video["height"]) == expected
    decoded = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames",
        "-show_entries", "frame=width,height", "-of", "json", str(output),
    ], check=True, capture_output=True, text=True)
    frames = json.loads(decoded.stdout)["frames"]
    assert len(frames) == 6
    assert {(frame["width"], frame["height"]) for frame in frames} == {expected}
