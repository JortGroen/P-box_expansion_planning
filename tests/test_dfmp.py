from __future__ import annotations

from itertools import combinations

import pytest

from src.dfmp import probability_to_possibility


def test_dfmp_matches_dubois_et_al_2004_example_4_1() -> None:
    """Reproduce the primary source's continuous worked example.

    Dubois et al. (2004), Reliable Computing 10(4), Example 4.1, use the
    density with breakpoints (-2, 0), (-1.5, 0.3), (0, 0.4), (2, 0) and report
    the maximally specific transform value pi(-1.5) = 0.3. At x = -1.5 the equal
    density point on the right shoulder is 0.5, so the DFMP grade is the
    probability in the two tails [-2, -1.5] and [0.5, 2].
    """

    target_density = 0.3
    right_equal_density_x = _linear_x_at_y(
        x0=0.0,
        y0=0.4,
        x1=2.0,
        y1=0.0,
        y=target_density,
    )
    left_tail_mass = _triangle_area(base=(-1.5 - -2.0), height=target_density)
    right_tail_mass = _triangle_area(
        base=(2.0 - right_equal_density_x),
        height=target_density,
    )
    higher_density_mass = 1.0 - left_tail_mass - right_tail_mass

    assert right_equal_density_x == pytest.approx(0.5)
    assert left_tail_mass == pytest.approx(0.075)
    assert right_tail_mass == pytest.approx(0.225)

    result = probability_to_possibility(
        [left_tail_mass, higher_density_mass, right_tail_mass],
        states=["left_tail_at_or_below_0.3", "above_0.3", "right_tail_at_or_below_0.3"],
        scores=[target_density, 0.4, target_density],
    )

    assert result.possibilities == pytest.approx((0.3, 1.0, 0.3))


def test_dfmp_transform_matches_hand_computed_finite_case() -> None:
    result = probability_to_possibility(
        [0.5, 0.3, 0.2],
        states=["mode", "middle", "tail"],
    )

    assert result.states == ("mode", "middle", "tail")
    assert result.probabilities == pytest.approx((0.5, 0.3, 0.2))
    assert result.scores == pytest.approx((0.5, 0.3, 0.2))
    assert result.possibilities == pytest.approx((1.0, 0.5, 0.2))
    assert result.as_mapping() == pytest.approx(
        {"mode": 1.0, "middle": 0.5, "tail": 0.2}
    )


def test_dfmp_transform_is_normalized_and_probability_dominated() -> None:
    probabilities = [0.4, 0.35, 0.15, 0.10]
    result = probability_to_possibility(probabilities)

    assert max(result.possibilities) == 1.0
    assert all(0.0 <= possibility <= 1.0 for possibility in result.possibilities)

    indices = range(len(probabilities))
    for size in range(1, len(probabilities) + 1):
        for event in combinations(indices, size):
            event_probability = sum(result.probabilities[index] for index in event)
            event_possibility = max(result.possibilities[index] for index in event)
            assert event_probability <= event_possibility + 1e-12


def test_dfmp_transform_normalizes_rounding_sensitive_valid_pmf() -> None:
    result = probability_to_possibility(
        [0.20487287959367187, 0.7951271204063283]
    )

    assert max(result.possibilities) == 1.0
    assert result.possibilities == pytest.approx((0.20487287959367184, 1.0))


def test_dfmp_transform_orders_more_probable_states_as_more_possible() -> None:
    result = probability_to_possibility([0.1, 0.6, 0.3])

    assert result.possibilities[1] > result.possibilities[2]
    assert result.possibilities[2] > result.possibilities[0]


def test_dfmp_transform_assigns_equal_possibility_to_tied_probabilities() -> None:
    first = probability_to_possibility([0.4, 0.3, 0.3])
    second = probability_to_possibility([0.3, 0.4, 0.3])

    assert first.possibilities == pytest.approx((1.0, 0.6, 0.6))
    assert second.possibilities == pytest.approx((0.6, 1.0, 0.6))


def test_score_ties_use_absolute_tolerance_for_large_magnitude_scores() -> None:
    result = probability_to_possibility(
        [0.2, 0.3, 0.5],
        scores=[1_000_000_000_000.0, 1_000_000_000_000.25, 1_000_000_000_002.0],
        tolerance=0.5,
    )

    assert result.scores == pytest.approx(
        (1_000_000_000_000.0, 1_000_000_000_000.0, 1_000_000_000_002.0)
    )
    assert result.possibilities == pytest.approx((0.5, 0.5, 1.0))


def test_score_tie_grouping_does_not_collapse_near_tie_chains() -> None:
    result = probability_to_possibility(
        [0.2, 0.3, 0.5],
        scores=[0.0, 0.75, 1.5],
        tolerance=1.0,
    )

    assert result.scores == pytest.approx((0.0, 0.0, 1.5))
    assert result.possibilities == pytest.approx((0.5, 0.5, 1.0))


def test_dfmp_transform_accepts_distinct_probability_weights_and_scores() -> None:
    result = probability_to_possibility(
        [0.2, 0.5, 0.3],
        states=["low_rank_heavy", "high_rank", "low_rank_light"],
        scores=[0.1, 0.9, 0.1],
    )

    assert result.possibilities == pytest.approx((0.5, 1.0, 0.5))


def test_dfmp_transform_handles_boundary_distributions() -> None:
    degenerate = probability_to_possibility([1.0, 0.0, 0.0])
    uniform = probability_to_possibility([0.25, 0.25, 0.25, 0.25])

    assert degenerate.possibilities == pytest.approx((1.0, 0.0, 0.0))
    assert uniform.possibilities == pytest.approx((1.0, 1.0, 1.0, 1.0))


@pytest.mark.parametrize(
    ("probabilities", "match"),
    [
        ([], "must not be empty"),
        ([0.2, 0.2], "sum to one"),
        ([0.5, -0.1, 0.6], "non-negative"),
        ([0.5, float("nan"), 0.5], "finite"),
        ([0.5, float("inf"), 0.5], "finite"),
    ],
)
def test_dfmp_transform_rejects_invalid_probabilities(
    probabilities: list[float],
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        probability_to_possibility(probabilities)


def test_dfmp_transform_rejects_invalid_metadata_and_tolerance() -> None:
    with pytest.raises(ValueError, match="states and probabilities"):
        probability_to_possibility([0.5, 0.5], states=["only-one"])

    with pytest.raises(ValueError, match="scores and probabilities"):
        probability_to_possibility([0.5, 0.5], scores=[1.0])

    with pytest.raises(ValueError, match="scores must be finite"):
        probability_to_possibility([0.5, 0.5], scores=[1.0, float("nan")])

    with pytest.raises(ValueError, match="tolerance"):
        probability_to_possibility([0.5, 0.5], tolerance=-1e-12)

    with pytest.raises(ValueError, match="tolerance"):
        probability_to_possibility([0.5, 0.5], tolerance=float("inf"))


def test_dfmp_transform_is_deterministic() -> None:
    first = probability_to_possibility([0.55, 0.25, 0.15, 0.05])
    second = probability_to_possibility([0.55, 0.25, 0.15, 0.05])

    assert first == second


def _linear_x_at_y(*, x0: float, y0: float, x1: float, y1: float, y: float) -> float:
    slope = (y1 - y0) / (x1 - x0)
    return x0 + (y - y0) / slope


def _triangle_area(*, base: float, height: float) -> float:
    return 0.5 * base * height
