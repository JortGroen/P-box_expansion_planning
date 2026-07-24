from __future__ import annotations

import json

import pytest

from src.fuzzy import TrapezoidalFuzzyNumber
from src.pbox import VertexUseMode, estimate_vertex_pbox
from src.pbox_interior import (
    assert_interior_fallback_report_payload,
    build_interior_fallback_report,
    estimate_interior_pbox,
)
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

    for alpha, result in interior.items():
        assert result.lower == vertex[alpha].lower
        assert result.upper == vertex[alpha].upper
        assert result.rho_at_lower_probability == vertex[alpha].rho_upper
        assert result.rho_at_upper_probability == vertex[alpha].rho_lower


def test_interior_pbox_detects_nonmonotone_interior_extrema() -> None:
    fuzzy = TrapezoidalFuzzyNumber(0.0, 0.0, 1.0, 1.0)
    root_seed = 19
    endpoint_success_seeds = {sample_seed(root_seed, index) for index in range(2)}

    def nonmonotone_evaluator(rho: float, seed: int) -> bool:
        if rho == pytest.approx(0.25) or rho == pytest.approx(0.75):
            return False
        if rho == pytest.approx(0.5):
            return True
        return seed in endpoint_success_seeds

    vertex = estimate_vertex_pbox(
        fuzzy_number=fuzzy,
        alpha_grid=[0.0],
        sample_count=4,
        root_seed=root_seed,
        evaluator=nonmonotone_evaluator,
        use_mode=VertexUseMode.PRE_G3_SYNTHETIC,
    )
    interior = estimate_interior_pbox(
        fuzzy_number=fuzzy,
        alpha_grid=[0.0],
        sample_count=4,
        root_seed=root_seed,
        evaluator=nonmonotone_evaluator,
        rho_grid_size=5,
    )

    assert vertex[0.0].lower.probability == 0.5
    assert vertex[0.0].upper.probability == 0.5
    assert interior[0.0].lower.probability == 0.0
    assert interior[0.0].rho_at_lower_probability == 0.25
    assert interior[0.0].upper.probability == 1.0
    assert interior[0.0].rho_at_upper_probability == 0.5


def test_interior_pbox_reuses_canonical_sample_seed_sequence_per_rho() -> None:
    fuzzy = TrapezoidalFuzzyNumber(0.0, 0.25, 0.75, 1.0)
    calls: list[tuple[float, int]] = []

    def evaluator(rho: float, seed: int) -> bool:
        calls.append((rho, seed))
        return _threshold_evaluator(rho, seed)

    sample_count = 3
    root_seed = 20260720
    estimate_interior_pbox(
        fuzzy_number=fuzzy,
        alpha_grid=[0.0, 1.0],
        sample_count=sample_count,
        root_seed=root_seed,
        evaluator=evaluator,
        rho_grid_size=3,
    )

    expected = [sample_seed(root_seed, index) for index in range(sample_count)]
    for start in range(0, len(calls), sample_count):
        assert [seed for _rho, seed in calls[start : start + sample_count]] == expected


def test_interior_fallback_report_is_json_stable_and_pre_g3_only() -> None:
    fuzzy = TrapezoidalFuzzyNumber(0.0, 0.25, 0.75, 1.0)
    family = estimate_interior_pbox(
        fuzzy_number=fuzzy,
        alpha_grid=[0.0, 0.5, 1.0],
        sample_count=40,
        root_seed=7,
        evaluator=_threshold_evaluator,
        rho_grid_size=9,
    )

    report = build_interior_fallback_report(family)
    payload = report.to_mapping()

    assert json.loads(json.dumps(payload, sort_keys=True)) == payload
    assert payload["report_protocol"] == "interior-pbox-fallback-report-v1"
    assert payload["use_status"] == "synthetic-pre-g3-only"
    assert payload["g3_claim"] == "none-pre-g3-fallback-scaffold"
    assert payload["probability_reporting"] == "alpha-indexed-lower-upper-only"
    assert "defuzzified_probability" not in json.dumps(payload)
    assert [row["alpha"] for row in payload["rows"]] == [0.0, 0.5, 1.0]
    assert_interior_fallback_report_payload(payload)


def test_interior_fallback_report_payload_rejects_serialized_tampering() -> None:
    fuzzy = TrapezoidalFuzzyNumber(0.0, 0.25, 0.75, 1.0)
    family = estimate_interior_pbox(
        fuzzy_number=fuzzy,
        alpha_grid=[0.0, 0.5],
        sample_count=8,
        root_seed=17,
        evaluator=_threshold_evaluator,
        rho_grid_size=5,
    )
    payload = build_interior_fallback_report(family).to_mapping()

    paper_facing = dict(payload)
    paper_facing["use_status"] = "paper-facing"
    with pytest.raises(ValueError, match="synthetic/pre-G3"):
        assert_interior_fallback_report_payload(paper_facing)

    collapsed = dict(payload)
    collapsed["defuzzified_probability"] = 0.5
    with pytest.raises(ValueError, match="defuzzified"):
        assert_interior_fallback_report_payload(collapsed)

    duplicate_alpha = dict(payload)
    duplicate_alpha["rows"] = [dict(payload["rows"][0]), dict(payload["rows"][0])]
    with pytest.raises(ValueError, match="strictly increasing"):
        assert_interior_fallback_report_payload(duplicate_alpha)

    outside_cut = dict(payload)
    outside_rows = [dict(row) for row in payload["rows"]]
    outside_rows[0]["rho_at_lower_probability"] = outside_rows[0]["rho_upper"] + 1.0
    outside_cut["rows"] = outside_rows
    with pytest.raises(ValueError, match="outside rho cut"):
        assert_interior_fallback_report_payload(outside_cut)

def test_interior_pbox_rejects_invalid_grid_and_negative_root_seed() -> None:
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
            rho_grid_size=2,
        )
