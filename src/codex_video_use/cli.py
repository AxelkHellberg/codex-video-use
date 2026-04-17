from __future__ import annotations

from pathlib import Path

from .grading import GRADE_PRESETS, apply_grade, build_grade_parser
from .packing import build_pack_parser, pack_edit_dir
from .rendering import build_render_parser, render_edl
from .syncer import build_sync_parser, run_sync_cli
from .timeline import build_timeline_parser, render_timeline_image
from .transcription import (
    build_transcribe_batch_parser,
    build_transcribe_parser,
    resolve_api_key,
    transcribe_batch,
    transcribe_one,
)


def transcribe_main() -> int:
    args = build_transcribe_parser().parse_args()
    source = args.source.resolve()
    edit_dir = (args.edit_dir or (source.parent / "edit")).resolve()
    api_key = resolve_api_key(source.parent)
    transcribe_one(
        source,
        edit_dir=edit_dir,
        api_key=api_key,
        language=args.language,
        num_speakers=args.num_speakers,
    )
    return 0


def transcribe_batch_main() -> int:
    args = build_transcribe_batch_parser().parse_args()
    transcribe_batch(
        args.directory,
        edit_dir=args.edit_dir,
        language=args.language,
        num_speakers=args.num_speakers,
        workers=args.workers,
    )
    return 0


def pack_main() -> int:
    args = build_pack_parser().parse_args()
    pack_edit_dir(args.edit_dir, silence_threshold=args.silence_threshold, output=args.output)
    return 0


def timeline_main() -> int:
    args = build_timeline_parser().parse_args()
    output_path = args.output or (Path.cwd() / "timeline.png")
    render_timeline_image(
        args.video.resolve(),
        args.start,
        args.end,
        output_path=output_path.resolve(),
        transcript_path=args.transcript.resolve() if args.transcript else None,
        frame_count=args.frames,
    )
    return 0


def render_main() -> int:
    args = build_render_parser().parse_args()
    render_edl(
        args.edl.resolve(),
        output_path=args.output.resolve(),
        preview=args.preview,
        build_subtitles_flag=args.build_subtitles,
        no_subtitles=args.no_subtitles,
        no_normalize=args.no_normalize,
    )
    return 0


def grade_main() -> int:
    args = build_grade_parser().parse_args()
    if args.list_presets:
        for name, value in GRADE_PRESETS.items():
            print(f"{name}: {value}")
        return 0
    output = args.output or args.input_path.with_name(f"{args.input_path.stem}.graded{args.input_path.suffix}")
    apply_grade(args.input_path.resolve(), output.resolve(), filter_string=args.filter)
    return 0


def sync_main() -> int:
    return run_sync_cli(build_sync_parser().parse_args())
