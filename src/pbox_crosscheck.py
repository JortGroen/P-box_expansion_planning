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
class GaussianCrosscheckAlphaRecord:
    """Manifest row comparing one alpha-cut p-box result with its oracle."""

    alpha: float
    rho_lower: float
    rho_upper: float
    closed_form_lower: float
    closed_form_upper: float
    estimated_lower: float
    estimated_upper: float
    estimated_lower_ci_lower: float
    estimated_lower_ci_upper: float
    estimated_upper_ci_lower: float
    estimated_upper_ci_upper: float
    closed_form_lower_in_ci: bool
    closed_form_upper_in_ci: bool
    absolute_error_lower: float
    absolute_error_upper: float

    def __post_init__(self) -> None:
        for name, value in self.to_mapping().items():
            if name == "alpha" or name.startswith("rho_"):
                if not isinstance(value, float) or not math.isfinite(value):
                    raise ValueError(f"{name} must be finite")
            elif name.endswith("_in_ci"):
                if not isinstance(value, bool):
                    raise TypeError(f"{name} must be boolean")
            elif isinstance(value, float) and (
                not math.isfinite(value) or not 0.0 <= value <= 1.0
            ):
                raise ValueError(f"{name} must be finite and in [0, 1]")
        if self.rho_lower > self.rho_upper:
            raise ValueError("rho_lower must be <= rho_upper")
        if self.closed_form_lower > self.closed_form_upper:
            raise ValueError("closed-form lower bound must not exceed upper bound")
        if self.estimated_lower > self.estimated_upper:
            raise ValueError("estimated lower bound must not exceed upper bound")
        if not (
            self.estimated_lower_ci_lower
            <= self.estimated_lower
            <= self.estimated_lower_ci_upper
        ):
            raise ValueError("estimated lower CI must contain estimated lower probability")
        if not (
            self.estimated_upper_ci_lower
            <= self.estimated_upper
            <= self.estimated_upper_ci_upper
        ):
            raise ValueError("estimated upper CI must contain estimated upper probability")
        if self.closed_form_lower_in_ci != (
            self.estimated_lower_ci_lower
            <= self.closed_form_lower
            <= self.estimated_lower_ci_upper
        ):
            raise ValueError("closed_form_lower_in_ci is inconsistent with CI endpoints")
        if self.closed_form_upper_in_ci != (
            self.estimated_upper_ci_lower
            <= self.closed_form_upper
            <= self.estimated_upper_ci_upper
        ):
            raise ValueError("closed_form_upper_in_ci is inconsistent with CI endpoints")

    def to_mapping(self) -> dict[str, float | bool]:
        return {
            "absolute_error_lower": self.absolute_error_lower,
            "absolute_error_upper": self.absolute_error_upper,
            "alpha": self.alpha,
            "closed_form_lower": self.closed_form_lower,
            "closed_form_lower_in_ci": self.closed_form_lower_in_ci,
            "closed_form_upper": self.closed_form_upper,
            "closed_form_upper_in_ci": self.closed_form_upper_in_ci,
            "estimated_lower": self.estimated_lower,
            "estimated_lower_ci_lower": self.estimated_lower_ci_lower,
            "estimated_lower_ci_upper": self.estimated_lower_ci_upper,
            "estimated_upper": self.estimated_upper,
            "estimated_upper_ci_lower": self.estimated_upper_ci_lower,
            "estimated_upper_ci_upper": self.estimated_upper_ci_upper,
            "rho_lower": self.rho_lower,
            "rho_upper": self.rho_upper,
        }


