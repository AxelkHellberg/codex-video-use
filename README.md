# codex-video-use

`codex-video-use` is a Codex-native video editing skill and toolkit for turning a folder of source footage into a polished edit with subtitles, timing-aware cuts, optional overlays, and verification passes.

It is designed around a simple idea:

- transcribe the footage with word timestamps
- compress that transcript into an edit-friendly reading surface
- reason about cuts from text first
- drill into visuals only when a decision needs visual confirmation
- render the result with clean audio edges, subtitles, and review artifacts

## What it includes

- A Codex skill at `skills/codex-video-use/SKILL.md`
- A Python package with CLIs for:
  - transcription
  - transcript packing
  - timeline image generation
  - grading
  - rendering
  - upstream sync scans and validation
- Tests, CI, and a daily Codex automation flow for tracking upstream changes

## Prerequisites

- Python 3.11+
- `ffmpeg` and `ffprobe`
- An ElevenLabs API key in `.env` or the environment as `ELEVENLABS_API_KEY`

Optional:

- `yt-dlp` if you want to pull reference footage
- `manim` if you want custom motion graphics authored outside the default overlay flow

## Setup prompt

Paste this into Codex on a fresh machine:

```text
Set up codex-video-use for me.

Read install.md first. Use it to create the venv, install the package, verify ffmpeg and ffprobe, register the skill with Codex, and configure ELEVENLABS_API_KEY in the repo .env if it is missing. Do not transcribe any footage yet. When setup is done, tell me the toolkit is ready and wait for source media.
```

## Manual install

If you prefer to set it up yourself:

```bash
git clone https://github.com/AxelkHellberg/codex-video-use ~/Developer/codex-video-use
cd ~/Developer/codex-video-use
uv venv .venv
uv pip install --python .venv/bin/python -e .
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
ln -sfn "$(pwd)/skills/codex-video-use" "${CODEX_HOME:-$HOME/.codex}/skills/codex-video-use"
```

Create `.env` from the example:

```bash
cp .env.example .env
```

Then set:

```bash
ELEVENLABS_API_KEY=...
```

For a full first-time setup checklist, see [`install.md`](./install.md).

## Use from Codex

Open Codex inside a folder that contains your raw footage:

```bash
cd /path/to/my-footage
codex
```

Example prompts:

- `Use $codex-video-use to cut these takes into a 30 second launch edit.`
- `Use $codex-video-use to make a vertical talking-head video with bold subtitles.`
- `Use $codex-video-use to review the last edit and tighten pauses without changing the message.`

Outputs are written next to the footage in:

```text
<videos_dir>/edit/
```

Typical outputs:

- `transcripts/*.json`
- `takes_packed.md`
- `edl.json`
- `verify/*.png`
- `preview.mp4`
- `final.mp4`

## Use the CLIs directly

Transcribe a folder:

```bash
codex-video-use-transcribe-batch /path/to/my-footage
```

Pack transcripts:

```bash
codex-video-use-pack --edit-dir /path/to/my-footage/edit
```

Build a decision image:

```bash
codex-video-use-timeline-view /path/to/my-footage/clip.mp4 12.0 18.0 -o /path/to/my-footage/edit/verify/cut-01.png
```

Render from an EDL:

```bash
codex-video-use-render /path/to/my-footage/edit/edl.json -o /path/to/my-footage/edit/preview.mp4 --preview --build-subtitles
codex-video-use-render /path/to/my-footage/edit/edl.json -o /path/to/my-footage/edit/final.mp4 --build-subtitles
```

Scan upstream:

```bash
codex-video-use-sync scan --json
codex-video-use-sync validate
```

## Repository layout

```text
codex-video-use/
├── skills/codex-video-use/
├── src/codex_video_use/
├── sync/
├── tests/
└── .github/workflows/
```

## Verification

The main local verification path is:

```bash
pytest
```

CI runs:

- unit tests
- a synthetic render smoke test
- sync dry-run validation
