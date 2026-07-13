"""X-Plane 12 navdata adapter."""

from __future__ import annotations

import shutil
from pathlib import Path

from autoairac.airac.cycle import parse_cycle_from_navdata_header
from autoairac.config import PathsConfig
from autoairac.simulators.base import InstallResult, SimulatorAdapter

_NAVDATA_FILES = (
    "earth_fix.dat",
    "earth_awy.dat",
    "earth_nav.dat",
    "earth_hold.dat",
    "earth_mora.dat",
    "earth_msa.dat",
)

_CYCLE_PROBE_FILES = ("earth_fix.dat", "earth_nav.dat", "earth_awy.dat")


class XPlane12Adapter(SimulatorAdapter):
    id = "xplane12"
    display_name = "X-Plane 12"

    def __init__(self, paths: PathsConfig) -> None:
        super().__init__(paths)
        self._root = Path(paths.xplane12).expanduser() if paths.xplane12 else None

    def resolve_install_path(self) -> Path | None:
        if self._root and self._root.is_dir():
            return self._root
        for candidate in (
            Path("C:/X-Plane 12"),
            Path.home() / "X-Plane 12",
        ):
            if candidate.is_dir():
                return candidate
        return None

    def _custom_data_dir(self) -> Path | None:
        root = self.resolve_install_path()
        if root is None:
            return None
        custom = root / "Custom Data"
        return custom if custom.is_dir() or (root / "Resources").is_dir() else None

    def read_installed_cycle(self) -> int | None:
        custom = self._custom_data_dir()
        if custom is None:
            root = self.resolve_install_path()
            if root is None:
                return None
            default = root / "Resources" / "default data" / "earth_fix.dat"
            if default.is_file():
                return self._cycle_from_file(default)
            return None

        for name in _CYCLE_PROBE_FILES:
            probe = custom / name
            if probe.is_file():
                cycle = self._cycle_from_file(probe)
                if cycle is not None:
                    return cycle
        return None

    @staticmethod
    def _cycle_from_file(path: Path) -> int | None:
        try:
            with path.open(encoding="utf-8", errors="ignore") as handle:
                for _ in range(5):
                    line = handle.readline()
                    if not line:
                        break
                    cycle = parse_cycle_from_navdata_header(line)
                    if cycle is not None:
                        return cycle
        except OSError:
            return None
        return None

    def torrent_file_patterns(self) -> tuple[str, ...]:
        # Navigraph packs ship per-sim zips; XP12 uses the *_native_* archive only.
        return ("*xplane12_native*",)

    def install_from_staging(self, staging_dir: Path) -> InstallResult:
        custom = self._custom_data_dir()
        root = self.resolve_install_path()
        if custom is None and root is None:
            return InstallResult(self.id, False, "X-Plane 12 installation not found.")

        target = custom or (root / "Custom Data")
        target.mkdir(parents=True, exist_ok=True)

        installed: list[str] = []
        for name in _NAVDATA_FILES:
            source = self._find_in_staging(staging_dir, name)
            if source is None:
                continue
            dest = target / name
            shutil.copy2(source, dest)
            installed.append(name)

        cifp_src = self._find_cifp_dir(staging_dir)
        if cifp_src is not None:
            cifp_dest = target / "CIFP"
            if cifp_dest.exists():
                shutil.rmtree(cifp_dest)
            shutil.copytree(cifp_src, cifp_dest)
            installed.append("CIFP/")

        airspace_src = self._find_in_staging(staging_dir, "airspace.txt")
        if airspace_src is not None:
            airspace_dest = target / "airspaces"
            airspace_dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(airspace_src, airspace_dest / "airspace.txt")
            installed.append("airspaces/airspace.txt")

        atc_src = self._find_in_staging(staging_dir, "atc.dat")
        if atc_src is not None:
            atc_dest = target / "1200 atc data" / "Earth nav data"
            atc_dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(atc_src, atc_dest / "atc.dat")
            installed.append("1200 atc data/Earth nav data/atc.dat")

        if not installed:
            return InstallResult(
                self.id,
                False,
                f"No X-Plane 12 navdata found in {staging_dir}.",
            )
        return InstallResult(
            self.id,
            True,
            f"Installed {len(installed)} item(s) to {target}.",
            tuple(installed),
        )

    @staticmethod
    def _find_in_staging(staging_dir: Path, filename: str) -> Path | None:
        for path in staging_dir.rglob(filename):
            if path.is_file():
                return path
        return None

    @staticmethod
    def _find_cifp_dir(staging_dir: Path) -> Path | None:
        for path in staging_dir.rglob("CIFP"):
            if path.is_dir() and any(path.glob("*.dat")):
                return path
        for path in staging_dir.rglob("CIFP"):
            if path.is_dir():
                return path
        return None