from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image
import pytest

from codex_video_use import timeline


@pytest.mark.parametrize('transcript_kind', ['none', 'missing-explicit', 'empty', 'speech'])
def test_silence_shading_requires_an_available_transcript(tmp_path, monkeypatch, transcript_kind):
    # Isolate transcript semantics from decoding; the waveform represents audio.
    frame = tmp_path / 'frame.jpg'
    Image.new('RGB', (300, 180), 'black').save(frame)
    monkeypatch.setattr(timeline, '_extract_frames', lambda *_args: [frame])
    monkeypatch.setattr(timeline, '_extract_waveform', lambda *_args: np.ones(1400))
    transcript = None
    if transcript_kind != 'none':
        transcript = tmp_path / 'transcript.json'
        if transcript_kind != 'missing-explicit':
            words = [] if transcript_kind == 'empty' else [
                {'type': 'word', 'text': 'hi', 'start': 0, 'end': 0.8}]
            transcript.write_text(json.dumps({'words': words}))
    output = tmp_path / 'timeline.png'

    timeline.render_timeline_image(tmp_path / 'video.mp4', 0, 2, output_path=output,
                                   transcript_path=transcript, frame_count=1)

    with Image.open(output) as image:
        # Sample inside the inferred end gap, away from the waveform and border.
        color = image.getpixel((280, 282))
    if transcript_kind in ('none', 'missing-explicit'):
        assert color == timeline.BG
    else:
        assert color != timeline.BG
