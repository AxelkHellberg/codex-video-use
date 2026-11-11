from pathlib import Path

import pytest

from codex_video_use.rendering import composite_output
from codex_video_use.utils import media_duration, run


@pytest.mark.parametrize("overlay_duration,start", [(2.0, 0), (0.2, 0), (2.0, 0.3)])
def test_overlay_preserves_base_duration(tmp_path: Path, overlay_duration: float, start: float) -> None:
    base = tmp_path / "base.mp4"
    overlay = tmp_path / "overlay.mp4"
    output = tmp_path / "output.mp4"
    run([
        "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=black:s=64x64:d=0.6",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "0.6",
        "-c:v", "libx264", "-c:a", "aac", str(base),
    ], quiet=True)
    run([
        "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
        f"color=red:s=32x32:d={overlay_duration}", "-c:v", "libx264", str(overlay),
    ], quiet=True)
    composite_output(base, overlays=[dict(file=str(overlay), start=start, duration=overlay_duration)],
                     subtitles_path=None, output_path=output, edit_dir=tmp_path)
    assert media_duration(output) == pytest.approx(media_duration(base), abs=0.05)
