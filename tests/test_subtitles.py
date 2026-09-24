from __future__ import annotations

import json
from pathlib import Path

from codex_video_use.rendering import (
    CAPTION_MIN_DURATION,
    CAPTION_PAUSE_BREAK,
    _chunk_words,
    _resolve_subtitles_path,
    build_master_srt,
)


def test_build_master_srt_offsets_words_into_output_timeline(tmp_path: Path) -> None:
    edit_dir = tmp_path / "edit"
    transcripts_dir = edit_dir / "transcripts"
    transcripts_dir.mkdir(parents=True)
    transcript = {
        "words": [
            {"text": "hello", "start": 1.0, "end": 1.3, "type": "word"},
            {"text": "world", "start": 1.3, "end": 1.7, "type": "word"},
            {"text": "again", "start": 3.0, "end": 3.3, "type": "word"}
        ]
    }
    (transcripts_dir / "clip_a.json").write_text(json.dumps(transcript), encoding="utf-8")
    edl = {
        "sources": {"clip_a": "/tmp/clip_a.mp4"},
        "segments": [
            {"source": "clip_a", "start": 1.0, "end": 2.0},
            {"source": "clip_a", "start": 3.0, "end": 3.5}
        ]
    }
    output = build_master_srt(edl, edit_dir, edit_dir / "master.srt")
    text = output.read_text(encoding="utf-8")
    assert "HELLO WORLD" in text
    assert "AGAIN" in text
    assert "00:00:01,000" in text


def test_caption_chunks_break_at_pauses_and_avoid_fast_two_word_flashes() -> None:
    words = [
        {"text": "does", "start": 0.0, "end": 0.2, "type": "word"},
        {"text": "is", "start": 0.2 + CAPTION_PAUSE_BREAK, "end": 0.6, "type": "word"},
        {"text": "very", "start": 0.61, "end": 0.68, "type": "word"},
        {"text": "fast", "start": 0.69, "end": 0.76, "type": "word"},
    ]

    chunks = _chunk_words(words)

    assert [[word["text"] for word in chunk] for chunk in chunks] == [["does"], ["is", "very", "fast"]]
    assert all(
        len(chunk) == 1
        or len(chunk) == 3
        or float(chunk[-1]["end"]) - float(chunk[0]["start"]) >= CAPTION_MIN_DURATION
        for chunk in chunks
    )


def test_resolve_subtitles_path_checks_edl_directory_then_working_directory(
    tmp_path: Path, monkeypatch
) -> None:
    edit_dir = tmp_path / "edit"
    edit_dir.mkdir()
    (edit_dir / "master.srt").write_text("", encoding="utf-8")
    assert _resolve_subtitles_path("master.srt", edit_dir) == (edit_dir / "master.srt").resolve()

    monkeypatch.chdir(tmp_path)
    assert _resolve_subtitles_path("edit/master.srt", edit_dir) == (edit_dir / "master.srt").resolve()


def test_missing_explicit_subtitles_stops_render_before_captionless_output(tmp_path: Path) -> None:
    try:
        _resolve_subtitles_path("missing.srt", tmp_path)
    except SystemExit as error:
        assert "--no-subtitles" in str(error)
    else:
        raise AssertionError("expected missing subtitles to stop rendering")
