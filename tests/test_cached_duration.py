from __future__ import annotations

import json

import pytest

from codex_video_use import transcription
from codex_video_use.packing import pack_edit_dir


VALID_WORD = {"text": "hello", "type": "word", "start": 0.0, "end": 0.8}


@pytest.mark.parametrize("duration", [
    "broken", "1.0", None, {}, [], True, False, -1, -0.5,
    float("nan"), float("inf"), float("-inf"), 10 ** 400,
])
def test_invalid_cached_duration_is_replaced_before_packing(tmp_path, monkeypatch, duration):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"media")
    edit_dir = tmp_path / "edit"
    cache = transcription.transcript_path(edit_dir, source)
    cache.write_text(json.dumps({
        "source_path": str(source.resolve()),
        "source_size": source.stat().st_size,
        "source_mtime_ns": source.stat().st_mtime_ns,
        "duration_seconds": duration,
        "words": [VALID_WORD],
    }), encoding="utf-8")
    uploads = []
    monkeypatch.setattr(transcription, "count_audio_tracks", lambda _: 1)
    monkeypatch.setattr(transcription, "extract_audio_track", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(transcription, "peak_dbfs", lambda _: -12.0)
    monkeypatch.setattr(transcription, "media_duration", lambda _: 1.0)

    def request(*_args, **_kwargs):
        uploads.append(True)
        return {"text": "hello", "words": [VALID_WORD]}

    monkeypatch.setattr(transcription, "request_transcript", request)

    assert transcription.transcript_is_current(cache, source) is False
    assert transcription.transcribe_one(source, edit_dir=edit_dir, api_key="unused") == cache
    assert uploads == [True]
    packed = pack_edit_dir(edit_dir).read_text(encoding="utf-8")
    assert "duration: 1.0s" in packed
    assert "hello" in packed
    assert transcription.transcribe_one(source, edit_dir=edit_dir, api_key="unused") == cache
    assert uploads == [True]


@pytest.mark.parametrize("duration", [0, 1, 1.5])
def test_valid_cached_duration_is_reused(tmp_path, duration):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"media")
    cache = tmp_path / "clip.json"
    cache.write_text(json.dumps({
        "source_path": str(source.resolve()),
        "source_size": source.stat().st_size,
        "source_mtime_ns": source.stat().st_mtime_ns,
        "duration_seconds": duration,
        "words": [VALID_WORD],
    }), encoding="utf-8")

    assert transcription.transcript_is_current(cache, source) is True


def test_legacy_cache_without_duration_still_packs_and_is_reused(tmp_path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"media")
    edit_dir = tmp_path / "edit"
    cache = transcription.transcript_path(edit_dir, source)
    cache.write_text(json.dumps({
        "source_path": str(source.resolve()),
        "source_size": source.stat().st_size,
        "source_mtime_ns": source.stat().st_mtime_ns,
        "words": [VALID_WORD],
    }), encoding="utf-8")

    assert transcription.transcript_is_current(cache, source) is True
    assert "duration: 0.8s" in pack_edit_dir(edit_dir).read_text(encoding="utf-8")
