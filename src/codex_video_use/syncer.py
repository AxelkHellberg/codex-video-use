from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from .utils import REPO_ROOT, load_json, load_yaml, now_iso, run, write_json


def _git(args: list[str], *, repo_root: Path, capture_output: bool = False, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], cwd=repo_root, capture_output=capture_output, check=check, quiet=True)


def ensure_upstream_remote(repo_root: Path, upstream_repo: str) -> None:
    remotes = _git(["remote"], repo_root=repo_root, capture_output=True).stdout.splitlines()
    if "upstream" not in remotes:
        _git(["remote", "add", "upstream", upstream_repo], repo_root=repo_root)


def fetch_upstream(repo_root: Path) -> None:
    _git(["fetch", "upstream"], repo_root=repo_root)


def upstream_head(repo_root: Path, branch: str) -> str:
    return _git(["rev-parse", f"upstream/{branch}"], repo_root=repo_root, capture_output=True).stdout.strip()


def changed_paths(repo_root: Path, previous_sha: str | None, current_sha: str) -> list[str]:
    if previous_sha:
        result = _git(["diff", "--name-only", previous_sha, current_sha], repo_root=repo_root, capture_output=True)
    else:
        result = _git(["ls-tree", "-r", "--name-only", current_sha], repo_root=repo_root, capture_output=True)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def classify_changes(paths: list[str], mapping: dict[str, Any]) -> list[dict[str, Any]]:
    relevant = []
    for entry in mapping.get("mappings", []):
        matches = []
        for candidate in entry.get("upstream_paths", []):
            prefix = candidate.removesuffix("/**")
            for path in paths:
                if candidate.endswith("/**"):
                    if path.startswith(prefix.rstrip("/") + "/"):
                        matches.append(path)
                elif path == candidate:
                    matches.append(path)
        if matches:
            relevant.append(
                {
                    "name": entry["name"],
                    "matches": sorted(set(matches)),
                    "targets": entry.get("codex_targets", []),
                    "strategy": entry.get("strategy"),
                }
            )
    return relevant


def read_state(path: Path) -> dict[str, Any]:
    return load_json(path)


def write_state(path: Path, payload: dict[str, Any]) -> None:
    write_json(path, payload)


def scan(repo_root: Path, *, state_path: Path, map_path: Path) -> dict[str, Any]:
    state = read_state(state_path)
    mapping = load_yaml(map_path)
    ensure_upstream_remote(repo_root, state["upstream_repo"])
    fetch_upstream(repo_root)
    head = upstream_head(repo_root, state["tracked_branch"])
    last_synced = state.get("last_synced_sha")
    diff_paths = changed_paths(repo_root, last_synced, head) if head != last_synced else []
    relevant = classify_changes(diff_paths, mapping)
    status = "up_to_date" if head == last_synced else "changes_detected"
    return {
        "status": status,
        "upstream_repo": state["upstream_repo"],
        "branch": state["tracked_branch"],
        "current_upstream_sha": head,
        "last_synced_sha": last_synced,
        "changed_paths": diff_paths,
        "relevant_groups": relevant,
        "recommended_commit": f"sync: port upstream changes from video-use {head[:12]}",
    }


def record_result(state_path: Path, *, sha: str, result: str) -> dict[str, Any]:
    state = read_state(state_path)
    state["last_checked_sha"] = sha
    if result == "success":
        state["last_synced_sha"] = sha
    state["last_result"] = result
    state["last_run_at"] = now_iso()
    write_state(state_path, state)
    return state


def validate(repo_root: Path) -> None:
    run(["pytest"], cwd=repo_root)


def build_sync_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan, validate, and record upstream sync state.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--state", type=Path, default=REPO_ROOT / "sync" / "upstream-state.json")
    parser.add_argument("--map", dest="map_path", type=Path, default=REPO_ROOT / "sync" / "upstream-map.yaml")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan")
    scan_parser.add_argument("--json", action="store_true")

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--json", action="store_true")

    record_parser = subparsers.add_parser("record")
    record_parser.add_argument("--sha", required=True)
    record_parser.add_argument("--result", choices=["success", "failure"], required=True)
    record_parser.add_argument("--json", action="store_true")
    return parser


def run_sync_cli(args: argparse.Namespace) -> int:
    repo_root = args.repo_root.resolve()
    state_path = args.state.resolve()
    map_path = args.map_path.resolve()

    if args.command == "scan":
        payload = scan(repo_root, state_path=state_path, map_path=map_path)
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"status: {payload['status']}")
            print(f"upstream: {payload['current_upstream_sha']}")
            for group in payload["relevant_groups"]:
                print(f"- {group['name']}: {', '.join(group['matches'])}")
        return 0

    if args.command == "validate":
        validate(repo_root)
        if getattr(args, "json", False):
            print(json.dumps({"status": "ok"}, indent=2))
        return 0

    if args.command == "record":
        payload = record_result(state_path, sha=args.sha, result=args.result)
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"recorded {args.result} for {args.sha}")
        return 0

    raise SystemExit(f"unsupported sync command: {args.command}")

