from __future__ import annotations

import argparse
import json
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
    monkeypatch.setattr(rendering, "_display_dimensions", lambda _: (1920, 1080))

    vf = rendering._video_filters(Path("/tmp/clip.mp4"), preview=True, grade="neutral")

    assert vf.startswith(rendering.HDR_TONEMAP_FILTER)
    assert "scale=1280:720:force_original_aspect_ratio=decrease" in vf
    assert "pad=1280:720:(ow-iw)/2:(oh-ih)/2" in vf
    assert "eq=saturation=1.05" in vf
    assert vf.endswith("eq=saturation=1.05")


def test_fit_filter_uses_vertical_canvas_for_portrait_sources(monkeypatch) -> None:
    monkeypatch.setattr(rendering, "_display_dimensions", lambda _: (1080, 1920))

    preview_filter = rendering._fit_filter(Path("/tmp/portrait.mp4"), preview=True)
    final_filter = rendering._fit_filter(Path("/tmp/portrait.mp4"), preview=False)

    assert preview_filter == (
        "scale=720:1280:force_original_aspect_ratio=decrease,"
        "pad=720:1280:(ow-iw)/2:(oh-ih)/2"
    )
    assert final_filter == (
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
    )


def test_fit_filter_defaults_to_landscape_when_probe_has_no_dimensions(monkeypatch) -> None:
    monkeypatch.setattr(rendering, "_display_dimensions", lambda _: (0, 0))

    preview_filter = rendering._fit_filter(Path("/tmp/unknown.mp4"), preview=True)

    assert preview_filter == (
        "scale=1280:720:force_original_aspect_ratio=decrease,"
        "pad=1280:720:(ow-iw)/2:(oh-ih)/2"
    )


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


def test_target_canvas_uses_display_rotation_side_data(monkeypatch) -> None:
    def fake_run(command: list[str], **_: object) -> CompletedProcess[str]:
        payload = {
            "streams": [
                {
                    "width": 1920,
                    "height": 1080,
                    "side_data_list": [{"rotation": -90}],
                }
            ]
        }
        return CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(rendering, "run", fake_run)

    assert rendering._target_canvas(Path("/tmp/rotated.mp4"), preview=True) == (720, 1280)


def test_parse_fps_accepts_and_canonicalizes_common_values() -> None:
    assert rendering._parse_fps_arg("60") == "60/1"
    assert rendering._parse_fps_arg("29.97") == "2997/100"
    assert rendering._parse_fps_arg("30000/1001") == "30000/1001"


def test_parse_fps_rejects_invalid_values() -> None:
    for candidate in ("", "0", "-24", "1/0", "abc", "1e3", "1" * 33):
        try:
            rendering._parse_fps_arg(candidate)
        except argparse.ArgumentTypeError:
            continue
        raise AssertionError(f"expected argparse.ArgumentTypeError for {candidate!r}")


def test_render_edl_reuses_one_source_fps_for_every_segment(tmp_path: Path, monkeypatch) -> None:
    edit_dir = tmp_path / "edit"
    edit_dir.mkdir()
    output_path = edit_dir / "preview.mp4"
    edl_path = edit_dir / "edl.json"
    edl_path.write_text(
        json.dumps(
            {
                "sources": {"first": "first.mp4", "second": "second.mp4"},
                "segments": [
                    {"source": "first", "start": 0.0, "end": 1.0},
                    {"source": "second", "start": 1.0, "end": 2.0},
                ],
                "overlays": [],
            }
        ),
        encoding="utf-8",
    )

    issued_fps: list[str | None] = []

    def fake_extract_segment(source_path: Path, **kwargs: object) -> Path:
        issued_fps.append(kwargs.get("output_fps"))
        rendered = Path(kwargs["output_path"])
        rendered.parent.mkdir(parents=True, exist_ok=True)
        rendered.write_bytes(b"")
        return rendered

    monkeypatch.setattr(rendering, "_probe_source_fps", lambda _: "30000/1001")
    monkeypatch.setattr(rendering, "extract_segment", fake_extract_segment)
    monkeypatch.setattr(rendering, "concat_segments", lambda _segments, base, _edit: base.write_bytes(b"") or base)
    monkeypatch.setattr(
        rendering,
        "composite_output",
        lambda _base, **kwargs: Path(kwargs["output_path"]).write_bytes(b"") or Path(kwargs["output_path"]),
    )

    rendering.render_edl(edl_path, output_path=output_path, no_normalize=True)

    assert issued_fps == ["30000/1001", "30000/1001"]
