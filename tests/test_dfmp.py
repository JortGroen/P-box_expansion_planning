from __future__ import annotations

from itertools import combinations

import pytest

from src.dfmp import probability_to_possibility


def test_dfmp_transform_matches_hand_computed_finite_case() -> None:
    result = probability_to_possibility(
        [0.5, 0.3, 0.2],
        states=["mode", "middle", "tail"],
    )

    assert result.states == ("mode", "middle", "tail")
    assert result.probabilities == pytest.approx((0.5, 0.3, 0.2))
    assert result.possibilities == pytest.approx((1.0, 0.5, 0.2))


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


def test_dfmp_transform_orders_more_probable_states_as_more_possible() -> None:
    result = probability_to_possibility([0.1, 0.6, 0.3])

    assert result.possibilities[1] > result.possibilities[2]
    assert result.possibilities[2] > result.possibilities[0]


def test_dfmp_transform_assigns_equal_possibility_to_tied_probabilities() -> None:
    first = probability_to_possibility([0.4, 0.3, 0.3])
    second = probability_to_possibility([0.3, 0.4, 0.3])

    assert first.possibilities == pytest.approx((1.0, 0.6, 0.6))
    assert second.possibilities == pytest.approx((0.6, 1.0, 0.6))


def test_dfmp_transform_handles_boundary_distributions() -> None:
    degenerate = probability_to_possibility([1.0, 0.0, 0.0])
    uniform = probability_to_possibility([0.25, 0.25, 0.25, 0.25])

    assert degenerate.possibilities == pytest.approx((1.0, 0.0, 0.0))
    assert uniform.possibilities == pytest.approx((1.0, 1.0, 1.0, 1.0))


@pytest.mark.parametrize(
    "probabilities, match",
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


def test_dfmp_transform_rejects_misaligned_states_and_negative_tolerance() -> None:
    with pytest.raises(ValueError, match="same length"):
        probability_to_possibility([0.5, 0.5], states=["only-one"])

    with pytest.raises(ValueError, match="tolerance"):
        probability_to_possibility([0.5, 0.5], tolerance=-1e-12)


def test_dfmp_transform_is_deterministic() -> None:
    first = probability_to_possibility([0.55, 0.25, 0.15, 0.05])
    second = probability_to_possibility([0.55, 0.25, 0.15, 0.05])

    assert first == second
