from __future__ import annotations

import pytest

from src.fuzzy import TrapezoidalFuzzyNumber
from src.pbox import (
    ModelErrorWidening,
    PBoxAlphaResult,
    ProbabilityEstimate,
    apply_model_error_widening,
    assert_nested,
    estimate_vertex_pbox,
)


def _threshold_evaluator(rho: float, seed: int) -> bool:
    sample_value = seed % 100
    threshold = round(80 - 40 * rho)
    return sample_value < threshold


def test_vertex_pbox_matches_hand_counted_endpoint_probabilities() -> None:
    fuzzy = TrapezoidalFuzzyNumber(0.0, 0.25, 0.75, 1.0)

    pbox = estimate_vertex_pbox(
        fuzzy_number=fuzzy,
        alpha_grid=[0.0, 1.0],
        sample_count=40,
        root_seed=7,
        evaluator=_threshold_evaluator,
    )

    calls = _recording_calls(fuzzy, [0.0], 40, 7)
    seeds = [seed for _rho, seed in calls[:40]]
    expected_lower = sum(_threshold_evaluator(1.0, seed) for seed in seeds) / 40
    expected_upper = sum(_threshold_evaluator(0.0, seed) for seed in seeds) / 40

    assert pbox[0.0].rho_lower == 0.0
    assert pbox[0.0].rho_upper == 1.0
    assert pbox[0.0].lower.probability == expected_lower
    assert pbox[0.0].upper.probability == expected_upper
    assert pbox[1.0].rho_lower == 0.25
    assert pbox[1.0].rho_upper == 0.75


def test_vertex_pbox_reuses_common_random_numbers_across_endpoints_and_alpha() -> None:
    fuzzy = TrapezoidalFuzzyNumber(0.0, 0.25, 0.75, 1.0)
    calls = _recording_calls(fuzzy, [0.0, 0.5, 1.0], 12, 123)

    by_rho: dict[float, list[int]] = {}
    for rho, seed in calls:
        by_rho.setdefault(rho, []).append(seed)

    seed_sequences = list(by_rho.values())
    assert len(seed_sequences) == 6
    assert all(seeds == seed_sequences[0] for seeds in seed_sequences)


def test_vertex_pbox_is_deterministic_for_same_root_seed() -> None:
    fuzzy = TrapezoidalFuzzyNumber(0.0, 0.2, 0.8, 1.0)

    first = estimate_vertex_pbox(
        fuzzy_number=fuzzy,
        alpha_grid=[0.0, 0.5, 1.0],
        sample_count=50,
        root_seed=99,
        evaluator=_threshold_evaluator,
    )
    second = estimate_vertex_pbox(
        fuzzy_number=fuzzy,
        alpha_grid=[0.0, 0.5, 1.0],
        sample_count=50,
        root_seed=99,
        evaluator=_threshold_evaluator,
    )

    assert first == second


def test_vertex_pbox_satisfies_bound_order_and_nestedness() -> None:
    fuzzy = TrapezoidalFuzzyNumber(0.0, 0.25, 0.75, 1.0)

    pbox = estimate_vertex_pbox(
        fuzzy_number=fuzzy,
        alpha_grid=[0.0, 0.5, 1.0],
        sample_count=100,
        root_seed=1,
        evaluator=_threshold_evaluator,
    )

    for result in pbox.values():
        assert result.lower.probability <= result.upper.probability

    assert pbox[0.0].lower.probability <= pbox[0.5].lower.probability
    assert pbox[0.5].lower.probability <= pbox[1.0].lower.probability
    assert pbox[1.0].upper.probability <= pbox[0.5].upper.probability
    assert pbox[0.5].upper.probability <= pbox[0.0].upper.probability


def test_probability_estimate_rejects_invalid_ci_order() -> None:
    with pytest.raises(ValueError, match="ci_lower <= probability <= ci_upper"):
        ProbabilityEstimate(
            probability=0.4,
            ci_lower=0.5,
            ci_upper=0.6,
            successes=4,
            sample_count=10,
        )


