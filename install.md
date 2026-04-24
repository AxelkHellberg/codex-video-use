# Install codex-video-use

Use this guide for first-time setup or to reconnect the repo on a machine where the toolkit is only partially configured. For daily editing work, use [`skills/codex-video-use/SKILL.md`](./skills/codex-video-use/SKILL.md).

## What setup should leave behind

- A local clone of this repo in a stable location.
- A Python environment with the `codex-video-use-*` entrypoints installed.
- `ffmpeg` and `ffprobe` on `PATH`.
- A Codex skill symlink at `${CODEX_HOME:-$HOME/.codex}/skills/codex-video-use`.
- `ELEVENLABS_API_KEY` available from the environment or the repo `.env`.

## Setup contract

- Do the setup work directly when possible.
- Ask the user only for the ElevenLabs API key or for permission to install missing system packages.
- Do not start a transcription job as part of setup.
- Finish with a lightweight real verification, not just file existence checks.

## Steps

### 1. Clone or update the repo

```bash
test -d ~/Developer/codex-video-use || git clone https://github.com/AxelkHellberg/codex-video-use ~/Developer/codex-video-use
cd ~/Developer/codex-video-use
git pull --ff-only
```

### 2. Create the virtual environment and install the package

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e .
```

Fallback if `uv` is unavailable:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

### 3. Verify `ffmpeg` and `ffprobe`

```bash
command -v ffmpeg >/dev/null
command -v ffprobe >/dev/null
```

If either command is missing, install `ffmpeg` with the platform package manager before continuing.

### 4. Register the Codex skill

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
ln -sfn ~/Developer/codex-video-use/skills/codex-video-use "${CODEX_HOME:-$HOME/.codex}/skills/codex-video-use"
```

### 5. Configure the ElevenLabs API key

Check for the key in the environment first. If it is not present, look for it in `~/Developer/codex-video-use/.env`. If both are missing, ask the user for a key from <https://elevenlabs.io/app/settings/api-keys> and write:

```bash
printf 'ELEVENLABS_API_KEY=%s\n' "$KEY" > ~/Developer/codex-video-use/.env
chmod 600 ~/Developer/codex-video-use/.env
```

Never echo the key back in logs or commit `.env`.

### 6. Run a lightweight verification

```bash
~/Developer/codex-video-use/.venv/bin/python -c 'from codex_video_use.cli import timeline_main; print("cli import ok")'
ffprobe -version | head -1
```

If the package was installed into the active shell already, `codex-video-use-timeline-view --help` is also a valid verification.

## Handoff

Once setup is complete, tell the user:

- The repo path.
- That they should open Codex inside their footage directory.
- That a good first prompt is `Use $codex-video-use to inventory these takes and propose an edit strategy.`
- That all generated outputs land in `<videos_dir>/edit/`.
