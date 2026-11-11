from __future__ import annotations

import pytest

from codex_video_use import cli
from codex_video_use.grading import GRADE_PRESETS


def test_list_presets_needs_no_input_or_media_work(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr('sys.argv', ['codex-video-use-grade', '--list-presets'])
    monkeypatch.setattr(cli, 'apply_grade', lambda *_a, **_k: pytest.fail('must not process media'))
    assert cli.grade_main() == 0
    assert capsys.readouterr().out.splitlines() == [f'{name}: {value}' for name, value in GRADE_PRESETS.items()]
    assert list(tmp_path.iterdir()) == []


def test_missing_grade_input_has_conditional_usage_error(monkeypatch, capsys):
    monkeypatch.setattr('sys.argv', ['codex-video-use-grade'])
    monkeypatch.setattr(cli, 'apply_grade', lambda *_a, **_k: pytest.fail('must not process media'))
    with pytest.raises(SystemExit) as exc:
        cli.grade_main()
    assert exc.value.code == 2
    assert 'input_path is required unless --list-presets is used' in capsys.readouterr().err


@pytest.mark.parametrize('explicit_output', [False, True])
def test_grade_still_resolves_input_and_output(tmp_path, monkeypatch, explicit_output):
    monkeypatch.chdir(tmp_path)
    args = ['codex-video-use-grade', 'clip.mp4', '--filter', 'neutral']
    if explicit_output:
        args += ['--output', 'custom.mp4']
    monkeypatch.setattr('sys.argv', args)
    seen = []
    monkeypatch.setattr(cli, 'apply_grade', lambda *a, **kw: seen.append((a, kw)))
    assert cli.grade_main() == 0
    assert seen == [((tmp_path / 'clip.mp4', tmp_path / ('custom.mp4' if explicit_output else 'clip.graded.mp4')),
                     {'filter_string': 'neutral'})]
