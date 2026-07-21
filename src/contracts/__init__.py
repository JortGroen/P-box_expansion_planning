"""Interface contract package.

Concrete IC-1 through IC-6 implementations are added by the owning agents
after the relevant gate freezes the schema.
"""

from src.contracts.loading_trajectory import (
    LoadingTrajectoryResult,
    TimeDomain,
    validate_loading_trajectory_result,
)
from src.contracts.net_load import (
    ComponentKind,
    ComponentProvenance,
    NetLoadComponent,
    NetLoadProvider,
    NetLoadResult,
    build_net_load_result,
    validate_net_load_result,
)

__all__ = [
    "ComponentKind",
    "ComponentProvenance",
    "LoadingTrajectoryResult",
    "NetLoadComponent",
    "NetLoadProvider",
    "NetLoadResult",
    "TimeDomain",
    "build_net_load_result",
    "validate_loading_trajectory_result",
    "validate_net_load_result",
]

