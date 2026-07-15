from __future__ import annotations

import pytest

from src.fuzzy import (
    AlphaCut,
    PiecewiseLinearFuzzyNumber,
    TrapezoidalFuzzyNumber,
    TriangularFuzzyNumber,
    alpha_cuts,
)


def test_trapezoid_alpha_cuts_match_hand_values() -> None:
    fuzzy = TrapezoidalFuzzyNumber(0.0, 2.0, 4.0, 10.0)

    assert fuzzy.alpha_cut(0.0) == AlphaCut(alpha=0.0, lower=0.0, upper=10.0)
    assert fuzzy.alpha_cut(0.5) == AlphaCut(alpha=0.5, lower=1.0, upper=7.0)
    assert fuzzy.alpha_cut(1.0) == AlphaCut(alpha=1.0, lower=2.0, upper=4.0)


def test_trapezoid_membership_matches_linear_shoulders_and_core() -> None:
    fuzzy = TrapezoidalFuzzyNumber(0.0, 2.0, 4.0, 10.0)

    assert fuzzy.membership(-1.0) == 0.0
    assert fuzzy.membership(1.0) == 0.5
    assert fuzzy.membership(3.0) == 1.0
    assert fuzzy.membership(7.0) == 0.5
    assert fuzzy.membership(11.0) == 0.0


def test_triangle_is_zero_width_core_trapezoid() -> None:
    fuzzy = TriangularFuzzyNumber(0.0, 4.0, 10.0)

    assert fuzzy.alpha_cut(0.25) == AlphaCut(alpha=0.25, lower=1.0, upper=8.5)
    assert fuzzy.alpha_cut(1.0) == AlphaCut(alpha=1.0, lower=4.0, upper=4.0)
    assert fuzzy.membership(2.0) == 0.5
    assert fuzzy.membership(7.0) == 0.5


def test_piecewise_linear_alpha_cuts_interpolate_each_shoulder() -> None:
    fuzzy = PiecewiseLinearFuzzyNumber(
        left=((0.0, 0.0), (1.0, 0.25), (3.0, 1.0)),
        right=((5.0, 1.0), (7.0, 0.5), (11.0, 0.0)),
    )

    assert fuzzy.alpha_cut(0.25) == AlphaCut(alpha=0.25, lower=1.0, upper=9.0)
    mid_cut = fuzzy.alpha_cut(0.5)
    assert mid_cut.alpha == 0.5
    assert mid_cut.lower == pytest.approx(1.6666666666666665)
    assert mid_cut.upper == 7.0
    assert fuzzy.alpha_cut(1.0) == AlphaCut(alpha=1.0, lower=3.0, upper=5.0)


def test_piecewise_linear_alpha_cut_includes_shoulder_plateaus() -> None:
    fuzzy = PiecewiseLinearFuzzyNumber(
        left=((0.0, 0.0), (1.0, 0.5), (2.0, 0.5), (3.0, 1.0)),
        right=((4.0, 1.0), (5.0, 0.5), (6.0, 0.5), (7.0, 0.0)),
    )

    assert fuzzy.alpha_cut(0.5) == AlphaCut(alpha=0.5, lower=1.0, upper=6.0)


def test_piecewise_linear_membership_interpolates_by_value() -> None:
    fuzzy = PiecewiseLinearFuzzyNumber(
        left=((0.0, 0.0), (2.0, 0.5), (4.0, 1.0)),
        right=((6.0, 1.0), (8.0, 0.25), (10.0, 0.0)),
    )

    assert fuzzy.membership(1.0) == 0.25
    assert fuzzy.membership(5.0) == 1.0
    assert fuzzy.membership(7.0) == 0.625
    assert fuzzy.membership(11.0) == 0.0


def test_alpha_cuts_helper_preserves_grid_order() -> None:
    fuzzy = TrapezoidalFuzzyNumber(0.0, 1.0, 2.0, 4.0)

    cuts = alpha_cuts(fuzzy, [0.0, 0.5, 1.0])

    assert cuts == (
        AlphaCut(alpha=0.0, lower=0.0, upper=4.0),
        AlphaCut(alpha=0.5, lower=0.5, upper=3.0),
        AlphaCut(alpha=1.0, lower=1.0, upper=2.0),
    )


@pytest.mark.parametrize(
    "args",
    [
        (2.0, 1.0, 3.0, 4.0),
        (0.0, 3.0, 2.0, 4.0),
        (0.0, 1.0, 5.0, 4.0),
    ],
)
def test_trapezoid_rejects_invalid_endpoint_order(
    args: tuple[float, float, float, float],
) -> None:
    with pytest.raises(ValueError):
        TrapezoidalFuzzyNumber(*args)


def test_alpha_level_must_be_unit_interval() -> None:
    fuzzy = TriangularFuzzyNumber(0.0, 1.0, 2.0)

    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        fuzzy.alpha_cut(1.5)


def test_piecewise_linear_rejects_nonmonotone_profiles() -> None:
    with pytest.raises(ValueError, match="nondecreasing"):
        PiecewiseLinearFuzzyNumber(
            left=((0.0, 0.0), (2.0, 0.4), (1.0, 1.0)),
            right=((3.0, 1.0), (4.0, 0.0)),
        )

    with pytest.raises(ValueError, match="nonincreasing"):
        PiecewiseLinearFuzzyNumber(
            left=((0.0, 0.0), (1.0, 1.0)),
            right=((2.0, 1.0), (3.0, 0.5), (4.0, 0.75), (5.0, 0.0)),
        )
