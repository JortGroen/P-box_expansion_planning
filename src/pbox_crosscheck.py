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

import numpy as np

from src.evaluator_sum import Tier1Evaluation, count_import_overload_episodes
from src.fuzzy import TrapezoidalFuzzyNumber
from src.pbox import PBoxAlphaResult, VertexUseMode, estimate_vertex_pbox
from src.pbox_error import OutputErrorProtocolConfig, build_output_error_manifest_record
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
class OutputErrorToyTrajectory:
    """Synthetic loading trajectory for output-error trust-certificate checks."""

    sample_id: str
    loading_pu: tuple[float, ...]
    p_signs: tuple[int, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.sample_id, str) or not self.sample_id.strip():
            raise ValueError("sample_id must be a nonempty string")
        if len(self.loading_pu) == 0:
            raise ValueError("loading_pu must not be empty")
        if len(self.loading_pu) != len(self.p_signs):
            raise ValueError("loading_pu and p_signs must have the same length")
        if any(not math.isfinite(value) or value < 0.0 for value in self.loading_pu):
            raise ValueError("loading_pu values must be finite and nonnegative")
        if any(sign not in (-1, 0, 1) for sign in self.p_signs):
            raise ValueError("p_signs must contain only -1, 0, or 1")

    def to_loading_trajectory(
        self,
        *,
        threshold_pu: float,
        min_consecutive_steps: int,
    ) -> Tier1Evaluation:
        """Materialize the shared IC-2 loading contract for this toy sample."""

        denominator_kva = 1_000.0
        loading = np.asarray(self.loading_pu, dtype=float)
        signs = np.asarray(self.p_signs, dtype=int)
        p_net_kw = signs * loading * denominator_kva
        q_net_kvar = np.where(signs == 0, loading * denominator_kva, 0.0)
        s_net_kva = np.hypot(p_net_kw, q_net_kvar)
        screening_loading_pu = s_net_kva / denominator_kva
        import_mask = p_net_kw > 0.0
        export_mask = p_net_kw < 0.0
        zero_mask = p_net_kw == 0.0
        import_loading_pu = np.where(import_mask, screening_loading_pu, 0.0)
        export_loading_pu = np.where(export_mask, screening_loading_pu, 0.0)
        episodes, longest = count_import_overload_episodes(
            import_loading_pu,
            threshold_pu=threshold_pu,
            min_consecutive_steps=min_consecutive_steps,
        )
        return Tier1Evaluation(
            p_net_kw=p_net_kw,
            q_net_kvar=q_net_kvar,
            s_net_kva=s_net_kva,
            screening_loading_pu=screening_loading_pu,
            import_loading_pu=import_loading_pu,
            export_loading_pu=export_loading_pu,
            import_mask=import_mask,
            export_mask=export_mask,
            zero_mask=zero_mask,
            overload=episodes > 0,
            overload_episode_count=episodes,
            longest_import_run_steps=longest,
            time_domain="full_year",
            primary_probability_domain=True,
            threshold_pu=threshold_pu,
            min_consecutive_steps=min_consecutive_steps,
        )


@dataclass(frozen=True)
class OutputErrorAlphaCrosscheckResult:
    """Manifest-ready endpoint-count cross-check for one synthetic alpha level."""

    alpha: float
    sample_ids: tuple[str, ...]
    lower_successes: int
    upper_successes: int
    sample_count: int
    manifest_record: Mapping[str, object]

    def __post_init__(self) -> None:
        if not math.isfinite(self.alpha) or not 0.0 <= self.alpha <= 1.0:
            raise ValueError("alpha must be finite and in [0, 1]")
        if len(self.sample_ids) != self.sample_count:
            raise ValueError("sample_ids must match sample_count")
        if not 0 <= self.lower_successes <= self.upper_successes <= self.sample_count:
            raise ValueError("expected 0 <= lower_successes <= upper_successes <= sample_count")


def output_error_alpha_crosscheck_records(
    *,
    samples_by_alpha: Mapping[float, Sequence[OutputErrorToyTrajectory]],
    config: OutputErrorProtocolConfig,
    confidence_level: float = 0.95,
) -> dict[float, OutputErrorAlphaCrosscheckResult]:
    """Build synthetic output-error records while preserving alpha CRN identity.

    Each alpha level is evaluated separately, but the ordered ``sample_id``
    sequence must be identical across levels. That makes CRN reuse observable
    without sampling model-error intervals or widening probabilities afterward.
    """

    if not samples_by_alpha:
        raise ValueError("samples_by_alpha must contain at least one alpha level")
    ordered_alpha = tuple(sorted(samples_by_alpha))
    baseline_ids: tuple[str, ...] | None = None
    results: dict[float, OutputErrorAlphaCrosscheckResult] = {}
    for alpha in ordered_alpha:
        if not math.isfinite(alpha) or not 0.0 <= alpha <= 1.0:
            raise ValueError("alpha values must be finite and in [0, 1]")
        samples = tuple(samples_by_alpha[alpha])
        if not samples:
            raise ValueError("each alpha level must contain at least one sample")
        sample_ids = tuple(sample.sample_id for sample in samples)
        if baseline_ids is None:
            baseline_ids = sample_ids
        elif sample_ids != baseline_ids:
            raise ValueError("all alpha levels must preserve the same ordered sample_id sequence")
        trajectories = [
            sample.to_loading_trajectory(
                threshold_pu=config.threshold_pu,
                min_consecutive_steps=config.min_consecutive_steps,
            )
            for sample in samples
        ]
        record = build_output_error_manifest_record(
            trajectories,
            config,
            confidence_level=confidence_level,
        )
        event_counts = record["event_count_bounds"]
        results[alpha] = OutputErrorAlphaCrosscheckResult(
            alpha=alpha,
            sample_ids=sample_ids,
            lower_successes=int(event_counts["lower_successes"]),
            upper_successes=int(event_counts["upper_successes"]),
            sample_count=int(event_counts["sample_count"]),
            manifest_record=record,
        )
    return results


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
