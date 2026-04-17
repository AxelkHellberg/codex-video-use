from __future__ import annotations

import argparse
from pathlib import Path

from .utils import run


GRADE_PRESETS = {
    "neutral": "eq=contrast=1.04:saturation=1.02:brightness=0.01",
    "cinematic-warm": "eq=contrast=1.07:saturation=0.96:brightness=0.01,colorbalance=rs=.02:gs=-.01:bs=-.02",
    "clean-social": "eq=contrast=1.03:saturation=1.08:gamma=1.02",
}


def resolve_filter(name_or_filter: str | None) -> str:
    if not name_or_filter:
        return ""
    return GRADE_PRESETS.get(name_or_filter, name_or_filter)


def apply_grade(input_path: Path, output_path: Path, *, filter_string: str) -> Path:
    vf = resolve_filter(filter_string)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
    ]
    if vf:
        command += ["-vf", vf]
    command += [
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy",
        str(output_path),
    ]
    run(command)
    print(f"graded -> {output_path}")
    return output_path


def build_grade_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply a grading filter or preset to a clip.")
    parser.add_argument("input_path", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=False, default=None)
    parser.add_argument("--filter", type=str, default="neutral")
    parser.add_argument("--list-presets", action="store_true")
    return parser

