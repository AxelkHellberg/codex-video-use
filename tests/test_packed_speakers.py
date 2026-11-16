from __future__ import annotations

import json
from pathlib import Path

import pytest

from codex_video_use.packing import group_words, pack_edit_dir


def word(text: str, start: float, speaker: str | None = None) -> dict:
    result = {'text': text, 'start': start, 'end': start + 0.2, 'type': 'word'}
    if speaker is not None:
        result['speaker_id'] = speaker
    return result


@pytest.mark.parametrize('speakers', [('speaker_0', None), (None, 'speaker_0')])
def test_known_and_unknown_speech_have_separate_phrases(speakers: tuple) -> None:
    phrases = group_words([word('Hello', 0, speakers[0]), word('there', 0.2, speakers[1])])
    assert [p['text'] for p in phrases] == ['Hello', 'there']
    assert [p['speaker'] for p in phrases] == [s.removeprefix('speaker_') if s else None for s in speakers]
    assert [(p['start'], p['end']) for p in phrases] == [(0, 0.2), (0.2, 0.4)]


def test_unknown_speech_is_not_attributed_to_neighboring_known_speaker() -> None:
    phrases = group_words([word('One', 0, 'speaker_0'), word('unknown', 0.2), word('two', 0.4, 'speaker_0')])
    assert [p['speaker'] for p in phrases] == ['0', None, '0']
    assert [p['text'] for p in phrases] == ['One', 'unknown', 'two']


def test_unattributed_audio_event_does_not_inherit_speech_speaker() -> None:
    event = {**word('laughter', 0.2), 'type': 'audio_event'}
    phrases = group_words([word('Hello', 0, 'speaker_1'), event])
    assert [(p['speaker'], p['text']) for p in phrases] == [('1', 'Hello'), (None, '(laughter)')]


@pytest.mark.parametrize('speaker', [None, 'speaker_0'])
def test_equal_speakers_remain_grouped(speaker: str | None) -> None:
    phrases = group_words([word('Hello', 0, speaker), word('world', 0.2, speaker)])
    assert len(phrases) == 1
    assert phrases[0]['text'] == 'Hello world'


def test_packed_markdown_does_not_label_unknown_words_as_known_speech(tmp_path: Path) -> None:
    transcripts = tmp_path / 'transcripts'
    transcripts.mkdir()
    (transcripts / 'take.json').write_text(json.dumps({'words': [
        word('Known', 0, 'speaker_0'), word('Unknown', 0.2), word('Other', 0.4, 'speaker_1'),
    ]}))
    output = pack_edit_dir(tmp_path).read_text()
    assert '[000.00-000.20] S0 Known' in output
    assert '[000.20-000.40] Unknown' in output
    assert '[000.40-000.60] S1 Other' in output
