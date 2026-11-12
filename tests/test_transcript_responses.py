from __future__ import annotations

import json
from pathlib import Path

import pytest

from codex_video_use import transcription
from codex_video_use.packing import group_words
from codex_video_use.rendering import build_master_srt


@pytest.mark.parametrize('payload', [
    None, [], 'not an object', {}, {'words': None}, {'words': {}},
    {'words': [None]}, {'words': [{'text': 'hi', 'type': 'word'}]},
    {'words': [{'text': 'hi', 'start': '0', 'end': 1}]},
    {'words': [{'text': 'hi', 'start': True, 'end': 1}]},
    {'words': [{'text': 'hi', 'start': 0, 'end': float('nan')}]},
    {'words': [{'text': 'hi', 'start': -1, 'end': 1}]},
    {'words': [{'text': 'hi', 'start': 2, 'end': 1}]},
    {'words': [{'text': None, 'start': 0, 'end': 1}]},
    {'words': [], 'text': []},
])
def test_bad_response_does_not_replace_cache(tmp_path, monkeypatch, payload):
    source = tmp_path / 'clip.mp4'
    source.write_bytes(b'current media')
    edit = tmp_path / 'edit'
    output = transcription.transcript_path(edit, source)
    old_cache = json.dumps({'source_path': 'an older source', 'text': 'keep this'})
    output.write_text(old_cache)
    monkeypatch.setattr(transcription, 'count_audio_tracks', lambda _: 1)
    monkeypatch.setattr(transcription, 'extract_audio_track', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(transcription, 'peak_dbfs', lambda _: -12)
    monkeypatch.setattr(transcription, 'media_duration', lambda _: 2)
    monkeypatch.setattr(transcription, 'request_transcript', lambda *_args, **_kwargs: payload)

    with pytest.raises(RuntimeError, match='transcription response'):
        transcription.transcribe_one(source, edit_dir=edit, api_key='unused-test-key')

    assert output.read_text() == old_cache


def test_valid_words_remain_usable_by_packing_and_subtitles(tmp_path, monkeypatch):
    source = tmp_path / 'clip.mp4'
    source.write_bytes(b'media')
    monkeypatch.setattr(transcription, 'media_duration', lambda _: 2)
    # Overlapping speakers, zero-duration spacing, and audio events are valid.
    words = [
        {'type': 'word', 'text': 'Hello', 'start': 0, 'end': 0.8, 'speaker_id': 'speaker_0'},
        {'type': 'word', 'text': 'world', 'start': 0.5, 'end': 1, 'speaker_id': 'speaker_1'},
        {'type': 'spacing', 'text': ' ', 'start': 1, 'end': 1},
        {'type': 'audio_event', 'text': 'laughing', 'start': 1, 'end': 1.5},
    ]
    payload = transcription.normalize_transcript(source, {'words': words, 'text': 'Hello world'}, audio_track=0)
    assert payload['words'] == words
    assert group_words(payload['words'])
    transcripts = tmp_path / 'transcripts'
    transcripts.mkdir()
    (transcripts / 'clip.json').write_text(json.dumps(payload))
    edl = {'sources': {'clip': str(source)}, 'segments': [{'source': 'clip', 'start': 0, 'end': 2}]}
    result = build_master_srt(edl, tmp_path, tmp_path / 'master.srt')
    assert 'HELLO' in result.read_text() and 'WORLD' in result.read_text()
    assert transcription.normalize_transcript(source, {'words': [], 'text': ''}, audio_track=0)['words'] == []
