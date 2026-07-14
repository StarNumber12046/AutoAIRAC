# AutoAIRAC

[![CI](https://github.com/StarNumber12046/AutoAIRAC/actions/workflows/ci.yml/badge.svg)](https://github.com/StarNumber12046/AutoAIRAC/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

Automatically checks whether installed AIRAC navdata is expired for your flight simulators, searches [ruTracker](https://rutracker.org) for an update, downloads only the archives you need via **qBittorrent**, installs them, and sends a **Windows toast** at each step.

> **Disclaimer:** This tool is not affiliated with Navigraph, Laminar Research, Asobo, or ruTracker. You are responsible for complying with the terms of service and licensing requirements of any data sources you use. `config.yaml` contains credentials and is excluded from version control — never commit it.

## Supported simulators

| ID | Simulator | Install target | Torrent pattern |
|----|-----------|----------------|-----------------|
| `xplane12` | X-Plane 12 | `Custom Data/` | `*xplane12_native*` |
| `msfs2020` | MSFS 2020 | `%LOCALAPPDATA%/Packages/.../Community/` | `*msfs*` |
| `msfs2024` | MSFS 2024 | Same (2024 package name) | `*msfs*` |
| `p3d4` | Prepar3D v4 | `NavData/` | `*p3dv4*`, `*p3d4*`, `*as_p3d4*` |
| `p3d5` | Prepar3D v5 | `NavData/` | `*p3dv5*`, `*p3dv45*`, `*as_p3dv45*` |
| `fsx` | FSX / FSX:SE | `NavData/` | `*fsx*`, `*aerosoft*` |

Each simulator is a pluggable adapter under `src/autoairac/simulators/`. Add a new file, register it in `registry.py`, and enable it in config.

## Prerequisites

- **[uv](https://docs.astral.sh/uv/)** — Python and dependency management
- **qBittorrent** with Web UI enabled (`Tools → Options → Web UI`)
- **ruTracker account** — required for magnet/torrent download links
- **Windows 10/11** — native toast notifications via [winotify](https://pypi.org/project/winotify/)

## Quick start

```powershell
git clone https://github.com/StarNumber12046/AutoAIRAC.git
cd AutoAIRAC
uv sync --group dev

copy config.example.yaml config.yaml
# Edit config.yaml — simulator paths, ruTracker login, qBittorrent Web UI password

# Check only (toasts + console, no download)
uv run autoairac --dry-run

# Full pipeline
uv run autoairac

# Run daily (interval from config)
uv run autoairac --watch
```

### Task Scheduler (optional)

| Setting | Value |
|---------|-------|
| Program | `uv` |
| Arguments | `run autoairac` |
| Start in | `C:\path\to\AutoAIRAC` |

Or call the venv entry point directly: `.venv\Scripts\autoairac.exe`

## Configuration

Copy `config.example.yaml` to `config.yaml` (gitignored). Key settings:

| Key | Purpose |
|-----|---------|
| `simulators.enabled` | Which adapters to check/install |
| `paths.xplane12` | X-Plane root folder |
| `rutracker.username` / `password` | Forum login |
| `rutracker.topic_id` | Optional pinned topic (skips search) |
| `qbittorrent.host` | Default `http://127.0.0.1:8080` |

## CLI

```
autoairac [--config PATH] [--dry-run] [--force] [--watch] [-v]
```

| Flag | Description |
|------|-------------|
| `--dry-run` | Expiry check only |
| `--force` | Download/install current cycle even if not expired |
| `--watch` | Loop at `watch_interval_minutes` |

## Pipeline (each step sends a Windows toast)

1. **Checking AIRAC** — current ICAO cycle vs installed data
2. **Per-simulator status**
3. **Update required** — if any simulator is expired
4. **Searching ruTracker**
5. **Torrent found**
6. **Downloading** — selective qBittorrent download
7. **Download complete**
8. **Installing** — copy navdata into simulator paths
9. **Done**

## Project layout

```
src/autoairac/
  airac/          # Cycle math & navdata header parsing
  simulators/     # Pluggable per-sim adapters
  search/         # ruTracker client
  download/       # qBittorrent selective downloader
  install/        # Staging → simulator copy
  notify/         # Windows toasts
  orchestrator.py # Main pipeline
  cli.py
```

## Development

```powershell
uv sync --group dev
uv run pytest
uv build
```

## Releasing on GitHub

1. Create the repository on GitHub (empty, no README).
2. Push:

   ```powershell
   git remote add origin https://github.com/StarNumber12046/AutoAIRAC.git
   git push -u origin main
   ```

3. Tag a release (triggers the release workflow and uploads build artifacts):

   ```powershell
   git tag v0.1.0
   git push origin v0.1.0
   ```

## License

[MIT](LICENSE)