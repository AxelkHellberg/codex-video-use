import json
from pathlib import Path

import pytest

import codex_video_use.transcription as transcription


@pytest.mark.parametrize("options", [{"language": "es"}, {"num_speakers": 2}, {"language": "en", "num_speakers": 1}])
def test_legacy_default_cache_does_not_hide_requested_options(tmp_path: Path, options) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"source")
    output = tmp_path / "clip.json"
    output.write_text(json.dumps({"source_path": str(source.resolve()), "source_size": source.stat().st_size,
                                  "source_mtime_ns": source.stat().st_mtime_ns, "source_audio_track": 0}))
    assert transcription.transcript_is_current(output, source)
    assert not transcription.transcript_is_current(output, source, **options)


def test_option_changes_replace_cache_once_then_reuse(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"source")
    requests = []
    monkeypatch.setattr(transcription, "count_audio_tracks", lambda _: 1)
    monkeypatch.setattr(transcription, "extract_audio_track", lambda *args, **kwargs: kwargs["output_path"].write_bytes(b"wav"))
    monkeypatch.setattr(transcription, "peak_dbfs", lambda _: -12.0)
    monkeypatch.setattr(transcription, "media_duration", lambda _: 1.0)

    def fake_request(*args, **kwargs):
        requests.append((kwargs["language"], kwargs["num_speakers"]))
        return {"text": "hello", "language_code": "en", "words": []}

    monkeypatch.setattr(transcription, "request_transcript", fake_request)
    for options in [{"language": "es", "num_speakers": 2}, {"language": "en", "num_speakers": 2},
                    {"language": "en", "num_speakers": 1}, {"language": None, "num_speakers": None}]:
        output = transcription.transcribe_one(source, edit_dir=tmp_path / "edit", api_key="test", **options)
        payload = json.loads(output.read_text())
        assert payload["request_language"] == options["language"]
        assert payload["request_num_speakers"] == options["num_speakers"]
        transcription.transcribe_one(source, edit_dir=tmp_path / "edit", api_key="test", **options)
    assert requests == [("es", 2), ("en", 2), ("en", 1), (None, None)]
