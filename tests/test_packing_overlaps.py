from __future__ import annotations

import json
from pathlib import Path

import pytest

from codex_video_use.packing import group_words, pack_edit_dir


def word(text: str, start: float, end: float, speaker: str = "speaker_0") -> dict:
    return {"text": text, "start": start, "end": end, "type": "word", "speaker_id": speaker}


@pytest.mark.parametrize("kind", ["word", "audio_event"])
def test_nested_intervals_keep_the_complete_phrase_end(kind: str) -> None:
    first = {**word("long", 0.0, 2.0), "type": kind}

    phrases = group_words([first, word("short", 0.5, 0.75)])

    assert len(phrases) == 1
    assert phrases[0]["start"] == 0.0
    assert phrases[0]["end"] == 2.0
    assert phrases[0]["text"] == ("long short" if kind == "word" else "(long) short")


def test_silence_is_measured_after_all_covered_speech() -> None:
    phrases = group_words([
        word("long", 0.0, 2.0),
        word("nested", 0.5, 0.75),
        word("still covered", 1.5, 1.7),
        word("after silence", 2.6, 2.9),
    ], silence_threshold=0.5)

    assert phrases == [
        {"start": 0.0, "end": 2.0, "speaker": "0", "text": "long nested still covered"},
        {"start": 2.6, "end": 2.9, "speaker": "0", "text": "after silence"},
    ]


def test_speaker_switch_starts_a_fresh_covered_interval() -> None:
    phrases = group_words([
        word("first speaker", 0.0, 5.0),
        word("second speaker", 0.5, 0.75, "speaker_1"),
        word("after silence", 1.5, 1.7, "speaker_1"),
    ])

    assert [(phrase["speaker"], phrase["start"], phrase["end"]) for phrase in phrases] == [
        ("0", 0.0, 5.0), ("1", 0.5, 0.75), ("1", 1.5, 1.7),
    ]


def test_explicit_spacing_starts_a_fresh_covered_interval() -> None:
    phrases = group_words([
        word("before spacing", 0.0, 5.0),
        {"text": " ", "type": "spacing", "start": 0.5, "end": 1.1},
        word("after spacing", 1.1, 1.3),
        word("after silence", 2.0, 2.2),
    ])

    assert [phrase["text"] for phrase in phrases] == [
        "before spacing", "after spacing", "after silence",
    ]


def test_nonoverlapping_words_keep_existing_gap_boundaries() -> None:
    phrases = group_words([
        word("hello", 0.0, 0.2),
        word("world", 0.3, 0.5),
        word("next", 1.0, 1.2),
    ], silence_threshold=0.5)

    assert phrases == [
        {"start": 0.0, "end": 0.5, "speaker": "0", "text": "hello world"},
        {"start": 1.0, "end": 1.2, "speaker": "0", "text": "next"},
    ]


def test_packed_markdown_keeps_overlapping_phrase_duration(tmp_path: Path) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    (transcripts / "clip.json").write_text(json.dumps({
        "words": [word("long", 0.0, 3.0), word("short", 0.5, 0.75)],
    }), encoding="utf-8")

    output = pack_edit_dir(tmp_path)

    text = output.read_text(encoding="utf-8")
    assert "duration: 3.0s, 1 phrases" in text
    assert "[000.00-003.00] S0 long short" in text


@pytest.mark.parametrize(("duration", "expected_duration"), [(None, 5.0), (10.0, 10.0)])
def test_packed_duration_covers_all_speakers_unless_metadata_is_present(
    tmp_path: Path, duration: float | None, expected_duration: float,
) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    payload = {"words": [
        word("first speaker", 0.0, 5.0),
        word("second speaker", 0.5, 0.75, "speaker_1"),
    ]}
    if duration is not None:
        payload["duration_seconds"] = duration
    (transcripts / "clip.json").write_text(json.dumps(payload), encoding="utf-8")

    text = pack_edit_dir(tmp_path).read_text(encoding="utf-8")

    assert f"duration: {expected_duration:.1f}s, 2 phrases" in text
    assert "[000.00-005.00] S0 first speaker" in text
    assert "[000.50-000.75] S1 second speaker" in text
