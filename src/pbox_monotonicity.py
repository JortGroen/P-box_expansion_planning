"""Synthetic dense-rho monotonicity sweep scaffolds for E4 readiness.

The helpers in this module use toy callbacks only. They prepare the B-owned
math surface for a future G3 monotonicity verdict without running real event
analysis or authorizing vertex-shortcut use.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from src.pbox import ProbabilityEstimate, _wilson_interval
from src.rng import sample_seed

RHO_SWEEP_MANIFEST_PROTOCOL = "e4s1-synthetic-rho-sweep-v1"
RHO_SWEEP_G3_STATUS = "pending-no-paper-facing-vertex-claim"
RHO_SWEEP_USE_STATUS = "synthetic-only"
RHO_SWEEP_NON_CLAIMS = (
    "no real trajectories",
    "no real P(E)",
    "no real rho sweep",
    "no capacity-convention choice",
    "no G3 vertex-shortcut claim",
    "no manuscript number",
)
_FORBIDDEN_RHO_SWEEP_PAYLOAD_FIELDS = frozenset(
    {
        "capacity_screen_result",
        "defuzzified_probability",
        "expected_probability",
        "manuscript_number",
        "mean_probability",
        "p_hat",
        "p_mid",
        "paper_facing_probability",
        "paper_facing_result",
        "pbox_probability",
        "vertex_shortcut_claim",
    }
)

RhoSweepEvaluator = Callable[[float, int], bool]


@dataclass(frozen=True)
class RhoSweepPoint:
    """Estimated synthetic event probability at one controllability value."""

    rho: float
    estimate: ProbabilityEstimate

    def __post_init__(self) -> None:
        if not math.isfinite(self.rho) or not 0.0 <= self.rho <= 1.0:
            raise ValueError("rho must be in [0, 1]")


@dataclass(frozen=True)
class RhoSweepResult:
    """Synthetic dense-rho sweep result with monotonicity diagnostics."""

    points: tuple[RhoSweepPoint, ...]
    monotone_nonincreasing: bool
    max_upward_violation: float
    sample_count: int
    use_status: str = RHO_SWEEP_USE_STATUS
    g3_status: str = RHO_SWEEP_G3_STATUS

    def __post_init__(self) -> None:
        if self.use_status != RHO_SWEEP_USE_STATUS:
            raise ValueError("rho sweep scaffold is synthetic-only before G3")
        if self.g3_status != RHO_SWEEP_G3_STATUS:
            raise ValueError("rho sweep payload must not claim G3 approval")
        if self.sample_count <= 0:
            raise ValueError("sample_count must be positive")
        if not self.points:
            raise ValueError("points must not be empty")
        rhos = [point.rho for point in self.points]
        if rhos != sorted(rhos) or len(set(rhos)) != len(rhos):
            raise ValueError("rho sweep points must have unique sorted rho values")
        if any(point.estimate.sample_count != self.sample_count for point in self.points):
            raise ValueError("rho sweep point sample_count must match result sample_count")
        if self.max_upward_violation < 0.0:
            raise ValueError("max_upward_violation must be nonnegative")
        expected = _max_upward_violation(self.points)
        if abs(self.max_upward_violation - expected) > 1e-12:
            raise ValueError("max_upward_violation must match adjacent sweep points")
        if self.monotone_nonincreasing != (expected == 0.0):
            raise ValueError("monotone_nonincreasing must reflect sweep points")

    def to_mapping(self) -> dict[str, object]:
        """Return a manifest-ready synthetic monotonicity diagnostic payload."""

        return {
            "g3_status": self.g3_status,
            "manifest_protocol": RHO_SWEEP_MANIFEST_PROTOCOL,
            "max_upward_violation": self.max_upward_violation,
            "monotone_nonincreasing": self.monotone_nonincreasing,
            "non_claims": list(RHO_SWEEP_NON_CLAIMS),
            "points": [
                {
                    "ci_lower": point.estimate.ci_lower,
                    "ci_upper": point.estimate.ci_upper,
                    "probability": point.estimate.probability,
                    "rho": point.rho,
                    "sample_count": point.estimate.sample_count,
                    "successes": point.estimate.successes,
                }
                for point in self.points
            ],
            "sample_count": self.sample_count,
            "use_status": self.use_status,
        }


RhoSweepFamily = Mapping[str, RhoSweepResult]


def estimate_dense_rho_sweep(
    *,
    rho_grid: Sequence[float],
    sample_count: int,
    root_seed: int,
    evaluator: RhoSweepEvaluator,
    confidence_level: float = 0.95,
) -> RhoSweepResult:
    """Estimate a synthetic dense-rho event-probability sweep.

    The same canonical sample seeds are replayed at every rho value. That CRN
    discipline lets later monotonicity checks compare controllability levels
    without accidentally changing the aleatory realization under inspection.
    """

    if sample_count <= 0:
        raise ValueError("sample_count must be positive")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must be in (0, 1)")
    ordered_rhos = _validate_rho_grid(rho_grid)
    sample_seeds = tuple(sample_seed(root_seed, index) for index in range(sample_count))
    points = tuple(
        RhoSweepPoint(
            rho=rho,
            estimate=_estimate_probability(
                rho,
                sample_seeds,
                evaluator,
                confidence_level,
            ),
        )
        for rho in ordered_rhos
    )
    max_violation = _max_upward_violation(points)
    return RhoSweepResult(
        points=points,
        monotone_nonincreasing=max_violation == 0.0,
        max_upward_violation=max_violation,
        sample_count=sample_count,
    )


def assert_synthetic_rho_sweep_payload(payload: Mapping[str, object]) -> None:
    """Validate a serialized synthetic rho-sweep diagnostic payload."""

    if not isinstance(payload, Mapping):
        raise TypeError("rho sweep payload must be a mapping")
    _reject_forbidden_rho_sweep_fields(payload)
    required = {
        "g3_status",
        "manifest_protocol",
        "max_upward_violation",
        "monotone_nonincreasing",
        "non_claims",
        "points",
        "sample_count",
        "use_status",
    }
    missing = required.difference(payload)
    if missing:
        raise ValueError(f"rho sweep payload is missing fields: {sorted(missing)}")
    if payload["manifest_protocol"] != RHO_SWEEP_MANIFEST_PROTOCOL:
        raise ValueError(f"manifest_protocol must be {RHO_SWEEP_MANIFEST_PROTOCOL!r}")
    if payload["use_status"] != RHO_SWEEP_USE_STATUS:
        raise ValueError("rho sweep payload must remain synthetic-only before G3")
    if payload["g3_status"] != RHO_SWEEP_G3_STATUS:
        raise ValueError("rho sweep payload must not claim G3 approval")
    non_claims = _expect_string_sequence(payload["non_claims"], name="non_claims")
    if non_claims != RHO_SWEEP_NON_CLAIMS:
        raise ValueError("rho sweep non_claims must match the synthetic protocol")
    points = payload.get("points")
    if not isinstance(points, Sequence) or isinstance(points, (str, bytes)):
        raise TypeError("rho sweep payload points must be a sequence")
    reconstructed = tuple(
        RhoSweepPoint(
            rho=float(point_mapping["rho"]),
            estimate=ProbabilityEstimate(
                probability=float(point_mapping["probability"]),
                ci_lower=float(point_mapping["ci_lower"]),
                ci_upper=float(point_mapping["ci_upper"]),
                successes=_expect_nonnegative_int(
                    point_mapping["successes"], name="successes"
                ),
                sample_count=_expect_nonnegative_int(
                    point_mapping["sample_count"], name="sample_count"
                ),
            ),
        )
        for point_mapping in (_expect_mapping(point, name="rho sweep point") for point in points)
    )
    RhoSweepResult(
        points=reconstructed,
        monotone_nonincreasing=bool(payload.get("monotone_nonincreasing")),
        max_upward_violation=float(payload.get("max_upward_violation", -1.0)),
        sample_count=_expect_nonnegative_int(payload.get("sample_count"), name="sample_count"),
        use_status=str(payload.get("use_status")),
        g3_status=str(payload.get("g3_status")),
    )


def _validate_rho_grid(rho_grid: Sequence[float]) -> tuple[float, ...]:
    if not rho_grid:
        raise ValueError("rho_grid must not be empty")
    ordered = tuple(float(rho) for rho in rho_grid)
    if ordered != tuple(sorted(ordered)) or len(set(ordered)) != len(ordered):
        raise ValueError("rho_grid must contain unique sorted values")
    if any(not math.isfinite(rho) or rho < 0.0 or rho > 1.0 for rho in ordered):
        raise ValueError("rho_grid values must be in [0, 1]")
    return ordered


def _estimate_probability(
    rho: float,
    sample_seeds: Sequence[int],
    evaluator: RhoSweepEvaluator,
    confidence_level: float,
) -> ProbabilityEstimate:
    successes = sum(1 for seed in sample_seeds if evaluator(rho, seed))
    probability = successes / len(sample_seeds)
    ci_lower, ci_upper = _wilson_interval(
        successes,
        len(sample_seeds),
        confidence_level=confidence_level,
    )
    return ProbabilityEstimate(
        probability=probability,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        successes=successes,
        sample_count=len(sample_seeds),
    )


def _max_upward_violation(points: Sequence[RhoSweepPoint]) -> float:
    violations = (
        right.estimate.probability - left.estimate.probability
        for left, right in zip(points, points[1:])
    )
    return max((violation for violation in violations if violation > 0.0), default=0.0)


def _expect_mapping(value: object, *, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return value


def _expect_nonnegative_int(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be a nonnegative integer")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
    return value


def _expect_string_sequence(value: object, *, name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{name} must be a sequence")
    if any(not isinstance(item, str) for item in value):
        raise TypeError(f"{name} must contain strings")
    return tuple(value)


def _reject_forbidden_rho_sweep_fields(value: object) -> None:
    if isinstance(value, Mapping):
        collapsed = sorted(_FORBIDDEN_RHO_SWEEP_PAYLOAD_FIELDS.intersection(value))
        if collapsed:
            raise ValueError(
                "synthetic rho-sweep payload must not carry paper-facing or "
                f"collapsed result fields: {collapsed}"
            )
        for nested in value.values():
            _reject_forbidden_rho_sweep_fields(nested)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for nested in value:
            _reject_forbidden_rho_sweep_fields(nested)