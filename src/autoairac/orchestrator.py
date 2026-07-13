"""Main AIRAC check → search → download → install pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from autoairac.airac.cycle import current_airac_cycle
from autoairac.config import AppConfig
from autoairac.download.qbittorrent import QBittorrentDownloader
from autoairac.install.installer import NavdataInstaller
from autoairac.notify.windows import NotifyLevel, WindowsNotifier
from autoairac.search.rutracker import RuTrackerClient
from autoairac.simulators.base import InstallResult, SimulatorStatus
from autoairac.simulators.registry import create_enabled_adapters

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineResult:
    checked: list[SimulatorStatus]
    expired_simulators: list[str]
    target_cycle: int | None
    torrent_title: str | None
    download_path: Path | None
    install_results: list[InstallResult]
    skipped: bool
    message: str


class AutoAIRACOrchestrator:
    """Coordinates expiry checks, torrent acquisition, and installation."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._notifier = WindowsNotifier(
            app_id=config.notifications.app_id,
            enabled=config.notifications.enabled,
        )
        self._installer = NavdataInstaller()

    def run(self, *, dry_run: bool = False, force: bool = False) -> PipelineResult:
        current = current_airac_cycle()
        adapters = create_enabled_adapters(self._config.simulators.enabled, self._config.paths)

        self._notifier.step(
            "Checking AIRAC",
            f"Current cycle: {current}. Scanning {len(adapters)} simulator(s)…",
        )

        statuses = [adapter.status(current) for adapter in adapters]
        expired = [s for s in statuses if s.expired or force]

        for status in statuses:
            level = NotifyLevel.WARNING if status.expired else NotifyLevel.SUCCESS
            self._notifier.step(status.display_name, status.message, level=level)

        if not expired:
            msg = "All configured simulators have a current AIRAC cycle."
            self._notifier.step("Up to date", msg, level=NotifyLevel.SUCCESS)
            return PipelineResult(
                checked=statuses,
                expired_simulators=[],
                target_cycle=None,
                torrent_title=None,
                download_path=None,
                install_results=[],
                skipped=True,
                message=msg,
            )

        expired_ids = {s.simulator_id for s in expired}
        expired_adapters = [a for a in adapters if a.id in expired_ids]
        target_cycle = current

        names = ", ".join(s.display_name for s in expired)
        self._notifier.step(
            "Update required",
            f"Expired: {names}. Target AIRAC {target_cycle}.",
            level=NotifyLevel.WARNING,
        )

        if dry_run:
            msg = f"Dry run — would search ruTracker for AIRAC {target_cycle}."
            self._notifier.step("Dry run", msg)
            return PipelineResult(
                checked=statuses,
                expired_simulators=list(expired_ids),
                target_cycle=target_cycle,
                torrent_title=None,
                download_path=None,
                install_results=[],
                skipped=True,
                message=msg,
            )

        torrent = self._search_torrent(target_cycle)
        if torrent is None:
            msg = f"No ruTracker torrent found for AIRAC {target_cycle}."
            self._notifier.step("Search failed", msg, level=NotifyLevel.ERROR)
            return PipelineResult(
                checked=statuses,
                expired_simulators=list(expired_ids),
                target_cycle=target_cycle,
                torrent_title=None,
                download_path=None,
                install_results=[],
                skipped=True,
                message=msg,
            )

        self._notifier.step(
            "Torrent found",
            torrent.title,
            level=NotifyLevel.SUCCESS,
        )

        staging = self._config.resolved_staging_dir() / f"airac_{target_cycle}"
        staging.mkdir(parents=True, exist_ok=True)

        try:
            download = self._download_torrent(
                torrent.download_url,
                expired_adapters,
                staging,
            )
        except Exception as exc:
            msg = f"Download failed: {exc}"
            logger.exception(msg)
            self._notifier.step("Download failed", msg, level=NotifyLevel.ERROR)
            return PipelineResult(
                checked=statuses,
                expired_simulators=list(expired_ids),
                target_cycle=target_cycle,
                torrent_title=torrent.title,
                download_path=None,
                install_results=[],
                skipped=True,
                message=msg,
            )

        self._notifier.step(
            "Download complete",
            f"{len(download.downloaded_files)} file(s) saved.",
            level=NotifyLevel.SUCCESS,
        )

        extract_root = download.extracted_to or download.save_path
        install_results = self._install(expired_adapters, Path(extract_root))

        for result in install_results:
            level = NotifyLevel.SUCCESS if result.success else NotifyLevel.ERROR
            self._notifier.step(
                f"Install — {result.simulator_id}",
                result.message,
                level=level,
            )

        successes = sum(1 for r in install_results if r.success)
        if successes == len(install_results):
            msg = f"AIRAC {target_cycle} installed for all expired simulators."
            self._notifier.step("Done", msg, level=NotifyLevel.SUCCESS)
        else:
            msg = f"Installed {successes}/{len(install_results)} simulator(s)."
            self._notifier.step("Partial success", msg, level=NotifyLevel.WARNING)

        if successes:
            statuses = [adapter.status(current) for adapter in adapters]

        return PipelineResult(
            checked=statuses,
            expired_simulators=list(expired_ids),
            target_cycle=target_cycle,
            torrent_title=torrent.title,
            download_path=Path(extract_root),
            install_results=install_results,
            skipped=False,
            message=msg,
        )

    def _search_torrent(self, target_cycle: int):
        self._notifier.step(
            "Searching ruTracker",
            f"Looking for AIRAC {target_cycle}…",
        )
        with RuTrackerClient(self._config.rutracker) as client:
            return client.find_airac_torrent(target_cycle)

    def _download_torrent(self, url: str, adapters, staging: Path):
        self._notifier.step(
            "Downloading",
            "Adding torrent to qBittorrent (selective files)…",
        )
        downloader = QBittorrentDownloader(self._config.qbittorrent)

        def on_progress(message: str) -> None:
            self._notifier.step("Downloading", message)

        return downloader.download_selective(
            url,
            adapters,
            extract_dir=staging,
            on_progress=on_progress,
        )

    def _install(self, adapters, staging: Path) -> list[InstallResult]:
        self._notifier.step("Installing", "Copying navdata into simulators…")
        return self._installer.install_all(adapters, staging)