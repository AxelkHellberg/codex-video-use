import json
from pathlib import Path

import pytest

from codex_video_use import rendering


@pytest.mark.parametrize("available", [False, True])
def test_composition_never_silently_drops_requested_subtitles(tmp_path, monkeypatch, available):
    subtitle = tmp_path / "captions.srt"
    if not available:
        subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nHELLO\n")
    output = tmp_path / "existing.mp4"
    output.write_bytes(b"previous export")
    monkeypatch.setattr(rendering, "_has_subtitles_filter", lambda: available)
    commands = []
    monkeypatch.setattr(rendering, "run", lambda *args, **kwargs: commands.append(args))
    with pytest.raises(SystemExit, match="subtitles"):
        rendering.composite_output(tmp_path / "base.mp4", overlays=[], subtitles_path=subtitle,
                                   output_path=output, edit_dir=tmp_path)
    assert commands == []
    assert output.read_bytes() == b"previous export"


@pytest.mark.parametrize("build", [False, True])
def test_missing_filter_stops_render_before_media_or_output_creation(tmp_path, monkeypatch, build):
    subtitle = tmp_path / "captions.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nHELLO\n")
    edl = tmp_path / "edl.json"
    edl.write_text(json.dumps({"sources": {"clip": "clip.mp4"},
                               "segments": [{"source": "clip", "start": 0, "end": 1}],
                               "subtitles": subtitle.name}))
    monkeypatch.setattr(rendering, "_has_subtitles_filter", lambda: False)
    monkeypatch.setattr(rendering, "run", lambda *a, **kw: pytest.fail("media processing started"))
    with pytest.raises(SystemExit, match="subtitles filter"):
        rendering.render_edl(edl, output_path=tmp_path / "exports" / "out.mp4",
                             build_subtitles_flag=build)
    assert not (tmp_path / "exports").exists()
    assert not (tmp_path / "clips").exists()


def test_composition_without_subtitles_does_not_require_filter(tmp_path, monkeypatch):
    monkeypatch.setattr(rendering, "_has_subtitles_filter", lambda: pytest.fail("unneeded probe"))
    commands = []
    monkeypatch.setattr(rendering, "run", lambda command, **kw: commands.append(command))
    rendering.composite_output(tmp_path / "base.mp4", overlays=[], subtitles_path=None,
                               output_path=tmp_path / "out.mp4", edit_dir=tmp_path)
    assert len(commands) == 1


def test_explicit_opt_out_bypasses_unavailable_filter(tmp_path, monkeypatch):
    edl = tmp_path / "edl.json"
    edl.write_text(json.dumps({"sources": {"clip": "clip.mp4"},
                               "segments": [{"source": "clip", "start": 0, "end": 1}],
                               "subtitles": "missing.srt"}))
    monkeypatch.setattr(rendering, "_has_subtitles_filter", lambda: pytest.fail("unneeded filter probe"))

    def reached_media(_):
        raise RuntimeError("normal media path")

    monkeypatch.setattr(rendering, "_probe_source_fps", reached_media)
    with pytest.raises(RuntimeError, match="normal media path"):
        rendering.render_edl(edl, output_path=tmp_path / "out.mp4", no_subtitles=True)
