from __future__ import annotations

import math

import pytest

from src.decision import (
    RhoProbabilityPoint,
    RhoStarAlphaResult,
    alpha_star,
    rho_star_from_probability_curves,
    rho_star_membership,
)
from src.fuzzy import TrapezoidalFuzzyNumber, TriangularFuzzyNumber
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


def test_rho_star_returns_alpha_indexed_bounds_from_synthetic_curves() -> None:
    curves = {
        0.5: [
            RhoProbabilityPoint(0.0, lower_probability=0.020, upper_probability=0.030),
            RhoProbabilityPoint(0.5, lower_probability=0.010, upper_probability=0.020),
            RhoProbabilityPoint(1.0, lower_probability=0.004, upper_probability=0.008),
        ],
        0.0: [
            RhoProbabilityPoint(0.0, lower_probability=0.030, upper_probability=0.050),
            RhoProbabilityPoint(1.0, lower_probability=0.005, upper_probability=0.025),
        ],
    }

    result = rho_star_from_probability_curves(curves, p_crit=0.01)

    assert list(result) == [0.0, 0.5]
    assert result[0.0].rho_lower == pytest.approx(0.8)
    assert math.isinf(result[0.0].rho_upper)
    assert result[0.5].rho_lower == pytest.approx(0.5)
    assert result[0.5].rho_upper == pytest.approx(11 / 12)


def test_rho_star_handles_first_point_exact_boundary_and_never_satisfied() -> None:
    curves = {
        0.0: [
            RhoProbabilityPoint(0.0, lower_probability=0.010, upper_probability=0.010),
            RhoProbabilityPoint(1.0, lower_probability=0.003, upper_probability=0.003),
        ],
        0.5: [
            RhoProbabilityPoint(0.0, lower_probability=0.012, upper_probability=0.014),
            RhoProbabilityPoint(0.5, lower_probability=0.010, upper_probability=0.012),
            RhoProbabilityPoint(1.0, lower_probability=0.006, upper_probability=0.009),
        ],
        1.0: [
            RhoProbabilityPoint(0.0, lower_probability=0.040, upper_probability=0.050),
            RhoProbabilityPoint(1.0, lower_probability=0.020, upper_probability=0.030),
        ],
    }

    result = rho_star_from_probability_curves(curves, p_crit=0.01)

    assert result[0.0].rho_lower == 0.0
    assert result[0.0].rho_upper == 0.0
    assert result[0.5].rho_lower == 0.5
    assert result[0.5].rho_upper == pytest.approx(5 / 6)
    assert math.isinf(result[1.0].rho_lower)
    assert math.isinf(result[1.0].rho_upper)


def test_rho_star_rejects_invalid_inputs_and_nonmonotone_curves() -> None:
    with pytest.raises(ValueError, match="at least one alpha"):
        rho_star_from_probability_curves({}, p_crit=0.01)

    valid_curve = {
        0.0: [RhoProbabilityPoint(0.0, 0.02, 0.03)],
    }
    for p_crit in (-0.1, 1.1, math.inf, math.nan):
        with pytest.raises(ValueError, match="p_crit"):
            rho_star_from_probability_curves(valid_curve, p_crit=p_crit)

    with pytest.raises(ValueError, match="rho"):
        RhoProbabilityPoint(-0.1, 0.01, 0.02)
    with pytest.raises(ValueError, match="lower_probability"):
        RhoProbabilityPoint(0.0, math.nan, 0.02)
    with pytest.raises(ValueError, match="lower_probability <= upper_probability"):
        RhoProbabilityPoint(0.0, 0.03, 0.02)

    with pytest.raises(ValueError, match="unique"):
        rho_star_from_probability_curves(
            {
                0.0: [
                    RhoProbabilityPoint(0.0, 0.02, 0.03),
                    RhoProbabilityPoint(0.0, 0.01, 0.02),
                ]
            },
            p_crit=0.01,
        )

    with pytest.raises(ValueError, match="lower probability curve"):
        rho_star_from_probability_curves(
            {
                0.0: [
                    RhoProbabilityPoint(0.0, 0.02, 0.03),
                    RhoProbabilityPoint(1.0, 0.025, 0.026),
                ]
            },
            p_crit=0.01,
        )


def test_rho_star_membership_preserves_bounds_for_finite_targets() -> None:
    rho_star = {
        0.0: RhoStarAlphaResult(
            alpha=0.0,
            p_crit=0.01,
            rho_lower=0.25,
            rho_upper=0.75,
        )
    }
    fuzzy = TrapezoidalFuzzyNumber(
        support_left=0.0,
        core_left=0.4,
        core_right=0.6,
        support_right=1.0,
    )

    membership = rho_star_membership(rho_star, fuzzy)

    assert membership[0.0].mu_lower == pytest.approx(0.625)
    assert membership[0.0].mu_upper == 1.0


def test_rho_star_membership_rejects_never_satisfied_target() -> None:
    rho_star = {
        0.0: RhoStarAlphaResult(
            alpha=0.0,
            p_crit=0.01,
            rho_lower=0.8,
            rho_upper=math.inf,
        )
    }

    with pytest.raises(ValueError, match="finite rho_star"):
        rho_star_membership(rho_star, TriangularFuzzyNumber(0.0, 0.5, 1.0))


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
