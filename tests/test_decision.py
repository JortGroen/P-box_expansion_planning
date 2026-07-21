from __future__ import annotations

import math

import pytest

from src.decision import (
    DeferralHorizonResult,
    DeferralYearResult,
    ProcurementTargetClassification,
    ProcurementTargetResult,
    RhoProbabilityPoint,
    RhoStarAlphaResult,
    SyntheticMonetaryInterval,
    ValueOfInformationClassification,
    ValueOfInformationInput,
    ValueOfInformationResult,
    alpha_star,
    classify_procurement_target,
    deferral_horizon_from_procurement_targets,
    rho_star_from_probability_curves,
    rho_star_membership,
    value_of_information_scaffold,
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


def test_procurement_target_classifies_alpha_indexed_synthetic_intervals() -> None:
    rho_star = {
        0.0: RhoStarAlphaResult(0.0, 0.01, rho_lower=0.20, rho_upper=0.80),
        0.25: RhoStarAlphaResult(0.25, 0.01, rho_lower=0.25, rho_upper=0.85),
        0.5: RhoStarAlphaResult(0.5, 0.01, rho_lower=0.45, rho_upper=0.55),
        0.75: RhoStarAlphaResult(0.75, 0.01, rho_lower=0.90, rho_upper=1.00),
        1.0: RhoStarAlphaResult(1.0, 0.01, rho_lower=0.8, rho_upper=math.inf),
    }
    delivery = TrapezoidalFuzzyNumber(
        support_left=0.20,
        core_left=0.40,
        core_right=0.60,
        support_right=0.90,
    )

    result = classify_procurement_target(rho_star, delivery)

    assert list(result) == [0.0, 0.25, 0.5, 0.75, 1.0]
    assert result[0.0].classification is ProcurementTargetClassification.INSIDE_ENVELOPE
    assert result[0.0].envelope_lower == pytest.approx(0.20)
    assert result[0.0].envelope_upper == pytest.approx(0.90)
    assert (
        result[0.25].classification
        is ProcurementTargetClassification.OVERLAPPING_MONITOR
    )
    assert result[0.5].classification is ProcurementTargetClassification.INSIDE_ENVELOPE
    assert result[0.5].envelope_lower == pytest.approx(0.30)
    assert result[0.5].envelope_upper == pytest.approx(0.75)
    assert result[0.75].classification is ProcurementTargetClassification.OUTSIDE_ENVELOPE
    assert result[1.0].classification is ProcurementTargetClassification.NEVER_SATISFIED


def test_procurement_target_treats_boundary_touch_as_overlap_monitor() -> None:
    rho_star = {
        0.0: RhoStarAlphaResult(0.0, 0.01, rho_lower=0.90, rho_upper=1.00),
    }
    delivery = TrapezoidalFuzzyNumber(0.20, 0.40, 0.60, 0.90)

    result = classify_procurement_target(rho_star, delivery)

    assert (
        result[0.0].classification
        is ProcurementTargetClassification.OVERLAPPING_MONITOR
    )


def test_procurement_target_rejects_empty_family_and_invalid_results() -> None:
    with pytest.raises(ValueError, match="at least one alpha"):
        classify_procurement_target({}, TrapezoidalFuzzyNumber(0.0, 0.3, 0.6, 1.0))

    with pytest.raises(TypeError, match="classification"):
        ProcurementTargetResult(
            alpha=0.0,
            rho_lower=0.2,
            rho_upper=0.4,
            envelope_lower=0.1,
            envelope_upper=0.5,
            classification="inside-envelope",  # type: ignore[arg-type]
        )

    with pytest.raises(ValueError, match="envelope_lower"):
        ProcurementTargetResult(
            alpha=0.0,
            rho_lower=0.2,
            rho_upper=0.4,
            envelope_lower=0.6,
            envelope_upper=0.5,
            classification=ProcurementTargetClassification.INSIDE_ENVELOPE,
        )


def test_deferral_horizon_reports_alpha_indexed_synthetic_year_bounds() -> None:
    yearly_targets = {
        2030: {
            0.0: _procurement_result(
                alpha=0.0,
                rho_lower=0.30,
                rho_upper=0.50,
                classification=ProcurementTargetClassification.INSIDE_ENVELOPE,
            ),
            0.5: _procurement_result(
                alpha=0.5,
                rho_lower=0.40,
                rho_upper=0.50,
                classification=ProcurementTargetClassification.INSIDE_ENVELOPE,
            ),
        },
        2033: {
            0.0: _procurement_result(
                alpha=0.0,
                rho_lower=0.55,
                rho_upper=0.85,
                classification=ProcurementTargetClassification.OVERLAPPING_MONITOR,
            ),
            0.5: _procurement_result(
                alpha=0.5,
                rho_lower=0.55,
                rho_upper=0.70,
                classification=ProcurementTargetClassification.INSIDE_ENVELOPE,
            ),
        },
        2035: {
            0.0: _procurement_result(
                alpha=0.0,
                rho_lower=0.95,
                rho_upper=1.0,
                classification=ProcurementTargetClassification.OUTSIDE_ENVELOPE,
            ),
            0.5: _procurement_result(
                alpha=0.5,
                rho_lower=0.8,
                rho_upper=math.inf,
                classification=ProcurementTargetClassification.NEVER_SATISFIED,
            ),
        },
    }

    result = deferral_horizon_from_procurement_targets(yearly_targets)

    assert list(result) == [0.0, 0.5]
    assert result[0.0].lower_year == 2030
    assert result[0.0].upper_year == 2033
    assert result[0.0].first_unmet_year == 2035
    assert result[0.0].first_never_satisfied_year is None
    assert result[0.0].monotone_in_year is True
    assert [year.year for year in result[0.0].yearly_results] == [2030, 2033, 2035]
    assert result[0.0].yearly_results[1].rho_upper == pytest.approx(0.85)

    assert result[0.5].lower_year == 2033
    assert result[0.5].upper_year == 2033
    assert result[0.5].first_unmet_year == 2035
    assert result[0.5].first_never_satisfied_year == 2035
    assert result[0.5].yearly_results[2].classification is (
        ProcurementTargetClassification.NEVER_SATISFIED
    )


def test_deferral_horizon_handles_no_safe_or_monitoring_year() -> None:
    result = deferral_horizon_from_procurement_targets(
        {
            2030: {
                0.0: _procurement_result(
                    alpha=0.0,
                    rho_lower=0.91,
                    rho_upper=1.0,
                    classification=ProcurementTargetClassification.OUTSIDE_ENVELOPE,
                )
            },
            2033: {
                0.0: _procurement_result(
                    alpha=0.0,
                    rho_lower=0.8,
                    rho_upper=math.inf,
                    classification=ProcurementTargetClassification.NEVER_SATISFIED,
                )
            },
        }
    )

    assert result[0.0].lower_year is None
    assert result[0.0].upper_year is None
    assert result[0.0].first_unmet_year == 2030
    assert result[0.0].first_never_satisfied_year == 2033


def test_deferral_horizon_flags_nonmonotone_synthetic_year_sequence() -> None:
    result = deferral_horizon_from_procurement_targets(
        {
            2030: {
                0.0: _procurement_result(
                    alpha=0.0,
                    classification=ProcurementTargetClassification.OUTSIDE_ENVELOPE,
                )
            },
            2033: {
                0.0: _procurement_result(
                    alpha=0.0,
                    classification=ProcurementTargetClassification.INSIDE_ENVELOPE,
                )
            },
        }
    )

    assert result[0.0].monotone_in_year is False
    assert result[0.0].lower_year == 2033
    assert result[0.0].upper_year == 2033


def test_deferral_horizon_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="at least one year"):
        deferral_horizon_from_procurement_targets({})

    with pytest.raises(ValueError, match="positive"):
        deferral_horizon_from_procurement_targets(
            {
                0: {
                    0.0: _procurement_result(
                        alpha=0.0,
                        classification=ProcurementTargetClassification.INSIDE_ENVELOPE,
                    )
                }
            }
        )

    with pytest.raises(ValueError, match="same alpha grid"):
        deferral_horizon_from_procurement_targets(
            {
                2030: {
                    0.0: _procurement_result(
                        alpha=0.0,
                        classification=ProcurementTargetClassification.INSIDE_ENVELOPE,
                    )
                },
                2033: {
                    0.5: _procurement_result(
                        alpha=0.5,
                        classification=ProcurementTargetClassification.INSIDE_ENVELOPE,
                    )
                },
            }
        )

    with pytest.raises(ValueError, match="mapping key"):
        deferral_horizon_from_procurement_targets(
            {
                2030: {
                    0.0: _procurement_result(
                        alpha=0.5,
                        classification=ProcurementTargetClassification.INSIDE_ENVELOPE,
                    )
                }
            }
        )

    with pytest.raises(ValueError, match="yearly_results"):
        DeferralHorizonResult(
            alpha=0.0,
            lower_year=None,
            upper_year=None,
            first_unmet_year=None,
            first_never_satisfied_year=None,
            monotone_in_year=True,
            yearly_results=(),
        )

    with pytest.raises(ValueError, match="must match result alpha"):
        DeferralHorizonResult(
            alpha=0.5,
            lower_year=2030,
            upper_year=2030,
            first_unmet_year=None,
            first_never_satisfied_year=None,
            monotone_in_year=True,
            yearly_results=(
                DeferralYearResult(
                    year=2030,
                    alpha=0.0,
                    rho_lower=0.2,
                    rho_upper=0.4,
                    envelope_lower=0.1,
                    envelope_upper=0.6,
                    classification=ProcurementTargetClassification.INSIDE_ENVELOPE,
                ),
            ),
        )


