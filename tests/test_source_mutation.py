from __future__ import annotations

import json
import os

import pytest

from codex_video_use import transcription as t


@pytest.mark.parametrize('phase', ['extract', 'request', 'duration'])
@pytest.mark.parametrize('mutation', ['rewrite', 'replace', 'remove'])
def test_changed_source_does_not_replace_previous_transcript(tmp_path, monkeypatch, phase, mutation):
    source = tmp_path / 'clip.mp4'
    source.write_bytes(b'original')
    original_stat = source.stat()
    edit_dir = tmp_path / 'edit'
    output = t.transcript_path(edit_dir, source)
    output.write_text('{"previous":"retained"}')
    previous = output.read_bytes()
    calls = []

    def mutate():
        if mutation == 'rewrite':
            source.write_bytes(b'modified')
            # A same-size rewrite with restored mtime must also be detected.
            os.utime(source, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
        elif mutation == 'replace':
            replacement = tmp_path / 'replacement.mp4'
            replacement.write_bytes(b'original')
            os.utime(replacement, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
            replacement.replace(source)
        else:
            source.unlink()

    def extract(_source, *, output_path, **_kwargs):
        output_path.write_bytes(b'wav')
        if phase == 'extract':
            mutate()

    def request(*_args, **_kwargs):
        calls.append('upload')
        if phase == 'request':
            mutate()
        return {'text': 'old words', 'words': []}

    def duration(_source):
        if phase == 'duration':
            mutate()
        return 2.0

    monkeypatch.setattr(t, 'count_audio_tracks', lambda _source: 1)
    monkeypatch.setattr(t, 'extract_audio_track', extract)
    monkeypatch.setattr(t, 'peak_dbfs', lambda _path: -12)
    monkeypatch.setattr(t, 'request_transcript', request)
    monkeypatch.setattr(t, 'media_duration', duration)
    with pytest.raises(RuntimeError, match='source changed'):
        t.transcribe_one(source, edit_dir=edit_dir, api_key='unused-test-key')
    assert output.read_bytes() == previous
    assert calls == ([] if phase == 'extract' else ['upload'])


def test_unchanged_source_saves_once_then_reuses_cache(tmp_path, monkeypatch):
    source = tmp_path / 'clip.mp4'
    source.write_bytes(b'original')
    calls = []
    monkeypatch.setattr(t, 'count_audio_tracks', lambda _source: 1)
    monkeypatch.setattr(t, 'extract_audio_track', lambda _source, *, output_path, **_kwargs: output_path.write_bytes(b'wav'))
    monkeypatch.setattr(t, 'peak_dbfs', lambda _path: -12)
    monkeypatch.setattr(t, 'media_duration', lambda _source: 2.0)
    def request(*_args, **_kwargs):
        calls.append('upload')
        return {'text': 'correct words', 'words': []}
    monkeypatch.setattr(t, 'request_transcript', request)
    first = t.transcribe_one(source, edit_dir=tmp_path / 'edit', api_key='unused-test-key')
    second = t.transcribe_one(source, edit_dir=tmp_path / 'edit', api_key='unused-test-key')
    assert first == second
    assert json.loads(first.read_text())['text'] == 'correct words'
    assert calls == ['upload']
