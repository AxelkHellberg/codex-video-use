from pathlib import Path

import pytest

from codex_video_use import rendering
from codex_video_use.utils import ffprobe_json, run


def test_final_normalization_accepts_silent_audio(tmp_path: Path) -> None:
    source = tmp_path / "silent.mp4"
    output = tmp_path / "normalized.mp4"
    run([
        "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=s=64x64:d=0.5",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "0.5",
        "-c:v", "libx264", "-c:a", "aac", str(source),
    ], quiet=True)
    rendering.normalize_audio(source, output, preview=False)
    assert {s["codec_type"] for s in ffprobe_json(output)["streams"]} == {"audio", "video"}
    assert ffprobe_json(output)["format"]["duration"] == ffprobe_json(source)["format"]["duration"]


def test_final_normalization_accepts_audible_audio(tmp_path: Path) -> None:
    source = tmp_path / "audible.mp4"
    output = tmp_path / "normalized.mp4"
    run([
        "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=s=64x64:d=3",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "3",
        "-c:v", "libx264", "-c:a", "aac", str(source),
    ], quiet=True)
    rendering.normalize_audio(source, output, preview=False)
    assert {s["codec_type"] for s in ffprobe_json(output)["streams"]} == {"audio", "video"}


@pytest.mark.parametrize("bad", ["-inf", "inf", "nan", None, "invalid"])
def test_unusable_measurement_uses_single_pass(monkeypatch, tmp_path, bad) -> None:
    measurement = dict(input_i="-20", input_tp="-3", input_lra="2", input_thresh="-30", target_offset="0")
    measurement["input_i"] = bad
    monkeypatch.setattr(rendering, "_measure_loudnorm", lambda _: measurement)
    commands = []
    monkeypatch.setattr(rendering, "run", lambda cmd, **kw: commands.append(cmd))
    rendering.normalize_audio(tmp_path / "in.mp4", tmp_path / "out.mp4", preview=False)
    assert len(commands) == 1
    assert "measured_I" not in commands[0][commands[0].index("-af") + 1]


def test_finite_measurements_keep_two_pass_normalization(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(rendering, "_measure_loudnorm", lambda _: dict(
        input_i="-20", input_tp="-3", input_lra="2", input_thresh="-30", target_offset="0"))
    commands = []
    monkeypatch.setattr(rendering, "run", lambda cmd, **kw: commands.append(cmd))
    rendering.normalize_audio(tmp_path / "in.mp4", tmp_path / "out.mp4", preview=False)
    assert "measured_I=-20" in commands[0][commands[0].index("-af") + 1]
