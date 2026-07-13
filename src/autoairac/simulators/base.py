"""Abstract simulator adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from autoairac.config import PathsConfig


@dataclass(frozen=True)
class SimulatorStatus:
    simulator_id: str
    display_name: str
    install_path: Path | None
    installed_cycle: int | None
    current_cycle: int
    expired: bool
    message: str


@dataclass(frozen=True)
class InstallResult:
    simulator_id: str
    success: bool
    message: str
    files_installed: tuple[str, ...] = ()


class SimulatorAdapter(ABC):
    """Pluggable backend for a single flight simulator."""

    id: ClassVar[str]
    display_name: ClassVar[str]

    def __init__(self, paths: PathsConfig) -> None:
        self._paths = paths

    @abstractmethod
    def resolve_install_path(self) -> Path | None:
        """Return the simulator root / navdata target directory."""

    @abstractmethod
    def read_installed_cycle(self) -> int | None:
        """Read the currently installed AIRAC cycle, if detectable."""

    @abstractmethod
    def torrent_file_patterns(self) -> tuple[str, ...]:
        """Glob-style substrings used to select files inside a torrent."""

    @abstractmethod
    def install_from_staging(self, staging_dir: Path) -> InstallResult:
        """Copy extracted navdata from *staging_dir* into the simulator."""

    def status(self, current_cycle: int) -> SimulatorStatus:
        from autoairac.airac.cycle import is_cycle_expired

        install_path = self.resolve_install_path()
        installed = self.read_installed_cycle()
        if installed is None:
            expired = True
            message = "No navdata cycle detected — treat as expired."
        elif is_cycle_expired(installed):
            expired = True
            message = f"AIRAC {installed} expired (current: {current_cycle})."
        else:
            expired = False
            message = f"AIRAC {installed} is current."

        return SimulatorStatus(
            simulator_id=self.id,
            display_name=self.display_name,
            install_path=install_path,
            installed_cycle=installed,
            current_cycle=current_cycle,
            expired=expired,
            message=message,
        )