from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from codex_video_use import rendering
from codex_video_use.utils import ffprobe_json, run


def make_edl(edit_dir: Path, source: Path) -> Path:
    edl = edit_dir / 'edl.json'
    edl.write_text(json.dumps({'sources': {'clip': str(source)},
        'segments': [{'source': 'clip', 'start': 0, 'end': 0.4}]}))
    return edl


@pytest.mark.skipif(shutil.which('ffmpeg') is None, reason='ffmpeg required')
@pytest.mark.parametrize('no_normalize', [False, True])
def test_render_preserves_files_named_like_its_intermediates(tmp_path, monkeypatch, no_normalize):
    # A previous export can legitimately be the next edit's source.
    source = tmp_path / 'base-preview.mp4'
    run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=red:s=96x64:r=25',
         '-f', 'lavfi', '-i', 'sine=frequency=600:sample_rate=48000', '-t', '0.5',
         '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(source)], quiet=True)
    output = tmp_path / 'out.mp4'
    clip = tmp_path / 'clips-preview' / 'segment-000.mp4'
    clip.parent.mkdir()
    clip.write_bytes(b'an unrelated saved clip')
    concat = tmp_path / '_concat.txt'
    concat.write_bytes(b'a saved concat manifest')
    prenorm = tmp_path / 'out.prenorm.mp4'
    prenorm.write_bytes(b'an unrelated output')
    protected = [source, clip, concat, prenorm]
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    monkeypatch.setattr(rendering, '_target_canvas', lambda *_args, **_kwargs: (96, 64))

    rendering.render_edl(make_edl(tmp_path, source), output_path=output,
                         preview=True, no_subtitles=True, no_normalize=no_normalize)

    assert {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in protected} == before
    assert {s['codec_type'] for s in ffprobe_json(output)['streams']} == {'video', 'audio'}
    assert not list(tmp_path.glob('.render-*'))


def test_failed_render_preserves_previous_output_and_cleans_workspace(tmp_path, monkeypatch):
    output = tmp_path / 'out.mp4'
    output.write_bytes(b'previous complete export')
    monkeypatch.setattr(rendering, '_probe_source_fps', lambda _: '25')
    def extract(_source, **kwargs):
        Path(kwargs['output_path']).write_bytes(b'clip')
        return Path(kwargs['output_path'])
    monkeypatch.setattr(rendering, 'extract_segment', extract)
    monkeypatch.setattr(rendering, 'concat_segments', lambda _paths, base, _edit: base.write_bytes(b'base') or base)
    def broken_composite(_base, **kwargs):
        Path(kwargs['output_path']).write_bytes(b'incomplete export')
        raise RuntimeError('encoder failed')
    monkeypatch.setattr(rendering, 'composite_output', broken_composite)

    with pytest.raises(RuntimeError, match='encoder failed'):
        rendering.render_edl(make_edl(tmp_path, tmp_path / 'source.mp4'), output_path=output,
                             no_subtitles=True, no_normalize=True)

    assert output.read_bytes() == b'previous complete export'
    assert not list(tmp_path.glob('.render-*'))
