# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Personal emoji/emote collection for chat apps (Slack, Discord, etc.). Contains 3000+ custom emoji images in `emoji/` with Python tooling for maintenance: listing generation and perceptual deduplication.

## Commands

```bash
# Install dependencies (uses uv package manager)
uv sync

# Regenerate README.md and index.html from emoji/ contents
python3 create_listing.py

# Find duplicate emojis (dry run)
python3 dedup.py --dry-run

# Find duplicates with custom threshold (0=exact match, default)
python3 dedup.py --threshold 5 --dry-run

# Actually remove duplicates
python3 dedup.py --dir emoji/

# Or via uv entry point
uv run dedup --dry-run

# Run tests
uv run pytest

# Run tests with verbose output
uv run pytest -v
```

## Architecture

Two standalone Python scripts, no shared modules:

- **`create_listing.py`** — Generates `README.md` (HTML tables) and `index.html` (searchable dark-theme SPA) from all images in `emoji/`. No dependencies beyond stdlib. Both output files are auto-generated and committed by CI on push.

- **`dedup.py`** — Finds and removes duplicate images using multi-algorithm perceptual hashing (pHash, aHash, dHash, colorHash). Uses Union-Find clustering. Animated GIFs get extra frame-by-frame verification including timing. Keeps alphabetically-first filename per duplicate group.

## Key Conventions

- Python >=3.11 required; dependencies managed via `uv` with `uv.lock`
- Image formats: `.png`, `.gif`, `.jpg`, `.jpeg`
- `README.md` and `index.html` are generated artifacts — edit the scripts, not the outputs
- CI uses pinned action SHAs (not tags) for security
- Dependency updates managed by Renovate bot
- Always use `uv run` to execute Python commands (e.g. `uv run pytest`, `uv run ruff`, `uv run python3 script.py`) to ensure the correct virtualenv and dependencies are used
