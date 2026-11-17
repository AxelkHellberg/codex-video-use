from __future__ import annotations

import json
from pathlib import Path

import pytest

from codex_video_use.syncer import build_sync_parser, classify_changes, run_sync_cli, scan
from codex_video_use.utils import CommandFailure, run, write_json, write_yaml


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


def _scan_files(repo: Path, upstream: Path, branch: str, previous_sha: str) -> tuple[Path, Path]:
    state = repo / "state.json"
    mapping = repo / "map.yaml"
    write_json(state, {
        "upstream_repo": upstream.as_uri(),
        "tracked_branch": branch,
        "last_synced_sha": previous_sha,
        "last_result": "validated",
    })
    write_yaml(mapping, {"mappings": []})
    return state, mapping


def test_scan_fetches_tracked_branch_outside_existing_remote_refspec(tmp_path: Path) -> None:
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    run(["git", "init", "-b", "main"], cwd=upstream, quiet=True)
    (upstream / "README.md").write_text("initial\n", encoding="utf-8")
    initial = _commit(upstream, "initial")
    run(["git", "checkout", "-b", "release/video"], cwd=upstream, quiet=True)
    (upstream / "README.md").write_text("release update\n", encoding="utf-8")
    release = _commit(upstream, "release update")
    run(["git", "checkout", "main"], cwd=upstream, quiet=True)

    repo = tmp_path / "repo"
    run(["git", "clone", "--single-branch", "--branch", "main", "--origin", "upstream",
         upstream.as_uri(), str(repo)], quiet=True)
    state, mapping = _scan_files(repo, upstream, "release/video", initial)
    before = state.read_bytes()

    payload = scan(repo, state_path=state, map_path=mapping)

    assert payload["current_upstream_sha"] == release
    assert payload["changed_paths"] == ["README.md"]
    assert state.read_bytes() == before
    assert run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, quiet=True).stdout.strip() == initial
    assert (repo / "README.md").read_text(encoding="utf-8") == "initial\n"
    assert run(["git", "config", "--get-all", "remote.upstream.fetch"], cwd=repo,
               capture_output=True, quiet=True).stdout.strip() == "+refs/heads/main:refs/remotes/upstream/main"


def test_scan_retrieves_checkpoint_older_than_shallow_history(tmp_path: Path) -> None:
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    run(["git", "init", "-b", "main"], cwd=upstream, quiet=True)
    (upstream / "README.md").write_text("initial\n", encoding="utf-8")
    initial = _commit(upstream, "initial")
    for index in range(3):
        (upstream / "README.md").write_text(f"update {index}\n", encoding="utf-8")
        current = _commit(upstream, f"update {index}")

    repo = tmp_path / "repo"
    run(["git", "clone", "--depth=1", "--single-branch", "--branch", "main", "--origin", "upstream",
         upstream.as_uri(), str(repo)], quiet=True)
    state, mapping = _scan_files(repo, upstream, "main", initial)
    before = state.read_bytes()
    assert run(["git", "cat-file", "-e", initial], cwd=repo, check=False, capture_output=True, quiet=True).returncode != 0

    payload = scan(repo, state_path=state, map_path=mapping)

    assert payload["current_upstream_sha"] == current
    assert payload["last_synced_sha"] == initial
    assert payload["changed_paths"] == ["README.md"]
    assert state.read_bytes() == before
    assert run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, quiet=True).stdout.strip() == current


def test_scan_rejects_deleted_tracked_branch_instead_of_using_stale_ref(tmp_path: Path) -> None:
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    run(["git", "init", "-b", "main"], cwd=upstream, quiet=True)
    (upstream / "README.md").write_text("initial\n", encoding="utf-8")
    initial = _commit(upstream, "initial")
    run(["git", "branch", "release"], cwd=upstream, quiet=True)
    repo = tmp_path / "repo"
    run(["git", "clone", "--origin", "upstream", upstream.as_uri(), str(repo)], quiet=True)
    state, mapping = _scan_files(repo, upstream, "release", initial)
    before = state.read_bytes()
    run(["git", "branch", "-D", "release"], cwd=upstream, quiet=True)

    with pytest.raises(CommandFailure):
        scan(repo, state_path=state, map_path=mapping)

    assert state.read_bytes() == before


def test_scan_keeps_checkpoint_when_previous_object_cannot_be_retrieved(tmp_path: Path) -> None:
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    run(["git", "init", "-b", "main"], cwd=upstream, quiet=True)
    (upstream / "README.md").write_text("initial\n", encoding="utf-8")
    current = _commit(upstream, "initial")
    repo = tmp_path / "repo"
    run(["git", "clone", "--origin", "upstream", upstream.as_uri(), str(repo)], quiet=True)
    state, mapping = _scan_files(repo, upstream, "main", "0" * 40)
    before = state.read_bytes()

    with pytest.raises(CommandFailure):
        scan(repo, state_path=state, map_path=mapping)

    assert state.read_bytes() == before
    assert run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, quiet=True).stdout.strip() == current

