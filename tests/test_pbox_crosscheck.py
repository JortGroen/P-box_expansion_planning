from __future__ import annotations

from pathlib import Path
from statistics import NormalDist

import pytest

from src.fuzzy import TrapezoidalFuzzyNumber
from src.pbox import VertexUseMode, estimate_vertex_pbox
from src.rng import sample_seed


def _gaussian_tail_probability(
    *,
    rho: float,
    mu_0: float,
    beta: float,
    sigma: float,
    threshold: float,
) -> float:
    z_score = (threshold - mu_0 + beta * rho) / sigma
    return 1.0 - NormalDist().cdf(z_score)


def test_gaussian_crosscheck_closed_form_is_monotone_and_endpoint_bounded() -> None:
    fuzzy = TrapezoidalFuzzyNumber(0.0, 0.25, 0.75, 1.0)
    alpha_grid = [0.0, 0.5, 1.0]
    params = {"mu_0": 1.0, "beta": 0.4, "sigma": 0.2, "threshold": 1.1}

    intervals: list[tuple[float, float]] = []
    for alpha in alpha_grid:
        cut = fuzzy.alpha_cut(alpha)
        lower = _gaussian_tail_probability(rho=cut.upper, **params)
        upper = _gaussian_tail_probability(rho=cut.lower, **params)
        intervals.append((lower, upper))

        assert lower <= upper
        assert lower == pytest.approx(
            1.0
            - NormalDist().cdf(
                (params["threshold"] - params["mu_0"] + params["beta"] * cut.upper)
                / params["sigma"]
            )
        )

    assert intervals[0][0] <= intervals[1][0] <= intervals[2][0]
    assert intervals[2][1] <= intervals[1][1] <= intervals[0][1]


def test_gaussian_crosscheck_known_synthetic_tail_values_are_stable() -> None:
    params = {"mu_0": 1.0, "beta": 0.4, "sigma": 0.2, "threshold": 1.1}

    assert _gaussian_tail_probability(rho=0.0, **params) == pytest.approx(
        0.3085375387259869
    )
    assert _gaussian_tail_probability(rho=1.0, **params) == pytest.approx(
        0.006209665325776159
    )


def test_gaussian_crosscheck_exercises_vertex_pbox_against_closed_form() -> None:
    fuzzy = TrapezoidalFuzzyNumber(0.0, 0.25, 0.75, 1.0)
    alpha_grid = [0.0, 0.5, 1.0]
    sample_count = 4096
    root_seed = 20260721
    params = {"mu_0": 1.0, "beta": 0.4, "sigma": 0.2, "threshold": 1.1}
    seed_to_index = {
        sample_seed(root_seed, sample_index): sample_index
        for sample_index in range(sample_count)
    }
    normal = NormalDist()

    def evaluator(rho: float, seed: int) -> bool:
        sample_index = seed_to_index[seed]
        quantile = (sample_index + 0.5) / sample_count
        z_value = normal.inv_cdf(quantile)
        loading = params["mu_0"] - params["beta"] * rho + params["sigma"] * z_value
        return loading > params["threshold"]

    pbox = estimate_vertex_pbox(
        fuzzy_number=fuzzy,
        alpha_grid=alpha_grid,
        sample_count=sample_count,
        root_seed=root_seed,
        evaluator=evaluator,
        use_mode=VertexUseMode.PRE_G3_SYNTHETIC,
    )

    for alpha, result in pbox.items():
        expected_lower = _gaussian_tail_probability(
            rho=fuzzy.alpha_cut(alpha).upper,
            **params,
        )
        expected_upper = _gaussian_tail_probability(
            rho=fuzzy.alpha_cut(alpha).lower,
            **params,
        )
        assert abs(result.lower.probability - expected_lower) < 0.01
        assert abs(result.upper.probability - expected_upper) < 0.01
        assert result.lower.probability <= result.upper.probability


def test_crosscheck_report_records_scaffold_only_guardrails() -> None:
    report = Path("reports/crosscheck.md").read_text(encoding="utf-8")

    required_phrases = [
        "scaffold-only plan",
        "does not run integrated net load",
        "P(E_toy | rho)",
        "1 - Phi",
        "absolute error below 0.01",
        "Baudrit-style hybrid propagation",
        "executable synthetic scaffold",
        "no scalar defuzzified probability",
        "G3 remains pending",
        "Q-5 remains open",
    ]
    for phrase in required_phrases:
        assert phrase in report
