from __future__ import annotations

import json

import pytest

from codex_video_use.transcription import transcript_is_current


@pytest.mark.parametrize("payload", [[], None, "text", 7])
def test_non_object_cache_is_a_miss(tmp_path, payload):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"media")
    cache = tmp_path / "source.json"
    cache.write_text(json.dumps(payload))
    assert transcript_is_current(cache, source) is False


@pytest.mark.parametrize("track", [None, "bad", {}, [], float("inf"), 1.5, True])
def test_invalid_track_metadata_is_a_miss(tmp_path, track):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"media")
    cache = tmp_path / "source.json"
    cache.write_text(json.dumps({"source_path": str(source.resolve()), "source_size": source.stat().st_size,
        "source_mtime_ns": source.stat().st_mtime_ns, "source_audio_track": track}))
    assert transcript_is_current(cache, source, audio_track=1) is False


def test_invalid_utf8_cache_is_a_miss(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"media")
    cache = tmp_path / "source.json"
    cache.write_bytes(b"\xff")
    assert transcript_is_current(cache, source) is False


@pytest.mark.parametrize("track", [0, "0", None])
def test_valid_or_legacy_default_cache_is_reused(tmp_path, track):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"media")
    payload = {"source_path": str(source.resolve()), "source_size": source.stat().st_size,
        "source_mtime_ns": source.stat().st_mtime_ns}
    if track is not None:
        payload["source_audio_track"] = track
    cache = tmp_path / "source.json"
    cache.write_text(json.dumps(payload))
    assert transcript_is_current(cache, source) is True
    source.write_bytes(b"changed media")
    assert transcript_is_current(cache, source) is False


def test_corrupt_cache_can_be_replaced_by_a_successful_transcription(tmp_path, monkeypatch):
    import codex_video_use.transcription as transcription

    source = tmp_path / "source.mp4"
    source.write_bytes(b"media")
    edit_dir = tmp_path / "edit"
    cache = transcription.transcript_path(edit_dir, source)
    cache.write_text("[]")
    uploads = []
    monkeypatch.setattr(transcription, "count_audio_tracks", lambda _: 1)
    monkeypatch.setattr(transcription, "extract_audio_track", lambda *args, **kwargs: None)
    monkeypatch.setattr(transcription, "peak_dbfs", lambda _: -12.0)
    monkeypatch.setattr(transcription, "media_duration", lambda _: 1.0)

    def request(*args, **kwargs):
        uploads.append(True)
        return {"text": "hello", "words": []}

    monkeypatch.setattr(transcription, "request_transcript", request)
    assert transcription.transcribe_one(source, edit_dir=edit_dir, api_key="unused") == cache
    assert uploads == [True]
    assert transcript_is_current(cache, source)
    # The repaired cache must be reused, without a second service request.
    assert transcription.transcribe_one(source, edit_dir=edit_dir, api_key="unused") == cache
    assert uploads == [True]
