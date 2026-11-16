from __future__ import annotations

from pathlib import Path

import pytest

from codex_video_use.cli import pack_main
from codex_video_use.packing import group_words, pack_edit_dir


INVALID_THRESHOLDS = [float("nan"), float("inf"), float("-inf"), -0.1, True, None, "0.5"]


@pytest.mark.parametrize("threshold", INVALID_THRESHOLDS)
@pytest.mark.parametrize("words", [[], [
    {"type": "word", "text": "first", "start": 0.0, "end": 0.2},
    {"type": "word", "text": "later", "start": 5.0, "end": 5.2},
]])
def test_group_words_rejects_invalid_threshold_even_without_words(threshold, words) -> None:
    with pytest.raises(ValueError, match="finite non-negative number"):
        group_words(words, silence_threshold=threshold)


@pytest.mark.parametrize("threshold", INVALID_THRESHOLDS)
def test_pack_rejects_invalid_threshold_before_reading_or_replacing_output(
    tmp_path: Path, threshold
) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    (transcripts / "clip.json").write_text("not JSON", encoding="utf-8")
    output = tmp_path / "takes_packed.md"
    output.write_text("keep the existing packed transcript", encoding="utf-8")

    with pytest.raises(ValueError, match="finite non-negative number"):
        pack_edit_dir(tmp_path, silence_threshold=threshold)

    assert output.read_text(encoding="utf-8") == "keep the existing packed transcript"


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "-0.1", "not-a-number"])
def test_pack_cli_rejects_invalid_threshold_with_usage_error(monkeypatch, capsys, value) -> None:
    monkeypatch.setattr("sys.argv", [
        "codex-video-use-pack", "--edit-dir", "missing", f"--silence-threshold={value}",
    ])

    with pytest.raises(SystemExit) as error:
        pack_main()

    assert error.value.code == 2
    assert "--silence-threshold" in capsys.readouterr().err


def test_zero_threshold_is_supported_and_positive_threshold_preserves_short_gaps() -> None:
    words = [
        {"type": "word", "text": "first", "start": 0.0, "end": 0.2},
        {"type": "word", "text": "second", "start": 0.3, "end": 0.5},
        {"type": "word", "text": "later", "start": 5.0, "end": 5.2},
    ]

    assert [phrase["text"] for phrase in group_words(words, silence_threshold=0)] == [
        "first", "second", "later",
    ]
    assert [phrase["text"] for phrase in group_words(words, silence_threshold=0.5)] == [
        "first second", "later",
    ]
