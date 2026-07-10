"""Vertex p-box propagation for alpha-cut uncertainty.

This module is the pre-G3 test-mode implementation for E5.S2. It assumes a
monotone-decreasing overload event in the propagated fuzzy parameter, but it
does not run paper experiments or depend on grid-specific contracts.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from statistics import NormalDist
from typing import Callable, Mapping, Sequence

from src.fuzzy import (
    PiecewiseLinearFuzzyNumber,
    TrapezoidalFuzzyNumber,
    TriangularFuzzyNumber,
)

FuzzyNumber = (
    TrapezoidalFuzzyNumber | TriangularFuzzyNumber | PiecewiseLinearFuzzyNumber
)
SampleEvaluator = Callable[[float, int], bool]


@dataclass(frozen=True)
class ProbabilityEstimate:
    """Binomial probability estimate for one endpoint.

    Parameters
    ----------
    probability:
        Estimated event probability, dimensionless in [0, 1].
    ci_lower:
        Lower confidence bound, dimensionless in [0, 1].
    ci_upper:
        Upper confidence bound, dimensionless in [0, 1].
    successes:
        Number of event occurrences.
    sample_count:
        Number of Monte-Carlo samples.
    """

    probability: float
    ci_lower: float
    ci_upper: float
    successes: int
    sample_count: int

    def __post_init__(self) -> None:
        if self.sample_count <= 0:
            raise ValueError("sample_count must be positive")
        if not 0 <= self.successes <= self.sample_count:
            raise ValueError("successes must be between 0 and sample_count")
        for name, value in (
            ("probability", self.probability),
            ("ci_lower", self.ci_lower),
            ("ci_upper", self.ci_upper),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        if self.ci_lower > self.probability or self.probability > self.ci_upper:
            raise ValueError("expected ci_lower <= probability <= ci_upper")


@dataclass(frozen=True)
class PBoxAlphaResult:
    """P-box bounds for one alpha level."""

    alpha: float
    rho_lower: float
    rho_upper: float
    lower: ProbabilityEstimate
    upper: ProbabilityEstimate

    def __post_init__(self) -> None:
        if self.rho_lower > self.rho_upper:
            raise ValueError("rho_lower must be <= rho_upper")
        if self.lower.probability > self.upper.probability:
            raise ValueError("expected P_lower <= P_upper")
        if self.lower.ci_lower > self.upper.ci_upper:
            raise ValueError("confidence intervals imply disjoint reversed bounds")


PBoxFamily = Mapping[float, PBoxAlphaResult]


@dataclass(frozen=True)
class ModelErrorWidening:
    """Additive model-error margins for p-box probability bounds.

    Parameters
    ----------
    lower_probability_margin:
        Non-negative probability margin subtracted from the lower bound,
        dimensionless in [0, 1].
    upper_probability_margin:
        Non-negative probability margin added to the upper bound, dimensionless
        in [0, 1].
    """

    lower_probability_margin: float
    upper_probability_margin: float

    def __post_init__(self) -> None:
        for name, value in (
            ("lower_probability_margin", self.lower_probability_margin),
            ("upper_probability_margin", self.upper_probability_margin),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")

    @classmethod
    def from_config(cls, config: Mapping[str, float]) -> "ModelErrorWidening":
        """Build widening margins from a config mapping.

        The caller must supply both margins explicitly. This method deliberately
        has no scientific default values.
        """

        required = ("lower_probability_margin", "upper_probability_margin")
        missing = [key for key in required if key not in config]
        if missing:
            raise ValueError(f"missing model-error widening keys: {', '.join(missing)}")
        return cls(
            lower_probability_margin=float(config["lower_probability_margin"]),
            upper_probability_margin=float(config["upper_probability_margin"]),
        )


def estimate_vertex_pbox(
    *,
    fuzzy_number: FuzzyNumber,
    alpha_grid: Sequence[float],
    sample_count: int,
    root_seed: int,
    evaluator: SampleEvaluator,
    confidence_level: float = 0.95,
) -> dict[float, PBoxAlphaResult]:
    """Estimate alpha-indexed p-box bounds using endpoint propagation.

    The event probability is assumed monotone decreasing in the fuzzy
    parameter. Therefore each alpha-cut ``[rho_lower, rho_upper]`` maps to
    ``P_lower = P(E | rho_upper)`` and ``P_upper = P(E | rho_lower)``.

    Parameters
    ----------
    fuzzy_number:
        Fuzzy parameter whose alpha-cuts are propagated.
    alpha_grid:
        Alpha levels to evaluate. Results preserve this order and are keyed by
        alpha.
    sample_count:
        Number of Monte-Carlo samples per endpoint.
    root_seed:
        Integer root seed for deterministic common random numbers.
    evaluator:
        Callable returning whether event E occurs for ``(rho, sample_seed)``.
    confidence_level:
        Binomial confidence level used for Wilson intervals.
    """

    if sample_count <= 0:
        raise ValueError("sample_count must be positive")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must be in (0, 1)")

    sample_seeds = _sample_seeds(root_seed, sample_count)
    results: dict[float, PBoxAlphaResult] = {}
    for alpha in alpha_grid:
        cut = fuzzy_number.alpha_cut(alpha)
        lower_estimate = _estimate_probability(
            cut.upper, sample_seeds, evaluator, confidence_level
        )
        upper_estimate = _estimate_probability(
            cut.lower, sample_seeds, evaluator, confidence_level
        )
        results[alpha] = PBoxAlphaResult(
            alpha=alpha,
            rho_lower=cut.lower,
            rho_upper=cut.upper,
            lower=lower_estimate,
            upper=upper_estimate,
        )

    assert_bound_order(results)
    assert_nested(results)
    return results


def apply_model_error_widening(
    pbox_family: PBoxFamily,
    widening: ModelErrorWidening,
) -> dict[float, PBoxAlphaResult]:
    """Apply additive model-error interval widening to a p-box family.

    Widening is a deterministic post-processor: for every alpha level it moves
    ``P_lower`` down by ``lower_probability_margin`` and ``P_upper`` up by
    ``upper_probability_margin``, clipping to the probability range [0, 1]. The
    same margins are applied to the corresponding confidence limits.
    """

    widened: dict[float, PBoxAlphaResult] = {}
    for alpha, result in pbox_family.items():
        widened[alpha] = PBoxAlphaResult(
            alpha=result.alpha,
            rho_lower=result.rho_lower,
            rho_upper=result.rho_upper,
            lower=_shift_probability_estimate(
                result.lower, -widening.lower_probability_margin
            ),
            upper=_shift_probability_estimate(
                result.upper, widening.upper_probability_margin
            ),
        )

    assert_bound_order(widened)
    assert_nested(widened)
    return widened


def assert_bound_order(pbox_family: PBoxFamily) -> None:
    """Raise if any alpha result violates ``P_lower <= P_upper``."""

    for alpha, result in pbox_family.items():
        if result.lower.probability > result.upper.probability:
            raise ValueError(f"bound-order violation at alpha={alpha}")


def assert_nested(pbox_family: PBoxFamily, *, tolerance: float = 0.0) -> None:
    """Raise if cuts are not nested as alpha increases.

    For alpha_1 < alpha_2, the probability interval at alpha_2 must sit inside
    the interval at alpha_1.
    """

    ordered = sorted(pbox_family.values(), key=lambda result: result.alpha)
    for outer, inner in zip(ordered, ordered[1:]):
        lower_ok = outer.lower.probability <= inner.lower.probability + tolerance
        upper_ok = inner.upper.probability <= outer.upper.probability + tolerance
        if not lower_ok or not upper_ok:
            raise ValueError(
                "nestedness violation between "
                f"alpha={outer.alpha} and alpha={inner.alpha}"
            )


def _estimate_probability(
    rho: float,
    sample_seeds: Sequence[int],
    evaluator: SampleEvaluator,
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


def _shift_probability_estimate(
    estimate: ProbabilityEstimate,
    probability_delta: float,
) -> ProbabilityEstimate:
    return ProbabilityEstimate(
        probability=_clip_probability(estimate.probability + probability_delta),
        ci_lower=_clip_probability(estimate.ci_lower + probability_delta),
        ci_upper=_clip_probability(estimate.ci_upper + probability_delta),
        successes=estimate.successes,
        sample_count=estimate.sample_count,
    )


def _clip_probability(value: float) -> float:
    return min(1.0, max(0.0, value))


def _sample_seeds(root_seed: int, sample_count: int) -> tuple[int, ...]:
    return tuple(_sample_seed(root_seed, sample_index) for sample_index in range(sample_count))


def _sample_seed(root_seed: int, sample_index: int) -> int:
    payload = f"{root_seed}:{sample_index}".encode("ascii")
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big", signed=False)


def _wilson_interval(
    successes: int,
    sample_count: int,
    *,
    confidence_level: float,
) -> tuple[float, float]:
    if sample_count <= 0:
        raise ValueError("sample_count must be positive")

    phat = successes / sample_count
    z = NormalDist().inv_cdf((1.0 + confidence_level) / 2.0)
    z_squared = z * z
    denominator = 1.0 + z_squared / sample_count
    center = (phat + z_squared / (2.0 * sample_count)) / denominator
    spread = (
        z
        * math.sqrt(
            (phat * (1.0 - phat) + z_squared / (4.0 * sample_count))
            / sample_count
        )
        / denominator
    )
    return max(0.0, center - spread), min(1.0, center + spread)
