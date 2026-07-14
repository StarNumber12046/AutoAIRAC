"""Prepar3D and FSX (Aerosoft NavDataPro) adapters."""

from __future__ import annotations

import re
import shutil
from abc import abstractmethod
from pathlib import Path

from autoairac.config import PathsConfig
from autoairac.simulators.base import InstallResult, SimulatorAdapter


class _LegacySimAdapter(SimulatorAdapter):
    _default_path: Path
    _configured_attr: str
    _navdata_subdir: str

    def __init__(self, paths: PathsConfig) -> None:
        super().__init__(paths)
        configured = getattr(paths, self._configured_attr, "")
        self._root = Path(configured).expanduser() if configured else None

    def resolve_install_path(self) -> Path | None:
        if self._root and self._root.is_dir():
            return self._root
        if self._default_path.is_dir():
            return self._default_path
        return None

    def _navdata_dir(self) -> Path | None:
        root = self.resolve_install_path()
        if root is None:
            return None
        for candidate in (
            root / self._navdata_subdir,
            root / "NavData",
            root / "navdata",
        ):
            if candidate.is_dir():
                return candidate
        return root

    def read_installed_cycle(self) -> int | None:
        navdata = self._navdata_dir()
        if navdata is None:
            return None
        for path in navdata.rglob("*"):
            name = path.name
            match = re.search(r"(\d{4})", name)
            if match and path.suffix.lower() in {".txt", ".dat", ".nav", ".zip", ""}:
                return int(match.group(1))
        return None

    @abstractmethod
    def torrent_file_patterns(self) -> tuple[str, ...]:
        ...

    def install_from_staging(self, staging_dir: Path) -> InstallResult:
        navdata = self._navdata_dir()
        if navdata is None:
            return InstallResult(self.id, False, f"{self.display_name} installation not found.")

        payloads = [p for p in staging_dir.rglob("*") if p.is_dir() or p.suffix.lower() == ".zip"]
        if not payloads:
            return InstallResult(self.id, False, f"No legacy sim navdata in {staging_dir}.")

        installed: list[str] = []
        for item in payloads:
            dest = navdata / item.name
            if item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
            installed.append(item.name)

        return InstallResult(
            self.id,
            True,
            f"Copied {len(installed)} item(s) to {navdata}.",
            tuple(installed),
        )


class P3D4Adapter(_LegacySimAdapter):
    id = "p3d4"
    display_name = "Prepar3D v4"
    _default_path = Path("C:/Program Files/Lockheed Martin/Prepar3D v4")
    _configured_attr = "p3d4"
    _navdata_subdir = "NavData"

    def torrent_file_patterns(self) -> tuple[str, ...]:
        return ("*p3dv4*", "*p3d4*", "*p3d_v4*", "*as_p3d4*", "*as_p3dv4*")


class P3D5Adapter(_LegacySimAdapter):
    id = "p3d5"
    display_name = "Prepar3D v5"
    _default_path = Path("C:/Program Files/Lockheed Martin/Prepar3D v5")
    _configured_attr = "p3d5"
    _navdata_subdir = "NavData"

    def torrent_file_patterns(self) -> tuple[str, ...]:
        return ("*p3dv5*", "*p3d5*", "*p3d_v5*", "*as_p3d5*", "*as_p3dv5*")


class FSXAdapter(_LegacySimAdapter):
    id = "fsx"
    display_name = "FSX / FSX:SE"
    _default_path = Path("C:/Program Files (x86)/Steam/steamapps/common/FSX")
    _configured_attr = "fsx"
    _navdata_subdir = "NavData"

    def torrent_file_patterns(self) -> tuple[str, ...]:
        return ("*fsx*", "*as_fsx*", "*aerosoft*")