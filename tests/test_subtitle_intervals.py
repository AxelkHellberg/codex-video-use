from __future__ import annotations

import json
from pathlib import Path

import pytest

from codex_video_use.rendering import build_master_srt


def word(text: str, start: float, end: float) -> dict:
    return {
        "text": text,
        "start": start,
        "end": end,
        "type": "word",
        "speaker_id": "speaker_0",
    }


def write_transcript(edit_dir: Path, words: list[dict]) -> None:
    transcripts = edit_dir / "transcripts"
    transcripts.mkdir()
    (transcripts / "clip.json").write_text(
        json.dumps({"words": words}), encoding="utf-8"
    )


@pytest.mark.parametrize(
    ("words", "segment_start", "segment_end", "expected_timing"),
    [
        (
            [word("long", 0.0, 2.0), word("nested", 0.5, 0.75)],
            0.0, 2.5,
            "00:00:00,000 --> 00:00:02,000",
        ),
        (
            [word("long", 0.0, 3.0), word("nested", 1.2, 1.4)],
            1.0, 2.0,
            "00:00:00,000 --> 00:00:01,000",
        ),
        (
            [word("hello", 0.0, 0.2), word("world", 0.2, 0.6)],
            0.0, 1.0,
            "00:00:00,000 --> 00:00:00,600",
        ),
        (
            [word("hello", 1.0, 1.3), word("world", 1.2, 2.0)],
            1.0, 2.0,
            "00:00:00,000 --> 00:00:01,000",
        ),
    ],
    ids=["nested-word", "clip-to-segment", "nonoverlapping", "extending-overlap"],
)
def test_subtitle_cue_covers_all_words_within_the_segment(
    tmp_path: Path,
    words: list[dict],
    segment_start: float,
    segment_end: float,
    expected_timing: str,
) -> None:
    write_transcript(tmp_path, words)
    edl = {
        "sources": {"clip": "clip.mp4"},
        "segments": [{"source": "clip", "start": segment_start, "end": segment_end}],
    }

    output = build_master_srt(edl, tmp_path, tmp_path / "master.srt")

    assert output.read_text(encoding="utf-8").splitlines() == [
        "1", expected_timing, " ".join(item["text"] for item in words).upper(),
    ]


def test_overlapping_subtitles_keep_offsets_across_repeated_segments(tmp_path: Path) -> None:
    write_transcript(tmp_path, [word("long", 0.0, 2.0), word("nested", 0.5, 0.75)])
    edl = {
        "sources": {"clip": "clip.mp4"},
        "segments": [
            {"source": "clip", "start": 0.0, "end": 1.0},
            {"source": "clip", "start": 1.0, "end": 2.5},
        ],
    }

    output = build_master_srt(edl, tmp_path, tmp_path / "master.srt")

    assert output.read_text(encoding="utf-8").splitlines() == [
        "1", "00:00:00,000 --> 00:00:01,000", "LONG NESTED", "",
        "2", "00:00:01,000 --> 00:00:02,000", "LONG",
    ]
