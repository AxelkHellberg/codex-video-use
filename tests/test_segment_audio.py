from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from codex_video_use import rendering
from codex_video_use.utils import run

pytestmark = pytest.mark.skipif(shutil.which('ffmpeg') is None, reason='ffmpeg required')


def make_source(path: Path, channels: int | None) -> None:
    command = ['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=black:s=96x64:r=25']
    if channels:
        command += ['-f', 'lavfi', '-i', 'sine=frequency=600:sample_rate=48000', '-ac', str(channels)]
    command += ['-t', '0.4', '-c:v', 'libx264', '-pix_fmt', 'yuv420p']
    if channels:
        command += ['-c:a', 'aac']
    run(command + [str(path)], quiet=True)


@pytest.mark.parametrize('channels', [(None, 1), (1, None), (1, 2)])
def test_concat_has_consistent_stereo_audio_across_segment_boundaries(tmp_path, monkeypatch, channels):
    # Keep the production extraction and concatenation; only shrink the canvas.
    monkeypatch.setattr(rendering, '_target_canvas', lambda *_args, **_kwargs: (96, 64))
    clips = []
    for index, count in enumerate(channels):
        source = tmp_path / f'source-{index}.mp4'
        make_source(source, count)
        clip = tmp_path / f'clip-{index}.mp4'
        rendering.extract_segment(source, start=0, end=0.4, grade=None,
                                  output_path=clip, preview=True, output_fps='25')
        clips.append(clip)
        info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'a',
                          '-show_entries', 'stream=channels,sample_rate', '-of', 'json', str(clip)]))
        assert info['streams'] == [{'sample_rate': '48000', 'channels': 2}]
    output = tmp_path / 'joined.mp4'
    rendering.concat_segments(clips, output, tmp_path)
    decoded = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(output), '-vn', '-f', 'f32le',
                              '-ac', '1', '-ar', '48000', '-'], capture_output=True, check=True)
    pcm = np.frombuffer(decoded.stdout, dtype='<f4')
    # Allow AAC padding; sample away from fades and concat boundaries.
    assert 0.75 < len(pcm) / 48000 < 0.9
    for index, count in enumerate(channels):
        window = pcm[int((index * 0.4 + 0.12) * 48000):int((index * 0.4 + 0.28) * 48000)]
        rms = float(np.sqrt(np.mean(window ** 2)))
        assert rms > 0.02 if count else rms < 0.001
