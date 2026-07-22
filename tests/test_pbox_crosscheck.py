from __future__ import annotations

from pathlib import Path

import pytest

from src.fuzzy import TrapezoidalFuzzyNumber
from src.pbox_crosscheck import (
    FiniteHybridState,
    GaussianToyParameters,
    estimate_gaussian_toy_pbox,
    finite_hybrid_bounds,
    gaussian_closed_form_bounds,
    gaussian_tail_probability,
)


def _gaussian_fixture() -> tuple[TrapezoidalFuzzyNumber, list[float], GaussianToyParameters]:
    return (
        TrapezoidalFuzzyNumber(0.0, 0.25, 0.75, 1.0),
        [0.0, 0.5, 1.0],
        GaussianToyParameters(mu_0=1.0, beta=0.4, sigma=0.2, threshold=1.1),
    )


def test_gaussian_crosscheck_closed_form_is_monotone_and_endpoint_bounded() -> None:
    fuzzy, alpha_grid, params = _gaussian_fixture()

    bounds = gaussian_closed_form_bounds(
        fuzzy_number=fuzzy,
        alpha_grid=alpha_grid,
        params=params,
    )

    assert list(bounds) == alpha_grid
    for alpha, (lower, upper) in bounds.items():
        cut = fuzzy.alpha_cut(alpha)
        assert lower <= upper
        assert lower == pytest.approx(gaussian_tail_probability(rho=cut.upper, params=params))
        assert upper == pytest.approx(gaussian_tail_probability(rho=cut.lower, params=params))

    assert bounds[0.0][0] <= bounds[0.5][0] <= bounds[1.0][0]
    assert bounds[1.0][1] <= bounds[0.5][1] <= bounds[0.0][1]


def test_gaussian_crosscheck_known_synthetic_tail_values_are_stable() -> None:
    _, _, params = _gaussian_fixture()

    assert gaussian_tail_probability(rho=0.0, params=params) == pytest.approx(
        0.3085375387259869
    )
    assert gaussian_tail_probability(rho=1.0, params=params) == pytest.approx(
        0.006209665325776159
    )


def test_gaussian_crosscheck_exercises_vertex_pbox_against_closed_form() -> None:
    fuzzy, alpha_grid, params = _gaussian_fixture()
    expected = gaussian_closed_form_bounds(
        fuzzy_number=fuzzy,
        alpha_grid=alpha_grid,
        params=params,
    )

    pbox = estimate_gaussian_toy_pbox(
        fuzzy_number=fuzzy,
        alpha_grid=alpha_grid,
        params=params,
        sample_count=4096,
        root_seed=20260721,
    )

    for alpha, result in pbox.items():
        expected_lower, expected_upper = expected[alpha]
        assert abs(result.lower.probability - expected_lower) < 0.01
        assert abs(result.upper.probability - expected_upper) < 0.01
        assert result.lower.probability <= result.upper.probability


def test_gaussian_crosscheck_replays_same_root_seed_deterministically() -> None:
    fuzzy, alpha_grid, params = _gaussian_fixture()

    first = estimate_gaussian_toy_pbox(
        fuzzy_number=fuzzy,
        alpha_grid=alpha_grid,
        params=params,
        sample_count=512,
        root_seed=20260722,
    )
    second = estimate_gaussian_toy_pbox(
        fuzzy_number=fuzzy,
        alpha_grid=alpha_grid,
        params=params,
        sample_count=512,
        root_seed=20260722,
    )

    assert first.keys() == second.keys()
    for alpha in alpha_grid:
        assert first[alpha].lower == second[alpha].lower
        assert first[alpha].upper == second[alpha].upper


def test_finite_hybrid_crosscheck_matches_hand_computed_probability_bounds() -> None:
    fuzzy = TrapezoidalFuzzyNumber(0.0, 0.2, 0.4, 0.6)
    states = [
        FiniteHybridState(value=0.2, probability=0.25),
        FiniteHybridState(value=0.7, probability=0.25),
        FiniteHybridState(value=1.05, probability=0.5),
    ]

    bounds = finite_hybrid_bounds(
        fuzzy_number=fuzzy,
        alpha_grid=[0.0, 0.5, 1.0],
        states=states,
        threshold=0.5,
    )

    assert bounds[0.0].lower_probability == pytest.approx(0.0)
    assert bounds[0.0].upper_probability == pytest.approx(0.75)
    assert bounds[0.5].lower_probability == pytest.approx(0.5)
    assert bounds[0.5].upper_probability == pytest.approx(0.75)
    assert bounds[1.0].lower_probability == pytest.approx(0.5)
    assert bounds[1.0].upper_probability == pytest.approx(0.5)
    assert bounds[0.0].lower_probability <= bounds[0.5].lower_probability <= bounds[1.0].lower_probability
    assert bounds[1.0].upper_probability <= bounds[0.5].upper_probability <= bounds[0.0].upper_probability


def test_finite_hybrid_crosscheck_keeps_alpha_indexed_bounds_only() -> None:
    fuzzy = TrapezoidalFuzzyNumber(0.0, 0.2, 0.4, 0.6)
    states = [
        FiniteHybridState(value=0.2, probability=0.25),
        FiniteHybridState(value=0.7, probability=0.25),
        FiniteHybridState(value=1.05, probability=0.5),
    ]

    bounds = finite_hybrid_bounds(
        fuzzy_number=fuzzy,
        alpha_grid=[0.0, 1.0],
        states=states,
        threshold=0.5,
    )

    assert set(bounds) == {0.0, 1.0}
    assert all(hasattr(result, "lower_probability") for result in bounds.values())
    assert all(hasattr(result, "upper_probability") for result in bounds.values())
    assert all(not hasattr(result, "defuzzified_probability") for result in bounds.values())


def test_crosscheck_helpers_reject_invalid_synthetic_inputs() -> None:
    with pytest.raises(ValueError, match="beta must be positive"):
        GaussianToyParameters(mu_0=1.0, beta=0.0, sigma=0.2, threshold=1.1)

    with pytest.raises(ValueError, match="state probabilities must sum to 1"):
        finite_hybrid_bounds(
            fuzzy_number=TrapezoidalFuzzyNumber(0.0, 0.2, 0.4, 0.6),
            alpha_grid=[0.0],
            states=[FiniteHybridState(value=1.0, probability=0.5)],
            threshold=0.5,
        )


def test_crosscheck_report_records_scaffold_only_guardrails() -> None:
    report = Path("reports/crosscheck.md").read_text(encoding="utf-8")

    required_phrases = [
        "scaffold-only plan",
        "does not run integrated net load",
        "P(E_toy | rho)",
        "1 - Phi",
        "absolute-error tolerance",
        "finite hybrid toy",
        "Baudrit-style hybrid propagation",
        "executable synthetic package",
        "no scalar defuzzified probability",
        "G3 remains pending",
        "Q-5 is resolved by G0-A3",
    ]
    for phrase in required_phrases:
        assert phrase in report
