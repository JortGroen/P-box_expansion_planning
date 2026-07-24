from __future__ import annotations

import json

import numpy as np
import pytest

from src.evaluator_sum import Tier1Evaluation, count_import_overload_episodes
from src.pbox_error import OutputErrorProtocolConfig
from src.pbox_monotonicity import estimate_dense_rho_sweep
from src.pbox_runner_readiness import (
    REAL_RUN_BLOCKERS,
    assert_real_runner_blocker_payload,
    assert_synthetic_runner_readiness_payload,
    build_real_runner_blocker_manifest,
    build_synthetic_runner_readiness_manifest,
)
from src.rng import sample_seed


def test_runner_readiness_combines_endpoint_counts_and_rho_sweep() -> None:
    config = _output_error_config()
    rho_sweep = estimate_dense_rho_sweep(
        rho_grid=[0.0, 0.5, 1.0],
        sample_count=2,
        root_seed=17,
        evaluator=lambda rho, seed: seed == sample_seed(17, 0) and rho < 1.0,
    ).to_mapping()

    manifest = build_synthetic_runner_readiness_manifest(
        manifest_id="synthetic-e4-e5-runner-readiness",
        results_by_alpha={
            0.0: [
                _trajectory([0.8, 0.8, 0.8, 0.8], p_signs=[1, 1, 1, 1]),
                _trajectory([1.2, 1.2, 1.2, 1.2], p_signs=[1, 1, 1, 1]),
            ],
            0.5: [
                _trajectory([0.95, 0.95, 0.95, 0.95], p_signs=[1, 1, 1, 1]),
                _trajectory([1.2, 1.2, 1.2, 1.2], p_signs=[1, 1, 1, 1]),
            ],
        },
        output_error_config=config,
        rho_sweep_payload=rho_sweep,
    )
    payload = manifest.to_mapping()

    assert json.loads(json.dumps(payload, sort_keys=True)) == payload
    assert payload["protocol"] == "e4-e5-synthetic-runner-readiness-v1"
    assert payload["use_status"] == "synthetic-runner-readiness"
    assert payload["g3_status"] == "pending-no-paper-facing-vertex-claim"
    assert payload["invariants"]["alpha_indexed_lower_upper_reporting"] is True
    assert payload["invariants"]["defuzzification"] == "forbidden"
    assert payload["invariants"]["probability_widening"] == "forbidden"
    assert [record["alpha"] for record in payload["alpha_endpoint_records"]] == [0.0, 0.5]
    assert payload["alpha_endpoint_records"][0]["event_count_bounds"] == {
        "lower_successes": 1,
        "sample_count": 2,
        "upper_successes": 1,
    }
    assert payload["alpha_endpoint_records"][1]["event_count_bounds"] == {
        "lower_successes": 1,
        "sample_count": 2,
        "upper_successes": 2,
    }
    assert all(
        record["sample_indices"] == [0, 1]
        for record in payload["alpha_endpoint_records"]
    )
    assert payload["real_use_blocker_manifest"]["blockers"] == list(REAL_RUN_BLOCKERS)
    assert "defuzzified_probability" not in json.dumps(payload)
    assert_synthetic_runner_readiness_payload(payload)


def test_runner_readiness_records_unwidened_direction_gate_and_episode_reset() -> None:
    manifest = build_synthetic_runner_readiness_manifest(
        manifest_id="synthetic-direction-gate-readiness",
        results_by_alpha={
            0.0: [
                _trajectory([1.4, 1.4, 1.4, 1.4], p_signs=[1, -1, 1, 1]),
                _trajectory([1.4, 1.4, 1.4, 1.4], p_signs=[1, 1, 1, 1]),
            ],
        },
        output_error_config=_output_error_config(epsilon_tier1_plus=0.0),
    )
    record = manifest.to_mapping()["alpha_endpoint_records"][0]

    assert record["event_count_bounds"] == {
        "lower_successes": 1,
        "sample_count": 2,
        "upper_successes": 1,
    }
    assert record["sample_endpoint_events"][0]["upper_longest_run_steps"] == 2
    assert record["sample_endpoint_events"][0]["upper_event"] is False
    assert record["sample_endpoint_events"][1]["upper_longest_run_steps"] == 4
    assert record["sample_endpoint_events"][1]["upper_event"] is True
    assert_synthetic_runner_readiness_payload(manifest.to_mapping())


def test_runner_readiness_rejects_alpha_sample_identity_mismatch() -> None:
    with pytest.raises(ValueError, match="identical ordered sample indices|same sample_count"):
        build_synthetic_runner_readiness_manifest(
            manifest_id="mismatched-alpha-samples",
            results_by_alpha={
                0.0: [_trajectory([1.2, 1.2, 1.2, 1.2], p_signs=[1, 1, 1, 1])],
                0.5: [
                    _trajectory([1.2, 1.2, 1.2, 1.2], p_signs=[1, 1, 1, 1]),
                    _trajectory([0.8, 0.8, 0.8, 0.8], p_signs=[1, 1, 1, 1]),
                ],
            },
            output_error_config=_output_error_config(),
        )


