from __future__ import annotations

import json

import numpy as np
import pytest

from src.evaluator_sum import Tier1Evaluation, count_import_overload_episodes
from src.pbox_error import OutputErrorProtocolConfig
from src.pbox_monotonicity import estimate_dense_rho_sweep
from src.pbox_runner_readiness import (
    REAL_INPUT_BLOCKER_DESCRIPTIONS,
    REAL_INPUT_READINESS_PROTOCOL,
    REAL_RUN_BLOCKERS,
    assert_real_input_readiness_payload,
    assert_real_runner_blocker_payload,
    assert_synthetic_runner_readiness_payload,
    build_real_input_readiness_manifest,
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



def test_real_input_readiness_manifest_names_machine_readable_missing_blockers() -> None:
    payload = build_real_input_readiness_manifest(
        manifest_id="real-input-readiness-missing",
        approval_ids={},
        artifact_references={},
    )

    assert payload["manifest_protocol"] == REAL_INPUT_READINESS_PROTOCOL
    assert payload["ready_for_real_run"] is False
    assert tuple(payload["blocker_keys"]) == (
        "missing_signed_g2_tier1_endpoints",
        "missing_signed_a013_grid_error",
        "missing_capacity_convention_approval",
        "missing_a016_scenario_consistency",
        "missing_capacity_denominator_provenance",
        "missing_real_loading_trajectory_manifests",
        "missing_real_output_error_endpoint_records",
        "missing_output_error_config",
    )
    assert payload["blockers"] == {
        key: REAL_INPUT_BLOCKER_DESCRIPTIONS[key]
        for key in payload["blocker_keys"]
    }
    assert "no probability generated by this guard" in payload["non_claims"]
    assert_real_input_readiness_payload(payload)


def test_real_input_readiness_manifest_accepts_complete_alpha_endpoint_fixture() -> None:
    config = _approved_output_error_config()
    records = _alpha_endpoint_records(config)

    payload = build_real_input_readiness_manifest(
        manifest_id="real-input-readiness-complete-fixture",
        approval_ids=_real_input_approval_ids(config),
        artifact_references=_real_input_artifact_references(config),
        output_error_config=config.manifest_metadata(),
        alpha_endpoint_records=records,
    )

    assert payload["ready_for_real_run"] is True
    assert payload["blocker_keys"] == []
    assert payload["blockers"] == {}
    assert [record["alpha"] for record in payload["alpha_endpoint_records"]] == [0.0, 0.5]
    assert "defuzzified_probability" not in json.dumps(payload)
    assert_real_input_readiness_payload(payload)


def test_real_input_readiness_requires_g3_when_vertex_shortcut_is_claimed() -> None:
    config = _approved_output_error_config()
    approval_ids = _real_input_approval_ids(config)
    payload = build_real_input_readiness_manifest(
        manifest_id="real-input-readiness-vertex-blocked",
        approval_ids=approval_ids,
        artifact_references=_real_input_artifact_references(config),
        output_error_config=config.manifest_metadata(),
        alpha_endpoint_records=_alpha_endpoint_records(config),
        uses_vertex_shortcut=True,
    )

    assert payload["ready_for_real_run"] is False
    assert payload["blocker_keys"] == ["missing_g3_monotonicity_approval"]
    assert_real_input_readiness_payload(payload)

    approval_ids = {**approval_ids, "g3_monotonicity_approval_id": "g3-approved-record"}
    approved = build_real_input_readiness_manifest(
        manifest_id="real-input-readiness-vertex-ready",
        approval_ids=approval_ids,
        artifact_references=_real_input_artifact_references(config),
        output_error_config=config.manifest_metadata(),
        alpha_endpoint_records=_alpha_endpoint_records(config),
        uses_vertex_shortcut=True,
    )
    assert approved["ready_for_real_run"] is True


def test_real_input_readiness_rejects_stale_or_proposed_approval_ids() -> None:
    config = _approved_output_error_config()
    approval_ids = _real_input_approval_ids(config)
    approval_ids["a013_grid_error_approval_id"] = "A-013-proposed-review-packet"

    with pytest.raises(ValueError, match="stale or unsigned"):
        build_real_input_readiness_manifest(
            manifest_id="real-input-readiness-stale-a013",
            approval_ids=approval_ids,
            artifact_references=_real_input_artifact_references(config),
            output_error_config=config.manifest_metadata(),
            alpha_endpoint_records=_alpha_endpoint_records(config),
        )


def test_real_input_readiness_payload_validator_recomputes_ready_and_blockers() -> None:
    config = _approved_output_error_config()
    payload = build_real_input_readiness_manifest(
        manifest_id="real-input-readiness-tamper",
        approval_ids=_real_input_approval_ids(config),
        artifact_references=_real_input_artifact_references(config),
        output_error_config=config.manifest_metadata(),
        alpha_endpoint_records=_alpha_endpoint_records(config),
    )

    with pytest.raises(ValueError, match="ready_for_real_run"):
        assert_real_input_readiness_payload({**payload, "ready_for_real_run": False})

    with pytest.raises(ValueError, match="blocker_keys"):
        assert_real_input_readiness_payload(
            {**payload, "blocker_keys": ["missing_signed_a013_grid_error"]}
        )

    bad_blockers = {
        **payload,
        "blockers": {"missing_signed_a013_grid_error": "tampered"},
    }
    with pytest.raises(ValueError, match="blockers"):
        assert_real_input_readiness_payload(bad_blockers)


def test_real_input_readiness_rejects_collapsed_or_non_alpha_outputs() -> None:
    config = _approved_output_error_config()
    payload = build_real_input_readiness_manifest(
        manifest_id="real-input-readiness-output-shape",
        approval_ids=_real_input_approval_ids(config),
        artifact_references=_real_input_artifact_references(config),
        output_error_config=config.manifest_metadata(),
        alpha_endpoint_records=_alpha_endpoint_records(config),
    )

    with pytest.raises(ValueError, match="collapse probability"):
        assert_real_input_readiness_payload({**payload, "defuzzified_probability": 0.5})

    for field in ("probability_bounds", "event_count_bounds", "probability_rows"):
        with pytest.raises(ValueError, match="alpha_endpoint_records"):
            assert_real_input_readiness_payload({**payload, field: {}})


def test_real_input_readiness_blocks_config_reference_mismatches() -> None:
    config = _approved_output_error_config()
    approval_ids = _real_input_approval_ids(config)
    approval_ids["g2_tier1_endpoints_approval_id"] = "g2-approved-different-record"

    payload = build_real_input_readiness_manifest(
        manifest_id="real-input-readiness-config-mismatch",
        approval_ids=approval_ids,
        artifact_references=_real_input_artifact_references(config),
        output_error_config=config.manifest_metadata(),
        alpha_endpoint_records=_alpha_endpoint_records(config),
    )

    assert payload["ready_for_real_run"] is False
    assert payload["blocker_keys"] == ["output_error_config_approval_mismatch"]
    assert_real_input_readiness_payload(payload)
def _output_error_config(
    *,
    epsilon_tier1_plus: float = 0.1,
    a013_approval_id: str = "A-013-pending",
    g2_approval_id: str = "G2-pending",
    capacity_convention_linkage: str = "pending-g1-a2-e3-s2b",
    capacity_denominator_provenance: str = "capacity-convention-pending",
) -> OutputErrorProtocolConfig:
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
            "capacity_denominator_provenance": capacity_denominator_provenance,
            "capacity_convention_linkage": capacity_convention_linkage,
            "a013_grid_error_approval_id": a013_approval_id,
            "g2_tier1_envelope_approval_id": g2_approval_id,
        }
    )




