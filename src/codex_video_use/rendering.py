from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .grading import resolve_filter
from .utils import CommandFailure, ensure_dir, load_json, run


LOUDNORM_I = -14.0
LOUDNORM_TP = -1.0
LOUDNORM_LRA = 11.0
SUBTITLE_FORCE_STYLE = (
    "FontName=Helvetica,FontSize=18,Bold=1,"
    "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
    "BorderStyle=1,Outline=2,Shadow=0,"
    "Alignment=2,MarginV=90"
)
HDR_TRANSFERS = {"smpte2084", "arib-std-b67"}
HDR_TONEMAP_FILTER = (
    "zscale=t=linear:npl=100,"
    "format=gbrpf32le,"
    "zscale=p=bt709,"
    "tonemap=tonemap=hable:desat=0,"
    "zscale=t=bt709:m=bt709:r=tv,"
    "format=yuv420p"
)


def _has_subtitles_filter() -> bool:
    try:
        result = run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, quiet=True)
    except CommandFailure:
        return False
    return " subtitles " in result.stdout


def _segment_list(edl: dict[str, Any]) -> list[dict[str, Any]]:
    if "segments" in edl:
        return list(edl["segments"])
    if "ranges" in edl:
        return [
            {
                "source": item["source"],
                "start": item["start"],
                "end": item["end"],
                "label": item.get("beat") or item.get("note") or item.get("label"),
            }
            for item in edl["ranges"]
        ]
    raise SystemExit("EDL must contain a 'segments' or 'ranges' list")




def _source_color_transfer(source_path: Path) -> str:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=color_transfer",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(source_path),
        ],
        capture_output=True,
        check=False,
        quiet=True,
    )
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


def _needs_hdr_tonemap(source_path: Path) -> bool:
    return _source_color_transfer(source_path) in HDR_TRANSFERS


def _video_filters(source_path: Path, *, preview: bool, grade: str | None) -> str:
    vf_parts = []
    if _needs_hdr_tonemap(source_path):
        vf_parts.append(HDR_TONEMAP_FILTER)
    vf_parts.append("scale=1280:-2" if preview else "scale=1920:-2")
    resolved_grade = resolve_filter(grade)
    if resolved_grade:
        vf_parts.append(resolved_grade)
    return ",".join(vf_parts)


def _source_map(edl: dict[str, Any], edit_dir: Path) -> dict[str, Path]:
    mapping = {}
    for key, value in edl["sources"].items():
        path = Path(value)
        mapping[key] = path if path.is_absolute() else (edit_dir / path).resolve()
    return mapping


def _chunk_words(words: list[dict[str, Any]], chunk_size: int = 2) -> list[list[dict[str, Any]]]:
    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for word in words:
        if word.get("type") != "word":
            continue
        current.append(word)
        if len(current) >= chunk_size or str(word.get("text", "")).strip().endswith((".", "!", "?")):
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)
    return chunks


def _srt_time(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def build_master_srt(edl: dict[str, Any], edit_dir: Path, output_path: Path) -> Path:
    segments = _segment_list(edl)
    sources = _source_map(edl, edit_dir)
    offset = 0.0
    cues: list[tuple[float, float, str]] = []
    for segment in segments:
        transcript_path = edit_dir / "transcripts" / f"{segment['source']}.json"
        if not transcript_path.exists():
            source_stem = sources[segment["source"]].stem
            transcript_path = edit_dir / "transcripts" / f"{source_stem}.json"
        if not transcript_path.exists():
            offset += float(segment["end"]) - float(segment["start"])
            continue
        payload = load_json(transcript_path)
        in_range = [
            word
            for word in payload.get("words", [])
            if word.get("type") == "word"
            and float(word.get("end", 0.0)) > float(segment["start"])
            and float(word.get("start", 0.0)) < float(segment["end"])
        ]
        for chunk in _chunk_words(in_range):
            local_start = max(float(segment["start"]), float(chunk[0]["start"]))
            local_end = min(float(segment["end"]), float(chunk[-1]["end"]))
            out_start = offset + (local_start - float(segment["start"]))
            out_end = offset + (local_end - float(segment["start"]))
            if out_end <= out_start:
                out_end = out_start + 0.35
            text = " ".join(str(item["text"]).strip() for item in chunk).upper()
            cues.append((out_start, out_end, text))
        offset += float(segment["end"]) - float(segment["start"])
    lines = []
    for index, (start, end, text) in enumerate(cues, start=1):
        lines += [str(index), f"{_srt_time(start)} --> {_srt_time(end)}", text, ""]
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"master subtitles -> {output_path}")
    return output_path


