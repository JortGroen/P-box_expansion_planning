"""Interior alpha-cut fallback for p-box propagation.

This module is an E4.S2 scaffold. It provides a deterministic interior-search
path that can be activated if G3 rejects endpoint-only vertex propagation; it
does not authorize paper-facing probability results by itself.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
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
INTERIOR_FALLBACK_REPORT_PROTOCOL = "interior-pbox-fallback-report-v1"


@dataclass(frozen=True)
class InteriorFallbackReport:
    """Synthetic report payload for interior p-box fallback rows."""

    rows: tuple[dict[str, object], ...]
    use_status: str = "synthetic-pre-g3-only"
    report_protocol: str = INTERIOR_FALLBACK_REPORT_PROTOCOL
    g3_claim: str = "none-pre-g3-fallback-scaffold"

    def __post_init__(self) -> None:
        if self.report_protocol != INTERIOR_FALLBACK_REPORT_PROTOCOL:
            raise ValueError(
                f"report_protocol must be {INTERIOR_FALLBACK_REPORT_PROTOCOL!r}"
            )
        if self.use_status != "synthetic-pre-g3-only":
            raise ValueError("interior fallback report must remain synthetic/pre-G3")
        if self.g3_claim != "none-pre-g3-fallback-scaffold":
            raise ValueError("interior fallback report must not claim G3 approval")
        assert_interior_fallback_report_payload(self.to_mapping())

    def to_mapping(self) -> dict[str, object]:
        return {
            "g3_claim": self.g3_claim,
            "probability_reporting": "alpha-indexed-lower-upper-only",
            "report_protocol": self.report_protocol,
            "rows": [dict(row) for row in self.rows],
            "synthetic_non_claims": [
                "no real trajectories",
                "no real P(E)",
                "no G3 verdict",
                "no manuscript number",
            ],
            "use_status": self.use_status,
        }


def build_interior_fallback_report(
    family: InteriorPBoxFamily,
) -> InteriorFallbackReport:
    """Build a synthetic-only report around interior fallback p-box rows."""

    if not family:
        raise ValueError("family must not be empty")
    rows = tuple(
        _interior_result_to_row(result)
        for result in sorted(family.values(), key=lambda item: item.alpha)
    )
    return InteriorFallbackReport(rows=rows)


def assert_interior_fallback_report_payload(payload: Mapping[str, object]) -> None:
    """Validate a serialized synthetic interior-fallback report payload."""

    required = {
        "g3_claim",
        "probability_reporting",
        "report_protocol",
        "rows",
        "synthetic_non_claims",
        "use_status",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise ValueError(f"interior fallback report missing fields: {missing}")
    if "defuzzified_probability" in payload:
        raise ValueError("interior fallback report must not be defuzzified")
    if payload["report_protocol"] != INTERIOR_FALLBACK_REPORT_PROTOCOL:
        raise ValueError(
            f"report_protocol must be {INTERIOR_FALLBACK_REPORT_PROTOCOL!r}"
        )
    if payload["use_status"] != "synthetic-pre-g3-only":
        raise ValueError("interior fallback report must remain synthetic/pre-G3")
    if payload["g3_claim"] != "none-pre-g3-fallback-scaffold":
        raise ValueError("interior fallback report must not claim G3 approval")
    if payload["probability_reporting"] != "alpha-indexed-lower-upper-only":
        raise ValueError("probability_reporting must remain alpha-indexed lower/upper")
    rows_obj = payload["rows"]
    if not isinstance(rows_obj, Sequence) or isinstance(rows_obj, (str, bytes)):
        raise TypeError("rows must be a sequence of row mappings")
    if not rows_obj:
        raise ValueError("rows must not be empty")
    alphas: list[float] = []
    for index, row_obj in enumerate(rows_obj):
        if not isinstance(row_obj, Mapping):
            raise TypeError(f"rows[{index}] must be a mapping")
        if "defuzzified_probability" in row_obj:
            raise ValueError("interior fallback rows must not be defuzzified")
        alpha = _validate_interior_report_row(row_obj, index=index)
        alphas.append(alpha)
    if alphas != sorted(alphas) or len(set(alphas)) != len(alphas):
        raise ValueError("rows must be strictly increasing in alpha")


def _interior_result_to_row(result: InteriorPBoxAlphaResult) -> dict[str, object]:
    return {
        "alpha": result.alpha,
        "ci_lower_lower": result.lower.ci_lower,
        "ci_lower_upper": result.lower.ci_upper,
        "ci_upper_lower": result.upper.ci_lower,
        "ci_upper_upper": result.upper.ci_upper,
        "p_lower": result.lower.probability,
        "p_upper": result.upper.probability,
        "rho_at_lower_probability": result.rho_at_lower_probability,
        "rho_at_upper_probability": result.rho_at_upper_probability,
        "rho_grid": list(result.rho_grid),
        "rho_lower": result.rho_lower,
        "rho_upper": result.rho_upper,
        "sample_count": result.lower.sample_count,
    }


def _validate_interior_report_row(row: Mapping[str, object], *, index: int) -> float:
    required = {
        "alpha",
        "ci_lower_lower",
        "ci_lower_upper",
        "ci_upper_lower",
        "ci_upper_upper",
        "p_lower",
        "p_upper",
        "rho_at_lower_probability",
        "rho_at_upper_probability",
        "rho_grid",
        "rho_lower",
        "rho_upper",
        "sample_count",
    }
    missing = sorted(required.difference(row))
    if missing:
        raise ValueError(f"rows[{index}] missing fields: {missing}")
    alpha = _finite_unit(row["alpha"], name=f"rows[{index}].alpha")
    p_lower = _finite_unit(row["p_lower"], name=f"rows[{index}].p_lower")
    p_upper = _finite_unit(row["p_upper"], name=f"rows[{index}].p_upper")
    if p_lower > p_upper:
        raise ValueError(f"rows[{index}] p_lower must not exceed p_upper")
    ci_lower_lower = _finite_unit(
        row["ci_lower_lower"], name=f"rows[{index}].ci_lower_lower"
    )
    ci_lower_upper = _finite_unit(
        row["ci_lower_upper"], name=f"rows[{index}].ci_lower_upper"
    )
    ci_upper_lower = _finite_unit(
        row["ci_upper_lower"], name=f"rows[{index}].ci_upper_lower"
    )
    ci_upper_upper = _finite_unit(
        row["ci_upper_upper"], name=f"rows[{index}].ci_upper_upper"
    )
    if ci_lower_lower > ci_lower_upper or ci_upper_lower > ci_upper_upper:
        raise ValueError(f"rows[{index}] confidence intervals are inverted")
    rho_lower = _finite_number(row["rho_lower"], name=f"rows[{index}].rho_lower")
    rho_upper = _finite_number(row["rho_upper"], name=f"rows[{index}].rho_upper")
    if rho_lower > rho_upper:
        raise ValueError(f"rows[{index}] rho_lower must not exceed rho_upper")
    rho_at_lower = _finite_number(
        row["rho_at_lower_probability"],
        name=f"rows[{index}].rho_at_lower_probability",
    )
    rho_at_upper = _finite_number(
        row["rho_at_upper_probability"],
        name=f"rows[{index}].rho_at_upper_probability",
    )
    if not rho_lower <= rho_at_lower <= rho_upper:
        raise ValueError(f"rows[{index}] rho_at_lower_probability is outside rho cut")
    if not rho_lower <= rho_at_upper <= rho_upper:
        raise ValueError(f"rows[{index}] rho_at_upper_probability is outside rho cut")
    sample_count = row["sample_count"]
    if isinstance(sample_count, bool) or not isinstance(sample_count, int):
        raise TypeError(f"rows[{index}].sample_count must be an integer")
    if sample_count <= 0:
        raise ValueError(f"rows[{index}].sample_count must be positive")
    rho_grid = row["rho_grid"]
    if not isinstance(rho_grid, Sequence) or isinstance(rho_grid, (str, bytes)):
        raise TypeError(f"rows[{index}].rho_grid must be a sequence")
    if not rho_grid:
        raise ValueError(f"rows[{index}].rho_grid must not be empty")
    for grid_index, rho in enumerate(rho_grid):
        numeric_rho = _finite_number(
            rho,
            name=f"rows[{index}].rho_grid[{grid_index}]",
        )
        if not rho_lower <= numeric_rho <= rho_upper:
            raise ValueError(f"rows[{index}].rho_grid values must lie inside rho cut")
    return alpha


def _finite_unit(value: object, *, name: str) -> float:
    numeric = _finite_number(value, name=name)
    if not 0.0 <= numeric <= 1.0:
        raise ValueError(f"{name} must be in [0, 1]")
    return numeric


def _finite_number(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


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