def _approved_output_error_config() -> OutputErrorProtocolConfig:
    return _output_error_config(
        a013_approval_id="a013-approved-grid-error-record",
        g2_approval_id="g2-approved-tier1-endpoint-record",
        capacity_convention_linkage="capacity-convention-approved-record",
        capacity_denominator_provenance="capacity-denominator-provenance-record",
    )


def _alpha_endpoint_records(config: OutputErrorProtocolConfig) -> list[dict[str, object]]:
    payload = build_synthetic_runner_readiness_manifest(
        manifest_id="real-input-readiness-alpha-record-fixture",
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
    ).to_mapping()
    return [dict(record) for record in payload["alpha_endpoint_records"]]


def _real_input_approval_ids(config: OutputErrorProtocolConfig) -> dict[str, str]:
    metadata = config.manifest_metadata()
    return {
        "g2_tier1_endpoints_approval_id": str(metadata["g2_tier1_envelope_approval_id"]),
        "a013_grid_error_approval_id": str(metadata["a013_grid_error_approval_id"]),
        "capacity_convention_approval_id": "capacity-convention-approved-record",
        "a016_scenario_consistency_approval_id": "a016-approved-consistency-record",
    }


def _real_input_artifact_references(config: OutputErrorProtocolConfig) -> dict[str, str]:
    metadata = config.manifest_metadata()
    return {
        "capacity_convention_linkage": str(metadata["capacity_convention_linkage"]),
        "capacity_denominator_provenance": str(
            metadata["capacity_denominator_provenance"]
        ),
        "loading_trajectory_manifest_id": "loading-trajectory-manifest-record",
        "output_error_endpoint_record_id": "output-error-endpoint-record",
    }
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
