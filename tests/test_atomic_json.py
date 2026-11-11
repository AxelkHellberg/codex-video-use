import json
import os
from pathlib import Path
import stat

import pytest

from codex_video_use.utils import write_json


@pytest.mark.parametrize("existing", [False, True])
def test_failed_flush_preserves_previous_json(tmp_path: Path, monkeypatch, existing: bool) -> None:
    output = tmp_path / "transcript.json"
    old = '{"text": "previous complete transcript"}\n'
    if existing:
        output.write_text(old, encoding="utf-8")

    def failed_fsync(_fd):
        raise OSError("simulated storage failure")

    monkeypatch.setattr(os, "fsync", failed_fsync)
    with pytest.raises(OSError, match="simulated storage failure"):
        write_json(output, {"text": "new transcript"})
    assert output.read_text(encoding="utf-8") == old if existing else not output.exists()
    assert list(tmp_path.iterdir()) == ([output] if existing else [])


def test_readers_see_complete_old_json_until_replace(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "checkpoint.json"
    output.write_text('{"last_synced_sha": "old"}\n', encoding="utf-8")
    original_replace = os.replace
    observed = []

    def checked_replace(source, target):
        observed.append(json.loads(output.read_text(encoding="utf-8")))
        assert json.loads(Path(source).read_text(encoding="utf-8")) == {"last_synced_sha": "new"}
        original_replace(source, target)

    monkeypatch.setattr(os, "replace", checked_replace)
    write_json(output, {"last_synced_sha": "new"})
    assert observed == [{"last_synced_sha": "old"}]
    assert json.loads(output.read_text(encoding="utf-8")) == {"last_synced_sha": "new"}
    assert list(tmp_path.iterdir()) == [output]


def test_failed_replace_preserves_previous_file(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "transcript.json"
    output.write_text('{"text": "old"}\n', encoding="utf-8")

    def failed_replace(*_args):
        raise OSError("simulated replacement failure")

    monkeypatch.setattr(os, "replace", failed_replace)
    with pytest.raises(OSError, match="simulated replacement failure"):
        write_json(output, {"text": "new"})
    assert json.loads(output.read_text()) == {"text": "old"}
    assert list(tmp_path.iterdir()) == [output]


def test_replacement_retains_permissions_and_symlink_target(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    target.chmod(0o640)
    link = tmp_path / "cache.json"
    link.symlink_to(target)
    write_json(link, {"text": "café"})
    assert link.is_symlink()
    assert json.loads(target.read_text(encoding="utf-8")) == {"text": "café"}
    assert stat.S_IMODE(target.stat().st_mode) == 0o640


def test_unserializable_value_leaves_previous_file_intact(tmp_path: Path) -> None:
    output = tmp_path / "cache.json"
    output.write_text("{}\n", encoding="utf-8")
    with pytest.raises(TypeError):
        write_json(output, {"bad": object()})
    assert output.read_text(encoding="utf-8") == "{}\n"
    assert list(tmp_path.iterdir()) == [output]
