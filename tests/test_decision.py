from __future__ import annotations

import math

import pytest

from src.decision import alpha_star
from src.pbox import PBoxAlphaResult, ProbabilityEstimate, VertexUseMode


def test_alpha_star_returns_lowest_alpha_when_always_satisfied() -> None:
    pbox = _pbox_family(
        [
            (1.0, 0.005),
            (0.0, 0.008),
            (0.5, 0.006),
        ]
    )

    assert alpha_star(pbox, p_crit=0.01) == 0.0


def test_alpha_star_returns_first_crossing_on_ordered_grid() -> None:
    pbox = _pbox_family(
        [
            (0.0, 0.03),
            (0.5, 0.012),
            (1.0, 0.009),
        ]
    )

    assert alpha_star(pbox, p_crit=0.01) == 1.0


def test_alpha_star_accepts_exact_boundary() -> None:
    pbox = _pbox_family(
        [
            (0.0, 0.025),
            (0.5, 0.010),
            (1.0, 0.004),
        ]
    )

    assert alpha_star(pbox, p_crit=0.01) == 0.5


def test_alpha_star_returns_infinity_when_never_satisfied() -> None:
    pbox = _pbox_family(
        [
            (0.0, 0.03),
            (0.5, 0.02),
            (1.0, 0.011),
        ]
    )

    assert math.isinf(alpha_star(pbox, p_crit=0.01))


def test_alpha_star_rejects_empty_family_and_invalid_pcrit() -> None:
    with pytest.raises(ValueError, match="at least one alpha"):
        alpha_star({}, p_crit=0.01)

    pbox = _pbox_family([(0.0, 0.01)])
    for p_crit in (-0.1, 1.1, math.inf, math.nan):
        with pytest.raises(ValueError, match="p_crit"):
            alpha_star(pbox, p_crit=p_crit)


def _pbox_family(rows: list[tuple[float, float]]) -> dict[float, PBoxAlphaResult]:
    return {
        alpha: PBoxAlphaResult(
            use_mode=VertexUseMode.PRE_G3_SYNTHETIC,
            alpha=alpha,
            rho_lower=alpha,
            rho_upper=1.0,
            lower=_estimate(max(0.0, upper_probability - 0.001)),
            upper=_estimate(upper_probability),
        )
        for alpha, upper_probability in rows
    }


def _estimate(probability: float) -> ProbabilityEstimate:
    successes = round(probability * 1000)
    return ProbabilityEstimate(
        probability=probability,
        ci_lower=max(0.0, probability - 0.001),
        ci_upper=min(1.0, probability + 0.001),
        successes=successes,
        sample_count=1000,
    )
