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
    use_status: str = "synthetic-only"

    def __post_init__(self) -> None:
        if self.use_status != "synthetic-only":
            raise ValueError("rho sweep scaffold is synthetic-only before G3")
        if self.sample_count <= 0:
            raise ValueError("sample_count must be positive")
        if not self.points:
            raise ValueError("points must not be empty")
        rhos = [point.rho for point in self.points]
        if rhos != sorted(rhos) or len(set(rhos)) != len(rhos):
            raise ValueError("rho sweep points must have unique sorted rho values")
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
            "max_upward_violation": self.max_upward_violation,
            "monotone_nonincreasing": self.monotone_nonincreasing,
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

    if payload.get("use_status") != "synthetic-only":
        raise ValueError("rho sweep payload must remain synthetic-only before G3")
    points = payload.get("points")
    if not isinstance(points, Sequence) or isinstance(points, (str, bytes)):
        raise TypeError("rho sweep payload points must be a sequence")
    reconstructed = tuple(
        RhoSweepPoint(
            rho=float(point["rho"]),
            estimate=ProbabilityEstimate(
                probability=float(point["probability"]),
                ci_lower=float(point["ci_lower"]),
                ci_upper=float(point["ci_upper"]),
                successes=_expect_nonnegative_int(point["successes"], name="successes"),
                sample_count=_expect_nonnegative_int(
                    point["sample_count"], name="sample_count"
                ),
            ),
        )
        for point in points
    )
    RhoSweepResult(
        points=reconstructed,
        monotone_nonincreasing=bool(payload.get("monotone_nonincreasing")),
        max_upward_violation=float(payload.get("max_upward_violation", -1.0)),
        sample_count=_expect_nonnegative_int(payload.get("sample_count"), name="sample_count"),
        use_status=str(payload.get("use_status")),
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


def _expect_nonnegative_int(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be a nonnegative integer")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
    return value
