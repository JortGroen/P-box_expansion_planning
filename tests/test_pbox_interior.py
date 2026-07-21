from __future__ import annotations

import pytest

from src.fuzzy import TrapezoidalFuzzyNumber
from src.pbox import VertexUseMode, estimate_vertex_pbox
from src.pbox_interior import estimate_interior_pbox
from src.rng import sample_seed


def _threshold_evaluator(rho: float, seed: int) -> bool:
    sample_value = seed % 100
    threshold = round(80 - 40 * rho)
    return sample_value < threshold


def test_interior_pbox_agrees_with_vertex_on_monotone_synthetic_case() -> None:
    fuzzy = TrapezoidalFuzzyNumber(0.0, 0.25, 0.75, 1.0)

    vertex = estimate_vertex_pbox(
        fuzzy_number=fuzzy,
        alpha_grid=[0.0, 0.5, 1.0],
        sample_count=40,
        root_seed=7,
        evaluator=_threshold_evaluator,
        use_mode=VertexUseMode.PRE_G3_SYNTHETIC,
    )
    interior = estimate_interior_pbox(
        fuzzy_number=fuzzy,
        alpha_grid=[0.0, 0.5, 1.0],
        sample_count=40,
        root_seed=7,
        evaluator=_threshold_evaluator,
        rho_grid_size=9,
    )

    for alpha, vertex_result in vertex.items():
        interior_result = interior[alpha]
        assert interior_result.lower == vertex_result.lower
        assert interior_result.upper == vertex_result.upper
        assert interior_result.rho_at_lower_probability == vertex_result.rho_upper
        assert interior_result.rho_at_upper_probability == vertex_result.rho_lower


def test_interior_pbox_detects_nonmonotone_interior_extrema() -> None:
    fuzzy = TrapezoidalFuzzyNumber(0.0, 0.0, 1.0, 1.0)
    root_seed = 19
    sample_count = 4
    endpoint_success_seeds = {
        sample_seed(root_seed, sample_index) for sample_index in range(2)
    }

    def nonmonotone_evaluator(rho: float, seed: int) -> bool:
        if rho == pytest.approx(0.25) or rho == pytest.approx(0.75):
            return False
        if rho == pytest.approx(0.5):
            return True
        return seed in endpoint_success_seeds

    vertex = estimate_vertex_pbox(
        fuzzy_number=fuzzy,
        alpha_grid=[0.0],
        sample_count=sample_count,
        root_seed=root_seed,
        evaluator=nonmonotone_evaluator,
        use_mode=VertexUseMode.PRE_G3_SYNTHETIC,
    )
    interior = estimate_interior_pbox(
        fuzzy_number=fuzzy,
        alpha_grid=[0.0],
        sample_count=sample_count,
        root_seed=root_seed,
        evaluator=nonmonotone_evaluator,
        rho_grid_size=5,
    )

    assert vertex[0.0].lower.probability == 0.5
    assert vertex[0.0].upper.probability == 0.5
    assert interior[0.0].lower.probability == 0.0
    assert interior[0.0].upper.probability == 1.0
    assert interior[0.0].rho_at_lower_probability == pytest.approx(0.25)
    assert interior[0.0].rho_at_upper_probability == pytest.approx(0.5)


def test_interior_pbox_reuses_canonical_sample_seed_sequence_per_rho() -> None:
    fuzzy = TrapezoidalFuzzyNumber(0.0, 0.25, 0.75, 1.0)
    root_seed = 20260720
    sample_count = 3
    calls: list[tuple[float, int]] = []

    def evaluator(rho: float, seed: int) -> bool:
        calls.append((rho, seed))
        return False

    estimate_interior_pbox(
        fuzzy_number=fuzzy,
        alpha_grid=[0.0, 1.0],
        sample_count=sample_count,
        root_seed=root_seed,
        evaluator=evaluator,
        rho_grid_size=3,
    )

    expected = [sample_seed(root_seed, sample_index) for sample_index in range(sample_count)]
    assert len(calls) % sample_count == 0
    for index in range(0, len(calls), sample_count):
        assert [seed for _rho, seed in calls[index : index + sample_count]] == expected


def test_interior_pbox_rejects_invalid_grid_and_negative_root() -> None:
    fuzzy = TrapezoidalFuzzyNumber(0.0, 0.25, 0.75, 1.0)

    with pytest.raises(ValueError, match="rho_grid_size"):
        estimate_interior_pbox(
            fuzzy_number=fuzzy,
            alpha_grid=[0.0],
            sample_count=2,
            root_seed=1,
            evaluator=_threshold_evaluator,
            rho_grid_size=1,
        )

    with pytest.raises(ValueError, match="root_seed"):
        estimate_interior_pbox(
            fuzzy_number=fuzzy,
            alpha_grid=[0.0],
            sample_count=2,
            root_seed=-1,
            evaluator=_threshold_evaluator,
            rho_grid_size=3,
        )
