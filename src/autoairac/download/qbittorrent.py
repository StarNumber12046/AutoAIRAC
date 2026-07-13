"""qBittorrent Web API integration with selective file download."""

from __future__ import annotations

import fnmatch
import logging
import re
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import qbittorrentapi

from autoairac.config import QBittorrentConfig
from autoairac.simulators.base import SimulatorAdapter

logger = logging.getLogger(__name__)

_INFO_HASH_RE = re.compile(r"btih:([0-9a-fA-F]{32,40})", re.IGNORECASE)
_STALLED_STATES = frozenset({"stalledUP", "stalledDL", "pausedUP", "uploading", "stoppedUP"})


@dataclass(frozen=True)
class DownloadResult:
    torrent_hash: str
    save_path: Path
    downloaded_files: tuple[str, ...]
    extracted_to: Path | None


class QBittorrentDownloader:
    """Add torrents via qBittorrent and download only simulator-specific files."""

    def __init__(self, config: QBittorrentConfig) -> None:
        self._config = config
        self._client = qbittorrentapi.Client(
            host=config.host,
            username=config.username,
            password=config.password,
        )

    def connect(self) -> None:
        self._client.auth_log_in()

    def download_selective(
        self,
        torrent_url: str,
        adapters: list[SimulatorAdapter],
        *,
        extract_dir: Path,
        poll_interval: float = 5.0,
        timeout: float = 7200.0,
        on_progress: Callable[[str], None] | None = None,
    ) -> DownloadResult:
        def report(message: str) -> None:
            logger.info(message)
            if on_progress is not None:
                on_progress(message)

        self.connect()
        patterns = self._collect_patterns(adapters)
        info_hash = _info_hash_from_url(torrent_url)

        if self._config.download_category:
            try:
                self._client.torrents_create_category(self._config.download_category)
            except qbittorrentapi.Conflict409Error:
                pass

        existing_hash = self._find_torrent_hash(torrent_url, info_hash)
        if existing_hash is not None:
            report("Torrent already present in qBittorrent — reusing it.")
        else:
            report("Adding torrent to qBittorrent…")
            kwargs: dict = {}
            if self._config.save_path:
                kwargs["save_path"] = self._config.save_path
            if self._config.download_category:
                kwargs["category"] = self._config.download_category

            self._client.torrents_add(urls=torrent_url, **kwargs)
            existing_hash = self._wait_for_hash(
                torrent_url,
                info_hash,
                timeout=60.0,
                on_progress=report,
            )
            if existing_hash is None:
                raise RuntimeError(
                    "Torrent was not added to qBittorrent. "
                    "Check that the Web UI is enabled and the magnet/link is valid."
                )

        torrent_hash = existing_hash
        if self._config.download_category:
            try:
                self._client.torrents_set_category(
                    torrent_hashes=torrent_hash,
                    category=self._config.download_category,
                )
            except qbittorrentapi.APIError:
                pass

        selected_ids = self._apply_file_priorities(torrent_hash, patterns)
        self._client.torrents_resume(torrent_hash)
        try:
            self._client.torrents_set_force_start(torrent_hashes=torrent_hash, value=True)
        except qbittorrentapi.APIError:
            pass

        if selected_ids and self._selected_files_complete(torrent_hash, selected_ids):
            report("Selected files already downloaded.")
        else:
            report("Waiting for selected files to finish downloading…")
            info = self._wait_until_selected_complete(
                torrent_hash,
                selected_ids,
                poll_interval,
                timeout,
                on_progress=report,
            )
        info = self._client.torrents_info(torrent_hashes=torrent_hash)[0]
        save_path = Path(info.save_path)
        content_path = Path(info.content_path) if info.content_path else save_path

        extract_dir.mkdir(parents=True, exist_ok=True)
        files = self._selected_file_names(torrent_hash, selected_ids)
        extracted = self._extract_archives(content_path, extract_dir, files)
        return DownloadResult(
            torrent_hash=torrent_hash,
            save_path=content_path,
            downloaded_files=files,
            extracted_to=extracted,
        )

    def _collect_patterns(self, adapters: list[SimulatorAdapter]) -> list[str]:
        patterns: list[str] = []
        for adapter in adapters:
            patterns.extend(adapter.torrent_file_patterns())
        return patterns

    def _find_torrent_hash(self, torrent_url: str, info_hash: str | None) -> str | None:
        for entry in self._client.torrents.info():
            if info_hash and entry.hash.lower() == info_hash:
                return entry.hash
            magnet = (entry.magnet_uri or "").lower()
            if info_hash and info_hash in magnet:
                return entry.hash
            if torrent_url in (entry.magnet_uri or ""):
                return entry.hash
        return None

    def _wait_for_hash(
        self,
        torrent_url: str,
        info_hash: str | None,
        *,
        timeout: float,
        on_progress: Callable[[str], None] | None = None,
    ) -> str | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            found = self._find_torrent_hash(torrent_url, info_hash)
            if found is not None:
                return found
            if on_progress is not None:
                remaining = int(deadline - time.monotonic())
                on_progress(f"Waiting for torrent to appear in qBittorrent ({remaining}s)…")
            time.sleep(2.0)
        return self._find_torrent_hash(torrent_url, info_hash)

    def _apply_file_priorities(self, torrent_hash: str, patterns: list[str]) -> list[int]:
        files = self._client.torrents_files(torrent_hash)
        if not files:
            return []

        selected_ids: list[int] = []
        skipped_ids: list[int] = []
        for entry in files:
            if self._matches_any(entry.name, patterns):
                selected_ids.append(entry.id)
            else:
                skipped_ids.append(entry.id)

        if not selected_ids:
            logger.warning(
                "No torrent files matched simulator patterns — downloading all files."
            )
            selected_ids = [entry.id for entry in files]
            skipped_ids = []

        if skipped_ids:
            self._client.torrents_file_priority(
                torrent_hash=torrent_hash,
                file_ids=skipped_ids,
                priority=0,
            )
        if selected_ids:
            self._client.torrents_file_priority(
                torrent_hash=torrent_hash,
                file_ids=selected_ids,
                priority=7,
            )

        names = [entry.name for entry in files if entry.id in selected_ids]
        logger.info("Selected %s file(s): %s", len(names), ", ".join(names[:5]))
        return selected_ids

    @staticmethod
    def _matches_any(filename: str, patterns: list[str]) -> bool:
        lowered = filename.lower().replace("\\", "/")
        basename = lowered.rsplit("/", 1)[-1]
        for pattern in patterns:
            normalized = pattern.lower().replace("\\", "/")
            if fnmatch.fnmatch(lowered, normalized) or fnmatch.fnmatch(basename, normalized):
                return True
            needle = normalized.strip("*")
            if needle and needle in lowered:
                return True
        return False

    def _selected_files_complete(self, torrent_hash: str, selected_ids: list[int]) -> bool:
        if not selected_ids:
            return False
        info = self._client.torrents_info(torrent_hashes=torrent_hash)
        save_root = Path(info[0].content_path) if info and info[0].content_path else None
        if save_root is None and info:
            save_root = Path(info[0].save_path)

        files = self._client.torrents_files(torrent_hash)
        selected = [entry for entry in files if entry.id in selected_ids]
        if not selected:
            return False

        for entry in selected:
            if entry.progress >= 0.999:
                continue
            if save_root is not None and self._file_exists_on_disk(save_root, entry.name, entry.size):
                continue
            return False
        return True

    @staticmethod
    def _file_exists_on_disk(root: Path, torrent_name: str, expected_size: int) -> bool:
        relative = Path(torrent_name.replace("\\", "/"))
        if len(relative.parts) > 1 and relative.parts[0] == root.name:
            relative = Path(*relative.parts[1:])
        candidate = root / relative
        if not candidate.is_file():
            candidate = root / relative.name
        return candidate.is_file() and candidate.stat().st_size >= expected_size * 0.99

    def _wait_until_selected_complete(
        self,
        torrent_hash: str,
        selected_ids: list[int],
        poll_interval: float,
        timeout: float,
        *,
        on_progress: Callable[[str], None] | None = None,
    ):
        deadline = time.monotonic() + timeout
        last_report = 0.0
        while time.monotonic() < deadline:
            info = self._client.torrents_info(torrent_hashes=torrent_hash)
            if not info:
                time.sleep(poll_interval)
                continue

            torrent = info[0]
            if selected_ids and self._selected_files_complete(torrent_hash, selected_ids):
                return torrent

            if torrent.progress >= 1.0 and torrent.state in _STALLED_STATES:
                return torrent

            if torrent.state in {"error", "missingFiles"} and torrent.progress <= 0:
                raise RuntimeError(f"Torrent failed with state: {torrent.state}")

            if on_progress is not None and time.monotonic() - last_report >= 30.0:
                if selected_ids:
                    files = self._client.torrents_files(torrent_hash)
                    selected = [entry for entry in files if entry.id in selected_ids]
                    if selected:
                        avg = sum(entry.progress for entry in selected) / len(selected)
                        on_progress(
                            f"Downloading… {avg * 100:.0f}% "
                            f"({torrent.state}, {len(selected)} file(s))"
                        )
                else:
                    on_progress(f"Downloading… {torrent.progress * 100:.0f}% ({torrent.state})")
                last_report = time.monotonic()

            time.sleep(poll_interval)

        raise TimeoutError("Timed out waiting for torrent download to complete.")

    def _selected_file_names(self, torrent_hash: str, selected_ids: list[int]) -> tuple[str, ...]:
        files = self._client.torrents_files(torrent_hash)
        if selected_ids:
            return tuple(entry.name for entry in files if entry.id in selected_ids)
        return tuple(entry.name for entry in files)

    @staticmethod
    def _extract_archives(
        content_path: Path,
        extract_dir: Path,
        selected_names: tuple[str, ...],
    ) -> Path | None:
        archives: list[Path] = []
        for name in selected_names:
            basename = Path(name.replace("\\", "/")).name
            candidate = content_path / basename
            if candidate.is_file():
                archives.append(candidate)
            elif content_path.is_dir():
                found = next(content_path.rglob(basename), None)
                if found is not None:
                    archives.append(found)

        if not archives and content_path.is_file() and content_path.suffix.lower() == ".zip":
            archives = [content_path]

        if not archives:
            if content_path.is_dir():
                return content_path
            return None

        for archive in archives:
            target = extract_dir / archive.stem
            target.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(archive, "r") as zf:
                zf.extractall(target)
        return extract_dir


def _info_hash_from_url(url: str) -> str | None:
    match = _INFO_HASH_RE.search(url)
    if not match:
        return None
    return match.group(1).lower()