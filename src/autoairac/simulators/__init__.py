"""Flight simulator adapters."""

from autoairac.simulators.base import InstallResult, SimulatorAdapter, SimulatorStatus
from autoairac.simulators.registry import all_simulator_ids, create_adapter, create_enabled_adapters

__all__ = [
    "InstallResult",
    "SimulatorAdapter",
    "SimulatorStatus",
    "all_simulator_ids",
    "create_adapter",
    "create_enabled_adapters",
]