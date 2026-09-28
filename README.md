# Audible bookmark transcriber

## Introduction

This is a small tool for [Audible](https://audible.com) users to extract the clips and bookmarks they saved in their audiobooks as text. Speech-to-text runs locally on your Mac with [mlx-whisper](https://pypi.org/project/mlx-whisper/), so no OpenAI account is needed.

> [!IMPORTANT]
> This tool is only meant to help users use the Audible books they **actually own**.

## Limitations
- Requires a Mac with Apple Silicon (mlx-whisper runs on the GPU via MLX).
- Transcription is set up for English books.

## User guide

### Install
Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then from the repository root:
```
uv sync
```
No ffmpeg, jq or audible-cli installation is needed: audio is decrypted and decoded with [PyAV](https://pyav.basswood.io/), which bundles its own FFmpeg.

### Log in to your Audible account
```
uv run audible-bookmarks login
```
You will be asked for your Audible marketplace (or pass `--country us`). The tool prints an Amazon sign-in URL: open it in your browser, sign in (including any 2FA or captcha), and when you land on a "page not found" page, copy the full URL from the address bar and paste it back into the terminal. The tool never sees your password.

This registers a new Audible device and stores its credentials in `data/audible_configs/audible.json`. Use `--encrypt` to protect that file with a password. To sign out and deregister the device, run `uv run audible-bookmarks logout`.

### List your books
```
uv run audible-bookmarks list
```
Prints the ASIN, title and author of each book in your library.

### Transcribe a book's clips and bookmarks
```
uv run audible-bookmarks transcribe <ASIN>
```
What happens:
1. The book is downloaded as Audible delivers it (encrypted `.aaxc`) together with its license voucher, into `data/audio/<ASIN>/`. Existing downloads are reused.
2. Your clips and bookmarks are fetched from Audible. Clips have a start and end; plain bookmarks only a position, so the 30 seconds after it are used (change with `--bookmark-window SECONDS`).
3. Only the bookmarked ranges are decrypted and decoded, in memory. No DRM-free copy of the book is written to disk.
4. Each range is transcribed locally with Whisper. The default model is `mlx-community/whisper-large-v3-turbo` (about 1.6 GB, downloaded on first use); pick another with `--model`, e.g. `--model mlx-community/whisper-small-mlx`.

Other options:
- `--clip-padding SECONDS` widens every clip by that many seconds on both sides, e.g. `--clip-padding 5` to catch the start and end of sentences the clip cuts off. The clip in Audible is not changed, and the notes keep the clip's own positions. Changing the padding re-transcribes the affected clips on the next run.
- `--save-clips` also writes each clip as an mp3 to `data/audio/<ASIN>/clips/`. These are for your personal use only; do not distribute them.
- `--force` re-transcribes clips that were already transcribed. By default, re-running only transcribes new clips and bookmarks.

### Output
The notes are saved to `data/audio/<ASIN>/transcribed_notes.json`, sorted by position:
```json
[
    {
        "id": "a5UD2AXN0N0DW",
        "kind": "clip",
        "start_ms": 26530133,
        "end_ms": 26560133,
        "timestamp": "07:22:10.133",
        "chapter": "Chapter 13",
        "note": "",
        "text": "end of the semester, but doubted if he could. ...",
        "padding_ms": 0
    }
]
```

## Development
```
uv run pytest                 # tests
uv run ruff check .           # lint
uv run ruff format .          # format
uv run pyrefly check          # type check
```