def extract_segment(
    source_path: Path,
    *,
    start: float,
    end: float,
    grade: str | None,
    output_path: Path,
    preview: bool,
) -> Path:
    duration = end - start
    fade_out_start = max(0.0, duration - 0.03)
    vf = _video_filters(source_path, preview=preview, grade=grade)
    command = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{start:.3f}",
        "-i",
        str(source_path),
        "-t",
        f"{duration:.3f}",
        "-vf",
        vf,
        "-af",
        f"afade=t=in:st=0:d=0.03,afade=t=out:st={fade_out_start:.3f}:d=0.03",
        "-c:v",
        "libx264",
        "-preset",
        "fast" if not preview else "veryfast",
        "-crf",
        "20" if not preview else "24",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "24",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        str(output_path),
    ]
    run(command, quiet=True)
    return output_path


def concat_segments(segment_paths: list[Path], output_path: Path, edit_dir: Path) -> Path:
    list_path = edit_dir / "_concat.txt"
    list_path.write_text("".join(f"file '{path.resolve()}'\n" for path in segment_paths), encoding="utf-8")
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-c",
            "copy",
            str(output_path),
        ],
        quiet=True,
    )
    list_path.unlink(missing_ok=True)
    return output_path


def _measure_loudnorm(input_path: Path) -> dict[str, Any] | None:
    result = run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-nostats",
            "-i",
            str(input_path),
            "-af",
            f"loudnorm=I={LOUDNORM_I}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}:print_format=json",
            "-vn",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        check=False,
        quiet=True,
    )
    stderr = result.stderr or ""
    start = stderr.rfind("{")
    end = stderr.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    import json

    try:
        return json.loads(stderr[start : end + 1])
    except json.JSONDecodeError:
        return None


def normalize_audio(input_path: Path, output_path: Path, *, preview: bool) -> Path:
    if preview:
        run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(input_path),
                "-c:v",
                "copy",
                "-af",
                f"loudnorm=I={LOUDNORM_I}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-ar",
                "48000",
                str(output_path),
            ],
            quiet=True,
        )
        return output_path
    measurement = _measure_loudnorm(input_path)
    if not measurement:
        return normalize_audio(input_path, output_path, preview=True)
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-c:v",
            "copy",
            "-af",
            (
                f"loudnorm=I={LOUDNORM_I}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}"
                f":measured_I={measurement['input_i']}"
                f":measured_TP={measurement['input_tp']}"
                f":measured_LRA={measurement['input_lra']}"
                f":measured_thresh={measurement['input_thresh']}"
                f":offset={measurement['target_offset']}:linear=true"
            ),
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            str(output_path),
        ],
        quiet=True,
    )
    return output_path


def _overlay_expression(value: Any, fallback: str) -> str:
    if value is None:
        return fallback
    return str(value)


