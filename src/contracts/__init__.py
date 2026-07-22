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
    ALLOWED_COMPONENT_ARTIFACT_STATUSES,
    ComponentAdapterSkeleton,
    ComponentKind,
    ComponentProvenance,
    REAL_COMPONENT_WIRING_KINDS,
    NetLoadAssemblyPlan,
    NetLoadComponent,
    NetLoadProvider,
    NetLoadResult,
    REQUIRED_INTEGRATION_COMPONENT_KINDS,
    assemble_net_load_from_real_component_outputs,
    assemble_net_load_from_components,
    build_net_load_result,
    validate_component_adapter_skeletons,
    validate_real_component_adapter_readiness,
    validate_net_load_result,
)

__all__ = [
    "ALLOWED_COMPONENT_ARTIFACT_STATUSES",
    "ComponentAdapterSkeleton",
    "ComponentKind",
    "ComponentProvenance",
    "LoadingTrajectoryResult",
    "NetLoadAssemblyPlan",
    "NetLoadComponent",
    "NetLoadProvider",
    "NetLoadResult",
    "REAL_COMPONENT_WIRING_KINDS",
    "REQUIRED_INTEGRATION_COMPONENT_KINDS",
    "TimeDomain",
    "assemble_net_load_from_real_component_outputs",
    "assemble_net_load_from_components",
    "build_net_load_result",
    "validate_loading_trajectory_result",
    "validate_component_adapter_skeletons",
    "validate_net_load_result",
    "validate_real_component_adapter_readiness",
]

