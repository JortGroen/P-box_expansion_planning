from __future__ import annotations

import pytest

from src.fuzzy import TrapezoidalFuzzyNumber
from src.pbox import (
    PBoxAlphaResult,
    ProbabilityEstimate,
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
