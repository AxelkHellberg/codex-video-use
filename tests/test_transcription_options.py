import pytest

from codex_video_use import transcription as t


@pytest.mark.parametrize("options", [dict(audio_track=-1), dict(audio_track=True), dict(audio_track=0.5),
                                    dict(num_speakers=0), dict(num_speakers=-1),
                                    dict(num_speakers=True), dict(num_speakers=1.5)])
def test_invalid_options_fail_before_media_or_credentials(monkeypatch, tmp_path, options):
    def unexpected(*args, **kwargs):
        pytest.fail("invalid options must fail before media inspection or credential lookup")
    monkeypatch.setattr(t, "count_audio_tracks", unexpected)
    monkeypatch.setattr(t, "discover_media", unexpected)
    monkeypatch.setattr(t, "resolve_api_key", unexpected)
    with pytest.raises(ValueError):
        t.transcribe_one(tmp_path / "missing.mp4", edit_dir=tmp_path, api_key="unused", **options)
    with pytest.raises(ValueError):
        t.transcribe_batch(tmp_path, **options)


@pytest.mark.parametrize("builder,positional", [(t.build_transcribe_parser, "clip.mp4"),
                                                (t.build_transcribe_batch_parser, "clips")])
@pytest.mark.parametrize("count", ["0", "-1"])
def test_cli_rejects_nonpositive_speaker_count(builder, positional, count):
    with pytest.raises(SystemExit):
        builder().parse_args([positional, "--num-speakers", count])


def test_valid_options_reach_media_inspection(monkeypatch, tmp_path):
    monkeypatch.setattr(t, "count_audio_tracks", lambda _: 0)
    with pytest.raises(RuntimeError, match="no audio streams"):
        t.transcribe_one(tmp_path / "missing.mp4", edit_dir=tmp_path, api_key="unused", audio_track=0, num_speakers=2)
