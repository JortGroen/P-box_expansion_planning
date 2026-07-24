from __future__ import annotations

import math

import pytest

from src.pbox_monotonicity import (
    RHO_SWEEP_G3_STATUS,
    RHO_SWEEP_MANIFEST_PROTOCOL,
    RHO_SWEEP_NON_CLAIMS,
    assert_synthetic_rho_sweep_payload,
    estimate_dense_rho_sweep,
)
from src.rng import sample_seed


def _monotone_evaluator(rho: float, seed: int) -> bool:
    percentile = seed % 100
    threshold = round(80 - 50 * rho)
    return percentile < threshold


def test_dense_rho_sweep_reports_monotone_synthetic_curve() -> None:
    result = estimate_dense_rho_sweep(
        rho_grid=[0.0, 0.5, 1.0],
        sample_count=20,
        root_seed=20260724,
        evaluator=_monotone_evaluator,
    )

    probabilities = [point.estimate.probability for point in result.points]
    payload = result.to_mapping()

    assert probabilities == sorted(probabilities, reverse=True)
    assert result.monotone_nonincreasing is True
    assert result.max_upward_violation == 0.0
    assert result.use_status == "synthetic-only"
    assert payload["manifest_protocol"] == RHO_SWEEP_MANIFEST_PROTOCOL
    assert payload["g3_status"] == RHO_SWEEP_G3_STATUS
    assert tuple(payload["non_claims"]) == RHO_SWEEP_NON_CLAIMS
    assert_synthetic_rho_sweep_payload(payload)


def test_dense_rho_sweep_flags_nonmonotone_synthetic_curve() -> None:
    def nonmonotone_evaluator(rho: float, seed: int) -> bool:
        if rho == pytest.approx(0.5):
            return True
        return seed == sample_seed(7, 0)

    result = estimate_dense_rho_sweep(
        rho_grid=[0.0, 0.5, 1.0],
        sample_count=4,
        root_seed=7,
        evaluator=nonmonotone_evaluator,
    )

    assert [point.estimate.probability for point in result.points] == [0.25, 1.0, 0.25]
    assert result.monotone_nonincreasing is False
    assert result.max_upward_violation == pytest.approx(0.75)


def test_dense_rho_sweep_reuses_canonical_sample_identities_at_each_rho() -> None:
    calls: list[tuple[float, int]] = []

    def evaluator(rho: float, seed: int) -> bool:
        calls.append((rho, seed))
        return _monotone_evaluator(rho, seed)

    estimate_dense_rho_sweep(
        rho_grid=[0.0, 0.25, 0.5],
        sample_count=3,
        root_seed=11,
        evaluator=evaluator,
    )

    expected = [sample_seed(11, index) for index in range(3)]
    for start in range(0, len(calls), 3):
        assert [seed for _rho, seed in calls[start : start + 3]] == expected


def test_dense_rho_sweep_rejects_invalid_inputs_and_negative_root_seed() -> None:
    with pytest.raises(ValueError, match="rho_grid"):
        estimate_dense_rho_sweep(
            rho_grid=[],
            sample_count=2,
            root_seed=1,
            evaluator=_monotone_evaluator,
        )

    with pytest.raises(ValueError, match="unique sorted"):
        estimate_dense_rho_sweep(
            rho_grid=[0.5, 0.0],
            sample_count=2,
            root_seed=1,
            evaluator=_monotone_evaluator,
        )
    with pytest.raises(ValueError, match="rho_grid values"):
        estimate_dense_rho_sweep(
            rho_grid=[math.nan],
            sample_count=2,
            root_seed=1,
            evaluator=_monotone_evaluator,
        )

    with pytest.raises(ValueError, match="sample_count"):
        estimate_dense_rho_sweep(
            rho_grid=[0.0],
            sample_count=0,
            root_seed=1,
            evaluator=_monotone_evaluator,
        )

    with pytest.raises(ValueError, match="root_seed"):
        estimate_dense_rho_sweep(
            rho_grid=[0.0],
            sample_count=2,
            root_seed=-1,
            evaluator=_monotone_evaluator,
        )


def test_rho_sweep_payload_validator_rejects_paper_facing_or_tampered_payload() -> None:
    result = estimate_dense_rho_sweep(
        rho_grid=[0.0, 1.0],
        sample_count=3,
        root_seed=5,
        evaluator=_monotone_evaluator,
    )
    payload = result.to_mapping()

    with pytest.raises(ValueError, match="synthetic-only"):
        assert_synthetic_rho_sweep_payload({**payload, "use_status": "paper-facing"})
    with pytest.raises(ValueError, match="manifest_protocol"):
        assert_synthetic_rho_sweep_payload({**payload, "manifest_protocol": "old"})
    with pytest.raises(ValueError, match="G3"):
        assert_synthetic_rho_sweep_payload({**payload, "g3_status": "G3_APPROVED"})
    with pytest.raises(ValueError, match="non_claims"):
        assert_synthetic_rho_sweep_payload({**payload, "non_claims": ["no real P(E)"]})

    bad_points = [dict(point) for point in payload["points"]]
    bad_points.reverse()
    with pytest.raises(ValueError, match="unique sorted"):
        assert_synthetic_rho_sweep_payload({**payload, "points": bad_points})
    mismatched_counts = [dict(point) for point in payload["points"]]
    mismatched_counts[0]["sample_count"] = payload["sample_count"] + 1
    with pytest.raises(ValueError, match="point sample_count"):
        assert_synthetic_rho_sweep_payload({**payload, "points": mismatched_counts})

    with pytest.raises(ValueError, match="monotone_nonincreasing"):
        assert_synthetic_rho_sweep_payload(
            {**payload, "monotone_nonincreasing": not payload["monotone_nonincreasing"]}
        )


def test_rho_sweep_payload_validator_rejects_collapsed_or_paper_facing_fields() -> None:
    result = estimate_dense_rho_sweep(
        rho_grid=[0.0, 1.0],
        sample_count=3,
        root_seed=5,
        evaluator=_monotone_evaluator,
    )
    payload = result.to_mapping()

    with pytest.raises(ValueError, match="collapsed result fields"):
        assert_synthetic_rho_sweep_payload({**payload, "defuzzified_probability": 0.5})

    bad_points = [dict(point) for point in payload["points"]]
    bad_points[0]["p_hat"] = bad_points[0]["probability"]
    with pytest.raises(ValueError, match="collapsed result fields"):
        assert_synthetic_rho_sweep_payload({**payload, "points": bad_points})

    with pytest.raises(ValueError, match="paper-facing"):
        assert_synthetic_rho_sweep_payload({**payload, "paper_facing_result": True})