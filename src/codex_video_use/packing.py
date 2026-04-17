from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .utils import load_json


def _speaker_label(word: dict[str, Any]) -> str | None:
    speaker = word.get("speaker_id")
    if speaker is None:
        return None
    text = str(speaker)
    return text.removeprefix("speaker_")


def _flush_phrase(bucket: list[dict[str, Any]], speaker: str | None) -> dict[str, Any] | None:
    if not bucket:
        return None
    start = float(bucket[0]["start"])
    end = float(bucket[-1]["end"])
    parts: list[str] = []
    for word in bucket:
        raw = str(word.get("text", "")).strip()
        if not raw:
            continue
        if word.get("type") == "audio_event" and not raw.startswith("("):
            raw = f"({raw})"
        parts.append(raw)
    if not parts:
        return None
    text = " ".join(parts).replace(" ,", ",").replace(" .", ".")
    return {"start": start, "end": end, "speaker": speaker, "text": text}


def group_words(words: list[dict[str, Any]], *, silence_threshold: float = 0.5) -> list[dict[str, Any]]:
    phrases: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    current_speaker: str | None = None
    last_end: float | None = None

    for word in words:
        kind = word.get("type", "word")
        if kind == "spacing":
            gap = float(word.get("end", 0.0)) - float(word.get("start", 0.0))
            if gap >= silence_threshold:
                flushed = _flush_phrase(current, current_speaker)
                if flushed:
                    phrases.append(flushed)
                current = []
                current_speaker = None
            continue

        speaker = _speaker_label(word)
        start = float(word.get("start", 0.0))
        if current and last_end is not None and start - last_end >= silence_threshold:
            flushed = _flush_phrase(current, current_speaker)
            if flushed:
                phrases.append(flushed)
            current = []
            current_speaker = None
        if current and speaker is not None and current_speaker is not None and speaker != current_speaker:
            flushed = _flush_phrase(current, current_speaker)
            if flushed:
                phrases.append(flushed)
            current = []
        if not current:
            current_speaker = speaker
        current.append(word)
        last_end = float(word.get("end", start))

    flushed = _flush_phrase(current, current_speaker)
    if flushed:
        phrases.append(flushed)
    return phrases


def format_clock(seconds: float) -> str:
    return f"{seconds:06.2f}"


def render_packed_markdown(items: list[tuple[str, float, list[dict[str, Any]]]], *, silence_threshold: float) -> str:
    lines = [
        "# Packed transcripts",
        "",
        f"Grouped on silence gaps >= {silence_threshold:.2f}s and speaker switches.",
        "",
    ]
    for name, duration, phrases in items:
        lines.append(f"## {name}  (duration: {duration:.1f}s, {len(phrases)} phrases)")
        if not phrases:
            lines.append("  _no transcripted speech_")
            lines.append("")
            continue
        for phrase in phrases:
            speaker = f" S{phrase['speaker']}" if phrase.get("speaker") is not None else ""
            lines.append(f"  [{format_clock(phrase['start'])}-{format_clock(phrase['end'])}]{speaker} {phrase['text']}")
        lines.append("")
    return "\n".join(lines)


def pack_edit_dir(edit_dir: Path, *, silence_threshold: float = 0.5, output: Path | None = None) -> Path:
    transcripts_dir = edit_dir.resolve() / "transcripts"
    transcript_files = sorted(transcripts_dir.glob("*.json"))
    if not transcript_files:
        raise SystemExit(f"no transcripts found in {transcripts_dir}")
    items = []
    for path in transcript_files:
        payload = load_json(path)
        phrases = group_words(payload.get("words", []), silence_threshold=silence_threshold)
        duration = float(payload.get("duration_seconds") or (phrases[-1]["end"] if phrases else 0.0))
        items.append((path.stem, duration, phrases))
    destination = output or (edit_dir / "takes_packed.md")
    destination.write_text(
        render_packed_markdown(items, silence_threshold=silence_threshold) + "\n",
        encoding="utf-8",
    )
    print(f"packed transcripts -> {destination}")
    return destination


def build_pack_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pack transcript JSON files into a compact markdown view.")
    parser.add_argument("--edit-dir", type=Path, required=True)
    parser.add_argument("--silence-threshold", type=float, default=0.5)
    parser.add_argument("-o", "--output", type=Path, default=None)
    return parser

