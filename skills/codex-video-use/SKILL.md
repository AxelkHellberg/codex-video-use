---
name: codex-video-use
description: Edit a folder of source footage into a finished video with transcript-first decisions, visual drill-down, subtitle generation, render passes, and output verification. Use when the user wants Codex to cut videos, tighten pauses, choose takes, build subtitles, inspect edit points, or render a final video from raw footage.
---

# Codex Video Use

Use this skill when the user wants a conversation-driven edit workflow over a folder of footage.

## Core approach

1. Read the footage through transcription first, not through frame dumping.
2. Convert raw word timestamps into a compact review surface before making cut decisions.
3. Ask for intent, pacing, must-keep moments, and delivery format before changing the structure.
4. Confirm the edit strategy before writing or overwriting the timeline.
5. Render a preview, inspect boundaries, and only then present the result.

## Working rules

- Keep all outputs in `<videos_dir>/edit/`.
- Preserve source files untouched.
- Never cut through the middle of a spoken word.
- Keep a small timing pad around cut edges.
- Apply subtitles after overlays in the final composite.
- Reuse cached transcripts whenever the source file has not changed.

## Typical workflow

1. Inventory the source directory.
2. Transcribe media:
   - `codex-video-use-transcribe <file>`
   - `codex-video-use-transcribe-batch <videos_dir>`
3. Pack transcripts:
   - `codex-video-use-pack --edit-dir <videos_dir>/edit`
4. Review `takes_packed.md` and gather user direction.
5. Build or revise `edl.json`.
6. Use `codex-video-use-timeline-view` at ambiguous cut points.
7. Render preview:
   - `codex-video-use-render <edl.json> -o <videos_dir>/edit/preview.mp4 --preview --build-subtitles`
8. Self-check the preview around cut boundaries and revise if needed.
9. Render final:
   - `codex-video-use-render <edl.json> -o <videos_dir>/edit/final.mp4 --build-subtitles`

## Output layout

Use this structure:

```text
<videos_dir>/
├── source-clip-01.mp4
└── edit/
    ├── transcripts/
    ├── takes_packed.md
    ├── edl.json
    ├── verify/
    ├── preview.mp4
    └── final.mp4
```

## Decision guidance

- Use transcript phrases to identify strong beats before comparing visuals.
- Prefer silence gaps and natural phrase endings as cut candidates.
- Use timeline images only for uncertainty, not as a constant scan mechanism.
- When a user asks for subtitles, decide chunk size and tone from the edit style rather than using a single hardcoded look.
- When motion graphics are requested, keep overlay timing synchronized with the spoken explanation and verify that captions remain visible.

## Sync workflow

This repo includes a sync tool for upstream monitoring:

- `codex-video-use-sync scan --json`
- `codex-video-use-sync validate`

Use it when the user asks to check for new upstream behavior, port changes, or prepare a sync commit.

