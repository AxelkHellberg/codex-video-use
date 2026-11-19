from __future__ import annotations

import json
from pathlib import Path

import pytest

from codex_video_use.syncer import build_sync_parser, changed_paths, classify_changes, run_sync_cli, scan
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


@pytest.mark.parametrize("initial_scan", [True, False])
def test_changed_paths_preserves_literal_git_filenames(tmp_path: Path, initial_scan: bool) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init", "-b", "main"], cwd=repo, quiet=True)
    (repo / "unchanged.md").write_text("unchanged\n", encoding="utf-8")
    previous_sha = _commit(repo, "initial")
    names = [
        "skills/manim-video/café.md",
        "skills/manim-video/tab\tname.md",
        "skills/manim-video/line\nname.md",
        "skills/manim-video/carriage\rreturn.md",
        "skills/manim-video/quote\"slash\\name.md",
        "skills/manim-video/trailing.md ",
        " leading.md",
    ]
    for name in names:
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("new\n", encoding="utf-8")
    current_sha = _commit(repo, "add named files")

    paths = changed_paths(repo, None if initial_scan else previous_sha, current_sha)

    assert sorted(paths) == sorted(names + (["unchanged.md"] if initial_scan else []))
    mapping = {"mappings": [
        {"name": "rendering", "upstream_paths": ["skills/manim-video/**"]},
        {"name": "leading", "upstream_paths": [" leading.md"]},
    ]}
    groups = classify_changes(paths, mapping)
    assert groups[0]["matches"] == sorted(names[:-1])
    assert groups[1]["matches"] == [names[-1]]


def test_changed_paths_preserves_deleted_filenames_and_empty_diff(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init", "-b", "main"], cwd=repo, quiet=True)
    path = repo / "deleted\r\nfile.md "
    path.write_text("removed\n", encoding="utf-8")
    previous_sha = _commit(repo, "initial")
    path.unlink()
    current_sha = _commit(repo, "delete file")

    assert changed_paths(repo, previous_sha, current_sha) == [path.name]
    assert changed_paths(repo, current_sha, current_sha) == []


def test_changed_paths_reports_git_failure(tmp_path: Path) -> None:
    with pytest.raises(CommandFailure, match="not a git repository"):
        changed_paths(tmp_path, None, "HEAD")


@pytest.mark.parametrize("initial_scan", [True, False])
def test_scan_classifies_unusual_filenames_without_changing_checkpoint(tmp_path: Path, initial_scan: bool) -> None:
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    run(["git", "init", "-b", "main"], cwd=upstream, quiet=True)
    (upstream / "README.md").write_text("initial\n", encoding="utf-8")
    previous_sha = _commit(upstream, "initial")
    name = "skills/manim-video/café\r\n.md "
    path = upstream / name
    path.parent.mkdir(parents=True)
    path.write_text("new\n", encoding="utf-8")
    current_sha = _commit(upstream, "add rendering guide")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    run(["git", "init", "-b", "main"], cwd=repo_root, quiet=True)
    state_path = repo_root / "state.json"
    map_path = repo_root / "map.yaml"
    write_json(state_path, {
        "upstream_repo": str(upstream),
        "tracked_branch": "main",
        "last_synced_sha": None if initial_scan else previous_sha,
    })
    write_yaml(map_path, {"mappings": [
        {"name": "rendering", "upstream_paths": ["skills/manim-video/**"]},
    ]})
    original_state = state_path.read_bytes()

    payload = scan(repo_root, state_path=state_path, map_path=map_path)

    assert payload["status"] == "changes_detected"
    assert payload["current_upstream_sha"] == current_sha
    assert name in payload["changed_paths"]
    assert payload["relevant_groups"][0]["matches"] == [name]
    assert state_path.read_bytes() == original_state


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