@dataclass(frozen=True)
class GaussianCrosscheckManifest:
    """JSON-stable synthetic E5.S4 analytic trust-certificate payload."""

    rows: tuple[GaussianCrosscheckAlphaRecord, ...]
    tolerance: float
    sample_count: int
    root_seed: int
    use_status: str = "synthetic-only"
    crosscheck_id: str = "E5.S4-gaussian-analytic-v1"

    def __post_init__(self) -> None:
        if self.crosscheck_id != "E5.S4-gaussian-analytic-v1":
            raise ValueError("crosscheck_id must identify the E5.S4 Gaussian fixture")
        if self.use_status != "synthetic-only":
            raise ValueError("Gaussian cross-check manifest must remain synthetic-only")
        if not self.rows:
            raise ValueError("rows must not be empty")
        if not math.isfinite(self.tolerance) or self.tolerance <= 0.0:
            raise ValueError("tolerance must be finite and positive")
        if self.sample_count <= 0:
            raise ValueError("sample_count must be positive")
        if self.root_seed < 0:
            raise ValueError("root_seed must be nonnegative")
        alphas = tuple(row.alpha for row in self.rows)
        if alphas != tuple(sorted(alphas)) or len(set(alphas)) != len(alphas):
            raise ValueError("rows must be strictly increasing in alpha")

    @property
    def max_absolute_error(self) -> float:
        return max(
            max(row.absolute_error_lower, row.absolute_error_upper)
            for row in self.rows
        )

    @property
    def alpha_rows_nested(self) -> bool:
        return _alpha_probability_rows_nested(self.rows)

    @property
    def closed_form_within_confidence_intervals(self) -> bool:
        return all(
            row.closed_form_lower_in_ci and row.closed_form_upper_in_ci
            for row in self.rows
        )

    @property
    def passed(self) -> bool:
        return (
            self.max_absolute_error <= self.tolerance
            and self.alpha_rows_nested
            and self.closed_form_within_confidence_intervals
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "alpha_rows": [row.to_mapping() for row in self.rows],
            "alpha_rows_nested": self.alpha_rows_nested,
            "closed_form_oracle": (
                "P(E_toy | rho)=1-Phi((c_toy-mu_0+beta*rho)/sigma)"
            ),
            "closed_form_within_confidence_intervals": (
                self.closed_form_within_confidence_intervals
            ),
            "confidence_interval_reporting": "separate-lower-upper-ci",
            "crosscheck_id": self.crosscheck_id,
            "g3_claim": "none-pre-g3-synthetic",
            "max_absolute_error": self.max_absolute_error,
            "passed": self.passed,
            "probability_reporting": "alpha-indexed-lower-upper-only",
            "root_seed": self.root_seed,
            "sample_count": self.sample_count,
            "synthetic_non_claims": [
                "no real trajectories",
                "no real P(E)",
                "no capacity screen",
                "no manuscript number",
            ],
            "tolerance": self.tolerance,
            "use_status": self.use_status,
        }


def _alpha_probability_rows_nested(
    rows: Sequence[GaussianCrosscheckAlphaRecord],
    *,
    tolerance: float = 1e-12,
) -> bool:
    previous: GaussianCrosscheckAlphaRecord | None = None
    for row in rows:
        if previous is not None:
            lower_expands = (
                row.closed_form_lower + tolerance < previous.closed_form_lower
            )
            upper_expands = (
                row.closed_form_upper > previous.closed_form_upper + tolerance
            )
            estimated_lower_expands = (
                row.estimated_lower + tolerance < previous.estimated_lower
            )
            estimated_upper_expands = (
                row.estimated_upper > previous.estimated_upper + tolerance
            )
            if (
                lower_expands
                or upper_expands
                or estimated_lower_expands
                or estimated_upper_expands
            ):
                return False
        previous = row
    return True


