# Publishing an upstream sync

`upstream-state.json` is versioned. Prepare its checkpoint before committing and
pushing; changing it after the push leaves fresh clones at the old checkpoint.

1. Inspect `git status --short` and compare `HEAD` with `origin/main`. Preserve
   unrelated edits. If a previous sync commit is ahead of the remote, inspect and
   finish publishing it before treating a scan's `up_to_date` result as complete.
2. Run `.venv/bin/codex-video-use-sync scan --json`, inspect the changed upstream
   files, and adapt relevant behavior. A scan can also be resolved by a documented
   decision to exclude a change that does not apply to this Codex toolkit.
3. Run `.venv/bin/codex-video-use-sync validate` and `git diff --check`. Only after
   these pass, prepare the checkpoint using the full upstream SHA from the scan:

   ```bash
   .venv/bin/codex-video-use-sync checkpoint --sha <upstream-sha> --note '<adaptations and exclusions>' --json
   ```

   `last_result: validated` describes the local review and validation. The command
   does not validate files or claim that GitHub received a push.
4. Stage only the intended adaptations and `sync/upstream-state.json`, review the
   staged diff, and commit them together. For an excluded upstream change, the
   checkpoint and its review note are sufficient; do not manufacture source edits.
5. Push the commit to `origin main` and verify that `git ls-remote origin
   refs/heads/main` reports the commit's SHA. Report publication success only after
   that check. If pushing fails, preserve the prepared commit and report the
   blocker so the next run can retry it.

Do not run `record --result success` after pushing as the normal sync sequence:
that creates a new uncommitted state-file change. The older `record` command stays
available for existing callers, but the committed checkpoint is the durable record
of which upstream SHA was reviewed.
