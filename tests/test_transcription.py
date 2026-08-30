from __future__ import annotations

import json
from pathlib import Path

import pytest

import codex_video_use.transcription as transcription


def test_transcript_path_adds_track_suffix_only_for_nonzero_tracks(tmp_path: Path) -> None:
    source = tmp_path / "clip.mp4"

    assert transcription.transcript_path(tmp_path, source).name == "clip.json"
    assert transcription.transcript_path(tmp_path, source, audio_track=2).name == "clip.track2.json"


def test_build_transcribe_parsers_accept_audio_track() -> None:
    single_args = transcription.build_transcribe_parser().parse_args(
        ["clip.mp4", "--audio-track", "1"]
    )
    batch_args = transcription.build_transcribe_batch_parser().parse_args(
        ["clips", "--audio-track", "2"]
    )

    assert single_args.audio_track == 1
    assert batch_args.audio_track == 2


def test_transcribe_one_rejects_silent_selected_track(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"clip")

    monkeypatch.setattr(transcription, "count_audio_tracks", lambda _source: 3)
    monkeypatch.setattr(
        transcription,
        "extract_audio_track",
        lambda _source, *, audio_track, output_path: output_path.write_bytes(b"wav"),
    )
    monkeypatch.setattr(transcription, "peak_dbfs", lambda _path: -80.0)
    monkeypatch.setattr(
        transcription,
        "request_transcript",
        lambda *_args, **_kwargs: pytest.fail("request_transcript should not run for silent tracks"),
    )

    with pytest.raises(RuntimeError, match="silent"):
        transcription.transcribe_one(
            source,
            edit_dir=tmp_path / "edit",
            api_key="test-key",
            audio_track=1,
        )


def test_transcribe_one_records_selected_audio_track_metadata(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"clip")

    captured_uploads: list[str] = []

    monkeypatch.setattr(transcription, "count_audio_tracks", lambda _source: 2)
    monkeypatch.setattr(
        transcription,
        "extract_audio_track",
        lambda _source, *, audio_track, output_path: output_path.write_bytes(b"wav"),
    )
    monkeypatch.setattr(transcription, "peak_dbfs", lambda _path: -12.0)
    monkeypatch.setattr(transcription, "media_duration", lambda _source: 12.345)
    monkeypatch.setattr(transcription, "now_iso", lambda: "2026-08-30T00:00:00+00:00")

    def fake_request(upload_path: Path, **_: object) -> dict[str, object]:
        captured_uploads.append(upload_path.name)
        return {"text": "hello world", "words": [{"text": "hello", "type": "word"}]}

    monkeypatch.setattr(transcription, "request_transcript", fake_request)

    output = transcription.transcribe_one(
        source,
        edit_dir=tmp_path / "edit",
        api_key="test-key",
        audio_track=1,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert output.name == "clip.track1.json"
    assert captured_uploads == ["clip.track1.wav"]
    assert payload["source_audio_track"] == 1
    assert payload["duration_seconds"] == 12.345
