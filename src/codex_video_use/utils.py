from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


class CommandFailure(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def run(
    command: list[str],
    *,
    cwd: Path | None = None,
    capture_output: bool = False,
    check: bool = True,
    quiet: bool = False,
) -> subprocess.CompletedProcess[str]:
    if not quiet:
        preview = " ".join(command[:8])
        suffix = " ..." if len(command) > 8 else ""
        print(f"$ {preview}{suffix}")
    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=capture_output,
    )
    if check and result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        raise CommandFailure(stderr or stdout or f"command failed: {' '.join(command)}")
    return result


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_yaml(path: Path, payload: Any) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def load_env_value(key: str, *, search_root: Path | None = None) -> str | None:
    candidates = []
    if search_root:
        candidates.append(search_root / ".env")
    candidates.append(Path.cwd() / ".env")
    candidates.append(REPO_ROOT / ".env")
    for candidate in candidates:
        if not candidate.exists():
            continue
        for line in candidate.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            current_key, value = stripped.split("=", 1)
            if current_key.strip() == key:
                return value.strip().strip('"').strip("'")
    return os.environ.get(key)


def ffprobe_json(path: Path) -> dict[str, Any]:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=index,codec_type,width,height",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        quiet=True,
    )
    return json.loads(result.stdout)


def media_duration(path: Path) -> float:
    info = ffprobe_json(path)
    return round(float(info["format"]["duration"]), 3)