def build_gaussian_crosscheck_manifest(
    *,
    fuzzy_number: TrapezoidalFuzzyNumber,
    alpha_grid: Sequence[float],
    params: GaussianToyParameters,
    sample_count: int,
    root_seed: int,
    tolerance: float = 0.01,
) -> GaussianCrosscheckManifest:
    """Compare the synthetic Gaussian p-box path with closed-form endpoints."""

    expected = gaussian_closed_form_bounds(
        fuzzy_number=fuzzy_number,
        alpha_grid=alpha_grid,
        params=params,
    )
    estimated = estimate_gaussian_toy_pbox(
        fuzzy_number=fuzzy_number,
        alpha_grid=alpha_grid,
        params=params,
        sample_count=sample_count,
        root_seed=root_seed,
    )
    rows = []
    for alpha in sorted(expected):
        cut = fuzzy_number.alpha_cut(alpha)
        expected_lower, expected_upper = expected[alpha]
        result = estimated[alpha]
        rows.append(
            GaussianCrosscheckAlphaRecord(
                alpha=alpha,
                rho_lower=cut.lower,
                rho_upper=cut.upper,
                closed_form_lower=expected_lower,
                closed_form_upper=expected_upper,
                estimated_lower=result.lower.probability,
                estimated_upper=result.upper.probability,
                estimated_lower_ci_lower=result.lower.ci_lower,
                estimated_lower_ci_upper=result.lower.ci_upper,
                estimated_upper_ci_lower=result.upper.ci_lower,
                estimated_upper_ci_upper=result.upper.ci_upper,
                closed_form_lower_in_ci=(
                    result.lower.ci_lower <= expected_lower <= result.lower.ci_upper
                ),
                closed_form_upper_in_ci=(
                    result.upper.ci_lower <= expected_upper <= result.upper.ci_upper
                ),
                absolute_error_lower=abs(result.lower.probability - expected_lower),
                absolute_error_upper=abs(result.upper.probability - expected_upper),
            )
        )
    return GaussianCrosscheckManifest(
        rows=tuple(rows),
        tolerance=tolerance,
        sample_count=sample_count,
        root_seed=root_seed,
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
class BootstrapProbabilityInterval:
    """Rank-bootstrap CI for a synthetic Bernoulli event probability."""

    probability: float
    ci_lower: float
    ci_upper: float
    confidence_level: float
    replicate_count: int

    def __post_init__(self) -> None:
        if self.replicate_count <= 0:
            raise ValueError("replicate_count must be positive")
        for name, value in (
            ("probability", self.probability),
            ("ci_lower", self.ci_lower),
            ("ci_upper", self.ci_upper),
        ):
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be finite and in [0, 1]")
        if not math.isfinite(self.confidence_level) or not 0.0 < self.confidence_level < 1.0:
            raise ValueError("confidence_level must be in (0, 1)")
        if self.ci_lower > self.probability or self.probability > self.ci_upper:
            raise ValueError("expected ci_lower <= probability <= ci_upper")


@dataclass(frozen=True)
class MonotonicitySweepPoint:
    """One synthetic rho-grid event-probability point."""

    rho: float
    probability: float
    ci_lower: float
    ci_upper: float
    successes: int
    sample_count: int

    def __post_init__(self) -> None:
        if not math.isfinite(self.rho):
            raise ValueError("rho must be finite")
        if self.sample_count <= 0:
            raise ValueError("sample_count must be positive")
        if not 0 <= self.successes <= self.sample_count:
            raise ValueError("successes must be between 0 and sample_count")
        for name, value in (
            ("probability", self.probability),
            ("ci_lower", self.ci_lower),
            ("ci_upper", self.ci_upper),
        ):
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be finite and in [0, 1]")
        if self.ci_lower > self.probability or self.probability > self.ci_upper:
            raise ValueError("expected ci_lower <= probability <= ci_upper")


@dataclass(frozen=True)
class MonotonicitySweepResult:
    """Synthetic monotonicity-sweep diagnostic, not a G3 verdict."""

    expected_direction: str
    points: tuple[MonotonicitySweepPoint, ...]
    violations: tuple[tuple[float, float, float, float], ...]

    def __post_init__(self) -> None:
        if self.expected_direction not in {"nonincreasing", "nondecreasing"}:
            raise ValueError("expected_direction must be 'nonincreasing' or 'nondecreasing'")
        if not self.points:
            raise ValueError("points must not be empty")
        rhos = tuple(point.rho for point in self.points)
        if rhos != tuple(sorted(rhos)) or len(set(rhos)) != len(rhos):
            raise ValueError("points must use a strictly increasing rho grid")


def bootstrap_probability_interval(
    events: Sequence[bool],
    *,
    resample_indices: Sequence[Sequence[int]],
    confidence_level: float = 0.95,
) -> BootstrapProbabilityInterval:
    """Return a deterministic rank-bootstrap interval for toy event indicators."""

    event_tuple = _coerce_event_tuple(events)
    if not math.isfinite(confidence_level) or not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must be in (0, 1)")
    if not resample_indices:
        raise ValueError("resample_indices must contain at least one replicate")
    replicate_probabilities = []
    for replicate in resample_indices:
        indices = tuple(replicate)
        if not indices:
            raise ValueError("bootstrap replicates must not be empty")
        if any(isinstance(index, bool) or index < 0 or index >= len(event_tuple) for index in indices):
            raise ValueError("bootstrap indices must address the event vector")
        replicate_probabilities.append(sum(event_tuple[index] for index in indices) / len(indices))

    probability = sum(event_tuple) / len(event_tuple)
    sorted_probabilities = tuple(sorted(replicate_probabilities))
    alpha = (1.0 - confidence_level) / 2.0
    lower_index = math.floor(alpha * (len(sorted_probabilities) - 1))
    upper_index = math.ceil((1.0 - alpha) * (len(sorted_probabilities) - 1))
    # Rank endpoints make the tiny synthetic fixtures reproducible by hand;
    # they are diagnostics only, not a paper-facing CI prescription.
    return BootstrapProbabilityInterval(
        probability=probability,
        ci_lower=min(sorted_probabilities[lower_index], probability),
        ci_upper=max(sorted_probabilities[upper_index], probability),
        confidence_level=confidence_level,
        replicate_count=len(sorted_probabilities),
    )


def monotonicity_sweep_from_events(
    *,
    events_by_rho: Mapping[float, Sequence[bool]],
    resample_indices: Sequence[Sequence[int]],
    expected_direction: str = "nonincreasing",
    confidence_level: float = 0.95,
) -> MonotonicitySweepResult:
    """Evaluate a synthetic rho sweep from fixed-CRN event indicators."""

    if expected_direction not in {"nonincreasing", "nondecreasing"}:
        raise ValueError("expected_direction must be 'nonincreasing' or 'nondecreasing'")
    if not events_by_rho:
        raise ValueError("events_by_rho must contain at least one rho level")
    ordered_rhos = tuple(sorted(events_by_rho))
    if any(not math.isfinite(rho) for rho in ordered_rhos):
        raise ValueError("rho values must be finite")
    event_tuples = {rho: _coerce_event_tuple(events_by_rho[rho]) for rho in ordered_rhos}
    sample_counts = {len(events) for events in event_tuples.values()}
    if len(sample_counts) != 1:
        raise ValueError("all rho levels must use the same sample count for CRN diagnostics")

    points = []
    for rho in ordered_rhos:
        interval = bootstrap_probability_interval(
            event_tuples[rho],
            resample_indices=resample_indices,
            confidence_level=confidence_level,
        )
        points.append(
            MonotonicitySweepPoint(
                rho=rho,
                probability=interval.probability,
                ci_lower=interval.ci_lower,
                ci_upper=interval.ci_upper,
                successes=sum(event_tuples[rho]),
                sample_count=len(event_tuples[rho]),
            )
        )

    violations: list[tuple[float, float, float, float]] = []
    for left, right in zip(points, points[1:]):
        if expected_direction == "nonincreasing" and right.probability > left.probability:
            violations.append((left.rho, right.rho, left.probability, right.probability))
        if expected_direction == "nondecreasing" and right.probability < left.probability:
            violations.append((left.rho, right.rho, left.probability, right.probability))
    return MonotonicitySweepResult(
        expected_direction=expected_direction,
        points=tuple(points),
        violations=tuple(violations),
    )


def _coerce_event_tuple(events: Sequence[bool]) -> tuple[bool, ...]:
    event_tuple = tuple(events)
    if not event_tuple:
        raise ValueError("events must not be empty")
    if any(not isinstance(event, bool) for event in event_tuple):
        raise TypeError("events must contain booleans")
    return event_tuple


HYBRID_REPRODUCTION_READINESS_PROTOCOL = "e5s4-hybrid-reproduction-readiness-v1"
_REQUIRED_HYBRID_PROVENANCE_ROLES = frozenset(
    {"source", "published-example", "reproduction-evidence"}
)
_UNSIGNED_PROVENANCE_TOKENS = frozenset(
    {"pending", "placeholder", "proposed", "tbd", "unsigned", "unknown"}
)


@dataclass(frozen=True)
class HybridReproductionReadiness:
    """Fail-closed readiness packet for the published hybrid cross-check."""

    source_id: str
    source_status: str
    published_example_id: str
    example_reproduced: bool
    qualitative_behavior_checked: bool
    blockers: tuple[str, ...]
    provenance_ids: tuple[str, ...] = ()
    use_status: str = "source-readiness-only"
    protocol: str = HYBRID_REPRODUCTION_READINESS_PROTOCOL

    def __post_init__(self) -> None:
        if self.protocol != HYBRID_REPRODUCTION_READINESS_PROTOCOL:
            raise ValueError(
                f"protocol must be {HYBRID_REPRODUCTION_READINESS_PROTOCOL!r}"
            )
        if self.use_status != "source-readiness-only":
            raise ValueError("hybrid reproduction readiness is source-readiness only")
        if self.source_status not in {"pending-source", "verified-approved"}:
            raise ValueError("source_status must be pending-source or verified-approved")
        for name, value in (
            ("source_id", self.source_id),
            ("published_example_id", self.published_example_id),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a nonempty string")
        if not isinstance(self.example_reproduced, bool):
            raise TypeError("example_reproduced must be boolean")
        if not isinstance(self.qualitative_behavior_checked, bool):
            raise TypeError("qualitative_behavior_checked must be boolean")
        if any(
            not isinstance(blocker, str) or not blocker.strip()
            for blocker in self.blockers
        ):
            raise ValueError("blockers must contain only nonempty strings")
        _validate_hybrid_provenance_ids(self.provenance_ids, ready=self.ready)
        if self.ready and self.blockers:
            raise ValueError("ready hybrid reproduction must not carry blockers")
        if not self.ready and not self.blockers:
            raise ValueError("blocked hybrid reproduction must name at least one blocker")

    @property
    def ready(self) -> bool:
        return (
            self.source_status == "verified-approved"
            and self.example_reproduced
            and self.qualitative_behavior_checked
            and not self.blockers
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "blockers": list(self.blockers),
            "example_reproduced": self.example_reproduced,
            "published_example_id": self.published_example_id,
            "provenance_ids": list(self.provenance_ids),
            "qualitative_behavior_checked": self.qualitative_behavior_checked,
            "ready": self.ready,
            "source_id": self.source_id,
            "source_status": self.source_status,
            "synthetic_non_claims": [
                "no published reproduction unless ready is true",
                "no real trajectories",
                "no real P(E)",
                "no manuscript number",
            ],
            "protocol": self.protocol,
            "use_status": self.use_status,
        }


def assert_hybrid_reproduction_ready_payload(payload: Mapping[str, object]) -> None:
    """Reject a serialized hybrid-reproduction packet until provenance is complete."""

    readiness = _coerce_hybrid_reproduction_readiness(payload)
    if "defuzzified_probability" in payload:
        raise ValueError("hybrid reproduction readiness must not be defuzzified")
    if (
        "ready" in payload
        and _expect_bool(payload["ready"], name="ready") != readiness.ready
    ):
        raise ValueError("serialized ready flag must match hybrid provenance state")
    if not readiness.ready:
        blockers = "; ".join(readiness.blockers)
        raise RuntimeError(f"hybrid reproduction is not ready: {blockers}")


def _coerce_hybrid_reproduction_readiness(
    payload: Mapping[str, object],
) -> HybridReproductionReadiness:
    required = {
        "blockers",
        "example_reproduced",
        "published_example_id",
        "provenance_ids",
        "qualitative_behavior_checked",
        "protocol",
        "source_id",
        "source_status",
        "use_status",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise ValueError(f"hybrid reproduction readiness missing fields: {missing}")
    blockers_obj = payload["blockers"]
    if not isinstance(blockers_obj, Sequence) or isinstance(
        blockers_obj, (str, bytes)
    ):
        raise TypeError("blockers must be a sequence of strings")
    provenance_obj = payload["provenance_ids"]
    if not isinstance(provenance_obj, Sequence) or isinstance(
        provenance_obj, (str, bytes)
    ):
        raise TypeError("provenance_ids must be a sequence of strings")
    return HybridReproductionReadiness(
        source_id=_expect_string(payload["source_id"], name="source_id"),
        source_status=_expect_string(payload["source_status"], name="source_status"),
        published_example_id=_expect_string(
            payload["published_example_id"], name="published_example_id"
        ),
        example_reproduced=_expect_bool(
            payload["example_reproduced"], name="example_reproduced"
        ),
        qualitative_behavior_checked=_expect_bool(
            payload["qualitative_behavior_checked"],
            name="qualitative_behavior_checked",
        ),
        blockers=tuple(
            _expect_string(blocker, name="blocker") for blocker in blockers_obj
        ),
        provenance_ids=tuple(
            _expect_string(provenance_id, name="provenance_id")
            for provenance_id in provenance_obj
        ),
        use_status=_expect_string(payload["use_status"], name="use_status"),
        protocol=_expect_string(payload["protocol"], name="protocol"),
    )


def _validate_hybrid_provenance_ids(
    provenance_ids: Sequence[str], *, ready: bool
) -> None:
    if any(
        not isinstance(provenance_id, str) or not provenance_id.strip()
        for provenance_id in provenance_ids
    ):
        raise ValueError("provenance_ids must contain only nonempty strings")
    if len(set(provenance_ids)) != len(tuple(provenance_ids)):
        raise ValueError("provenance_ids must not contain duplicates")
    roles = set()
    for provenance_id in provenance_ids:
        if ":" not in provenance_id:
            raise ValueError("provenance_ids must use '<role>:<id>' form")
        role, identifier = provenance_id.split(":", 1)
        if not role or not identifier.strip():
            raise ValueError("provenance_ids must use '<role>:<id>' form")
        if any(
            token in identifier.lower()
            for token in _UNSIGNED_PROVENANCE_TOKENS
        ):
            raise ValueError("provenance_ids must not contain unsigned placeholder IDs")
        roles.add(role)

    # The published-example gate must cite source, example, and reproduction
    # evidence separately; otherwise a true boolean could bypass provenance review.
    if ready and not _REQUIRED_HYBRID_PROVENANCE_ROLES.issubset(roles):
        missing = sorted(_REQUIRED_HYBRID_PROVENANCE_ROLES.difference(roles))
        raise ValueError(
            f"ready hybrid reproduction missing provenance roles: {missing}"
        )


def _expect_string(value: object, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")
    return value


def _expect_bool(value: object, *, name: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be boolean")
    return value


def _expect_float(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _expect_positive_int(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _expect_nonnegative_int(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
    return value


MATH_CORE_TRUST_CERTIFICATE_PROTOCOL = "e5s4-math-core-trust-certificate-v1"
_COLLAPSED_PROBABILITY_FIELDS = frozenset(
    {
        "defuzzified_probability",
        "expected_probability",
        "mean_probability",
        "mid_probability",
        "p_hat",
        "p_mid",
        "probability",
    }
)


@dataclass(frozen=True)
class MathCoreTrustCertificateManifest:
    """Synthetic E5.S4 trust-certificate boundary for p-box math checks."""

    analytic_gaussian: GaussianCrosscheckManifest
    hybrid_reproduction: HybridReproductionReadiness
    use_status: str = "synthetic-only"
    protocol: str = MATH_CORE_TRUST_CERTIFICATE_PROTOCOL
    g3_status: str = "pending-no-paper-facing-vertex-claim"

    def __post_init__(self) -> None:
        if self.protocol != MATH_CORE_TRUST_CERTIFICATE_PROTOCOL:
            raise ValueError(
                f"protocol must be {MATH_CORE_TRUST_CERTIFICATE_PROTOCOL!r}"
            )
        if self.use_status != "synthetic-only":
            raise ValueError("math-core trust certificate must remain synthetic-only")
        if self.g3_status != "pending-no-paper-facing-vertex-claim":
            raise ValueError("G3 must remain pending in this synthetic scaffold")

    @property
    def green_checks(self) -> tuple[str, ...]:
        checks: list[str] = []
        if self.analytic_gaussian.passed:
            checks.append("analytic Gaussian p-box cross-check within tolerance")
        if self.analytic_gaussian.alpha_rows_nested:
            checks.append("alpha-indexed lower/upper rows are nested")
        if self.analytic_gaussian.closed_form_within_confidence_intervals:
            checks.append("closed-form endpoints lie within separate lower/upper CIs")
        if (
            _find_collapsed_probability_field(self.to_mapping(include_checks=False))
            is None
        ):
            checks.append("no scalar defuzzified probability fields")
        return tuple(checks)

    @property
    def paper_facing_blockers(self) -> tuple[str, ...]:
        blockers: list[str] = []
        if not self.analytic_gaussian.passed:
            blockers.append("analytic Gaussian toy cross-check is not within tolerance")
        if not self.analytic_gaussian.alpha_rows_nested:
            blockers.append("analytic Gaussian alpha rows are not nested")
        if not self.analytic_gaussian.closed_form_within_confidence_intervals:
            blockers.append("closed-form endpoints are not contained in endpoint CIs")
        if not self.hybrid_reproduction.ready:
            blockers.extend(self.hybrid_reproduction.blockers)
        blockers.append("G3 remains pending for any paper-facing vertex-shortcut claim")
        return tuple(blockers)

    @property
    def ready_for_paper_math_claims(self) -> bool:
        return not self.paper_facing_blockers

    def to_mapping(self, *, include_checks: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "analytic_gaussian": self.analytic_gaussian.to_mapping(),
            "g3_status": self.g3_status,
            "hybrid_reproduction": self.hybrid_reproduction.to_mapping(),
            "paper_facing_blockers": list(self.paper_facing_blockers),
            "probability_reporting": "alpha-indexed-lower-upper-only",
            "protocol": self.protocol,
            "ready_for_paper_math_claims": self.ready_for_paper_math_claims,
            "synthetic_non_claims": [
                "no real trajectories",
                "no real P(E)",
                "no capacity screen",
                "no manuscript number",
                "no paper-facing G3 vertex claim",
            ],
            "use_status": self.use_status,
        }
        if include_checks:
            payload["green_checks"] = list(self.green_checks)
        return payload


def build_math_core_trust_certificate_manifest(
    *,
    analytic_gaussian: GaussianCrosscheckManifest,
    hybrid_reproduction: HybridReproductionReadiness,
) -> MathCoreTrustCertificateManifest:
    """Build the synthetic E5.S4 trust-certificate manifest boundary."""

    return MathCoreTrustCertificateManifest(
        analytic_gaussian=analytic_gaussian,
        hybrid_reproduction=hybrid_reproduction,
    )


def assert_math_core_trust_certificate_payload(payload: Mapping[str, object]) -> None:
    """Validate the serialized E5.S4 trust-certificate payload fail-closed."""

    _validate_no_probability_collapse(payload)
    required = {
        "analytic_gaussian",
        "g3_status",
        "green_checks",
        "hybrid_reproduction",
        "paper_facing_blockers",
        "probability_reporting",
        "protocol",
        "ready_for_paper_math_claims",
        "use_status",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise ValueError(f"math-core trust certificate missing fields: {missing}")
    if (
        _expect_string(payload["protocol"], name="protocol")
        != MATH_CORE_TRUST_CERTIFICATE_PROTOCOL
    ):
        raise ValueError(f"protocol must be {MATH_CORE_TRUST_CERTIFICATE_PROTOCOL!r}")
    if _expect_string(payload["use_status"], name="use_status") != "synthetic-only":
        raise ValueError("math-core trust certificate must remain synthetic-only")
    if (
        _expect_string(payload["probability_reporting"], name="probability_reporting")
        != "alpha-indexed-lower-upper-only"
    ):
        raise ValueError(
            "trust certificate must preserve alpha-indexed lower/upper reporting"
        )
    if (
        _expect_string(payload["g3_status"], name="g3_status")
        != "pending-no-paper-facing-vertex-claim"
    ):
        raise ValueError("G3 status must remain pending for this scaffold")

    analytic = payload["analytic_gaussian"]
    if not isinstance(analytic, Mapping):
        raise TypeError("analytic_gaussian must be a mapping")
    analytic_manifest = _coerce_gaussian_crosscheck_manifest(analytic)
    if dict(analytic) != analytic_manifest.to_mapping():
        raise ValueError("analytic_gaussian must match recomputed Gaussian manifest")

    hybrid = payload["hybrid_reproduction"]
    if not isinstance(hybrid, Mapping):
        raise TypeError("hybrid_reproduction must be a mapping")
    hybrid_readiness = _coerce_hybrid_reproduction_readiness(hybrid)

    blockers_obj = payload["paper_facing_blockers"]
    if not isinstance(blockers_obj, Sequence) or isinstance(
        blockers_obj, (str, bytes)
    ):
        raise TypeError("paper_facing_blockers must be a sequence of strings")
    blockers = tuple(
        _expect_string(blocker, name="paper_facing_blocker")
        for blocker in blockers_obj
    )
    ready = _expect_bool(
        payload["ready_for_paper_math_claims"],
        name="ready_for_paper_math_claims",
    )
    expected = MathCoreTrustCertificateManifest(
        analytic_gaussian=analytic_manifest,
        hybrid_reproduction=hybrid_readiness,
    ).to_mapping()
    if list(payload["green_checks"]) != expected["green_checks"]:
        raise ValueError("green_checks must match recomputed trust checks")
    if list(blockers) != expected["paper_facing_blockers"]:
        raise ValueError("paper_facing_blockers must match recomputed blockers")
    if ready != expected["ready_for_paper_math_claims"]:
        raise ValueError("ready_for_paper_math_claims must match blocker state")
    if ready and (not analytic_manifest.passed or not hybrid_readiness.ready):
        raise ValueError(
            "ready trust certificate must have green analytic and hybrid checks"
        )
    if "synthetic_non_claims" not in payload:
        raise ValueError("trust certificate must carry synthetic non-claims")
    if list(payload["synthetic_non_claims"]) != expected["synthetic_non_claims"]:
        raise ValueError("synthetic_non_claims must match the trust protocol")


def _coerce_gaussian_crosscheck_manifest(
    payload: Mapping[str, object],
) -> GaussianCrosscheckManifest:
    required = {
        "alpha_rows",
        "crosscheck_id",
        "root_seed",
        "sample_count",
        "tolerance",
        "use_status",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise ValueError(f"analytic Gaussian manifest missing fields: {missing}")
    rows_obj = payload["alpha_rows"]
    if not isinstance(rows_obj, Sequence) or isinstance(rows_obj, (str, bytes)):
        raise TypeError("analytic Gaussian alpha_rows must be a sequence")
    rows = tuple(_coerce_gaussian_crosscheck_alpha_record(row) for row in rows_obj)
    return GaussianCrosscheckManifest(
        rows=rows,
        tolerance=_expect_float(
            payload["tolerance"], name="analytic_gaussian.tolerance"
        ),
        sample_count=_expect_positive_int(
            payload["sample_count"], name="analytic_gaussian.sample_count"
        ),
        root_seed=_expect_nonnegative_int(
            payload["root_seed"], name="analytic_gaussian.root_seed"
        ),
        use_status=_expect_string(
            payload["use_status"], name="analytic_gaussian.use_status"
        ),
        crosscheck_id=_expect_string(
            payload["crosscheck_id"], name="analytic_gaussian.crosscheck_id"
        ),
    )


def _coerce_gaussian_crosscheck_alpha_record(
    payload: object,
) -> GaussianCrosscheckAlphaRecord:
    if not isinstance(payload, Mapping):
        raise TypeError("analytic Gaussian alpha row must be a mapping")
    required = {
        "absolute_error_lower",
        "absolute_error_upper",
        "alpha",
        "closed_form_lower",
        "closed_form_lower_in_ci",
        "closed_form_upper",
        "closed_form_upper_in_ci",
        "estimated_lower",
        "estimated_lower_ci_lower",
        "estimated_lower_ci_upper",
        "estimated_upper",
        "estimated_upper_ci_lower",
        "estimated_upper_ci_upper",
        "rho_lower",
        "rho_upper",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise ValueError(f"analytic Gaussian alpha row missing fields: {missing}")
    return GaussianCrosscheckAlphaRecord(
        alpha=_expect_float(payload["alpha"], name="alpha"),
        rho_lower=_expect_float(payload["rho_lower"], name="rho_lower"),
        rho_upper=_expect_float(payload["rho_upper"], name="rho_upper"),
        closed_form_lower=_expect_float(
            payload["closed_form_lower"], name="closed_form_lower"
        ),
        closed_form_upper=_expect_float(
            payload["closed_form_upper"], name="closed_form_upper"
        ),
        estimated_lower=_expect_float(payload["estimated_lower"], name="estimated_lower"),
        estimated_upper=_expect_float(payload["estimated_upper"], name="estimated_upper"),
        estimated_lower_ci_lower=_expect_float(
            payload["estimated_lower_ci_lower"], name="estimated_lower_ci_lower"
        ),
        estimated_lower_ci_upper=_expect_float(
            payload["estimated_lower_ci_upper"], name="estimated_lower_ci_upper"
        ),
        estimated_upper_ci_lower=_expect_float(
            payload["estimated_upper_ci_lower"], name="estimated_upper_ci_lower"
        ),
        estimated_upper_ci_upper=_expect_float(
            payload["estimated_upper_ci_upper"], name="estimated_upper_ci_upper"
        ),
        closed_form_lower_in_ci=_expect_bool(
            payload["closed_form_lower_in_ci"], name="closed_form_lower_in_ci"
        ),
        closed_form_upper_in_ci=_expect_bool(
            payload["closed_form_upper_in_ci"], name="closed_form_upper_in_ci"
        ),
        absolute_error_lower=_expect_float(
            payload["absolute_error_lower"], name="absolute_error_lower"
        ),
        absolute_error_upper=_expect_float(
            payload["absolute_error_upper"], name="absolute_error_upper"
        ),
    )


def _validate_no_probability_collapse(payload: object) -> None:
    path = _find_collapsed_probability_field(payload)
    if path is not None:
        raise ValueError(f"trust certificate must not contain collapsed field {path}")


def _find_collapsed_probability_field(
    payload: object, *, path: str = "payload"
) -> str | None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            key_text = str(key)
            current_path = f"{path}.{key_text}"
            if key_text in _COLLAPSED_PROBABILITY_FIELDS:
                return current_path
            nested = _find_collapsed_probability_field(value, path=current_path)
            if nested is not None:
                return nested
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        for index, value in enumerate(payload):
            nested = _find_collapsed_probability_field(value, path=f"{path}[{index}]")
            if nested is not None:
                return nested
    return None


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
