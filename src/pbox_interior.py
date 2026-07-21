"""Interior alpha-cut fallback for p-box propagation.

This module is an E4.S2 scaffold. It provides a deterministic interior-search
path that can be activated if G3 rejects endpoint-only vertex propagation; it
does not authorize paper-facing probability results by itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from src.pbox import (
    FuzzyNumber,
    ProbabilityEstimate,
    _wilson_interval,
    assert_bound_order,
    assert_nested,
)
from src.rng import sample_seed

InteriorSampleEvaluator = Callable[[float, int], bool]


@dataclass(frozen=True)
class InteriorPBoxAlphaResult:
    """P-box bounds for one alpha level found by interior rho search."""

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
        if self.lower.probability > self.upper.probability:
            raise ValueError("expected P_lower <= P_upper")
        if self.lower.ci_lower > self.upper.ci_upper:
            raise ValueError("confidence intervals imply disjoint reversed bounds")


InteriorPBoxFamily = Mapping[float, InteriorPBoxAlphaResult]


def estimate_interior_pbox(
    *,
    fuzzy_number: FuzzyNumber,
    alpha_grid: Sequence[float],
    sample_count: int,
    root_seed: int,
    evaluator: InteriorSampleEvaluator,
    rho_grid_size: int,
    confidence_level: float = 0.95,
) -> dict[float, InteriorPBoxAlphaResult]:
    """Estimate alpha-indexed p-box bounds by sampling inside each alpha-cut.

    For each alpha-cut, the scaffold evaluates a deterministic support-wide
    rho grid plus all alpha-cut endpoints, then reports the minimum and maximum
    event probabilities found within that cut. The same canonical sample seeds
    are reused at every rho candidate to preserve common random numbers.
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

    for alpha, cut in cuts.items():
        rho_grid = tuple(rho for rho in candidate_rhos if cut.lower <= rho <= cut.upper)
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
    candidates = set(_linspace(support.lower, support.upper, rho_grid_size))
    for alpha in alpha_grid:
        cut = fuzzy_number.alpha_cut(alpha)
        candidates.add(cut.lower)
        candidates.add(cut.upper)
    return tuple(sorted(candidates))


def _linspace(start: float, stop: float, count: int) -> tuple[float, ...]:
    if count == 1:
        return (start,)
    step = (stop - start) / (count - 1)
    return tuple(start + index * step for index in range(count))


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
    # Interior fallback branches replay canonical whole-system samples under
    # CRN; only rho candidates are allowed to vary across branches.
    return tuple(sample_seed(root_seed, sample_index) for sample_index in range(sample_count))