def composite_output(
    base_path: Path,
    *,
    overlays: list[dict[str, Any]],
    subtitles_path: Path | None,
    output_path: Path,
    edit_dir: Path,
) -> Path:
    if subtitles_path and subtitles_path.exists() and not _has_subtitles_filter():
        print("warning: ffmpeg subtitles filter is unavailable; skipping burned subtitles in this render")
        subtitles_path = None

    if not overlays and not subtitles_path:
        run(["ffmpeg", "-y", "-i", str(base_path), "-c", "copy", str(output_path)], quiet=True)
        return output_path

    inputs = ["-i", str(base_path)]
    filter_parts: list[str] = []
    for index, overlay in enumerate(overlays, start=1):
        overlay_path = Path(overlay["file"])
        resolved = overlay_path if overlay_path.is_absolute() else (edit_dir / overlay_path).resolve()
        inputs += ["-i", str(resolved)]
        start = float(overlay["start"])
        filter_parts.append(f"[{index}:v]setpts=PTS-STARTPTS+{start}/TB[ov{index}]")

    current = "[0:v]"
    for index, overlay in enumerate(overlays, start=1):
        start = float(overlay["start"])
        duration = float(overlay["duration"])
        end = start + duration
        x = _overlay_expression(overlay.get("x"), "0")
        y = _overlay_expression(overlay.get("y"), "0")
        next_label = f"[v{index}]"
        filter_parts.append(
            f"{current}[ov{index}]overlay={x}:{y}:enable='between(t,{start:.3f},{end:.3f})'{next_label}"
        )
        current = next_label

    if subtitles_path and subtitles_path.exists():
        escaped = str(subtitles_path.resolve()).replace(":", r"\:").replace("'", r"\'")
        filter_parts.append(
            f"{current}subtitles=filename='{escaped}':force_style='{SUBTITLE_FORCE_STYLE}'[vout]"
        )
        video_label = "[vout]"
    elif overlays:
        filter_parts.append(f"{current}null[vout]")
        video_label = "[vout]"
    else:
        video_label = "[0:v]"

    run(
        [
            "ffmpeg",
            "-y",
            *inputs,
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            video_label,
            "-map",
            "0:a",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            str(output_path),
        ],
        quiet=True,
    )
    return output_path


def render_edl(
    edl_path: Path,
    *,
    output_path: Path,
    preview: bool = False,
    build_subtitles_flag: bool = False,
    no_subtitles: bool = False,
    no_normalize: bool = False,
) -> Path:
    edl_path = edl_path.resolve()
    edit_dir = edl_path.parent
    ensure_dir(output_path.resolve().parent)
    edl = load_json(edl_path)
    source_paths = _source_map(edl, edit_dir)
    segments = _segment_list(edl)
    clips_dir = ensure_dir(edit_dir / ("clips-preview" if preview else "clips"))
    rendered_segments = []
    for index, segment in enumerate(segments):
        source = source_paths[segment["source"]]
        clip_path = clips_dir / f"segment-{index:03d}.mp4"
        rendered_segments.append(
            extract_segment(
                source,
                start=float(segment["start"]),
                end=float(segment["end"]),
                grade=segment.get("grade") or edl.get("grade"),
                output_path=clip_path,
                preview=preview,
            )
        )

    base_path = edit_dir / ("base-preview.mp4" if preview else "base.mp4")
    concat_segments(rendered_segments, base_path, edit_dir)

    subtitles_path: Path | None = None
    if not no_subtitles:
        if build_subtitles_flag:
            subtitles_path = build_master_srt(edl, edit_dir, edit_dir / "master.srt")
        elif "subtitles" in edl:
            candidate = Path(edl["subtitles"])
            subtitles_path = candidate if candidate.is_absolute() else (edit_dir / candidate).resolve()

    overlays = list(edl.get("overlays") or [])
    prenorm_path = output_path if no_normalize else output_path.with_suffix(".prenorm.mp4")
    composite_output(base_path, overlays=overlays, subtitles_path=subtitles_path, output_path=prenorm_path, edit_dir=edit_dir)
    if no_normalize:
        return output_path
    normalize_audio(prenorm_path, output_path, preview=preview)
    prenorm_path.unlink(missing_ok=True)
    return output_path


def build_render_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render an edit decision list into a preview or final output.")
    parser.add_argument("edl", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--build-subtitles", action="store_true")
    parser.add_argument("--no-subtitles", action="store_true")
    parser.add_argument("--no-normalize", action="store_true")
    return parser
