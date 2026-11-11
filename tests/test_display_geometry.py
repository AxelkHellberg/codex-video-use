from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from codex_video_use import rendering
from codex_video_use.utils import run


@pytest.mark.parametrize('sar,dimensions', [('2/1', (240, 120)), ('1/2', (60, 120)), ('1/1', (120, 120))])
def test_display_dimensions_include_sample_aspect_ratio(monkeypatch, sar, dimensions):
    monkeypatch.setattr(rendering, '_probe_primary_video_stream', lambda *_args, **_kwargs:
                        {'width': 120, 'height': 120, 'sample_aspect_ratio': sar})
    assert rendering._display_dimensions(Path('source.mp4')) == dimensions


def test_rotation_applies_after_pixel_aspect_ratio(monkeypatch):
    monkeypatch.setattr(rendering, '_probe_primary_video_stream', lambda *_args, **_kwargs:
                        {'width': 120, 'height': 120, 'sample_aspect_ratio': '2:1',
                         'side_data_list': [{'rotation': -90}]})
    assert rendering._display_dimensions(Path('source.mp4')) == (120, 240)


@pytest.mark.skipif(shutil.which('ffmpeg') is None, reason='ffmpeg required')
@pytest.mark.parametrize('sar,white_size', [('2/1', (96, 48)), ('1/2', (32, 64)), ('1/1', (64, 64))])
def test_anamorphic_render_has_square_pixels_without_stretch(tmp_path, monkeypatch, sar, white_size):
    source = tmp_path / 'source.mp4'
    output = tmp_path / 'output.mp4'
    run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=white:s=120x120:r=5',
         '-vf', f'setsar={sar}', '-t', '0.4', '-c:v', 'libx264', str(source)], quiet=True)
    monkeypatch.setattr(rendering, '_target_canvas', lambda *_args, **_kwargs: (96, 64))
    rendering.extract_segment(source, start=0, end=0.4, grade=None, output_path=output,
                              preview=True, output_fps='5')
    info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                      '-show_entries', 'stream=width,height,sample_aspect_ratio', '-of', 'json', str(output)]))
    assert info['streams'] == [{'width': 96, 'height': 64, 'sample_aspect_ratio': '1:1'}]
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(output), '-frames:v', '1',
                                   '-f', 'rawvideo', '-pix_fmt', 'gray', '-'])
    frame = np.frombuffer(raw, np.uint8).reshape(64, 96)
    ys, xs = np.where(frame > 200)
    assert (int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)) == white_size
