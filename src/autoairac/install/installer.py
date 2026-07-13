"""Install extracted navdata into configured simulators."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from autoairac.simulators.base import InstallResult, SimulatorAdapter

logger = logging.getLogger(__name__)


class NavdataInstaller:
    """Delegate installation to per-simulator adapters."""

    def install_all(
        self,
        adapters: list[SimulatorAdapter],
        staging_dir: Path,
    ) -> list[InstallResult]:
        results: list[InstallResult] = []
        for adapter in adapters:
            logger.info("Installing navdata for %s …", adapter.display_name)
            result = adapter.install_from_staging(staging_dir)
            results.append(result)
            logger.info("%s", result.message)
        return results

    @staticmethod
    def cleanup_staging(staging_dir: Path) -> None:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)