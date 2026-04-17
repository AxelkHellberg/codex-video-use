from __future__ import annotations

from pathlib import Path

from codex_video_use.packing import group_words, pack_edit_dir
from codex_video_use.utils import load_json


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_group_words_breaks_on_silence_and_speaker_change() -> None:
    payload = load_json(FIXTURE_DIR / "transcript_sample.json")
    phrases = group_words(payload["words"], silence_threshold=0.5)
    assert len(phrases) == 2
    assert phrases[0]["text"] == "Hello world"
    assert phrases[0]["speaker"] == "0"
    assert phrases[1]["text"] == "Next line"
    assert phrases[1]["speaker"] == "1"


def test_pack_edit_dir_writes_markdown(tmp_path: Path) -> None:
    edit_dir = tmp_path / "edit"
    transcripts_dir = edit_dir / "transcripts"
    transcripts_dir.mkdir(parents=True)
    fixture = FIXTURE_DIR / "transcript_sample.json"
    (transcripts_dir / "clip_001.json").write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
    output = pack_edit_dir(edit_dir)
    text = output.read_text(encoding="utf-8")
    assert "clip_001" in text
    assert "Hello world" in text

