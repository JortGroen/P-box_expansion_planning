"""Interface contract package.

Concrete IC-1 through IC-6 implementations are added by the owning agents
after the relevant gate freezes the schema.
"""

from src.contracts.loading_trajectory import (
    LoadingTrajectoryResult,
    TimeDomain,
    validate_loading_trajectory_result,
)

__all__ = [
    "LoadingTrajectoryResult",
    "TimeDomain",
    "validate_loading_trajectory_result",
]

