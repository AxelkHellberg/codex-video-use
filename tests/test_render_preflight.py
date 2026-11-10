from __future__ import annotations

import json

import pytest

import codex_video_use.rendering as rendering


@pytest.mark.parametrize("start,end", [(-1, 1), (1, 1), (2, 1), (float("nan"), 1), (0, float("inf")), (0, "oops"), (True, 2), (0, None)])
def test_invalid_later_segment_stops_before_any_media_or_output_work(tmp_path, monkeypatch, start, end):
    edl_path = tmp_path / "edl.json"
    edl_path.write_text(json.dumps({"sources": {"clip": "clip.mp4"}, "segments": [
        {"source": "clip", "start": 0, "end": 1},
        {"source": "clip", "start": start, "end": end},
    ]}))
    monkeypatch.setattr(rendering, "_probe_source_fps", lambda *_: pytest.fail("must validate all ranges before probing"))
    monkeypatch.setattr(rendering, "extract_segment", lambda *_, **__: pytest.fail("must not extract"))
    output = tmp_path / "output" / "render.mp4"
    with pytest.raises(SystemExit, match="segment 2"):
        rendering.render_edl(edl_path, output_path=output)
    assert not output.parent.exists()
    assert not (tmp_path / "clips").exists()


@pytest.mark.parametrize("segments", [[], [{"source": "missing", "start": 0, "end": 1}]])
def test_empty_or_unknown_source_stops_before_creating_outputs(tmp_path, segments):
    edl_path = tmp_path / "edl.json"
    edl_path.write_text(json.dumps({"sources": {"clip": "clip.mp4"}, "segments": segments}))
    with pytest.raises(SystemExit, match="segment"):
        rendering.render_edl(edl_path, output_path=tmp_path / "output" / "render.mp4")
    assert not (tmp_path / "output").exists()
