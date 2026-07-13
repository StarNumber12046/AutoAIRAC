"""Microsoft Flight Simulator navdata adapters."""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

from autoairac.airac.cycle import parse_cycle_from_navdata_header
from autoairac.config import PathsConfig
from autoairac.simulators.base import InstallResult, SimulatorAdapter

_MSFS_PACKAGES = {
    "msfs2020": "Microsoft.FlightSimulator_8wekyb3d8bbwe",
    "msfs2024": "Microsoft.Limitless_8wekyb3d8bbwe",
}


def _detect_msfs_community(package_name: str) -> Path | None:
    local = os.environ.get("LOCALAPPDATA", "")
    if not local:
        return None
    base = (
        Path(local)
        / "Packages"
        / package_name
        / "LocalCache"
        / "Packages"
    )
    community = base / "Community"
    if community.is_dir():
        return community
    if base.is_dir():
        return base
    return None


class _MSFSAdapterBase(SimulatorAdapter):
    _package_name: str

    def __init__(self, paths: PathsConfig, community_override: str) -> None:
        super().__init__(paths)
        self._community_override = (
            Path(community_override).expanduser() if community_override else None
        )

    def resolve_install_path(self) -> Path | None:
        if self._community_override and self._community_override.is_dir():
            return self._community_override
        return _detect_msfs_community(self._package_name)

    def _navigraph_dir(self) -> Path | None:
        community = self.resolve_install_path()
        if community is None:
            return None
        for candidate in (
            community / "navigraph-nav-base",
            community / "fsltl-trafficinjector",
        ):
            if candidate.is_dir():
                return candidate
        for entry in community.iterdir():
            if entry.is_dir() and "navigraph" in entry.name.lower():
                return entry
        return community

    def read_installed_cycle(self) -> int | None:
        target = self._navigraph_dir()
        if target is None:
            return None

        for manifest in target.rglob("manifest.json"):
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for key in ("package_version", "version", "title"):
                value = data.get(key, "")
                if isinstance(value, str):
                    match = re.search(r"(\d{4})", value)
                    if match:
                        return int(match.group(1))

        for nav_file in target.rglob("*.nav"):
            try:
                header = nav_file.read_text(encoding="utf-8", errors="ignore")[:200]
            except OSError:
                continue
            cycle = parse_cycle_from_navdata_header(header)
            if cycle is not None:
                return cycle

        for folder in target.iterdir():
            if folder.is_dir():
                match = re.search(r"(\d{4})", folder.name)
                if match:
                    return int(match.group(1))
        return None

    def torrent_file_patterns(self) -> tuple[str, ...]:
        return (
            "*msfs*",
            "*microsoft*flight*simulator*",
            "*flightsimulator*",
        )

    def install_from_staging(self, staging_dir: Path) -> InstallResult:
        community = self.resolve_install_path()
        if community is None:
            return InstallResult(self.id, False, f"{self.display_name} Community folder not found.")

        package_dirs = [
            p
            for p in staging_dir.rglob("*")
            if p.is_dir() and p.name.lower().startswith("navigraph")
        ]
        if not package_dirs:
            package_dirs = [p for p in staging_dir.iterdir() if p.is_dir()]

        if not package_dirs:
            return InstallResult(
                self.id,
                False,
                f"No MSFS navdata package found in {staging_dir}.",
            )

        installed: list[str] = []
        for package in package_dirs:
            dest = community / package.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(package, dest)
            installed.append(package.name)

        return InstallResult(
            self.id,
            True,
            f"Installed {len(installed)} package(s) to {community}.",
            tuple(installed),
        )


class MSFS2020Adapter(_MSFSAdapterBase):
    id = "msfs2020"
    display_name = "Microsoft Flight Simulator (2020)"
    _package_name = _MSFS_PACKAGES["msfs2020"]

    def __init__(self, paths: PathsConfig) -> None:
        super().__init__(paths, paths.msfs2020_community)


class MSFS2024Adapter(_MSFSAdapterBase):
    id = "msfs2024"
    display_name = "Microsoft Flight Simulator 2024"
    _package_name = _MSFS_PACKAGES["msfs2024"]

    def __init__(self, paths: PathsConfig) -> None:
        super().__init__(paths, paths.msfs2024_community)