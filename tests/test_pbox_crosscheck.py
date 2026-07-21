from __future__ import annotations

from pathlib import Path
from statistics import NormalDist

import pytest

from src.fuzzy import TrapezoidalFuzzyNumber


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


def test_crosscheck_report_records_scaffold_only_guardrails() -> None:
    report = Path("reports/crosscheck.md").read_text(encoding="utf-8")

    required_phrases = [
        "scaffold-only plan",
        "does not run integrated net load",
        "P(E_toy | rho)",
        "1 - Phi",
        "absolute error below 0.01",
        "Baudrit-style hybrid propagation",
        "no scalar defuzzified probability",
        "G3 remains pending",
        "Q-5 remains open",
    ]
    for phrase in required_phrases:
        assert phrase in report
