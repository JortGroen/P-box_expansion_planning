"""Synthetic E5.S4 cross-check fixtures for p-box math readiness.

The helpers here are trust-certificate scaffolds only. They use finite toy
models and closed-form probabilities; they do not consume project net-load
trajectories or produce paper-facing overload probabilities.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import NormalDist
from typing import Mapping, Sequence

from src.fuzzy import TrapezoidalFuzzyNumber
from src.pbox import PBoxAlphaResult, VertexUseMode, estimate_vertex_pbox
from src.rng import sample_seed


@dataclass(frozen=True)
class GaussianToyParameters:
    """Closed-form one-step Gaussian event model for E5.S4."""

    mu_0: float
    beta: float
    sigma: float
    threshold: float

    def __post_init__(self) -> None:
        for name, value in (
            ("mu_0", self.mu_0),
            ("beta", self.beta),
            ("sigma", self.sigma),
            ("threshold", self.threshold),
        ):
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if self.beta <= 0.0:
            raise ValueError("beta must be positive for the decreasing-rho toy")
        if self.sigma <= 0.0:
            raise ValueError("sigma must be positive")


def gaussian_tail_probability(*, rho: float, params: GaussianToyParameters) -> float:
    """Return closed-form ``P(mu_0 - beta*rho + sigma*Z > threshold)``."""

    if not math.isfinite(rho):
        raise ValueError("rho must be finite")
    z_score = (params.threshold - params.mu_0 + params.beta * rho) / params.sigma
    return 1.0 - NormalDist().cdf(z_score)


def gaussian_closed_form_bounds(
    *,
    fuzzy_number: TrapezoidalFuzzyNumber,
    alpha_grid: Sequence[float],
    params: GaussianToyParameters,
) -> dict[float, tuple[float, float]]:
    """Return exact endpoint bounds for the decreasing Gaussian toy."""

    bounds: dict[float, tuple[float, float]] = {}
    for alpha in alpha_grid:
        cut = fuzzy_number.alpha_cut(alpha)
        lower = gaussian_tail_probability(rho=cut.upper, params=params)
        upper = gaussian_tail_probability(rho=cut.lower, params=params)
        if lower > upper:
            raise ValueError("expected decreasing toy to produce lower <= upper")
        bounds[alpha] = (lower, upper)
    return bounds


def estimate_gaussian_toy_pbox(
    *,
    fuzzy_number: TrapezoidalFuzzyNumber,
    alpha_grid: Sequence[float],
    params: GaussianToyParameters,
    sample_count: int,
    root_seed: int,
) -> dict[float, PBoxAlphaResult]:
    """Estimate the Gaussian toy through the existing vertex p-box pathway."""

    if sample_count <= 0:
        raise ValueError("sample_count must be positive")
    seed_to_index = {
        sample_seed(root_seed, sample_index): sample_index
        for sample_index in range(sample_count)
    }
    normal = NormalDist()

    def evaluator(rho: float, seed: int) -> bool:
        sample_index = seed_to_index[seed]
        quantile = (sample_index + 0.5) / sample_count
        z_value = normal.inv_cdf(quantile)
        loading = params.mu_0 - params.beta * rho + params.sigma * z_value
        return loading > params.threshold

    return estimate_vertex_pbox(
        fuzzy_number=fuzzy_number,
        alpha_grid=alpha_grid,
        sample_count=sample_count,
        root_seed=root_seed,
        evaluator=evaluator,
        use_mode=VertexUseMode.PRE_G3_SYNTHETIC,
    )


@dataclass(frozen=True)
class FiniteHybridState:
    """One aleatory state in a finite synthetic hybrid propagation fixture."""

    value: float
    probability: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.value):
            raise ValueError("state value must be finite")
        if not math.isfinite(self.probability) or self.probability < 0.0:
            raise ValueError("state probability must be finite and nonnegative")


@dataclass(frozen=True)
class FiniteHybridAlphaResult:
    """Exact alpha-indexed probability interval for a finite hybrid toy."""

    alpha: float
    rho_lower: float
    rho_upper: float
    lower_probability: float
    upper_probability: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.alpha <= 1.0:
            raise ValueError("alpha must be in [0, 1]")
        if self.rho_lower > self.rho_upper:
            raise ValueError("rho_lower must be <= rho_upper")
        if self.lower_probability > self.upper_probability:
            raise ValueError("expected lower_probability <= upper_probability")


def finite_hybrid_bounds(
    *,
    fuzzy_number: TrapezoidalFuzzyNumber,
    alpha_grid: Sequence[float],
    states: Sequence[FiniteHybridState],
    threshold: float,
) -> dict[float, FiniteHybridAlphaResult]:
    """Return exact Baudrit-style alpha-indexed bounds for a finite toy.

    The toy event is ``state.value - rho > threshold``. It is monotone
    decreasing in ``rho``, so the upper alpha-cut endpoint gives the lower
    event probability and the lower endpoint gives the upper probability.
    """

    state_tuple = tuple(states)
    if not state_tuple:
        raise ValueError("states must not be empty")
    if not math.isfinite(threshold):
        raise ValueError("threshold must be finite")
    total_probability = sum(state.probability for state in state_tuple)
    if not math.isclose(total_probability, 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("state probabilities must sum to 1")

    results: dict[float, FiniteHybridAlphaResult] = {}
    for alpha in alpha_grid:
        cut = fuzzy_number.alpha_cut(alpha)
        # Preserve aleatory probabilities inside each alpha cut; epistemic
        # uncertainty selects endpoints and is not averaged or defuzzified.
        lower = _finite_event_probability(state_tuple, rho=cut.upper, threshold=threshold)
        upper = _finite_event_probability(state_tuple, rho=cut.lower, threshold=threshold)
        results[alpha] = FiniteHybridAlphaResult(
            alpha=alpha,
            rho_lower=cut.lower,
            rho_upper=cut.upper,
            lower_probability=lower,
            upper_probability=upper,
        )
    _assert_nested_finite(results)
    return results


def _finite_event_probability(
    states: Sequence[FiniteHybridState],
    *,
    rho: float,
    threshold: float,
) -> float:
    return sum(state.probability for state in states if state.value - rho > threshold)


def _assert_nested_finite(results: Mapping[float, FiniteHybridAlphaResult]) -> None:
    ordered = sorted(results.values(), key=lambda result: result.alpha)
    for outer, inner in zip(ordered, ordered[1:]):
        if outer.lower_probability > inner.lower_probability:
            raise ValueError("nested lower-probability violation")
        if inner.upper_probability > outer.upper_probability:
            raise ValueError("nested upper-probability violation")
