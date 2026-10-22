from __future__ import annotations

import json
from pathlib import Path

from codex_video_use.syncer import build_sync_parser, classify_changes, run_sync_cli, scan
from codex_video_use.utils import run, write_json, write_yaml


def _commit(repo: Path, message: str) -> str:
    run(["git", "add", "."], cwd=repo, quiet=True)
    run(["git", "config", "user.name", "Codex Test"], cwd=repo, quiet=True)
    run(["git", "config", "user.email", "codex@example.com"], cwd=repo, quiet=True)
    run(["git", "commit", "-m", message], cwd=repo, quiet=True)
    result = run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, quiet=True)
    return result.stdout.strip()


def test_classify_changes_maps_upstream_paths() -> None:
    mapping = {
        "mappings": [
            {
                "name": "docs",
                "upstream_paths": ["README.md", "helpers/render.py"],
                "codex_targets": ["README.md"],
                "strategy": "adapt"
            }
        ]
    }
    classified = classify_changes(["README.md", "helpers/render.py"], mapping)
    assert classified[0]["name"] == "docs"
    assert "README.md" in classified[0]["matches"]


def test_scan_reports_noop_and_changes(tmp_path: Path) -> None:
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    run(["git", "init", "-b", "main"], cwd=upstream, quiet=True)
    (upstream / "README.md").write_text("hello\n", encoding="utf-8")
    initial_sha = _commit(upstream, "initial")

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    run(["git", "init", "-b", "main"], cwd=repo_root, quiet=True)

    state_path = repo_root / "state.json"
    map_path = repo_root / "map.yaml"
    write_json(
        state_path,
        {
            "upstream_repo": str(upstream),
            "tracked_branch": "main",
            "last_checked_sha": initial_sha,
            "last_synced_sha": initial_sha,
            "last_run_at": None,
            "last_result": "initialized",
        },
    )
    write_yaml(
        map_path,
        {
            "upstream": {"repo": str(upstream), "branch": "main"},
            "mappings": [
                {
                    "name": "docs",
                    "upstream_paths": ["README.md"],
                    "codex_targets": ["README.md"],
                    "strategy": "adapt"
                }
            ],
        },
    )

    noop = scan(repo_root, state_path=state_path, map_path=map_path)
    assert noop["status"] == "up_to_date"

    (upstream / "README.md").write_text("hello world\n", encoding="utf-8")
    new_sha = _commit(upstream, "update")
    payload = scan(repo_root, state_path=state_path, map_path=map_path)
    assert payload["status"] == "changes_detected"
    assert payload["current_upstream_sha"] == new_sha
    assert "README.md" in payload["changed_paths"]


def test_published_checkpoint_survives_a_fresh_clone(tmp_path: Path, capsys) -> None:
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    run(["git", "init", "-b", "main"], cwd=upstream, quiet=True)
    (upstream / "README.md").write_text("An upstream promotion.\n", encoding="utf-8")
    upstream_sha = _commit(upstream, "upstream docs")

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    run(["git", "init", "-b", "main"], cwd=repo_root, quiet=True)
    state_path = repo_root / "state.json"
    map_path = repo_root / "map.yaml"
    write_json(state_path, {
        "upstream_repo": str(upstream),
        "tracked_branch": "main",
        "last_synced_sha": None,
        "last_result": "initialized",
    })
    write_yaml(map_path, {"mappings": []})
    _commit(repo_root, "initial toolkit")

    note = "Reviewed upstream promotion; excluded from the local Codex toolkit."
    args = build_sync_parser().parse_args([
        "--repo-root", str(repo_root), "--state", str(state_path), "--map", str(map_path),
        "checkpoint", "--sha", upstream_sha, "--note", note, "--json",
    ])
    assert run_sync_cli(args) == 0
    prepared = json.loads(capsys.readouterr().out)
    assert prepared["last_result"] == "validated"
    _commit(repo_root, "sync: checkpoint reviewed upstream")

    origin = tmp_path / "origin.git"
    run(["git", "init", "--bare", "-b", "main", str(origin)], quiet=True)
    run(["git", "remote", "add", "origin", str(origin)], cwd=repo_root, quiet=True)
    run(["git", "push", "origin", "main"], cwd=repo_root, quiet=True)
    fresh_clone = tmp_path / "fresh-clone"
    run(["git", "clone", str(origin), str(fresh_clone)], quiet=True)

    persisted = json.loads((fresh_clone / "state.json").read_text(encoding="utf-8"))
    assert persisted["last_synced_sha"] == upstream_sha
    assert persisted["last_checked_sha"] == upstream_sha
    assert persisted["last_review_note"] == note
    assert persisted["last_result"] == "validated"
    assert persisted["last_run_at"]
    assert scan(fresh_clone, state_path=fresh_clone / "state.json", map_path=fresh_clone / "map.yaml")["status"] == "up_to_date"
    assert run(["git", "status", "--porcelain"], cwd=fresh_clone, capture_output=True, quiet=True).stdout == ""

