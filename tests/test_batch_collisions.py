from pathlib import Path

import pytest

import codex_video_use.transcription as transcription


@pytest.mark.parametrize("audio_track", [0, 1])
def test_batch_rejects_output_collisions_before_credentials_or_upload(tmp_path: Path, monkeypatch, audio_track: int) -> None:
    (tmp_path / "take.mp4").touch()
    (tmp_path / "take.mov").touch()

    def unexpected_key_lookup(*args: object) -> str:
        pytest.fail("colliding targets must be rejected before credentials or paid requests")

    monkeypatch.setattr(transcription, "resolve_api_key", unexpected_key_lookup)
    with pytest.raises(ValueError, match="take.mov.*take.mp4"):
        transcription.transcribe_batch(tmp_path, audio_track=audio_track)
    assert not (tmp_path / "edit").exists()


def test_batch_keeps_distinct_transcript_targets(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "first.mov").touch()
    (tmp_path / "second.mp4").touch()
    monkeypatch.setattr(transcription, "resolve_api_key", lambda *_: "unused-test-key")
    monkeypatch.setattr(transcription, "transcribe_one", lambda target, **kwargs: Path(kwargs["edit_dir"]) / "transcripts" / f"{target.stem}.json")

    outputs = transcription.transcribe_batch(tmp_path)

    assert {path.name for path in outputs} == {"first.json", "second.json"}