def test_value_of_information_preserves_alpha_indexed_synthetic_bounds() -> None:
    horizons = {
        0.0: _horizon_result(alpha=0.0, lower_year=2030, upper_year=2033),
        0.5: _horizon_result(alpha=0.5, lower_year=2033, upper_year=2033),
        1.0: _horizon_result(alpha=1.0, lower_year=None, upper_year=2030),
    }
    value_inputs = {
        0.0: _voi_input(
            alpha=0.0,
            width=(0.20, 0.40),
            benefit=(100.0, 160.0),
            cost=(20.0, 50.0),
        ),
        0.5: _voi_input(
            alpha=0.5,
            width=(0.10, 0.25),
            benefit=(20.0, 40.0),
            cost=(50.0, 70.0),
        ),
        1.0: _voi_input(
            alpha=1.0,
            width=(0.0, 0.10),
            benefit=(30.0, 80.0),
            cost=(60.0, 90.0),
        ),
    }

    result = value_of_information_scaffold(horizons, value_inputs)

    assert list(result) == [0.0, 0.5, 1.0]
    assert result[0.0].lower_horizon_year == 2030
    assert result[0.0].upper_horizon_year == 2033
    assert result[0.0].decision_width_lower == pytest.approx(0.20)
    assert result[0.0].decision_width_upper == pytest.approx(0.40)
    assert result[0.0].net_value_lower == pytest.approx(50.0)
    assert result[0.0].net_value_upper == pytest.approx(140.0)
    assert result[0.0].classification is ValueOfInformationClassification.NET_POSITIVE

    assert result[0.5].net_value_lower == pytest.approx(-50.0)
    assert result[0.5].net_value_upper == pytest.approx(-10.0)
    assert result[0.5].classification is ValueOfInformationClassification.NET_NEGATIVE

    assert result[1.0].net_value_lower == pytest.approx(-60.0)
    assert result[1.0].net_value_upper == pytest.approx(20.0)
    assert result[1.0].classification is ValueOfInformationClassification.INDETERMINATE
    assert result[1.0].unit == "synthetic-eur"


