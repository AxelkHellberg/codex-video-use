import json
from pathlib import Path

import pytest

from codex_video_use.rendering import _chunk_words, build_master_srt


@pytest.mark.parametrize("speakers,expected", [
    (["speaker_0", "speaker_1"], [["YES"], ["NO"]]),
    ([0, 1], [["YES"], ["NO"]]),
    ([None, "speaker_1"], [["YES"], ["NO"]]),
    (["speaker_0", None], [["YES"], ["NO"]]),
    (["speaker_0", "speaker_0"], [["YES", "NO"]]),
    ([None, None], [["YES", "NO"]]),
])
def test_caption_chunks_respect_speaker_boundaries(speakers, expected) -> None:
    words = [
        {"text": "YES", "type": "word", "start": 0.0, "end": 0.2, "speaker_id": speakers[0]},
        {"text": "NO", "type": "word", "start": 0.2, "end": 0.4, "speaker_id": speakers[1]},
    ]
    assert [[word["text"] for word in chunk] for chunk in _chunk_words(words)] == expected


def test_master_srt_does_not_combine_two_speakers(tmp_path: Path) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    (transcripts / "clip.json").write_text(json.dumps({"words": [
        {"text": "yes", "type": "word", "start": 2.0, "end": 2.2, "speaker_id": "a"},
        {"text": "no", "type": "word", "start": 2.2, "end": 2.4, "speaker_id": "b"},
    ]}), encoding="utf-8")
    edl = {"sources": {"clip": "clip.mp4"}, "segments": [{"source": "clip", "start": 2.0, "end": 3.0}]}
    output = build_master_srt(edl, tmp_path, tmp_path / "master.srt")
    text = output.read_text(encoding="utf-8")
    assert "YES NO" not in text
    assert "00:00:00,000 --> 00:00:00,200\nYES" in text
    assert "00:00:00,200 --> 00:00:00,400\nNO" in text
