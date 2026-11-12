import json

import pytest

from codex_video_use import rendering


@pytest.mark.parametrize("overlays", [
    "overlay.mp4", {"file": "overlay.mp4"}, [None],
    [{"start": 0, "duration": 1}],
    [{"file": "", "start": 0, "duration": 1}],
    [{"file": "overlay.mp4", "duration": 1}],
    [{"file": "overlay.mp4", "start": 0}],
    *[[{"file": "overlay.mp4", "start": start, "duration": duration}]
      for start, duration in [(-1, 1), (float("nan"), 1), (float("inf"), 1),
                              (0, 0), (0, -1), (0, float("nan")), (0, float("inf")),
                              (True, 1), (0, False), ("bad", 1), (0, None), (1e308, 1e308)]],
])
def test_invalid_overlays_stop_before_media_and_output_creation(tmp_path, monkeypatch, overlays):
    edl = tmp_path / "edl.json"
    edl.write_text(json.dumps({"sources": {"clip": "clip.mp4"},
                              "segments": [{"source": "clip", "start": 0, "end": 1}],
                              "overlays": overlays}))
    monkeypatch.setattr(rendering, "run", lambda *a, **kw: pytest.fail("media work started"))
    with pytest.raises(SystemExit, match="overlays|overlay 1"):
        rendering.render_edl(edl, output_path=tmp_path / "exports" / "out.mp4")
    assert not (tmp_path / "exports").exists()
    assert not (tmp_path / "clips").exists()


def test_invalid_later_overlay_stops_direct_composition(tmp_path, monkeypatch):
    commands = []
    monkeypatch.setattr(rendering, "run", lambda *a, **kw: commands.append(a))
    output = tmp_path / "out.mp4"
    output.write_bytes(b"previous render")
    with pytest.raises(SystemExit, match="overlay 2"):
        rendering.composite_output(tmp_path / "base.mp4", overlays=[
            {"file": "valid.mp4", "start": 0, "duration": 1},
            {"file": "invalid.mp4", "start": -1, "duration": 1},
        ], subtitles_path=None, output_path=output, edit_dir=tmp_path)
    assert not commands
    assert output.read_bytes() == b"previous render"


def test_valid_overlay_timing_preserves_expressions_and_input(tmp_path, monkeypatch):
    commands = []
    monkeypatch.setattr(rendering, "run", lambda command, **kw: commands.append(command))
    overlays = [{"file": "overlay.mp4", "start": "0.5", "duration": "1.25", "x": "W-w", "y": 4}]
    rendering.composite_output(tmp_path / "base.mp4", overlays=overlays, subtitles_path=None,
                               output_path=tmp_path / "out.mp4", edit_dir=tmp_path)
    graph = commands[0][commands[0].index("-filter_complex") + 1]
    assert "between(t,0.500,1.750)" in graph
    assert "overlay=W-w:4" in graph
    assert overlays[0]["start"] == "0.5"
