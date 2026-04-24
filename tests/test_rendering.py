from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

import codex_video_use.rendering as rendering


def test_source_color_transfer_reads_ffprobe(monkeypatch) -> None:
    seen: dict[str, list[str]] = {}

    def fake_run(command: list[str], **_: object) -> CompletedProcess[str]:
        seen["command"] = command
        return CompletedProcess(command, 0, stdout="arib-std-b67\n", stderr="")

    monkeypatch.setattr(rendering, "run", fake_run)

    color_transfer = rendering._source_color_transfer(Path("/tmp/clip.mp4"))

    assert color_transfer == "arib-std-b67"
    assert seen["command"][:5] == ["ffprobe", "-v", "error", "-select_streams", "v:0"]


def test_video_filters_tonemap_hdr_sources(monkeypatch) -> None:
    monkeypatch.setattr(rendering, "_needs_hdr_tonemap", lambda _: True)
    monkeypatch.setattr(rendering, "resolve_filter", lambda _grade: "eq=saturation=1.05")

    vf = rendering._video_filters(Path("/tmp/clip.mp4"), preview=True, grade="neutral")

    assert vf.startswith(rendering.HDR_TONEMAP_FILTER)
    assert "scale=1280:-2" in vf
    assert vf.endswith("eq=saturation=1.05")


def test_composite_output_uses_vertical_safe_subtitle_margin(tmp_path: Path, monkeypatch) -> None:
    issued_commands: list[list[str]] = []

    def fake_run(command: list[str], **_: object) -> CompletedProcess[str]:
        issued_commands.append(command)
        return CompletedProcess(command, 0, stdout="", stderr="")

    subtitles_path = tmp_path / "master.srt"
    subtitles_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nHELLO\n", encoding="utf-8")

    monkeypatch.setattr(rendering, "_has_subtitles_filter", lambda: True)
    monkeypatch.setattr(rendering, "run", fake_run)

    rendering.composite_output(
        tmp_path / "base.mp4",
        overlays=[],
        subtitles_path=subtitles_path,
        output_path=tmp_path / "out.mp4",
        edit_dir=tmp_path,
    )

    filter_complex = issued_commands[0][issued_commands[0].index("-filter_complex") + 1]
    assert "MarginV=90" in filter_complex