def test_value_of_information_marks_no_horizon_as_not_applicable() -> None:
    result = value_of_information_scaffold(
        {
            0.0: _horizon_result(
                alpha=0.0,
                lower_year=None,
                upper_year=None,
            )
        },
        {
            0.0: _voi_input(
                alpha=0.0,
                width=(0.5, 0.8),
                benefit=(100.0, 200.0),
                cost=(10.0, 20.0),
            )
        },
    )

    assert result[0.0].classification is ValueOfInformationClassification.NOT_APPLICABLE
    assert result[0.0].net_value_lower == pytest.approx(80.0)
    assert result[0.0].net_value_upper == pytest.approx(190.0)


def test_value_of_information_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="deferral_horizons"):
        value_of_information_scaffold({}, {})

    with pytest.raises(ValueError, match="same alpha grid"):
        value_of_information_scaffold(
            {0.0: _horizon_result(alpha=0.0)},
            {0.5: _voi_input(alpha=0.5)},
        )

    with pytest.raises(ValueError, match="mapping keys"):
        value_of_information_scaffold(
            {0.0: _horizon_result(alpha=0.5)},
            {0.0: _voi_input(alpha=0.0)},
        )

    with pytest.raises(ValueError, match="nonnegative"):
        SyntheticMonetaryInterval(-1.0, 2.0, "synthetic-eur")

    with pytest.raises(ValueError, match="lower"):
        SyntheticMonetaryInterval(3.0, 2.0, "synthetic-eur")

    with pytest.raises(ValueError, match="unit"):
        SyntheticMonetaryInterval(1.0, 2.0, " ")

    with pytest.raises(ValueError, match="units must match"):
        ValueOfInformationInput(
            alpha=0.0,
            decision_width_lower=0.1,
            decision_width_upper=0.2,
            deferral_benefit=SyntheticMonetaryInterval(1.0, 2.0, "a"),
            information_cost=SyntheticMonetaryInterval(1.0, 2.0, "b"),
        )

    with pytest.raises(ValueError, match="decision_width_lower"):
        _voi_input(alpha=0.0, width=(0.4, 0.2))

    with pytest.raises(TypeError, match="classification"):
        ValueOfInformationResult(
            alpha=0.0,
            lower_horizon_year=2030,
            upper_horizon_year=2033,
            decision_width_lower=0.1,
            decision_width_upper=0.2,
            deferral_benefit_lower=10.0,
            deferral_benefit_upper=20.0,
            information_cost_lower=1.0,
            information_cost_upper=2.0,
            net_value_lower=8.0,
            net_value_upper=19.0,
            unit="synthetic-eur",
            classification="net-positive",  # type: ignore[arg-type]
        )


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


