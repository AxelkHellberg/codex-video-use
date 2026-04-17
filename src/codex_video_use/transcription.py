from __future__ import annotations

import argparse
import mimetypes
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import requests

from .utils import ensure_dir, load_env_value, media_duration, now_iso, write_json


TRANSCRIBE_URL = "https://api.elevenlabs.io/v1/speech-to-text"
DEFAULT_MODEL = "scribe_v2"
MEDIA_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".webm",
    ".mp3",
    ".wav",
    ".m4a",
    ".aac",
    ".flac",
}


def resolve_api_key(search_root: Path | None = None) -> str:
    value = load_env_value("ELEVENLABS_API_KEY", search_root=search_root)
    if not value:
        raise SystemExit("ELEVENLABS_API_KEY not found in .env or environment")
    return value


def transcript_path(edit_dir: Path, source: Path) -> Path:
    return ensure_dir(edit_dir / "transcripts") / f"{source.stem}.json"


def transcript_is_current(output_path: Path, source: Path) -> bool:
    if not output_path.exists():
        return False
    try:
        payload = output_path.read_text(encoding="utf-8")
    except OSError:
        return False
    if not payload:
        return False
    import json

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return False
    return (
        data.get("source_path") == str(source.resolve())
        and data.get("source_size") == source.stat().st_size
        and data.get("source_mtime_ns") == source.stat().st_mtime_ns
    )


def request_transcript(
    source: Path,
    *,
    api_key: str,
    language: str | None = None,
    num_speakers: int | None = None,
    model_id: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    data: dict[str, str] = {
        "model_id": model_id,
        "timestamps_granularity": "word",
        "diarize": "true",
        "tag_audio_events": "true",
    }
    if language:
        data["language_code"] = language
    if num_speakers:
        data["num_speakers"] = str(num_speakers)
    mime = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    with source.open("rb") as handle:
        response = requests.post(
            TRANSCRIBE_URL,
            headers={"xi-api-key": api_key},
            files={"file": (source.name, handle, mime)},
            data=data,
            timeout=3600,
        )
    if response.status_code != 200:
        raise RuntimeError(f"ElevenLabs returned {response.status_code}: {response.text[:500]}")
    return response.json()


def normalize_transcript(source: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if "transcripts" in payload:
        raise RuntimeError("multichannel transcripts are not supported in this workflow")
    words = payload.get("words", [])
    return {
        "engine": "elevenlabs-scribe",
        "model": DEFAULT_MODEL,
        "created_at": now_iso(),
        "source_path": str(source.resolve()),
        "source_size": source.stat().st_size,
        "source_mtime_ns": source.stat().st_mtime_ns,
        "duration_seconds": media_duration(source),
        "language_code": payload.get("language_code"),
        "language_probability": payload.get("language_probability"),
        "text": payload.get("text", ""),
        "words": words,
        "raw": payload,
    }


def transcribe_one(
    source: Path,
    *,
    edit_dir: Path,
    api_key: str,
    language: str | None = None,
    num_speakers: int | None = None,
) -> Path:
    source = source.resolve()
    output_path = transcript_path(edit_dir, source)
    if transcript_is_current(output_path, source):
        print(f"cached: {output_path.name}")
        return output_path
    payload = request_transcript(
        source,
        api_key=api_key,
        language=language,
        num_speakers=num_speakers,
    )
    normalized = normalize_transcript(source, payload)
    write_json(output_path, normalized)
    print(f"saved: {output_path}")
    return output_path


def discover_media(directory: Path) -> list[Path]:
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS
    )


def transcribe_batch(
    directory: Path,
    *,
    edit_dir: Path | None = None,
    language: str | None = None,
    num_speakers: int | None = None,
    workers: int = 4,
) -> list[Path]:
    directory = directory.resolve()
    targets = discover_media(directory)
    if not targets:
        raise SystemExit(f"no supported media files found in {directory}")
    resolved_edit_dir = (edit_dir or (directory / "edit")).resolve()
    api_key = resolve_api_key(directory)
    outputs: list[Path] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(
                transcribe_one,
                target,
                edit_dir=resolved_edit_dir,
                api_key=api_key,
                language=language,
                num_speakers=num_speakers,
            ): target
            for target in targets
        }
        for future in as_completed(futures):
            outputs.append(future.result())
    return outputs


def build_transcribe_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Transcribe a media file with ElevenLabs Scribe.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--edit-dir", type=Path, default=None)
    parser.add_argument("--language", type=str, default=None)
    parser.add_argument("--num-speakers", type=int, default=None)
    return parser


def build_transcribe_batch_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Transcribe all supported media files in a folder.")
    parser.add_argument("directory", type=Path)
    parser.add_argument("--edit-dir", type=Path, default=None)
    parser.add_argument("--language", type=str, default=None)
    parser.add_argument("--num-speakers", type=int, default=None)
    parser.add_argument("--workers", type=int, default=4)
    return parser
