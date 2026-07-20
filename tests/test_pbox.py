from __future__ import annotations

import pytest

from src.fuzzy import TrapezoidalFuzzyNumber
from src.pbox import (
    PBoxAlphaResult,
    ProbabilityEstimate,
    VertexUseMode,
    assert_nested,
    estimate_vertex_pbox,
)
from src.rng import sample_seed


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
        use_mode=VertexUseMode.PRE_G3_SYNTHETIC,
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
    sample_count = 12
    root_seed = 123
    calls = _recording_calls(fuzzy, [0.0, 0.5, 1.0], sample_count, root_seed)

    by_rho: dict[float, list[int]] = {}
    for rho, seed in calls:
        by_rho.setdefault(rho, []).append(seed)

    seed_sequences = list(by_rho.values())
    expected = [sample_seed(root_seed, sample_index) for sample_index in range(sample_count)]

    assert len(seed_sequences) == 6
    assert all(seeds == expected for seeds in seed_sequences)


def test_vertex_pbox_passes_canonical_sample_seeds_to_evaluator() -> None:
    fuzzy = TrapezoidalFuzzyNumber(0.0, 0.25, 0.75, 1.0)
    sample_count = 5
    root_seed = 20260720

    calls = _recording_calls(fuzzy, [0.0], sample_count, root_seed)

    expected = [sample_seed(root_seed, sample_index) for sample_index in range(sample_count)]
    assert [seed for _rho, seed in calls] == expected + expected


def test_vertex_pbox_repeated_runs_pass_identical_sample_seed_sequences() -> None:
    fuzzy = TrapezoidalFuzzyNumber(0.0, 0.25, 0.75, 1.0)

    first = _recording_calls(fuzzy, [0.0, 1.0], 8, 11)
    second = _recording_calls(fuzzy, [0.0, 1.0], 8, 11)

    assert [seed for _rho, seed in first] == [seed for _rho, seed in second]


def test_vertex_pbox_distinct_root_seeds_pass_distinct_sample_identities() -> None:
    fuzzy = TrapezoidalFuzzyNumber(0.0, 0.25, 0.75, 1.0)

    first = _recording_calls(fuzzy, [0.0], 6, 1)
    second = _recording_calls(fuzzy, [0.0], 6, 2)

    assert [seed for _rho, seed in first[:6]] != [seed for _rho, seed in second[:6]]


def test_vertex_pbox_rejects_negative_root_seed_via_canonical_rng() -> None:
    fuzzy = TrapezoidalFuzzyNumber(0.0, 0.25, 0.75, 1.0)

    with pytest.raises(ValueError, match="root_seed"):
        estimate_vertex_pbox(
            fuzzy_number=fuzzy,
            alpha_grid=[0.0],
            sample_count=2,
            root_seed=-1,
            evaluator=_threshold_evaluator,
            use_mode=VertexUseMode.PRE_G3_SYNTHETIC,
        )


def test_vertex_pbox_is_deterministic_for_same_root_seed() -> None:
    fuzzy = TrapezoidalFuzzyNumber(0.0, 0.2, 0.8, 1.0)

    first = estimate_vertex_pbox(
        fuzzy_number=fuzzy,
        alpha_grid=[0.0, 0.5, 1.0],
        sample_count=50,
        root_seed=99,
        evaluator=_threshold_evaluator,
        use_mode=VertexUseMode.PRE_G3_SYNTHETIC,
    )
    second = estimate_vertex_pbox(
        fuzzy_number=fuzzy,
        alpha_grid=[0.0, 0.5, 1.0],
        sample_count=50,
        root_seed=99,
        evaluator=_threshold_evaluator,
        use_mode=VertexUseMode.PRE_G3_SYNTHETIC,
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
        use_mode=VertexUseMode.PRE_G3_SYNTHETIC,
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
            use_mode=VertexUseMode.PRE_G3_SYNTHETIC,
            alpha=0.0,
            rho_lower=0.0,
            rho_upper=1.0,
            lower=ProbabilityEstimate(0.3, 0.2, 0.4, 3, 10),
            upper=ProbabilityEstimate(0.7, 0.6, 0.8, 7, 10),
        ),
        0.5: PBoxAlphaResult(
            use_mode=VertexUseMode.PRE_G3_SYNTHETIC,
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
        use_mode=VertexUseMode.PRE_G3_SYNTHETIC,
    )
    return calls


def test_vertex_pbox_rejects_implicit_string_use_mode() -> None:
    fuzzy = TrapezoidalFuzzyNumber(0.0, 0.25, 0.75, 1.0)

    with pytest.raises(TypeError, match="use_mode must be a VertexUseMode"):
        estimate_vertex_pbox(
            fuzzy_number=fuzzy,
            alpha_grid=[0.0],
            sample_count=10,
            root_seed=1,
            evaluator=_threshold_evaluator,
            use_mode="g3-approved",  # type: ignore[arg-type]
        )