def _procurement_result(
    *,
    alpha: float,
    classification: ProcurementTargetClassification,
    rho_lower: float = 0.3,
    rho_upper: float = 0.6,
    envelope_lower: float = 0.2,
    envelope_upper: float = 0.8,
) -> ProcurementTargetResult:
    return ProcurementTargetResult(
        alpha=alpha,
        rho_lower=rho_lower,
        rho_upper=rho_upper,
        envelope_lower=envelope_lower,
        envelope_upper=envelope_upper,
        classification=classification,
    )


def _horizon_result(
    *,
    alpha: float,
    lower_year: int | None = 2030,
    upper_year: int | None = 2033,
) -> DeferralHorizonResult:
    yearly_results = (
        DeferralYearResult(
            year=2030,
            alpha=alpha,
            rho_lower=0.2,
            rho_upper=0.4,
            envelope_lower=0.1,
            envelope_upper=0.6,
            classification=ProcurementTargetClassification.INSIDE_ENVELOPE,
        ),
    )
    return DeferralHorizonResult(
        alpha=alpha,
        lower_year=lower_year,
        upper_year=upper_year,
        first_unmet_year=None,
        first_never_satisfied_year=None,
        monotone_in_year=True,
        yearly_results=yearly_results,
    )


def _voi_input(
    *,
    alpha: float,
    width: tuple[float, float] = (0.1, 0.2),
    benefit: tuple[float, float] = (10.0, 20.0),
    cost: tuple[float, float] = (1.0, 2.0),
    unit: str = "synthetic-eur",
) -> ValueOfInformationInput:
    return ValueOfInformationInput(
        alpha=alpha,
        decision_width_lower=width[0],
        decision_width_upper=width[1],
        deferral_benefit=SyntheticMonetaryInterval(benefit[0], benefit[1], unit),
        information_cost=SyntheticMonetaryInterval(cost[0], cost[1], unit),
    )