def test_nestedness_violation_is_reported() -> None:
    pbox = {
        0.0: PBoxAlphaResult(
            alpha=0.0,
            rho_lower=0.0,
            rho_upper=1.0,
            lower=ProbabilityEstimate(0.3, 0.2, 0.4, 3, 10),
            upper=ProbabilityEstimate(0.7, 0.6, 0.8, 7, 10),
        ),
        0.5: PBoxAlphaResult(
            alpha=0.5,
            rho_lower=0.25,
            rho_upper=0.75,
            lower=ProbabilityEstimate(0.2, 0.1, 0.3, 2, 10),
            upper=ProbabilityEstimate(0.8, 0.7, 0.9, 8, 10),
        ),
    }

    with pytest.raises(ValueError, match="nestedness violation"):
        assert_nested(pbox)


def test_model_error_widening_expands_synthetic_pbox_bounds() -> None:
    pbox = {
        0.0: PBoxAlphaResult(
            alpha=0.0,
            rho_lower=0.0,
            rho_upper=1.0,
            lower=ProbabilityEstimate(0.30, 0.20, 0.40, 3, 10),
            upper=ProbabilityEstimate(0.70, 0.60, 0.80, 7, 10),
        ),
        1.0: PBoxAlphaResult(
            alpha=1.0,
            rho_lower=0.25,
            rho_upper=0.75,
            lower=ProbabilityEstimate(0.40, 0.30, 0.50, 4, 10),
            upper=ProbabilityEstimate(0.60, 0.50, 0.70, 6, 10),
        ),
    }

    widened = apply_model_error_widening(
        pbox,
        ModelErrorWidening.from_config(
            {
                "lower_probability_margin": 0.05,
                "upper_probability_margin": 0.10,
            }
        ),
    )

    assert widened[0.0].lower.probability == pytest.approx(0.25)
    assert widened[0.0].lower.ci_lower == pytest.approx(0.15)
    assert widened[0.0].upper.probability == pytest.approx(0.80)
    assert widened[0.0].upper.ci_upper == pytest.approx(0.90)
    assert widened[1.0].lower.probability == pytest.approx(0.35)
    assert widened[1.0].upper.probability == pytest.approx(0.70)
    assert pbox[0.0].lower.probability == pytest.approx(0.30)


def test_model_error_widening_clips_to_probability_range() -> None:
    pbox = {
        0.0: PBoxAlphaResult(
            alpha=0.0,
            rho_lower=0.0,
            rho_upper=1.0,
            lower=ProbabilityEstimate(0.03, 0.01, 0.05, 1, 10),
            upper=ProbabilityEstimate(0.97, 0.95, 0.99, 9, 10),
        )
    }

    widened = apply_model_error_widening(
        pbox,
        ModelErrorWidening(
            lower_probability_margin=0.10,
            upper_probability_margin=0.10,
        ),
    )

    assert widened[0.0].lower.probability == 0.0
    assert widened[0.0].lower.ci_lower == 0.0
    assert widened[0.0].upper.probability == 1.0
    assert widened[0.0].upper.ci_upper == 1.0


def test_model_error_widening_requires_explicit_nonnegative_config() -> None:
    with pytest.raises(ValueError, match="missing model-error widening keys"):
        ModelErrorWidening.from_config({"lower_probability_margin": 0.05})

    with pytest.raises(ValueError, match="upper_probability_margin must be"):
        ModelErrorWidening(
            lower_probability_margin=0.0,
            upper_probability_margin=-0.01,
        )


def _recording_calls(
    fuzzy: TrapezoidalFuzzyNumber,
    alpha_grid: list[float],
    sample_count: int,
    root_seed: int,
) -> list[tuple[float, int]]:
    calls: list[tuple[float, int]] = []

    def evaluator(rho: float, seed: int) -> bool:
        calls.append((rho, seed))
        return _threshold_evaluator(rho, seed)

    estimate_vertex_pbox(
        fuzzy_number=fuzzy,
        alpha_grid=alpha_grid,
        sample_count=sample_count,
        root_seed=root_seed,
        evaluator=evaluator,
    )
    return calls
