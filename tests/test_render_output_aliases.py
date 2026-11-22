from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from codex_video_use import rendering
from codex_video_use.utils import ffprobe_json, run


@pytest.mark.parametrize("media_role", ["source", "overlay"])
@pytest.mark.parametrize("alias", ["direct", "symlink", "hardlink", "parent-symlink"])
def test_render_rejects_input_media_output_aliases_before_side_effects(
    tmp_path: Path, monkeypatch, media_role: str, alias: str
) -> None:
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    source = media_dir / "source.mp4"
    overlay = media_dir / "overlay.mp4"
    source.write_bytes(b"source footage")
    overlay.write_bytes(b"overlay footage")
    protected = source if media_role == "source" else overlay
    output = protected
    if alias == "symlink":
        output = tmp_path / "output.mp4"
        output.symlink_to(protected)
    elif alias == "hardlink":
        output = tmp_path / "output.mp4"
        output.hardlink_to(protected)
    elif alias == "parent-symlink":
        (tmp_path / "media-alias").symlink_to(media_dir, target_is_directory=True)
        output = tmp_path / "media-alias" / protected.name

    edl = tmp_path / "edl.json"
    edl.write_text(json.dumps({
        "sources": {"clip": "media/source.mp4"},
        "segments": [{"source": "clip", "start": 0, "end": 0.4}],
        "overlays": [{"file": "media/overlay.mp4", "start": 0, "duration": 0.4}],
    }), encoding="utf-8")
    before = {source: source.read_bytes(), overlay: overlay.read_bytes()}

    def forbidden(*_args, **_kwargs):
        pytest.fail("output alias validation must precede directory creation and media work")

    monkeypatch.setattr(rendering, "ensure_dir", forbidden)
    monkeypatch.setattr(rendering, "_probe_source_fps", forbidden)
    monkeypatch.setattr(rendering, "extract_segment", forbidden)

    with pytest.raises(SystemExit, match="output.*input media"):
        rendering.render_edl(edl, output_path=output, no_subtitles=True)

    assert {source: source.read_bytes(), overlay: overlay.read_bytes()} == before
    assert not list(tmp_path.glob(".render-*"))


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required")
def test_render_rejects_source_output_and_preserves_real_footage(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.mp4"
    run([
        "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=red:s=96x64:r=25",
        "-f", "lavfi", "-i", "sine=frequency=600:sample_rate=48000", "-t", "0.6",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source),
    ], quiet=True)
    edl = tmp_path / "edl.json"
    edl.write_text(json.dumps({
        "sources": {"clip": str(source)},
        "segments": [{"source": "clip", "start": 0, "end": 0.2}],
    }), encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    original_duration = ffprobe_json(source)["format"]["duration"]
    monkeypatch.setattr(rendering, "_target_canvas", lambda *_args, **_kwargs: (96, 64))

    with pytest.raises(SystemExit, match="output.*input media"):
        rendering.render_edl(edl, output_path=source, preview=True,
                             no_subtitles=True, no_normalize=True)

    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    assert ffprobe_json(source)["format"]["duration"] == original_duration

    # A separate destination can replace an existing export while preserving its source.
    output = tmp_path / "export.mp4"
    output.write_bytes(b"previous export")
    assert rendering.render_edl(edl, output_path=output, preview=True,
                                no_subtitles=True, no_normalize=True) == output
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    assert {stream["codec_type"] for stream in ffprobe_json(output)["streams"]} == {"video", "audio"}
    assert not list(tmp_path.glob(".render-*"))
