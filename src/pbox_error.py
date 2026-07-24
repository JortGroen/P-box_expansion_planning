"""Output-domain model-error endpoint propagation for p-box scaffolding.

This E5.S3 scaffold consumes the shared IC-2 ``LoadingTrajectoryResult`` and
applies G1-A2 output-error endpoints to loading trajectories before event
detection. It is synthetic/protocol code only until G2, A-013, and the
capacity-denominator decisions allow paper-facing event analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence

import numpy as np

from src.contracts.loading_trajectory import (
    LoadingTrajectoryResult,
    validate_loading_trajectory_result,
)
from src.evaluator_sum import count_import_overload_episodes
from src.pbox import ProbabilityEstimate, _wilson_interval

EnvelopeValue = float | Sequence[float] | np.ndarray
OUTPUT_ERROR_LOWER_FORMULA = "L_lower=(1-epsilon_grid)*max(0,L_T1-epsilon_tier1_minus)"
OUTPUT_ERROR_UPPER_FORMULA = "L_upper=(1+epsilon_grid)*(L_T1+epsilon_tier1_plus)"
OUTPUT_ERROR_APPLICATION = "loading_trajectory_endpoints_before_event_detection"
OUTPUT_ERROR_DEPENDENCE = "arbitrary_unknown_dependence_not_independently_sampled"
OUTPUT_ERROR_SAMPLING = "forbidden"


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
class OutputErrorProtocolConfig:
    """Manifest-ready synthetic E5.S3 output-error protocol configuration.

    The numerical envelope values are explicit inputs so tests and later runner
    plumbing can record them without treating A-013 or G2 values as signed.
    """

    envelope: OutputErrorEnvelope
    threshold_pu: float
    min_consecutive_steps: int
    timestep_seconds: int
    envelope_source: str = "synthetic-placeholder"
    grid_error_source: str = "synthetic-placeholder"
    tier1_error_source: str = "synthetic-placeholder"
    capacity_denominator_provenance: str = "synthetic-placeholder"
    capacity_convention_linkage: str = "pending-g1-a2-e3-s2b"
    a013_grid_error_approval_id: str = "A-013-pending"
    g2_tier1_envelope_approval_id: str = "G2-pending"
    use_status: str = "synthetic-only"

    def __post_init__(self) -> None:
        if not math.isfinite(float(self.threshold_pu)) or self.threshold_pu < 0.0:
            raise ValueError("threshold_pu must be finite and nonnegative")
        if isinstance(self.min_consecutive_steps, bool) or not isinstance(
            self.min_consecutive_steps,
            int,
        ):
            raise TypeError("min_consecutive_steps must be an integer")
        if self.min_consecutive_steps <= 0:
            raise ValueError("min_consecutive_steps must be positive")
        if isinstance(self.timestep_seconds, bool) or not isinstance(self.timestep_seconds, int):
            raise TypeError("timestep_seconds must be an integer")
        if self.timestep_seconds <= 0:
            raise ValueError("timestep_seconds must be positive")
        for name, value in (
            ("envelope_source", self.envelope_source),
            ("grid_error_source", self.grid_error_source),
            ("tier1_error_source", self.tier1_error_source),
            ("capacity_denominator_provenance", self.capacity_denominator_provenance),
            ("capacity_convention_linkage", self.capacity_convention_linkage),
            ("a013_grid_error_approval_id", self.a013_grid_error_approval_id),
            ("g2_tier1_envelope_approval_id", self.g2_tier1_envelope_approval_id),
            ("use_status", self.use_status),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a nonempty string")
        _validate_envelope_values(self.envelope)

    @classmethod
    def from_mapping(cls, config: Mapping[str, Any]) -> "OutputErrorProtocolConfig":
        """Build a typed protocol config from an explicit mapping."""

        required = {
            "epsilon_grid",
            "epsilon_tier1_minus",
            "epsilon_tier1_plus",
            "threshold_pu",
            "min_consecutive_steps",
            "timestep_seconds",
        }
        optional = {
            "envelope_source",
            "grid_error_source",
            "tier1_error_source",
            "capacity_denominator_provenance",
            "capacity_convention_linkage",
            "a013_grid_error_approval_id",
            "g2_tier1_envelope_approval_id",
            "use_status",
        }
        missing = required.difference(config)
        if missing:
            raise ValueError(f"missing output-error config fields: {sorted(missing)}")
        unknown = set(config).difference(required | optional)
        if unknown:
            raise ValueError(f"unknown output-error config fields: {sorted(unknown)}")
        return cls(
            envelope=OutputErrorEnvelope(
                epsilon_grid=config["epsilon_grid"],
                epsilon_tier1_minus=config["epsilon_tier1_minus"],
                epsilon_tier1_plus=config["epsilon_tier1_plus"],
            ),
            threshold_pu=float(config["threshold_pu"]),
            min_consecutive_steps=_coerce_int_config(
                config["min_consecutive_steps"],
                name="min_consecutive_steps",
            ),
            timestep_seconds=_coerce_int_config(
                config["timestep_seconds"],
                name="timestep_seconds",
            ),
            envelope_source=str(config.get("envelope_source", "synthetic-placeholder")),
            grid_error_source=str(config.get("grid_error_source", "synthetic-placeholder")),
            tier1_error_source=str(config.get("tier1_error_source", "synthetic-placeholder")),
            capacity_denominator_provenance=str(
                config.get("capacity_denominator_provenance", "synthetic-placeholder")
            ),
            capacity_convention_linkage=str(
                config.get("capacity_convention_linkage", "pending-g1-a2-e3-s2b")
            ),
            a013_grid_error_approval_id=str(
                config.get("a013_grid_error_approval_id", "A-013-pending")
            ),
            g2_tier1_envelope_approval_id=str(
                config.get("g2_tier1_envelope_approval_id", "G2-pending")
            ),
            use_status=str(config.get("use_status", "synthetic-only")),
        )

    def manifest_metadata(self) -> dict[str, object]:
        """Return deterministic metadata suitable for an ExperimentRunner manifest."""

        return {
            "a013_grid_error_approval_id": self.a013_grid_error_approval_id,
            "capacity_convention_linkage": self.capacity_convention_linkage,
            "capacity_denominator_provenance": self.capacity_denominator_provenance,
            "composition_formula": {
                "lower": OUTPUT_ERROR_LOWER_FORMULA,
                "upper": OUTPUT_ERROR_UPPER_FORMULA,
            },
            "dependence_assumption": OUTPUT_ERROR_DEPENDENCE,
            "error_application": OUTPUT_ERROR_APPLICATION,
            "error_sampling": OUTPUT_ERROR_SAMPLING,
            "envelope": {
                "epsilon_grid": _jsonable_endpoint_value(self.envelope.epsilon_grid),
                "epsilon_tier1_minus": _jsonable_endpoint_value(
                    self.envelope.epsilon_tier1_minus
                ),
                "epsilon_tier1_plus": _jsonable_endpoint_value(self.envelope.epsilon_tier1_plus),
            },
            "envelope_source": self.envelope_source,
            "event_semantics": {
                "comparator": "strict_greater_than",
                "direction_gate": "unwidened_p_net_import_mask",
                "min_consecutive_steps": self.min_consecutive_steps,
                "threshold_pu": self.threshold_pu,
                "timestep_seconds": self.timestep_seconds,
            },
            "g2_tier1_envelope_approval_id": self.g2_tier1_envelope_approval_id,
            "grid_error_source": self.grid_error_source,
            "probability_widening": "forbidden",
            "tier1_error_source": self.tier1_error_source,
            "use_status": self.use_status,
        }


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


@dataclass(frozen=True)
class OutputErrorManifestRecord:
    """Manifest-ready synthetic endpoint-count record for E5.S3."""

    config: OutputErrorProtocolConfig
    probability: OutputErrorProbabilityResult

    def to_mapping(self) -> dict[str, object]:
        """Return a JSON-stable record for later runner manifest plumbing."""

        sample_count = self.probability.lower.sample_count
        return {
            "config": self.config.manifest_metadata(),
            "event_count_bounds": {
                "lower_successes": self.probability.lower.successes,
                "upper_successes": self.probability.upper.successes,
                "sample_count": sample_count,
            },
            "probability_bounds": {
                "lower": _probability_estimate_metadata(self.probability.lower),
                "upper": _probability_estimate_metadata(self.probability.upper),
            },
            "probability_widening": "forbidden",
            "sample_endpoint_events": [
                _endpoint_event_metadata(event) for event in self.probability.samples
            ],
        }


@dataclass(frozen=True)
class OutputErrorAlphaResult:
    """One alpha-indexed lower/upper probability result from endpoint counts."""

    alpha: float
    probability: OutputErrorProbabilityResult

    def __post_init__(self) -> None:
        if not math.isfinite(self.alpha) or not 0.0 <= self.alpha <= 1.0:
            raise ValueError("alpha must be finite and in [0, 1]")


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


def build_output_error_manifest_record(
    results: Sequence[LoadingTrajectoryResult],
    config: OutputErrorProtocolConfig,
    *,
    confidence_level: float = 0.95,
) -> dict[str, object]:
    """Build a manifest-ready record from endpoint event counts only."""

    probability = estimate_output_error_probability_from_config(
        results,
        config,
        confidence_level=confidence_level,
    )
    # The manifest-facing record preserves endpoint counts so output error
    # cannot be reintroduced later as a post-hoc probability margin.
    return OutputErrorManifestRecord(config=config, probability=probability).to_mapping()


def estimate_output_error_probability_from_config(
    results: Sequence[LoadingTrajectoryResult],
    config: OutputErrorProtocolConfig,
    *,
    confidence_level: float = 0.95,
) -> OutputErrorProbabilityResult:
    """Estimate endpoint probabilities using a manifest-ready protocol config."""

    for result in results:
        _validate_result_matches_config(result, config)
    return estimate_output_error_probability(
        results,
        config.envelope,
        confidence_level=confidence_level,
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


def estimate_alpha_output_error_probability(
    results_by_alpha: Mapping[float, Sequence[LoadingTrajectoryResult]],
    envelope: OutputErrorEnvelope | Mapping[float, OutputErrorEnvelope],
    *,
    confidence_level: float = 0.95,
) -> dict[float, OutputErrorAlphaResult]:
    """Estimate endpoint probabilities separately for each synthetic alpha level.

    ``envelope`` may be one common pure-interval model-error envelope or an
    alpha-indexed mapping for synthetic tests. The result remains alpha-indexed
    lower/upper counts; it never collapses or widens probabilities after
    estimation.
    """

    if not results_by_alpha:
        raise ValueError("results_by_alpha must contain at least one alpha level")

    alpha_grid = tuple(sorted(results_by_alpha))
    for alpha in alpha_grid:
        if not math.isfinite(alpha) or not 0.0 <= alpha <= 1.0:
            raise ValueError("alpha values must be finite and in [0, 1]")

    sample_counts = {len(results_by_alpha[alpha]) for alpha in alpha_grid}
    if len(sample_counts) != 1:
        raise ValueError("all alpha levels must use the same sample count")

    if isinstance(envelope, Mapping):
        if tuple(sorted(envelope)) != alpha_grid:
            raise ValueError("envelope mapping must use the same alpha grid")
        envelope_by_alpha = envelope
    else:
        envelope_by_alpha = {alpha: envelope for alpha in alpha_grid}

    return {
        alpha: OutputErrorAlphaResult(
            alpha=alpha,
            probability=estimate_output_error_probability(
                results_by_alpha[alpha],
                envelope_by_alpha[alpha],
                confidence_level=confidence_level,
            ),
        )
        for alpha in alpha_grid
    }


def _probability_estimate_metadata(estimate: ProbabilityEstimate) -> dict[str, object]:
    return {
        "ci_lower": estimate.ci_lower,
        "ci_upper": estimate.ci_upper,
        "probability": estimate.probability,
        "sample_count": estimate.sample_count,
        "successes": estimate.successes,
    }


def _endpoint_event_metadata(event: EndpointEventEvaluation) -> dict[str, object]:
    return {
        "lower_episode_count": event.lower_episode_count,
        "lower_event": event.lower_event,
        "lower_longest_run_steps": event.lower_longest_run_steps,
        "sample_index": event.sample_index,
        "upper_episode_count": event.upper_episode_count,
        "upper_event": event.upper_event,
        "upper_longest_run_steps": event.upper_longest_run_steps,
    }


def _validate_envelope_values(envelope: OutputErrorEnvelope) -> None:
    for name, value in (
        ("epsilon_grid", envelope.epsilon_grid),
        ("epsilon_tier1_minus", envelope.epsilon_tier1_minus),
        ("epsilon_tier1_plus", envelope.epsilon_tier1_plus),
    ):
        array = np.asarray(value, dtype=float)
        if not np.isfinite(array).all():
            raise ValueError(f"{name} must contain only finite values")
        if np.any(array < 0.0):
            raise ValueError(f"{name} must be nonnegative")
    if np.any(np.asarray(envelope.epsilon_grid, dtype=float) >= 1.0):
        raise ValueError("epsilon_grid must be less than 1")


def _validate_result_matches_config(
    result: LoadingTrajectoryResult,
    config: OutputErrorProtocolConfig,
) -> None:
    validate_loading_trajectory_result(result)
    if not math.isclose(result.threshold_pu, config.threshold_pu, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("trajectory threshold_pu must match output-error config")
    if result.min_consecutive_steps != config.min_consecutive_steps:
        raise ValueError("trajectory min_consecutive_steps must match output-error config")


def _jsonable_endpoint_value(value: EnvelopeValue) -> float | list[float]:
    array = np.asarray(value, dtype=float)
    if array.ndim == 0:
        return float(array)
    return [float(item) for item in array.reshape(-1)]


def _coerce_int_config(value: Any, *, name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    if isinstance(value, int):
        return value
    raise TypeError(f"{name} must be an integer")

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
