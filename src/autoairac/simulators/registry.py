"""Simulator adapter registry."""

from __future__ import annotations

from autoairac.config import PathsConfig, SimulatorId
from autoairac.simulators.base import SimulatorAdapter
from autoairac.simulators.msfs import MSFS2020Adapter, MSFS2024Adapter
from autoairac.simulators.p3d_fsx import FSXAdapter, P3D4Adapter, P3D5Adapter
from autoairac.simulators.xplane12 import XPlane12Adapter

_ADAPTERS: dict[SimulatorId, type[SimulatorAdapter]] = {
    "xplane12": XPlane12Adapter,
    "msfs2020": MSFS2020Adapter,
    "msfs2024": MSFS2024Adapter,
    "p3d4": P3D4Adapter,
    "p3d5": P3D5Adapter,
    "fsx": FSXAdapter,
}


def create_adapter(simulator_id: SimulatorId, paths: PathsConfig) -> SimulatorAdapter:
    try:
        cls = _ADAPTERS[simulator_id]
    except KeyError as exc:
        raise ValueError(f"Unknown simulator: {simulator_id}") from exc
    return cls(paths)


def create_enabled_adapters(
    enabled: list[SimulatorId],
    paths: PathsConfig,
) -> list[SimulatorAdapter]:
    return [create_adapter(sim_id, paths) for sim_id in enabled]


def all_simulator_ids() -> list[SimulatorId]:
    return list(_ADAPTERS.keys())