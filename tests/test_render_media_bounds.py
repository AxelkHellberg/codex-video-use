from __future__ import annotations

import json
import shutil
from pathlib import Path
from subprocess import CompletedProcess

import pytest

import codex_video_use.rendering as rendering


def _write_edl(root: Path, segments: list[dict]) -> Path:
    path = root / "edl.json"
    path.write_text(
        json.dumps({"sources": {"clip": "clip.mp4"}, "segments": segments}),
        encoding="utf-8",
    )
    return path


def _mock_media(monkeypatch, payload: dict) -> list[Path]:
    extracted: list[Path] = []

    def fake_extract(source: Path, **kwargs) -> Path:
        extracted.append(source)
        return kwargs["output_path"]

    monkeypatch.setattr(
        rendering,
        "run",
        lambda command, **kwargs: CompletedProcess(command, 0, json.dumps(payload), ""),
    )
    monkeypatch.setattr(rendering, "_probe_source_fps", lambda source: "24")
    monkeypatch.setattr(rendering, "extract_segment", fake_extract)
    monkeypatch.setattr(rendering, "concat_segments", lambda segments, output, edit: output)
    monkeypatch.setattr(rendering, "composite_output", lambda base, **kwargs: kwargs["output_path"])
    return extracted


@pytest.mark.parametrize("start,end", [(0, 2.1), (2, 3), (3, 4), (0.5, 2.1)])
def test_out_of_bounds_later_segment_stops_before_any_extraction(
    tmp_path: Path, monkeypatch, start: float, end: float
) -> None:
    extracted = _mock_media(
        monkeypatch, {"streams": [{"duration": "2.000000"}], "format": {"duration": "5.0"}}
    )
    edl = _write_edl(
        tmp_path,
        [{"source": "clip", "start": 0, "end": 1}, {"source": "clip", "start": start, "end": end}],
    )
    output = tmp_path / "exports" / "preview.mp4"

    with pytest.raises(SystemExit, match=r"segment 2.*duration"):
        rendering.render_edl(edl, output_path=output, no_normalize=True)

    assert extracted == []
    assert not output.parent.exists()
    assert not (tmp_path / "clips").exists()


@pytest.mark.parametrize("stream_duration", ["2.000000", None, "N/A"])
def test_exact_source_end_is_accepted_with_container_fallback(
    tmp_path: Path, monkeypatch, stream_duration: str | None
) -> None:
    stream = {} if stream_duration is None else {"duration": stream_duration}
    extracted = _mock_media(monkeypatch, {"streams": [stream], "format": {"duration": "2.000000"}})
    edl = _write_edl(tmp_path, [{"source": "clip", "start": "0", "end": "2.0"}])

    rendering.render_edl(edl, output_path=tmp_path / "exports" / "out.mp4", no_normalize=True)

    assert extracted == [(tmp_path / "clip.mp4").resolve()]


@pytest.mark.parametrize(
    "payload",
    [
        {"streams": [], "format": {"duration": "2"}},
        {"streams": [{}], "format": {}},
        {"streams": [{"duration": "nan"}], "format": {"duration": "inf"}},
        {"streams": [{"duration": "0"}], "format": {"duration": "-1"}},
    ],
)
def test_unknown_video_duration_stops_before_extraction(tmp_path: Path, monkeypatch, payload: dict) -> None:
    extracted = _mock_media(monkeypatch, payload)
    edl = _write_edl(tmp_path, [{"source": "clip", "start": 0, "end": 1}])
    output = tmp_path / "exports" / "out.mp4"

    with pytest.raises(SystemExit, match=r"segment 1.*duration"):
        rendering.render_edl(edl, output_path=output, no_normalize=True)

    assert extracted == []
    assert not output.parent.exists()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")
@pytest.mark.parametrize(
    "start,end,offset",
    [(0, 0.5, 0), (0, 0.75, 0), (0.5, 1, 0.5), (0, 0.25, 0.5), (0, 0.75, 0.5)],
)
def test_real_video_bounds_prefer_video_track_over_longer_audio(
    tmp_path: Path, start: float, end: float, offset: float
) -> None:
    source = tmp_path / "clip.mp4"
    rendering.run(
        [
            "ffmpeg", "-v", "error", "-y",
            "-itsoffset", str(offset),
            "-f", "lavfi", "-t", "0.5", "-i", "color=c=black:size=160x90:rate=24",
            "-f", "lavfi", "-t", "1", "-i", "sine=frequency=880:sample_rate=48000",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-fps_mode", "passthrough",
            "-c:a", "aac", str(source),
        ],
        capture_output=True,
        quiet=True,
    )
    edl = _write_edl(tmp_path, [{"source": "clip", "start": start, "end": end}])
    output = tmp_path / "exports" / "out.mp4"

    if start < offset or end > offset + 0.5:
        with pytest.raises(SystemExit, match=r"segment 1.*duration"):
            rendering.render_edl(edl, output_path=output, preview=True, no_normalize=True)
        assert not output.parent.exists()
        assert not (tmp_path / "clips-preview").exists()
    else:
        rendering.render_edl(edl, output_path=output, preview=True, no_normalize=True)
        assert output.exists()
        result = rendering.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
                "-show_entries", "stream=nb_read_frames", "-of", "json", str(output),
            ],
            capture_output=True,
            quiet=True,
        )
        assert int(json.loads(result.stdout)["streams"][0]["nb_read_frames"]) == 12


def test_video_endpoint_is_relative_to_container_start(tmp_path: Path, monkeypatch) -> None:
    extracted = _mock_media(
        monkeypatch,
        {
            "streams": [{"duration": "0.5", "start_time": "5.5"}],
            "format": {"duration": "1.0", "start_time": "5.0"},
        },
    )
    edl = _write_edl(tmp_path, [{"source": "clip", "start": 0.5, "end": 1.0}])

    rendering.render_edl(edl, output_path=tmp_path / "out.mp4", no_normalize=True)

    assert extracted == [(tmp_path / "clip.mp4").resolve()]
