from __future__ import annotations

import json

import pytest

from codex_video_use import transcription
from codex_video_use.packing import group_words


VALID_WORD = {"text": "hello", "type": "word", "start": 0.0, "end": 0.8}


@pytest.mark.parametrize("cached_words", [
    None, {}, "hello", 1, [None], [[]], [1], [{}],
    [{"start": 0, "end": 1}],
    [{**VALID_WORD, "text": None}],
    [{**VALID_WORD, "text": []}],
    [{**VALID_WORD, "start": None}],
    [{**VALID_WORD, "end": None}],
    [{**VALID_WORD, "start": "0"}],
    [{**VALID_WORD, "end": "1"}],
    [{**VALID_WORD, "start": True}],
    [{**VALID_WORD, "end": False}],
    [{**VALID_WORD, "start": -1}],
    [{**VALID_WORD, "end": -1}],
    [{**VALID_WORD, "start": 2}],
    [{**VALID_WORD, "start": float("nan")}],
    [{**VALID_WORD, "end": float("inf")}],
    [{**VALID_WORD, "end": 10 ** 400}],
    [VALID_WORD, {"text": "broken", "start": 1}],
])
def test_corrupt_cached_words_are_replaced_then_reused(tmp_path, monkeypatch, cached_words):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"media")
    edit_dir = tmp_path / "edit"
    cache = transcription.transcript_path(edit_dir, source)
    cache.write_text(json.dumps({
        "source_path": str(source.resolve()),
        "source_size": source.stat().st_size,
        "source_mtime_ns": source.stat().st_mtime_ns,
        "words": cached_words,
    }), encoding="utf-8")
    requests = []
    monkeypatch.setattr(transcription, "count_audio_tracks", lambda _: 1)
    monkeypatch.setattr(transcription, "extract_audio_track", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(transcription, "peak_dbfs", lambda _: -12.0)
    monkeypatch.setattr(transcription, "media_duration", lambda _: 1.0)

    def request(*_args, **_kwargs):
        requests.append(True)
        return {"text": "hello", "words": [VALID_WORD]}

    monkeypatch.setattr(transcription, "request_transcript", request)

    assert transcription.transcript_is_current(cache, source) is False
    assert transcription.transcribe_one(source, edit_dir=edit_dir, api_key="unused") == cache
    assert requests == [True]
    payload = json.loads(cache.read_text(encoding="utf-8"))
    assert group_words(payload["words"])[0]["text"] == "hello"
    assert transcription.transcribe_one(source, edit_dir=edit_dir, api_key="unused") == cache
    assert requests == [True]


def test_missing_cached_words_is_a_miss(tmp_path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"media")
    cache = tmp_path / "clip.json"
    cache.write_text(json.dumps({
        "source_path": str(source.resolve()),
        "source_size": source.stat().st_size,
        "source_mtime_ns": source.stat().st_mtime_ns,
    }), encoding="utf-8")

    assert transcription.transcript_is_current(cache, source) is False


@pytest.mark.parametrize("words", [
    [],
    [VALID_WORD],
    [
        VALID_WORD,
        {"text": " ", "type": "spacing", "start": 0.8, "end": 0.8},
        {"text": "laughing", "type": "audio_event", "start": 0.8, "end": 1},
        {"text": "overlap", "type": "word", "start": 0.9, "end": 1.2},
    ],
])
def test_valid_silent_and_timestamped_caches_remain_reusable(tmp_path, words):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"media")
    cache = tmp_path / "clip.json"
    cache.write_text(json.dumps({
        "source_path": str(source.resolve()),
        "source_size": source.stat().st_size,
        "source_mtime_ns": source.stat().st_mtime_ns,
        "words": words,
    }), encoding="utf-8")

    assert transcription.transcript_is_current(cache, source) is True
