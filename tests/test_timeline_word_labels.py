from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw
import pytest

from codex_video_use import timeline


def _render_word(tmp_path: Path, monkeypatch, *, start: float, end: float) -> Image.Image:
    def fake_frames(_video, _start, _end, _count, temp_dir):
        frame = temp_dir / "frame.png"
        Image.new("RGB", (300, 180), "black").save(frame)
        return [frame]

    monkeypatch.setattr(timeline, "_extract_frames", fake_frames)
    monkeypatch.setattr(timeline, "_extract_waveform", lambda *_args: np.zeros(5))
    transcript = tmp_path / "transcript.json"
    transcript.write_text(
        json.dumps({"words": [{"type": "word", "text": "HELLO", "start": start, "end": end}]}),
        encoding="utf-8",
    )
    output = tmp_path / "timeline.png"
    timeline.render_timeline_image(
        tmp_path / "clip.mp4", 5.0, 6.0,
        output_path=output, transcript_path=transcript, frame_count=1,
    )
    with Image.open(output) as image:
        return image.crop((0, 454, image.width, 490))


@pytest.mark.parametrize(
    ("word_start", "expected_x"), [(0.0, 40), (4.9, 40), (5.0, 40), (5.5, 190)],
)
def test_overlapping_word_labels_remain_visible(tmp_path, monkeypatch, word_start, expected_x):
    label_region = _render_word(tmp_path, monkeypatch, start=word_start, end=5.8)

    expected = Image.new("RGB", label_region.size, timeline.BG)
    ImageDraw.Draw(expected).text(
        (expected_x, 0), "HELLO", fill=timeline.ACCENT, font=timeline._font(12),
    )
    assert ImageChops.difference(label_region, expected).getbbox() is None


@pytest.mark.parametrize(("word_start", "word_end"), [(0.0, 5.0), (6.0, 6.5)])
def test_words_outside_the_interval_have_no_label(tmp_path, monkeypatch, word_start, word_end):
    label_region = _render_word(tmp_path, monkeypatch, start=word_start, end=word_end)

    expected = Image.new("RGB", label_region.size, timeline.BG)
    assert ImageChops.difference(label_region, expected).getbbox() is None
