from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def _run_with_piped_stdin(command: list[str], text: str) -> dict[str, str]:
    # Cross a real process boundary: pytest's own stdin is normally protected.
    program = """
import json
import sys
from codex_video_use.utils import run
result = run(json.loads(sys.argv[1]), capture_output=True, quiet=True)
print(json.dumps({
    "stdout": result.stdout,
    "stderr": result.stderr,
    "remaining_stdin": sys.stdin.read(),
}))
"""
    env = os.environ.copy()
    source_dir = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [source_dir, env.get("PYTHONPATH")]))
    result = subprocess.run(
        [sys.executable, "-c", program, json.dumps(command)],
        input=text,
        text=True,
        capture_output=True,
        env=env,
        timeout=30,
        check=True,
    )
    return json.loads(result.stdout)


def test_subprocess_cannot_consume_callers_piped_stdin() -> None:
    result = _run_with_piped_stdin(
        [sys.executable, "-c", "import sys; print(repr(sys.stdin.read()))"],
        "next file.mp4\n",
    )

    assert result["stdout"] == "''\n"
    assert result["remaining_stdin"] == "next file.mp4\n"


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg and ffprobe are required",
)
def test_ffmpeg_does_not_truncate_output_when_caller_receives_q(tmp_path: Path) -> None:
    output = tmp_path / "complete.mp4"
    result = _run_with_piped_stdin(
        [
            "ffmpeg", "-v", "error", "-y",
            # Pace this tiny fixture so FFmpeg checks its interactive input.
            "-re", "-f", "lavfi", "-i", "color=s=32x32:r=10:d=3",
            "-c:v", "libx264", str(output),
        ],
        "q\n",
    )
    info = subprocess.run(
        [
            "ffprobe", "-v", "error", "-count_frames",
            "-show_entries", "stream=nb_read_frames:format=duration",
            "-of", "json", str(output),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    media = json.loads(info.stdout)

    assert float(media["format"]["duration"]) == pytest.approx(3.0, abs=0.05)
    assert int(media["streams"][0]["nb_read_frames"]) == 30
    assert result["remaining_stdin"] == "q\n"
