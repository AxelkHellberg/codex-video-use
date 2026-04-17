from __future__ import annotations

import json
from pathlib import Path

from codex_video_use.syncer import classify_changes, scan
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

