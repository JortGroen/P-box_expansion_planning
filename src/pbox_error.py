"""Output-domain model-error endpoint propagation for p-box scaffolding.

This E5.S3 scaffold consumes the shared IC-2 ``LoadingTrajectoryResult`` and
applies G1-A2 output-error endpoints to loading trajectories before event
detection. It is synthetic/protocol code only until Q-5, G2, A-013, and the
capacity-denominator decisions allow paper-facing event analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from src.contracts.loading_trajectory import (
    LoadingTrajectoryResult,
    validate_loading_trajectory_result,
)
from src.evaluator_sum import count_import_overload_episodes
from src.pbox import ProbabilityEstimate, _wilson_interval

EnvelopeValue = float | Sequence[float] | np.ndarray


@dataclass(frozen=True)
class OutputErrorEnvelope:
    """G1-A2 output-error endpoint envelope in loading p.u.

    Parameters
    ----------
    epsilon_grid:
        Symmetric relative grid-model loading envelope. Values are
        dimensionless and must satisfy ``0 <= epsilon_grid < 1``.
    epsilon_tier1_minus:
        Additive lower Tier-1 endpoint in loading p.u.
    epsilon_tier1_plus:
        Additive upper Tier-1 endpoint in loading p.u.
    """

    epsilon_grid: EnvelopeValue
    epsilon_tier1_minus: EnvelopeValue
    epsilon_tier1_plus: EnvelopeValue


@dataclass(frozen=True)
class OutputErrorEndpointTrajectories:
    """Lower/upper endpoint trajectories after output-domain widening."""

    lower_loading_pu: np.ndarray
    upper_loading_pu: np.ndarray
    lower_import_loading_pu: np.ndarray
    upper_import_loading_pu: np.ndarray

    def __post_init__(self) -> None:
        arrays = (
            self.lower_loading_pu,
            self.upper_loading_pu,
            self.lower_import_loading_pu,
            self.upper_import_loading_pu,
        )
        shapes = {array.shape for array in arrays}
        if len(shapes) != 1:
            raise ValueError("endpoint trajectories must have identical shapes")
        if any(array.ndim != 1 for array in arrays):
            raise ValueError("endpoint trajectories must be one-dimensional")
        if any(not np.isfinite(array).all() for array in arrays):
            raise ValueError("endpoint trajectories must contain only finite values")
        if np.any(self.lower_loading_pu > self.upper_loading_pu):
            raise ValueError("expected lower loading <= upper loading")


@dataclass(frozen=True)
class EndpointEventEvaluation:
    """Event classification for one preserved aleatory sample identity."""

    sample_index: int
    lower_event: bool
    upper_event: bool
    lower_episode_count: int
    upper_episode_count: int
    lower_longest_run_steps: int
    upper_longest_run_steps: int

    def __post_init__(self) -> None:
        if self.sample_index < 0:
            raise ValueError("sample_index must be nonnegative")
        if self.lower_event and not self.upper_event:
            raise ValueError("lower endpoint event cannot exceed upper endpoint event")


@dataclass(frozen=True)
class OutputErrorProbabilityResult:
    """Lower/upper event-count probability result from endpoint trajectories."""

    lower: ProbabilityEstimate
    upper: ProbabilityEstimate
    samples: tuple[EndpointEventEvaluation, ...]

    def __post_init__(self) -> None:
        if self.lower.probability > self.upper.probability:
            raise ValueError("expected lower probability <= upper probability")
        if len(self.samples) != self.lower.sample_count:
            raise ValueError("sample diagnostics must match the probability sample count")
        if self.upper.sample_count != self.lower.sample_count:
            raise ValueError("lower and upper estimates must use the same sample count")


def apply_output_error_envelope(
    result: LoadingTrajectoryResult,
    envelope: OutputErrorEnvelope,
) -> OutputErrorEndpointTrajectories:
    """Apply G1-A2 loading endpoints before event detection.

    The import gate is derived only from the unwidened ``P_net`` sign in the
    validated IC-2 trajectory. The envelope widens loading magnitude, then the
    preserved import mask gates the endpoint import-loading trajectories.
    """

    validate_loading_trajectory_result(result)
    loading = np.asarray(result.screening_loading_pu, dtype=float)
    epsilon_grid = _as_endpoint_array(
        envelope.epsilon_grid,
        name="epsilon_grid",
        shape=loading.shape,
    )
    epsilon_tier1_minus = _as_endpoint_array(
        envelope.epsilon_tier1_minus,
        name="epsilon_tier1_minus",
        shape=loading.shape,
    )
    epsilon_tier1_plus = _as_endpoint_array(
        envelope.epsilon_tier1_plus,
        name="epsilon_tier1_plus",
        shape=loading.shape,
    )

    if np.any(epsilon_grid >= 1.0):
        raise ValueError("epsilon_grid must be less than 1")
    if np.any(epsilon_tier1_minus < 0.0) or np.any(epsilon_tier1_plus < 0.0):
        raise ValueError("Tier-1 endpoint errors must be nonnegative")

    lower_loading = (1.0 - epsilon_grid) * np.maximum(
        0.0,
        loading - epsilon_tier1_minus,
    )
    upper_loading = (1.0 + epsilon_grid) * (loading + epsilon_tier1_plus)
    import_mask = np.asarray(result.import_mask, dtype=bool)

    # G1-A2 forbids widening direction: export and zero-flow timesteps remain
    # non-import even if the magnitude endpoint would otherwise exceed.
    lower_import = np.where(import_mask, lower_loading, 0.0)
    upper_import = np.where(import_mask, upper_loading, 0.0)
    return OutputErrorEndpointTrajectories(
        lower_loading_pu=lower_loading,
        upper_loading_pu=upper_loading,
        lower_import_loading_pu=lower_import,
        upper_import_loading_pu=upper_import,
    )


def evaluate_output_error_endpoint_event(
    result: LoadingTrajectoryResult,
    envelope: OutputErrorEnvelope,
    *,
    sample_index: int = 0,
) -> EndpointEventEvaluation:
    """Classify lower/upper endpoint events for one IC-2 trajectory."""

    endpoints = apply_output_error_envelope(result, envelope)
    lower_episodes, lower_longest = count_import_overload_episodes(
        endpoints.lower_import_loading_pu,
        threshold_pu=result.threshold_pu,
        min_consecutive_steps=result.min_consecutive_steps,
    )
    upper_episodes, upper_longest = count_import_overload_episodes(
        endpoints.upper_import_loading_pu,
        threshold_pu=result.threshold_pu,
        min_consecutive_steps=result.min_consecutive_steps,
    )
    return EndpointEventEvaluation(
        sample_index=sample_index,
        lower_event=lower_episodes > 0,
        upper_event=upper_episodes > 0,
        lower_episode_count=lower_episodes,
        upper_episode_count=upper_episodes,
        lower_longest_run_steps=lower_longest,
        upper_longest_run_steps=upper_longest,
    )


def estimate_output_error_probability(
    results: Sequence[LoadingTrajectoryResult],
    envelope: OutputErrorEnvelope,
    *,
    confidence_level: float = 0.95,
) -> OutputErrorProbabilityResult:
    """Estimate lower/upper event probabilities from endpoint event counts."""

    if len(results) == 0:
        raise ValueError("results must not be empty")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must be in (0, 1)")

    sample_events = tuple(
        evaluate_output_error_endpoint_event(
            result,
            envelope,
            sample_index=sample_index,
        )
        for sample_index, result in enumerate(results)
    )
    lower_successes = sum(event.lower_event for event in sample_events)
    upper_successes = sum(event.upper_event for event in sample_events)
    sample_count = len(sample_events)
    lower_ci = _wilson_interval(
        lower_successes,
        sample_count,
        confidence_level=confidence_level,
    )
    upper_ci = _wilson_interval(
        upper_successes,
        sample_count,
        confidence_level=confidence_level,
    )
    return OutputErrorProbabilityResult(
        lower=ProbabilityEstimate(
            probability=lower_successes / sample_count,
            ci_lower=lower_ci[0],
            ci_upper=lower_ci[1],
            successes=lower_successes,
            sample_count=sample_count,
        ),
        upper=ProbabilityEstimate(
            probability=upper_successes / sample_count,
            ci_lower=upper_ci[0],
            ci_upper=upper_ci[1],
            successes=upper_successes,
            sample_count=sample_count,
        ),
        samples=sample_events,
    )


def _as_endpoint_array(
    value: EnvelopeValue,
    *,
    name: str,
    shape: tuple[int, ...],
) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    if np.any(array < 0.0):
        raise ValueError(f"{name} must be nonnegative")
    try:
        return np.broadcast_to(array, shape).astype(float, copy=False)
    except ValueError as exc:
        raise ValueError(f"{name} must be scalar or broadcastable to trajectory shape") from exc