def test_runner_readiness_rejects_tampered_payloads() -> None:
    payload = build_synthetic_runner_readiness_manifest(
        manifest_id="tamper-readiness",
        results_by_alpha={
            0.0: [
                _trajectory([0.8, 0.8, 0.8, 0.8], p_signs=[1, 1, 1, 1]),
                _trajectory([1.2, 1.2, 1.2, 1.2], p_signs=[1, 1, 1, 1]),
            ]
        },
        output_error_config=_output_error_config(),
    ).to_mapping()

    relabeled = dict(payload)
    relabeled["use_status"] = "paper-facing"
    with pytest.raises(ValueError, match="synthetic-only"):
        assert_synthetic_runner_readiness_payload(relabeled)

    collapsed = dict(payload)
    collapsed["defuzzified_probability"] = 0.5
    with pytest.raises(ValueError, match="collapse probability"):
        assert_synthetic_runner_readiness_payload(collapsed)

    bad_config = dict(payload)
    bad_config["output_error_config"] = dict(payload["output_error_config"])
    bad_config["output_error_config"]["probability_widening"] = "allowed"
    with pytest.raises(ValueError, match="probability widening"):
        assert_synthetic_runner_readiness_payload(bad_config)

    bad_indices = dict(payload)
    bad_records = [dict(record) for record in payload["alpha_endpoint_records"]]
    bad_records[0] = dict(bad_records[0])
    bad_records[0]["sample_indices"] = [1, 0]
    bad_indices["alpha_endpoint_records"] = bad_records
    with pytest.raises(ValueError, match="contiguous from zero"):
        assert_synthetic_runner_readiness_payload(bad_indices)

    bad_blockers = dict(payload)
    bad_blockers["real_use_blocker_manifest"] = dict(payload["real_use_blocker_manifest"])
    bad_blockers["real_use_blocker_manifest"]["blockers"] = []
    with pytest.raises(ValueError, match="signed-gap checklist"):
        assert_synthetic_runner_readiness_payload(bad_blockers)


def test_runner_readiness_rejects_mismatched_rho_sweep_sample_count() -> None:
    rho_sweep = estimate_dense_rho_sweep(
        rho_grid=[0.0, 1.0],
        sample_count=3,
        root_seed=9,
        evaluator=lambda rho, seed: rho < 0.5 and seed == sample_seed(9, 0),
    ).to_mapping()

    with pytest.raises(ValueError, match="rho sweep sample_count"):
        build_synthetic_runner_readiness_manifest(
            manifest_id="bad-rho-sample-count",
            results_by_alpha={
                0.0: [
                    _trajectory([0.8, 0.8, 0.8, 0.8], p_signs=[1, 1, 1, 1]),
                    _trajectory([1.2, 1.2, 1.2, 1.2], p_signs=[1, 1, 1, 1]),
                ]
            },
            output_error_config=_output_error_config(),
            rho_sweep_payload=rho_sweep,
        )


def test_real_runner_blocker_manifest_fails_closed() -> None:
    payload = build_real_runner_blocker_manifest(manifest_id="real-use-blockers")

    assert payload["ready_for_real_run"] is False
    assert payload["blockers"] == list(REAL_RUN_BLOCKERS)
    assert_real_runner_blocker_payload(payload)

    false_ready = dict(payload)
    false_ready["ready_for_real_run"] = True
    with pytest.raises(ValueError, match="fail closed"):
        assert_real_runner_blocker_payload(false_ready)


def _output_error_config(*, epsilon_tier1_plus: float = 0.1) -> OutputErrorProtocolConfig:
    return OutputErrorProtocolConfig.from_mapping(
        {
            "epsilon_grid": 0.0,
            "epsilon_tier1_minus": 0.1,
            "epsilon_tier1_plus": epsilon_tier1_plus,
            "threshold_pu": 1.0,
            "min_consecutive_steps": 4,
            "timestep_seconds": 900,
            "envelope_source": "synthetic-runner-readiness-envelope",
            "grid_error_source": "A-013-pending-synthetic-placeholder",
            "tier1_error_source": "G2-pending-synthetic-placeholder",
            "capacity_denominator_provenance": "capacity-convention-pending",
        }
    )


def _trajectory(
    loading_pu: list[float],
    *,
    p_signs: list[int],
    threshold_pu: float = 1.0,
    min_consecutive_steps: int = 4,
) -> Tier1Evaluation:
    denominator_kva = 1000.0
    loading = np.asarray(loading_pu, dtype=float)
    signs = np.asarray(p_signs, dtype=int)
    p_net_kw = signs * loading * denominator_kva
    q_net_kvar = np.where(signs == 0, loading * denominator_kva, 0.0)
    s_net_kva = np.hypot(p_net_kw, q_net_kvar)
    screening_loading_pu = s_net_kva / denominator_kva
    import_mask = p_net_kw > 0.0
    export_mask = p_net_kw < 0.0
    zero_mask = p_net_kw == 0.0
    import_loading_pu = np.where(import_mask, screening_loading_pu, 0.0)
    export_loading_pu = np.where(export_mask, screening_loading_pu, 0.0)
    episodes, longest = count_import_overload_episodes(
        import_loading_pu,
        threshold_pu=threshold_pu,
        min_consecutive_steps=min_consecutive_steps,
    )
    return Tier1Evaluation(
        p_net_kw=p_net_kw,
        q_net_kvar=q_net_kvar,
        s_net_kva=s_net_kva,
        screening_loading_pu=screening_loading_pu,
        import_loading_pu=import_loading_pu,
        export_loading_pu=export_loading_pu,
        import_mask=import_mask,
        export_mask=export_mask,
        zero_mask=zero_mask,
        overload=episodes > 0,
        overload_episode_count=episodes,
        longest_import_run_steps=longest,
        time_domain="full_year",
        primary_probability_domain=True,
        threshold_pu=threshold_pu,
        min_consecutive_steps=min_consecutive_steps,
    )
