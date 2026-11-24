from __future__ import annotations

import json
from pathlib import Path

import pytest

from codex_video_use import rendering


def _edl() -> dict:
    return {
        "sources": {"first": "first.mp4", "second": "second.mp4"},
        "segments": [
            {"source": "first", "start": 0.0, "end": 1.0},
            {"source": "second", "start": 0.0, "end": 1.0},
        ],
    }


def _transcript(edit_dir: Path, name: str, words: list[dict] | None = None) -> Path:
    path = edit_dir / "transcripts" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"words": words if words is not None else [
        {"text": name, "start": 0.0, "end": 0.5, "type": "word"},
    ]}), encoding="utf-8")
    return path


@pytest.mark.parametrize("missing", ["first", "second"])
def test_missing_transcript_preserves_existing_subtitles(tmp_path: Path, missing: str) -> None:
    _transcript(tmp_path, "second" if missing == "first" else "first")
    output = tmp_path / "master.srt"
    output.write_text("previous completed subtitles", encoding="utf-8")

    with pytest.raises(SystemExit, match=f"transcript for source '{missing}'") as error:
        rendering.build_master_srt(_edl(), tmp_path, output)

    assert str(tmp_path / "transcripts" / f"{missing}.json") in str(error.value)
    assert "--no-subtitles" in str(error.value)
    assert output.read_text(encoding="utf-8") == "previous completed subtitles"


def test_missing_transcript_does_not_create_subtitle_output(tmp_path: Path) -> None:
    output = tmp_path / "master.srt"
    with pytest.raises(SystemExit, match="transcript for source 'first'"):
        rendering.build_master_srt(_edl(), tmp_path, output)
    assert not output.exists()


def test_generated_subtitles_keep_source_stem_fallback(tmp_path: Path) -> None:
    edl = _edl()
    edl["sources"]["second"] = "footage/alternate.mp4"
    _transcript(tmp_path, "first")
    _transcript(tmp_path, "alternate")

    output = rendering.build_master_srt(edl, tmp_path, tmp_path / "master.srt")

    assert "FIRST" in output.read_text(encoding="utf-8")
    assert "ALTERNATE" in output.read_text(encoding="utf-8")
    assert "00:00:01,000 --> 00:00:01,500" in output.read_text(encoding="utf-8")


def test_generated_subtitles_prefer_source_key_and_allow_empty_words(tmp_path: Path) -> None:
    edl = _edl()
    edl["sources"]["first"] = "footage/alternate.mp4"
    edl["sources"]["unused"] = "unused.mp4"
    _transcript(tmp_path, "first")
    _transcript(tmp_path, "alternate")
    _transcript(tmp_path, "second", [])

    text = rendering.build_master_srt(edl, tmp_path, tmp_path / "master.srt").read_text(encoding="utf-8")

    assert "FIRST" in text
    assert "ALTERNATE" not in text
    assert "SECOND" not in text


def test_render_checks_all_transcripts_before_media_or_output_changes(tmp_path: Path, monkeypatch) -> None:
    edit_dir = tmp_path / "edit"
    edit_dir.mkdir()
    _transcript(edit_dir, "first")
    edl_path = edit_dir / "edl.json"
    edl_path.write_text(json.dumps(_edl()), encoding="utf-8")
    subtitles = edit_dir / "master.srt"
    subtitles.write_text("previous completed subtitles", encoding="utf-8")
    output = tmp_path / "exports" / "final.mp4"

    def unexpected_probe(*args, **kwargs):
        pytest.fail("media was probed before checking all caption transcripts")

    monkeypatch.setattr(rendering, "_probe_source_fps", unexpected_probe)
    monkeypatch.setattr(rendering, "run", unexpected_probe)

    with pytest.raises(SystemExit, match="transcript for source 'second'"):
        rendering.render_edl(edl_path, output_path=output, build_subtitles_flag=True)

    assert not output.parent.exists()
    assert not (edit_dir / "clips").exists()
    assert subtitles.read_text(encoding="utf-8") == "previous completed subtitles"


@pytest.mark.parametrize("build_subtitles_flag,no_subtitles", [(True, True), (False, False)])
def test_render_without_generated_captions_needs_no_transcripts(
    tmp_path: Path, monkeypatch, build_subtitles_flag: bool, no_subtitles: bool,
) -> None:
    edl_path = tmp_path / "edl.json"
    edl_path.write_text(json.dumps(_edl()), encoding="utf-8")
    output = tmp_path / "final.mp4"
    compositions = []
    monkeypatch.setattr(rendering, "_probe_source_fps", lambda source: "24")
    monkeypatch.setattr(rendering, "extract_segment", lambda source, **kwargs: kwargs["output_path"])
    monkeypatch.setattr(rendering, "concat_segments", lambda *args: None)
    monkeypatch.setattr(rendering, "composite_output", lambda *args, **kwargs: compositions.append(kwargs))

    assert rendering.render_edl(
        edl_path, output_path=output, build_subtitles_flag=build_subtitles_flag,
        no_subtitles=no_subtitles, no_normalize=True,
    ) == output

    assert len(compositions) == 1
    assert compositions[0]["subtitles_path"] is None
    assert not (tmp_path / "master.srt").exists()
