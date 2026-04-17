from __future__ import annotations

import argparse
import tempfile
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .utils import load_json, run


BG = (18, 18, 24)
FG = (240, 240, 245)
MUTED = (118, 126, 146)
ACCENT = (255, 138, 60)
WAVE = (119, 181, 255)
SILENCE = (80, 103, 140, 80)


FONT_CANDIDATES = [
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
]


def _font(size: int) -> ImageFont.ImageFont:
    for candidate in FONT_CANDIDATES:
        path = Path(candidate)
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                continue
    return ImageFont.load_default()


def _extract_frames(video: Path, start: float, end: float, frame_count: int, temp_dir: Path) -> list[Path]:
    moments = []
    if frame_count <= 1:
        moments = [(start + end) / 2.0]
    else:
        step = (end - start) / (frame_count - 1)
        moments = [start + (index * step) for index in range(frame_count)]
    outputs = []
    for index, moment in enumerate(moments):
        output = temp_dir / f"frame-{index:03d}.jpg"
        run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{moment:.3f}",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-q:v",
                "3",
                "-vf",
                "scale=300:-2",
                str(output),
            ],
            quiet=True,
        )
        outputs.append(output)
    return outputs


def _extract_waveform(video: Path, start: float, end: float, samples: int = 1400) -> np.ndarray:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
        wav_path = Path(handle.name)
    try:
        run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{start:.3f}",
                "-i",
                str(video),
                "-t",
                f"{end - start:.3f}",
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(wav_path),
            ],
            quiet=True,
        )
        with wave.open(str(wav_path), "rb") as stream:
            frames = stream.readframes(stream.getnframes())
        pcm = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        if pcm.size == 0:
            return np.zeros(samples)
        bucket = max(1, pcm.size // samples)
        usable = (pcm.size // bucket) * bucket
        rms = np.sqrt(np.mean(np.square(pcm[:usable].reshape(-1, bucket)), axis=1))
        if rms.size < samples:
            rms = np.pad(rms, (0, samples - rms.size))
        else:
            rms = rms[:samples]
        peak = float(rms.max()) if rms.size else 0.0
        return rms / peak if peak > 0 else rms
    finally:
        wav_path.unlink(missing_ok=True)


def _words_in_range(transcript_path: Path | None, start: float, end: float) -> list[dict]:
    if transcript_path is None or not transcript_path.exists():
        return []
    payload = load_json(transcript_path)
    words = []
    for word in payload.get("words", []):
        word_start = word.get("start")
        word_end = word.get("end")
        if word_start is None or word_end is None:
            continue
        if float(word_end) <= start or float(word_start) >= end:
            continue
        words.append(word)
    return words


def _default_transcript_path(video: Path) -> Path | None:
    candidates = [
        video.parent / "edit" / "transcripts" / f"{video.stem}.json",
        video.parent / "transcripts" / f"{video.stem}.json",
        video.parent.parent / "edit" / "transcripts" / f"{video.stem}.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _silence_windows(words: list[dict], start: float, end: float, threshold: float = 0.4) -> list[tuple[float, float]]:
    result = []
    cursor = start
    for word in words:
        if word.get("type") == "spacing":
            continue
        word_start = max(start, float(word.get("start", start)))
        if word_start - cursor >= threshold:
            result.append((cursor, word_start))
        cursor = max(cursor, float(word.get("end", word_start)))
    if end - cursor >= threshold:
        result.append((cursor, end))
    return result


def render_timeline_image(
    video: Path,
    start: float,
    end: float,
    *,
    output_path: Path,
    transcript_path: Path | None = None,
    frame_count: int = 10,
) -> Path:
    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        frame_paths = _extract_frames(video, start, end, frame_count, temp_dir)
        waveform = _extract_waveform(video, start, end)
        resolved_transcript = transcript_path or _default_transcript_path(video)
        words = _words_in_range(resolved_transcript, start, end)
        silences = _silence_windows(words, start, end)

        header_font = _font(20)
        label_font = _font(14)
        body_font = _font(12)

        frame_images = [Image.open(path).convert("RGB") for path in frame_paths]
        ribbon_height = 180
        scaled_frames = []
        for image in frame_images:
            aspect = image.width / image.height
            scaled_frames.append(image.resize((int(ribbon_height * aspect), ribbon_height), Image.LANCZOS))

        canvas_width = max(1600, sum(image.width for image in scaled_frames) + 120)
        canvas_height = 520
        canvas = Image.new("RGB", (canvas_width, canvas_height), BG)
        draw = ImageDraw.Draw(canvas, "RGBA")
        draw.text((40, 18), f"{video.name}   {start:.2f}s -> {end:.2f}s", fill=FG, font=header_font)

        cursor_x = 40
        strip_top = 60
        for image in scaled_frames:
            canvas.paste(image, (cursor_x, strip_top))
            cursor_x += image.width + 4
        strip_left = 40
        strip_right = max(strip_left + 1, cursor_x - 4)

        waveform_top = 280
        waveform_height = 120
        draw.rectangle((strip_left, waveform_top, strip_right, waveform_top + waveform_height), outline=MUTED, width=1)
        span = end - start
        for silence_start, silence_end in silences:
            left = strip_left + int(((silence_start - start) / span) * (strip_right - strip_left))
            right = strip_left + int(((silence_end - start) / span) * (strip_right - strip_left))
            draw.rectangle((left, waveform_top, right, waveform_top + waveform_height), fill=SILENCE)

        mid = waveform_top + waveform_height // 2
        samples = waveform.shape[0]
        points = []
        for index, value in enumerate(waveform):
            x = strip_left + int(index / max(1, samples - 1) * (strip_right - strip_left))
            amplitude = int(value * (waveform_height // 2 - 6))
            points.append((x, mid - amplitude))
            points.append((x, mid + amplitude))
        for index in range(0, len(points), 2):
            x = points[index][0]
            draw.line((x, points[index][1], x, points[index + 1][1]), fill=WAVE, width=1)

        label_top = 430
        draw.text((40, label_top), "Words in range", fill=FG, font=label_font)
        for word in words:
            if word.get("type") != "word":
                continue
            text = str(word.get("text", "")).strip()
            if not text:
                continue
            x = strip_left + int(((float(word["start"]) - start) / span) * (strip_right - strip_left))
            draw.text((x, label_top + 24), text, fill=ACCENT, font=body_font)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(output_path)
        print(f"saved: {output_path}")
        return output_path


def build_timeline_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a visual decision aid for a time range.")
    parser.add_argument("video", type=Path)
    parser.add_argument("start", type=float)
    parser.add_argument("end", type=float)
    parser.add_argument("-o", "--output", type=Path, default=None)
    parser.add_argument("--frames", type=int, default=10)
    parser.add_argument("--transcript", type=Path, default=None)
    return parser
