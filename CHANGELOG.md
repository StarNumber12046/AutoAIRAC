# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Prepar3D v4 (`p3d4`) simulator adapter with version-specific torrent file patterns

### Changed

- P3D v5 and FSX torrent patterns are now version-specific (no longer share broad `*p3d*` / `*fsx*` patterns)

## [0.1.0] - 2026-07-13

### Added

- Automatic AIRAC expiry detection for X-Plane 12, MSFS 2020/2024, P3D v5, and FSX
- ruTracker search and torrent resolution with optional pinned `topic_id`
- Selective qBittorrent downloads (per-simulator zip patterns)
- Automatic navdata extraction and installation
- Windows toast notifications for each pipeline step
- CLI with `--dry-run`, `--force`, and `--watch` modes
- YAML configuration via `config.example.yaml`
- uv-based project setup with `uv.lock`

### Fixed

- AIRAC cycle calculation with correct year rollover (e.g. 2413 → 2501)
- qBittorrent hash matching (case-insensitive info-hash)
- X-Plane 12 cycle detection from multi-line navdata headers
- X-Plane torrent selection limited to `xplane12_native` archives

[0.1.0]: https://github.com/StarNumber12046/AutoAIRAC/releases/tag/v0.1.0