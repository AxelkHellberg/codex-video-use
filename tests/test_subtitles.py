from __future__ import annotations

import json
from pathlib import Path

from codex_video_use.rendering import build_master_srt


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

