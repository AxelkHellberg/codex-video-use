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

## Setup

Use `install.md` in the repo root for first-time setup or reconnects. On normal editing runs, do not repeat installation work unless something is missing. Just verify:

- `ELEVENLABS_API_KEY` resolves from the environment or the repo `.env`.
- `ffmpeg` and `ffprobe` are on `PATH`.
- The repo package is installed so the `codex-video-use-*` CLIs are available.
- Node.js and `npm` only need to be present if the edit calls for a HyperFrames or Remotion animation slot. HyperFrames currently requires Node.js 22+.

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

## Animation slots

Choose the lightest engine that fits the job. Do not assume a single motion stack.

- HyperFrames: use for HTML/CSS/GSAP compositions, UI motion, or web-style overlays that benefit from a browser-native authoring model. Initialize and render inside `edit/animations/slot_<id>/`, and run the HyperFrames checks that make sense for the slot before using the output.
- Remotion: use when the overlay is easiest to build as a React composition or when the user explicitly wants Remotion. Keep the whole Remotion project inside the slot directory instead of installing it at the repo root.
- Manim: use for diagrammatic or math-heavy motion. Read the vendored Manim skill before authoring the slot.
- PIL plus ffmpeg: use for simple cards, counters, reveals, or image-sequence overlays when a full animation framework would be unnecessary.

For every animation slot:

- Keep all scaffolding, source files, and renders under `<videos_dir>/edit/animations/slot_<id>/`.
- Install or scaffold the chosen engine inside that slot on first use. Do not turn the repo root into a shared animation workspace.
- Verify the rendered overlay with the engine's own checks when available, then confirm duration and dimensions with `ffprobe` before wiring it into `edl.json`.

## Sync workflow

This repo includes a sync tool for upstream monitoring:

- `codex-video-use-sync scan --json`
- `codex-video-use-sync validate`

Use it when the user asks to check for new upstream behavior, port changes, or prepare a sync commit.
