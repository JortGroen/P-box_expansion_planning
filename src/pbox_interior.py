"""Interior alpha-cut p-box fallback scaffold.

This module does not authorize paper-facing use of the interior path. It
provides the deterministic synthetic/test-mode machinery needed if G3 rejects
endpoint-only vertex propagation for a non-monotone regime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from src.pbox import (
    FuzzyNumber,
    ProbabilityEstimate,
    SampleEvaluator,
    assert_bound_order,
    assert_nested,
    _wilson_interval,
)
from src.rng import sample_seed


@dataclass(frozen=True)
class InteriorPBoxAlphaResult:
    """Interior-sampled p-box bounds for one alpha level."""

    alpha: float
    rho_lower: float
    rho_upper: float
    rho_grid: tuple[float, ...]
    rho_at_lower_probability: float
    rho_at_upper_probability: float
    lower: ProbabilityEstimate
    upper: ProbabilityEstimate

    def __post_init__(self) -> None:
        if self.rho_lower > self.rho_upper:
            raise ValueError("rho_lower must be <= rho_upper")
        if not self.rho_grid:
            raise ValueError("rho_grid must not be empty")
        if any(rho < self.rho_lower or rho > self.rho_upper for rho in self.rho_grid):
            raise ValueError("rho_grid values must lie inside the alpha-cut")
        for name, rho in (
            ("rho_at_lower_probability", self.rho_at_lower_probability),
            ("rho_at_upper_probability", self.rho_at_upper_probability),
        ):
            if rho < self.rho_lower or rho > self.rho_upper:
                raise ValueError(f"{name} must lie inside the alpha-cut")
        if self.lower.probability > self.upper.probability:
            raise ValueError("expected P_lower <= P_upper")
        if self.lower.ci_lower > self.upper.ci_upper:
            raise ValueError("confidence intervals imply disjoint reversed bounds")


InteriorPBoxFamily = Mapping[float, InteriorPBoxAlphaResult]
InteriorSampleEvaluator = Callable[[float, int], bool]


def estimate_interior_pbox(
    *,
    fuzzy_number: FuzzyNumber,
    alpha_grid: Sequence[float],
    sample_count: int,
    root_seed: int,
    evaluator: SampleEvaluator,
    rho_grid_size: int,
    confidence_level: float = 0.95,
) -> dict[float, InteriorPBoxAlphaResult]:
    """Estimate alpha-indexed p-box bounds by scanning rho values inside cuts.

    Parameters
    ----------
    fuzzy_number:
        Fuzzy parameter whose alpha-cuts are propagated.
    alpha_grid:
        Alpha levels to evaluate. Results preserve this order and are keyed by
        alpha.
    sample_count:
        Number of Monte-Carlo samples per rho candidate.
    root_seed:
        Integer root seed for deterministic common random numbers.
    evaluator:
        Callable returning whether event E occurs for ``(rho, sample_seed)``.
    rho_grid_size:
        Number of deterministic support-grid candidates before alpha-cut
        filtering. The current cut endpoints are always included.
    confidence_level:
        Binomial confidence level used for Wilson intervals.
    """

    if sample_count <= 0:
        raise ValueError("sample_count must be positive")
    if rho_grid_size < 2:
        raise ValueError("rho_grid_size must be at least 2")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must be in (0, 1)")

    cuts = {alpha: fuzzy_number.alpha_cut(alpha) for alpha in alpha_grid}
    candidate_rhos = _global_candidate_rhos(
        fuzzy_number=fuzzy_number,
        alpha_grid=alpha_grid,
        rho_grid_size=rho_grid_size,
    )
    sample_seeds = _sample_seeds(root_seed, sample_count)
    results: dict[float, InteriorPBoxAlphaResult] = {}
    for alpha in alpha_grid:
        cut = cuts[alpha]
        rho_grid = tuple(
            rho for rho in candidate_rhos if cut.lower <= rho <= cut.upper
        )
        estimates = tuple(
            _RhoEstimate(
                rho=rho,
                estimate=_estimate_probability(
                    rho,
                    sample_seeds,
                    evaluator,
                    confidence_level,
                ),
            )
            for rho in rho_grid
        )
        # The fallback must search inside each alpha-cut because G3 may reject
        # endpoint monotonicity; CRN keeps aleatory identities fixed per rho.
        lower = min(estimates, key=lambda item: (item.estimate.probability, item.rho))
        upper = max(estimates, key=lambda item: (item.estimate.probability, -item.rho))
        results[alpha] = InteriorPBoxAlphaResult(
            alpha=alpha,
            rho_lower=cut.lower,
            rho_upper=cut.upper,
            rho_grid=rho_grid,
            rho_at_lower_probability=lower.rho,
            rho_at_upper_probability=upper.rho,
            lower=lower.estimate,
            upper=upper.estimate,
        )

    assert_bound_order(results)
    assert_nested(results)
    return results


@dataclass(frozen=True)
class _RhoEstimate:
    rho: float
    estimate: ProbabilityEstimate


def _global_candidate_rhos(
    *,
    fuzzy_number: FuzzyNumber,
    alpha_grid: Sequence[float],
    rho_grid_size: int,
) -> tuple[float, ...]:
    support = fuzzy_number.alpha_cut(0.0)
    support_grid = _linspace(support.lower, support.upper, rho_grid_size)
    cut_endpoints: list[float] = []
    for alpha in alpha_grid:
        cut = fuzzy_number.alpha_cut(alpha)
        cut_endpoints.extend((cut.lower, cut.upper))
    return tuple(sorted({*support_grid, *cut_endpoints}))


def _linspace(lower: float, upper: float, count: int) -> tuple[float, ...]:
    if count == 2:
        return lower, upper
    step = (upper - lower) / (count - 1)
    return tuple(lower + step * index for index in range(count))


def _estimate_probability(
    rho: float,
    sample_seeds: Sequence[int],
    evaluator: InteriorSampleEvaluator,
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


def _sample_seeds(root_seed: int, sample_count: int) -> tuple[int, ...]:
    return tuple(sample_seed(root_seed, sample_index) for sample_index in range(sample_count))
