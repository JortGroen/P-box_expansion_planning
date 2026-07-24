from __future__ import annotations

import pytest

from src.pbox import PBoxAlphaResult, ProbabilityEstimate, VertexUseMode
from src.pbox_error import (
    OUTPUT_ERROR_APPLICATION,
    OUTPUT_ERROR_DEPENDENCE,
    OUTPUT_ERROR_LOWER_FORMULA,
    OUTPUT_ERROR_SAMPLING,
    OUTPUT_ERROR_UPPER_FORMULA,
)
from src.pbox_reporting import (
    RUNNER_REPORT_BOUNDARY_PROTOCOL,
    OUTPUT_ERROR_ENDPOINT_COUNT_BLOCKED_STATUS,
    OUTPUT_ERROR_ENDPOINT_COUNT_BRIDGE_PROTOCOL,
    OUTPUT_ERROR_ENDPOINT_COUNT_PROVENANCE,
    REAL_OUTPUT_ERROR_ENDPOINT_COUNT_MANIFEST_PROTOCOL,
    AlphaEventCountRecord,
    assert_alpha_probability_estimator_packet,
    assert_output_error_endpoint_count_bridge_packet,
    assert_real_output_error_endpoint_count_manifest_preflight,
    assert_runner_report_boundary_payload,
    build_alpha_probability_estimator_packet,
    build_output_error_endpoint_count_bridge_packet,
    build_real_output_error_endpoint_count_manifest_preflight,
    build_guarded_pbox_report,
    build_runner_report_boundary_record,
    probability_rows_from_alpha_event_counts,
    probability_rows_from_pbox_family,
)
from src.pbox_result_guards import FinalResultPrerequisites, PaperFacingResultKind
from src.rng import sample_seed


def _estimate(probability: float, successes: int = 1) -> ProbabilityEstimate:
    return ProbabilityEstimate(
        probability=probability,
        ci_lower=max(0.0, probability - 0.05),
        ci_upper=min(1.0, probability + 0.05),
        successes=successes,
        sample_count=10,
    )


def _pbox_family(*, use_mode: VertexUseMode = VertexUseMode.PRE_G3_SYNTHETIC):
    return {
        0.5: PBoxAlphaResult(
            use_mode=use_mode,
            alpha=0.5,
            rho_lower=0.25,
            rho_upper=0.75,
            lower=_estimate(0.15),
            upper=_estimate(0.25, successes=2),
        ),
        0.0: PBoxAlphaResult(
            use_mode=use_mode,
            alpha=0.0,
            rho_lower=0.0,
            rho_upper=1.0,
            lower=_estimate(0.10),
            upper=_estimate(0.30, successes=3),
        ),
    }


def _complete_prerequisites(*, g3: bool = False) -> FinalResultPrerequisites:
    return FinalResultPrerequisites(
        g2_tier1_envelope_approved=True,
        a013_grid_error_signed=True,
        capacity_convention_approved=True,
        capacity_denominator_provenance="manifested synthetic capacity denominator",
        output_error_endpoint_records_manifested=True,
        a016_scenario_consistency_manifested=True,
        g3_vertex_shortcut_approved=g3,
    )


def _output_error_record() -> dict[str, object]:
    sample_events = [
        {"sample_index": 0, "lower_event": False, "upper_event": False},
        {"sample_index": 1, "lower_event": False, "upper_event": False},
        {"sample_index": 2, "lower_event": False, "upper_event": True},
        {"sample_index": 3, "lower_event": False, "upper_event": True},
        {"sample_index": 4, "lower_event": True, "upper_event": True},
    ]
    return {
        "config": {
            "a013_grid_error_approval_id": "A-013-synthetic-pending",
            "capacity_convention_linkage": "synthetic-capacity-linkage",
            "capacity_denominator_provenance": "synthetic-capacity-placeholder",
            "composition_formula": {
                "lower": OUTPUT_ERROR_LOWER_FORMULA,
                "upper": OUTPUT_ERROR_UPPER_FORMULA,
            },
            "dependence_assumption": OUTPUT_ERROR_DEPENDENCE,
            "envelope": {
                "epsilon_grid": 0.0,
                "epsilon_tier1_minus": 0.0,
                "epsilon_tier1_plus": 0.0,
            },
            "envelope_source": "synthetic-envelope-placeholder",
            "error_application": OUTPUT_ERROR_APPLICATION,
            "error_sampling": OUTPUT_ERROR_SAMPLING,
            "event_semantics": {
                "comparator": "strict_greater_than",
                "direction_gate": "unwidened_p_net_import_mask",
                "min_consecutive_steps": 4,
                "threshold_pu": 1.0,
                "timestep_seconds": 900,
            },
            "g2_tier1_envelope_approval_id": "G2-synthetic-pending",
            "grid_error_source": "synthetic-grid-placeholder",
            "probability_widening": "forbidden",
            "tier1_error_source": "synthetic-tier1-placeholder",
            "use_status": "synthetic-only",
        },
        "event_count_bounds": {
            "lower_successes": 1,
            "sample_count": 5,
            "upper_successes": 3,
        },
        "probability_bounds": {
            "lower": {
                "ci_lower": 0.05,
                "ci_upper": 0.45,
                "probability": 0.2,
                "sample_count": 5,
                "successes": 1,
            },
            "upper": {
                "ci_lower": 0.35,
                "ci_upper": 0.85,
                "probability": 0.6,
                "sample_count": 5,
                "successes": 3,
            },
        },
        "probability_widening": "forbidden",
        "sample_endpoint_events": sample_events,
    }


def _selective_ac_metadata() -> dict[str, object]:
    root_seed = 123
    return {
        "ac_execution_status": "not-run",
        "alpha_grid": [0.0, 0.5],
        "candidates": [
            {
                "alpha": 0.0,
                "lower_event": False,
                "lower_longest_run_steps": 3,
                "sample_index": 2,
                "sample_seed": sample_seed(root_seed, 2),
                "straddling_timestep_indices": [4, 5],
                "threshold_pu": 1.0,
                "upper_event": True,
                "upper_longest_run_steps": 4,
            },
            {
                "alpha": 0.5,
                "lower_event": True,
                "lower_longest_run_steps": 4,
                "sample_index": 4,
                "sample_seed": sample_seed(root_seed, 4),
                "straddling_timestep_indices": [8, 9],
                "threshold_pu": 1.0,
                "upper_event": True,
                "upper_longest_run_steps": 4,
            },
        ],
        "g2_status": "g2-pending-rule-not-approved",
        "metadata_format": "selective-ac-promotion-metadata-v1",
        "root_seed": root_seed,
        "rule_basis": "endpoint-threshold-straddling-candidate",
        "sample_count": 5,
        "use_status": "synthetic-only",
    }


def _alpha_event_counts() -> tuple[AlphaEventCountRecord, ...]:
    sample_ids = tuple(f"sample-{index}" for index in range(10))
    return (
        AlphaEventCountRecord(
            alpha=0.0,
            lower_successes=1,
            upper_successes=5,
            sample_count=10,
            sample_ids=sample_ids,
        ),
        AlphaEventCountRecord(
            alpha=0.5,
            lower_successes=2,
            upper_successes=4,
            sample_count=10,
            sample_ids=sample_ids,
        ),
        AlphaEventCountRecord(
            alpha=1.0,
            lower_successes=3,
            upper_successes=3,
            sample_count=10,
            sample_ids=sample_ids,
        ),
    )


def _alpha_endpoint_metadata() -> dict[str, object]:
    return {
        "a013_grid_error_approval_id": "A-013-synthetic-blocked",
        "a016_scenario_consistency_id": "A-016-synthetic-blocked",
        "capacity_convention_linkage": "capacity-convention-synthetic-blocked",
        "capacity_denominator_provenance": "capacity-provenance-synthetic-blocked",
        "direction_gate": "unwidened_p_net_import_mask",
        "endpoint_record_manifest_id": "synthetic-endpoint-records",
        "error_sampling": OUTPUT_ERROR_SAMPLING,
        "g2_tier1_envelope_approval_id": "G2-synthetic-blocked",
        "loading_endpoint_application": OUTPUT_ERROR_APPLICATION,
        "probability_widening": "forbidden",
    }


def _output_error_endpoint_count_metadata() -> dict[str, object]:
    metadata = _alpha_endpoint_metadata()
    metadata.update(
        {
            "a013_grid_error_approval_status": OUTPUT_ERROR_ENDPOINT_COUNT_BLOCKED_STATUS,
            "a016_scenario_consistency_status": OUTPUT_ERROR_ENDPOINT_COUNT_BLOCKED_STATUS,
            "capacity_convention_status": OUTPUT_ERROR_ENDPOINT_COUNT_BLOCKED_STATUS,
            "dependence_assumption": OUTPUT_ERROR_DEPENDENCE,
            "endpoint_count_provenance": OUTPUT_ERROR_ENDPOINT_COUNT_PROVENANCE,
            "g2_tier1_envelope_approval_status": OUTPUT_ERROR_ENDPOINT_COUNT_BLOCKED_STATUS,
            "lower_composition_formula": OUTPUT_ERROR_LOWER_FORMULA,
            "output_error_protocol": "g1-a2-output-domain-error",
            "upper_composition_formula": OUTPUT_ERROR_UPPER_FORMULA,
        }
    )
    return metadata


def _real_endpoint_count_metadata() -> dict[str, object]:
    return {
        "a013_grid_error_approval_id": "a013-approved-grid-error-record",
        "a016_scenario_consistency_id": "a016-approved-consistency-record",
        "capacity_convention_linkage": "capacity-convention-approved-record",
        "capacity_denominator_provenance": "capacity-denominator-provenance-record",
        "dependence_assumption": OUTPUT_ERROR_DEPENDENCE,
        "direction_gate": "unwidened_p_net_import_mask",
        "endpoint_count_provenance": OUTPUT_ERROR_ENDPOINT_COUNT_PROVENANCE,
        "endpoint_record_manifest_id": "output-error-endpoint-count-manifest-record",
        "error_sampling": OUTPUT_ERROR_SAMPLING,
        "g2_tier1_envelope_approval_id": "g2-approved-tier1-endpoint-record",
        "loading_endpoint_application": OUTPUT_ERROR_APPLICATION,
        "lower_composition_formula": OUTPUT_ERROR_LOWER_FORMULA,
        "output_error_protocol": "g1-a2-output-domain-error",
        "probability_widening": "forbidden",
        "upper_composition_formula": OUTPUT_ERROR_UPPER_FORMULA,
    }


def _real_endpoint_count_approval_ids() -> dict[str, object]:
    metadata = _real_endpoint_count_metadata()
    return {
        "a013_grid_error_approval_id": metadata["a013_grid_error_approval_id"],
        "a016_scenario_consistency_id": metadata["a016_scenario_consistency_id"],
        "capacity_convention_approval_id": "capacity-convention-approved-record",
        "g2_tier1_envelope_approval_id": metadata[
            "g2_tier1_envelope_approval_id"
        ],
    }


def _real_endpoint_count_artifact_references() -> dict[str, object]:
    metadata = _real_endpoint_count_metadata()
    return {
        "capacity_convention_linkage": metadata["capacity_convention_linkage"],
        "capacity_denominator_provenance": metadata[
            "capacity_denominator_provenance"
        ],
        "loading_trajectory_manifest_id": "loading-trajectory-manifest-record",
        "output_error_endpoint_count_manifest_id": metadata[
            "endpoint_record_manifest_id"
        ],
    }


def _real_endpoint_count_threshold_semantics() -> dict[str, object]:
    return {
        "comparator": "strict_greater_than",
        "direction_gate": "unwidened_p_net_import_mask",
        "event_scope": "full_planning_year",
        "min_consecutive_steps": 4,
        "threshold_pu": 1.0,
        "timestep_seconds": 900,
    }


def test_alpha_probability_rows_are_recomputed_from_event_counts() -> None:
    rows = probability_rows_from_alpha_event_counts(_alpha_event_counts())

    assert [row["alpha"] for row in rows] == [0.0, 0.5, 1.0]
    assert [row["p_lower"] for row in rows] == [0.1, 0.2, 0.3]
    assert [row["p_upper"] for row in rows] == [0.5, 0.4, 0.3]
    assert all(row["sample_count"] == 10 for row in rows)
    assert all("defuzzified_probability" not in row for row in rows)
    assert (
        rows[0]["ci_lower_lower"]
        <= rows[0]["p_lower"]
        <= rows[0]["ci_lower_upper"]
    )
    assert (
        rows[0]["ci_upper_lower"]
        <= rows[0]["p_upper"]
        <= rows[0]["ci_upper_upper"]
    )


def test_alpha_probability_estimator_packet_records_real_use_blockers() -> None:
    packet = build_alpha_probability_estimator_packet(
        packet_id="synthetic-alpha-count-estimator",
        event_count_records=_alpha_event_counts(),
        endpoint_metadata=_alpha_endpoint_metadata(),
    )
    payload = packet.to_mapping()

    assert payload["protocol"] == "e4s1-alpha-event-count-estimator-v1"
    assert payload["use_status"] == "synthetic-estimator-readiness"
    assert payload["invariants"]["defuzzification"] == "forbidden"
    assert payload["invariants"]["probability_widening"] == "forbidden"
    blockers = payload["real_use_blocker_manifest"]["blockers"]
    assert "missing_real_endpoint_event_manifests" in blockers
    assert "missing_signed_g2_tier1_endpoints" in blockers
    assert "missing_signed_a013_grid_error" in blockers
    assert "missing_capacity_convention_and_provenance" in blockers
    assert "missing_a016_scenario_consistency" in blockers
    assert "missing_g3_monotonicity_approval_if_vertex_shortcut_claimed" in blockers
    assert "defuzzified_probability" not in str(payload)
    assert_alpha_probability_estimator_packet(payload)


def test_alpha_probability_estimator_rejects_sample_count_or_identity_mismatch() -> None:
    records = list(_alpha_event_counts())
    sample_ids = tuple(f"sample-{index}" for index in range(8))
    records[1] = AlphaEventCountRecord(
        alpha=0.5,
        lower_successes=2,
        upper_successes=4,
        sample_count=8,
        sample_ids=sample_ids,
    )
    with pytest.raises(ValueError, match="same sample_count"):
        probability_rows_from_alpha_event_counts(records)

    records = list(_alpha_event_counts())
    records[1] = AlphaEventCountRecord(
        alpha=0.5,
        lower_successes=2,
        upper_successes=4,
        sample_count=10,
        sample_ids=tuple(reversed(records[1].sample_ids)),
    )
    with pytest.raises(ValueError, match="same ordered sample_ids"):
        probability_rows_from_alpha_event_counts(records)


def test_alpha_probability_estimator_rejects_non_nested_rows_when_required() -> None:
    records = list(_alpha_event_counts())
    records[1] = AlphaEventCountRecord(
        alpha=0.5,
        lower_successes=0,
        upper_successes=6,
        sample_count=10,
        sample_ids=records[1].sample_ids,
    )

    with pytest.raises(ValueError, match="nested"):
        probability_rows_from_alpha_event_counts(records)
    rows = probability_rows_from_alpha_event_counts(records, require_nested=False)
    assert rows[1]["p_lower"] == 0.0
    assert rows[1]["p_upper"] == 0.6


def test_alpha_probability_estimator_rejects_missing_endpoint_metadata_or_relabeling() -> None:
    metadata = _alpha_endpoint_metadata()
    metadata.pop("endpoint_record_manifest_id")
    with pytest.raises(ValueError, match="endpoint_metadata"):
        build_alpha_probability_estimator_packet(
            packet_id="missing-endpoint-metadata",
            event_count_records=_alpha_event_counts(),
            endpoint_metadata=metadata,
        )

    payload = build_alpha_probability_estimator_packet(
        packet_id="synthetic-alpha-count-estimator",
        event_count_records=_alpha_event_counts(),
        endpoint_metadata=_alpha_endpoint_metadata(),
    ).to_mapping()
    payload["use_status"] = "paper-facing"
    with pytest.raises(ValueError, match="synthetic-only"):
        assert_alpha_probability_estimator_packet(payload)


def test_alpha_probability_estimator_rejects_collapsed_or_tampered_payloads() -> None:
    payload = build_alpha_probability_estimator_packet(
        packet_id="synthetic-alpha-count-estimator",
        event_count_records=_alpha_event_counts(),
        endpoint_metadata=_alpha_endpoint_metadata(),
    ).to_mapping()

    collapsed = dict(payload)
    collapsed["defuzzified_probability"] = 0.25
    with pytest.raises(ValueError, match="collapsed"):
        assert_alpha_probability_estimator_packet(collapsed)

    tampered_rows = dict(payload)
    probability_rows = [dict(row) for row in payload["probability_rows"]]
    probability_rows[0]["p_upper"] = 0.9
    tampered_rows["probability_rows"] = probability_rows
    with pytest.raises(ValueError, match="recomputable"):
        assert_alpha_probability_estimator_packet(tampered_rows)

    tampered_metadata = dict(payload)
    endpoint_metadata = dict(payload["endpoint_metadata"])
    endpoint_metadata["probability_widening"] = "posthoc-margin"
    tampered_metadata["endpoint_metadata"] = endpoint_metadata
    with pytest.raises(ValueError, match="probability widening"):
        assert_alpha_probability_estimator_packet(tampered_metadata)


def test_output_error_endpoint_count_bridge_feeds_alpha_estimator() -> None:
    packet = build_output_error_endpoint_count_bridge_packet(
        packet_id="synthetic-e5-s3-endpoint-count-bridge",
        event_count_records=_alpha_event_counts(),
        endpoint_metadata=_output_error_endpoint_count_metadata(),
    )
    payload = packet.to_mapping()

    assert payload["protocol"] == OUTPUT_ERROR_ENDPOINT_COUNT_BRIDGE_PROTOCOL
    assert payload["use_status"] == "synthetic-output-error-endpoint-count-readiness"
    assert payload["probability_rows"] == payload[
        "alpha_probability_estimator_packet"
    ]["probability_rows"]
    assert [row["p_lower"] for row in payload["probability_rows"]] == [0.1, 0.2, 0.3]
    assert [row["p_upper"] for row in payload["probability_rows"]] == [0.5, 0.4, 0.3]
    assert (
        payload["invariants"]["endpoint_count_provenance"]
        == OUTPUT_ERROR_ENDPOINT_COUNT_PROVENANCE
    )
    assert payload["invariants"]["probability_widening"] == "forbidden"
    assert payload["real_use_blocker_manifest"]["ready_for_real_use"] is False
    blockers = payload["real_use_blocker_manifest"]["blockers"]
    assert "missing_signed_g2_tier1_endpoints" in blockers
    assert "missing_signed_a013_grid_error" in blockers
    assert_output_error_endpoint_count_bridge_packet(payload)


def test_output_error_endpoint_count_bridge_rejects_forbidden_error_semantics() -> None:
    metadata = _output_error_endpoint_count_metadata()
    metadata["probability_widening"] = "posthoc-margin"
    with pytest.raises(ValueError, match="probability widening"):
        build_output_error_endpoint_count_bridge_packet(
            packet_id="probability-margin-bridge",
            event_count_records=_alpha_event_counts(),
            endpoint_metadata=metadata,
        )

    metadata = _output_error_endpoint_count_metadata()
    metadata["error_sampling"] = "independent-random-draws"
    with pytest.raises(ValueError, match="independent error sampling"):
        build_output_error_endpoint_count_bridge_packet(
            packet_id="independent-error-bridge",
            event_count_records=_alpha_event_counts(),
            endpoint_metadata=metadata,
        )

    metadata = _output_error_endpoint_count_metadata()
    metadata["direction_gate"] = "widened_loading_sign"
    with pytest.raises(ValueError, match="unwidened P_net"):
        build_output_error_endpoint_count_bridge_packet(
            packet_id="widened-direction-bridge",
            event_count_records=_alpha_event_counts(),
            endpoint_metadata=metadata,
        )


def test_output_error_endpoint_count_bridge_rejects_missing_or_stale_inputs() -> None:
    metadata = _output_error_endpoint_count_metadata()
    metadata.pop("endpoint_count_provenance")
    with pytest.raises(ValueError, match="endpoint_count_provenance"):
        build_output_error_endpoint_count_bridge_packet(
            packet_id="missing-provenance-bridge",
            event_count_records=_alpha_event_counts(),
            endpoint_metadata=metadata,
        )

    metadata = _output_error_endpoint_count_metadata()
    metadata["a013_grid_error_approval_id"] = "A-013-unsigned"
    with pytest.raises(ValueError, match="stale or unsigned"):
        build_output_error_endpoint_count_bridge_packet(
            packet_id="unsigned-a013-reference-bridge",
            event_count_records=_alpha_event_counts(),
            endpoint_metadata=metadata,
        )

    metadata = _output_error_endpoint_count_metadata()
    metadata["capacity_denominator_provenance"] = "capacity-placeholder"
    with pytest.raises(ValueError, match="stale or unsigned"):
        build_output_error_endpoint_count_bridge_packet(
            packet_id="placeholder-capacity-reference-bridge",
            event_count_records=_alpha_event_counts(),
            endpoint_metadata=metadata,
        )

    metadata = _output_error_endpoint_count_metadata()
    metadata["a016_scenario_consistency_id"] = "A-016-proposed"
    with pytest.raises(ValueError, match="stale or unsigned"):
        build_output_error_endpoint_count_bridge_packet(
            packet_id="proposed-a016-reference-bridge",
            event_count_records=_alpha_event_counts(),
            endpoint_metadata=metadata,
        )

    metadata = _output_error_endpoint_count_metadata()
    metadata["a013_grid_error_approval_status"] = "signed"
    with pytest.raises(ValueError, match="blocked-pending-real-inputs"):
        build_output_error_endpoint_count_bridge_packet(
            packet_id="stale-a013-status-bridge",
            event_count_records=_alpha_event_counts(),
            endpoint_metadata=metadata,
        )

    metadata = _output_error_endpoint_count_metadata()
    metadata["g2_tier1_envelope_approval_status"] = "signed"
    with pytest.raises(ValueError, match="blocked-pending-real-inputs"):
        build_output_error_endpoint_count_bridge_packet(
            packet_id="stale-g2-status-bridge",
            event_count_records=_alpha_event_counts(),
            endpoint_metadata=metadata,
        )


def test_output_error_endpoint_count_bridge_rejects_relabeling_or_tampering() -> None:
    payload = build_output_error_endpoint_count_bridge_packet(
        packet_id="synthetic-e5-s3-endpoint-count-bridge",
        event_count_records=_alpha_event_counts(),
        endpoint_metadata=_output_error_endpoint_count_metadata(),
    ).to_mapping()

    relabeled = dict(payload)
    relabeled["use_status"] = "paper-facing"
    with pytest.raises(ValueError, match="remain synthetic"):
        assert_output_error_endpoint_count_bridge_packet(relabeled)

    collapsed = dict(payload)
    collapsed["probability_margin_widening"] = 0.05
    with pytest.raises(ValueError, match="collapsed"):
        assert_output_error_endpoint_count_bridge_packet(collapsed)

    tampered = dict(payload)
    rows = [dict(row) for row in payload["probability_rows"]]
    rows[0]["p_upper"] = 0.9
    tampered["probability_rows"] = rows
    with pytest.raises(
        ValueError,
        match="alpha estimator packet|supplied by the alpha estimator",
    ):
        assert_output_error_endpoint_count_bridge_packet(tampered)

    tampered_blockers = dict(payload)
    blocker_manifest = dict(payload["real_use_blocker_manifest"])
    blocker_manifest["blockers"] = []
    tampered_blockers["real_use_blocker_manifest"] = blocker_manifest
    with pytest.raises(ValueError, match="real_use_blocker_manifest"):
        assert_output_error_endpoint_count_bridge_packet(tampered_blockers)


def test_real_output_error_endpoint_count_preflight_accepts_structural_fixture() -> None:
    preflight = build_real_output_error_endpoint_count_manifest_preflight(
        manifest_id="real-endpoint-count-preflight-fixture",
        alpha_grid=[0.0, 0.5, 1.0],
        event_count_records=_alpha_event_counts(),
        endpoint_metadata=_real_endpoint_count_metadata(),
        approval_ids=_real_endpoint_count_approval_ids(),
        artifact_references=_real_endpoint_count_artifact_references(),
        threshold_semantics=_real_endpoint_count_threshold_semantics(),
    )
    payload = preflight.to_mapping()

    assert (
        payload["manifest_protocol"]
        == REAL_OUTPUT_ERROR_ENDPOINT_COUNT_MANIFEST_PROTOCOL
    )
    assert payload["ready_for_real_use"] is False
    assert payload["probability_rows"] == payload[
        "alpha_probability_estimator_packet"
    ]["probability_rows"]
    assert [row["p_lower"] for row in payload["probability_rows"]] == [0.1, 0.2, 0.3]
    assert [row["p_upper"] for row in payload["probability_rows"]] == [0.5, 0.4, 0.3]
    blocker_keys = payload["blocker_manifest"]["blocker_keys"]
    assert "missing_signed_g2_tier1_endpoints" in blocker_keys
    assert "missing_signed_a013_grid_error" in blocker_keys
    assert "defuzzified_probability" not in str(payload)
    assert_real_output_error_endpoint_count_manifest_preflight(payload)


def test_real_output_error_endpoint_count_preflight_rejects_missing_or_stale_ids() -> None:
    approval_ids = _real_endpoint_count_approval_ids()
    approval_ids.pop("g2_tier1_envelope_approval_id")
    with pytest.raises(ValueError, match="g2_tier1_envelope_approval_id"):
        build_real_output_error_endpoint_count_manifest_preflight(
            manifest_id="missing-g2-real-endpoint-preflight",
            alpha_grid=[0.0, 0.5, 1.0],
            event_count_records=_alpha_event_counts(),
            endpoint_metadata=_real_endpoint_count_metadata(),
            approval_ids=approval_ids,
            artifact_references=_real_endpoint_count_artifact_references(),
            threshold_semantics=_real_endpoint_count_threshold_semantics(),
        )

    approval_ids = _real_endpoint_count_approval_ids()
    approval_ids["a013_grid_error_approval_id"] = "A-013-proposed-packet"
    with pytest.raises(ValueError, match="stale or unsigned"):
        build_real_output_error_endpoint_count_manifest_preflight(
            manifest_id="stale-a013-real-endpoint-preflight",
            alpha_grid=[0.0, 0.5, 1.0],
            event_count_records=_alpha_event_counts(),
            endpoint_metadata=_real_endpoint_count_metadata(),
            approval_ids=approval_ids,
            artifact_references=_real_endpoint_count_artifact_references(),
            threshold_semantics=_real_endpoint_count_threshold_semantics(),
        )

    metadata = _real_endpoint_count_metadata()
    metadata["a013_grid_error_approval_status"] = "proposed"
    with pytest.raises(ValueError, match="stale or unsigned"):
        build_real_output_error_endpoint_count_manifest_preflight(
            manifest_id="stale-status-real-endpoint-preflight",
            alpha_grid=[0.0, 0.5, 1.0],
            event_count_records=_alpha_event_counts(),
            endpoint_metadata=metadata,
            approval_ids=_real_endpoint_count_approval_ids(),
            artifact_references=_real_endpoint_count_artifact_references(),
            threshold_semantics=_real_endpoint_count_threshold_semantics(),
        )


def test_real_output_error_endpoint_count_preflight_rejects_scalar_or_tampered_payload() -> None:
    payload = build_real_output_error_endpoint_count_manifest_preflight(
        manifest_id="real-endpoint-count-preflight-fixture",
        alpha_grid=[0.0, 0.5, 1.0],
        event_count_records=_alpha_event_counts(),
        endpoint_metadata=_real_endpoint_count_metadata(),
        approval_ids=_real_endpoint_count_approval_ids(),
        artifact_references=_real_endpoint_count_artifact_references(),
        threshold_semantics=_real_endpoint_count_threshold_semantics(),
    ).to_mapping()

    collapsed = dict(payload)
    collapsed["defuzzified_probability"] = 0.25
    with pytest.raises(ValueError, match="collapsed"):
        assert_real_output_error_endpoint_count_manifest_preflight(collapsed)

    relabeled = dict(payload)
    relabeled["use_status"] = "paper-facing"
    with pytest.raises(ValueError, match="cannot be relabeled"):
        assert_real_output_error_endpoint_count_manifest_preflight(relabeled)

    tampered_rows = dict(payload)
    rows = [dict(row) for row in payload["probability_rows"]]
    rows[0]["p_upper"] = 0.9
    tampered_rows["probability_rows"] = rows
    with pytest.raises(ValueError, match="alpha estimator|probability_rows"):
        assert_real_output_error_endpoint_count_manifest_preflight(tampered_rows)

    tampered_blockers = dict(payload)
    blocker_manifest = dict(payload["blocker_manifest"])
    blocker_manifest["ready_for_real_use"] = True
    tampered_blockers["blocker_manifest"] = blocker_manifest
    with pytest.raises(ValueError, match="blocker_manifest"):
        assert_real_output_error_endpoint_count_manifest_preflight(tampered_blockers)


def test_real_output_error_endpoint_count_preflight_rejects_alpha_or_crn_violations() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        build_real_output_error_endpoint_count_manifest_preflight(
            manifest_id="unordered-alpha-real-endpoint-preflight",
            alpha_grid=[0.0, 1.0, 0.5],
            event_count_records=_alpha_event_counts(),
            endpoint_metadata=_real_endpoint_count_metadata(),
            approval_ids=_real_endpoint_count_approval_ids(),
            artifact_references=_real_endpoint_count_artifact_references(),
            threshold_semantics=_real_endpoint_count_threshold_semantics(),
        )

    with pytest.raises(ValueError, match="alpha_grid"):
        build_real_output_error_endpoint_count_manifest_preflight(
            manifest_id="mismatched-alpha-real-endpoint-preflight",
            alpha_grid=[0.0, 0.25, 1.0],
            event_count_records=_alpha_event_counts(),
            endpoint_metadata=_real_endpoint_count_metadata(),
            approval_ids=_real_endpoint_count_approval_ids(),
            artifact_references=_real_endpoint_count_artifact_references(),
            threshold_semantics=_real_endpoint_count_threshold_semantics(),
        )

    records = list(_alpha_event_counts())
    records[1] = AlphaEventCountRecord(
        alpha=0.5,
        lower_successes=2,
        upper_successes=4,
        sample_count=10,
        sample_ids=tuple(reversed(records[1].sample_ids)),
    )
    with pytest.raises(ValueError, match="same ordered sample_ids"):
        build_real_output_error_endpoint_count_manifest_preflight(
            manifest_id="crn-mismatch-real-endpoint-preflight",
            alpha_grid=[0.0, 0.5, 1.0],
            event_count_records=records,
            endpoint_metadata=_real_endpoint_count_metadata(),
            approval_ids=_real_endpoint_count_approval_ids(),
            artifact_references=_real_endpoint_count_artifact_references(),
            threshold_semantics=_real_endpoint_count_threshold_semantics(),
        )


def test_real_output_error_endpoint_count_preflight_rejects_forbidden_semantics() -> None:
    metadata = _real_endpoint_count_metadata()
    metadata["probability_widening"] = "posthoc-margin"
    with pytest.raises(ValueError, match="probability widening"):
        build_real_output_error_endpoint_count_manifest_preflight(
            manifest_id="probability-widening-real-endpoint-preflight",
            alpha_grid=[0.0, 0.5, 1.0],
            event_count_records=_alpha_event_counts(),
            endpoint_metadata=metadata,
            approval_ids=_real_endpoint_count_approval_ids(),
            artifact_references=_real_endpoint_count_artifact_references(),
            threshold_semantics=_real_endpoint_count_threshold_semantics(),
        )

    metadata = _real_endpoint_count_metadata()
    metadata["error_sampling"] = "independent-random-draws"
    with pytest.raises(ValueError, match="independent error sampling"):
        build_real_output_error_endpoint_count_manifest_preflight(
            manifest_id="independent-sampling-real-endpoint-preflight",
            alpha_grid=[0.0, 0.5, 1.0],
            event_count_records=_alpha_event_counts(),
            endpoint_metadata=metadata,
            approval_ids=_real_endpoint_count_approval_ids(),
            artifact_references=_real_endpoint_count_artifact_references(),
            threshold_semantics=_real_endpoint_count_threshold_semantics(),
        )

    threshold = _real_endpoint_count_threshold_semantics()
    threshold["direction_gate"] = "widened_loading_sign"
    with pytest.raises(ValueError, match="unwidened P_net"):
        build_real_output_error_endpoint_count_manifest_preflight(
            manifest_id="widened-direction-real-endpoint-preflight",
            alpha_grid=[0.0, 0.5, 1.0],
            event_count_records=_alpha_event_counts(),
            endpoint_metadata=_real_endpoint_count_metadata(),
            approval_ids=_real_endpoint_count_approval_ids(),
            artifact_references=_real_endpoint_count_artifact_references(),
            threshold_semantics=threshold,
        )

    threshold = _real_endpoint_count_threshold_semantics()
    threshold["threshold_pu"] = 1.1
    with pytest.raises(ValueError, match="G0-A3"):
        build_real_output_error_endpoint_count_manifest_preflight(
            manifest_id="wrong-threshold-real-endpoint-preflight",
            alpha_grid=[0.0, 0.5, 1.0],
            event_count_records=_alpha_event_counts(),
            endpoint_metadata=_real_endpoint_count_metadata(),
            approval_ids=_real_endpoint_count_approval_ids(),
            artifact_references=_real_endpoint_count_artifact_references(),
            threshold_semantics=threshold,
        )


def test_probability_rows_from_pbox_family_are_sorted_alpha_indexed_bounds() -> None:
    rows = probability_rows_from_pbox_family(_pbox_family())

    assert [row["alpha"] for row in rows] == [0.0, 0.5]
    assert rows[0]["p_lower"] == 0.10
    assert rows[0]["p_upper"] == 0.30
    assert rows[0]["vertex_use_mode"] == "pre-g3-synthetic"
    assert "p_hat" not in rows[0]
    assert "defuzzified_probability" not in rows[0]


def test_synthetic_guarded_report_serializes_blocked_prerequisites() -> None:
    report = build_guarded_pbox_report(
        pbox_family=_pbox_family(),
        prerequisites=FinalResultPrerequisites(),
    )

    payload = report.to_mapping()

    assert payload["use_status"] == "synthetic-only"
    assert payload["guard"]["allowed"] is False
    assert "G2 Tier-1 envelope/adequacy approval" in payload["guard"]["missing_prerequisites"]
    assert len(payload["probability_rows"]) == 2


def test_paper_facing_report_rejects_missing_prerequisites() -> None:
    with pytest.raises(RuntimeError, match="signed A-013"):
        build_guarded_pbox_report(
            pbox_family=_pbox_family(),
            prerequisites=FinalResultPrerequisites(),
            use_status="paper-facing",
            output_error_record=_output_error_record(),
        )


def test_paper_facing_report_requires_endpoint_record_even_when_gates_are_supplied() -> None:
    with pytest.raises(RuntimeError, match="output-error endpoint records"):
        build_guarded_pbox_report(
            pbox_family=_pbox_family(),
            prerequisites=_complete_prerequisites(),
            use_status="paper-facing",
        )


def test_paper_facing_report_accepts_complete_guarded_fixture() -> None:
    report = build_guarded_pbox_report(
        pbox_family=_pbox_family(),
        prerequisites=_complete_prerequisites(),
        use_status="paper-facing",
        output_error_record=_output_error_record(),
    )

    payload = report.to_mapping()

    assert payload["guard"]["allowed"] is True
    assert payload["output_error_record"]["probability_widening"] == "forbidden"


def test_runner_report_boundary_accepts_selective_ac_metadata_with_endpoint_record() -> None:
    payload = build_runner_report_boundary_record(
        boundary_id="selective-ac-linked-fixture",
        pbox_family=_pbox_family(),
        prerequisites=_complete_prerequisites(),
        output_error_record=_output_error_record(),
        selective_ac_promotion_metadata=_selective_ac_metadata(),
    ).to_mapping()

    guarded_report = payload["guarded_report"]

    assert "selective_ac_promotion_metadata" in guarded_report
    assert_runner_report_boundary_payload(payload)


def test_selective_ac_metadata_requires_output_error_record() -> None:
    with pytest.raises(ValueError, match="requires output_error_record"):
        build_runner_report_boundary_record(
            boundary_id="selective-ac-without-endpoints",
            pbox_family=_pbox_family(),
            prerequisites=FinalResultPrerequisites(),
            selective_ac_promotion_metadata=_selective_ac_metadata(),
        )


def test_selective_ac_metadata_alpha_grid_must_match_probability_rows() -> None:
    metadata = _selective_ac_metadata()
    metadata["alpha_grid"] = [0.0, 0.25, 0.5]

    with pytest.raises(ValueError, match="alpha_grid"):
        build_runner_report_boundary_record(
            boundary_id="selective-ac-alpha-mismatch",
            pbox_family=_pbox_family(),
            prerequisites=_complete_prerequisites(),
            output_error_record=_output_error_record(),
            selective_ac_promotion_metadata=metadata,
        )


def test_selective_ac_metadata_sample_count_must_match_endpoint_record() -> None:
    metadata = _selective_ac_metadata()
    metadata["sample_count"] = 6

    with pytest.raises(ValueError, match="sample_count"):
        build_runner_report_boundary_record(
            boundary_id="selective-ac-sample-count-mismatch",
            pbox_family=_pbox_family(),
            prerequisites=_complete_prerequisites(),
            output_error_record=_output_error_record(),
            selective_ac_promotion_metadata=metadata,
        )


def test_selective_ac_metadata_candidate_events_must_match_endpoint_record() -> None:
    payload = build_runner_report_boundary_record(
        boundary_id="selective-ac-event-mismatch",
        pbox_family=_pbox_family(),
        prerequisites=_complete_prerequisites(),
        output_error_record=_output_error_record(),
        selective_ac_promotion_metadata=_selective_ac_metadata(),
    ).to_mapping()
    guarded_report = dict(payload["guarded_report"])
    metadata = dict(guarded_report["selective_ac_promotion_metadata"])
    candidate = dict(metadata["candidates"][0])
    candidate["lower_event"] = True
    metadata["candidates"] = [candidate, metadata["candidates"][1]]
    guarded_report["selective_ac_promotion_metadata"] = metadata

    with pytest.raises(ValueError, match="lower_event must match endpoint record"):
        assert_runner_report_boundary_payload({**payload, "guarded_report": guarded_report})


def test_output_error_record_rejects_missing_envelope_config_fields() -> None:
    record = _output_error_record()
    config = dict(record["config"])
    config.pop("a013_grid_error_approval_id")

    with pytest.raises(ValueError, match="a013_grid_error_approval_id"):
        build_guarded_pbox_report(
            pbox_family=_pbox_family(),
            prerequisites=_complete_prerequisites(),
            output_error_record={**record, "config": config},
        )


def test_output_error_record_rejects_non_g1_a2_formula() -> None:
    record = _output_error_record()
    config = dict(record["config"])
    config["composition_formula"] = {
        "lower": "L_lower=L_T1-epsilon",
        "upper": OUTPUT_ERROR_UPPER_FORMULA,
    }

    with pytest.raises(ValueError, match="composition_formula"):
        build_guarded_pbox_report(
            pbox_family=_pbox_family(),
            prerequisites=_complete_prerequisites(),
            output_error_record={**record, "config": config},
        )


def test_output_error_record_rejects_probability_widening_or_independent_sampling() -> None:
    record = _output_error_record()
    config = dict(record["config"])
    config["probability_widening"] = "posthoc-margin"

    with pytest.raises(ValueError, match="probability widening"):
        build_guarded_pbox_report(
            pbox_family=_pbox_family(),
            prerequisites=_complete_prerequisites(),
            output_error_record={**record, "config": config},
        )

    config = dict(record["config"])
    config["error_sampling"] = "independent-random-draws"
    with pytest.raises(ValueError, match="independent error sampling"):
        build_guarded_pbox_report(
            pbox_family=_pbox_family(),
            prerequisites=_complete_prerequisites(),
            output_error_record={**record, "config": config},
        )


def test_output_error_record_rejects_post_event_application_or_widened_direction_gate() -> None:
    record = _output_error_record()
    config = dict(record["config"])
    config["error_application"] = "probability_margin_after_event_detection"

    with pytest.raises(ValueError, match="before event detection"):
        build_guarded_pbox_report(
            pbox_family=_pbox_family(),
            prerequisites=_complete_prerequisites(),
            output_error_record={**record, "config": config},
        )

    config = dict(record["config"])
    event_semantics = dict(config["event_semantics"])
    event_semantics["direction_gate"] = "widened_loading_sign"
    config["event_semantics"] = event_semantics
    with pytest.raises(ValueError, match="unwidened P_net"):
        build_guarded_pbox_report(
            pbox_family=_pbox_family(),
            prerequisites=_complete_prerequisites(),
            output_error_record={**record, "config": config},
        )

def test_output_error_record_must_forbid_probability_widening() -> None:
    with pytest.raises(ValueError, match="probability_widening='forbidden'"):
        build_guarded_pbox_report(
            pbox_family=_pbox_family(),
            prerequisites=_complete_prerequisites(),
            output_error_record={
                **_output_error_record(),
                "probability_widening": "allowed",
            },
        )


def test_output_error_record_rejects_counts_that_do_not_match_sample_events() -> None:
    record = _output_error_record()
    bad_counts = dict(record["event_count_bounds"])
    bad_counts["upper_successes"] = 2

    with pytest.raises(ValueError, match="endpoint event counts"):
        build_guarded_pbox_report(
            pbox_family=_pbox_family(),
            prerequisites=_complete_prerequisites(),
            output_error_record={**record, "event_count_bounds": bad_counts},
        )


def test_output_error_record_rejects_probability_not_derived_from_counts() -> None:
    record = _output_error_record()
    probability_bounds = dict(record["probability_bounds"])
    upper = dict(probability_bounds["upper"])
    upper["probability"] = 0.7
    probability_bounds["upper"] = upper

    with pytest.raises(ValueError, match="successes / sample_count"):
        build_guarded_pbox_report(
            pbox_family=_pbox_family(),
            prerequisites=_complete_prerequisites(),
            output_error_record={**record, "probability_bounds": probability_bounds},
        )


def test_output_error_record_rejects_lower_event_without_upper_event() -> None:
    record = _output_error_record()
    sample_events = [dict(event) for event in record["sample_endpoint_events"]]
    sample_events[0]["lower_event"] = True

    with pytest.raises(ValueError, match="lower_event cannot exceed upper_event"):
        build_guarded_pbox_report(
            pbox_family=_pbox_family(),
            prerequisites=_complete_prerequisites(),
            output_error_record={**record, "sample_endpoint_events": sample_events},
        )


def test_output_error_record_rejects_nonconsecutive_sample_identity() -> None:
    record = _output_error_record()
    sample_events = [dict(event) for event in record["sample_endpoint_events"]]
    sample_events[2]["sample_index"] = 99

    with pytest.raises(ValueError, match="sample_index values"):
        build_guarded_pbox_report(
            pbox_family=_pbox_family(),
            prerequisites=_complete_prerequisites(),
            output_error_record={**record, "sample_endpoint_events": sample_events},
        )


def test_paper_facing_vertex_report_requires_g3_approved_pbox_rows() -> None:
    with pytest.raises(RuntimeError, match="G3-approved"):
        build_guarded_pbox_report(
            pbox_family=_pbox_family(use_mode=VertexUseMode.PRE_G3_SYNTHETIC),
            prerequisites=_complete_prerequisites(g3=True),
            result_kind=PaperFacingResultKind.VERTEX_SHORTCUT,
            use_status="paper-facing",
            output_error_record=_output_error_record(),
        )


def test_paper_facing_vertex_report_accepts_g3_approved_fixture_only_when_guard_allows() -> None:
    report = build_guarded_pbox_report(
        pbox_family=_pbox_family(use_mode=VertexUseMode.G3_APPROVED),
        prerequisites=_complete_prerequisites(g3=True),
        result_kind=PaperFacingResultKind.VERTEX_SHORTCUT,
        use_status="paper-facing",
        output_error_record=_output_error_record(),
    )

    assert report.to_mapping()["guard"]["allowed"] is True


def test_invalid_use_status_is_rejected() -> None:
    with pytest.raises(ValueError, match="use_status"):
        build_guarded_pbox_report(
            pbox_family=_pbox_family(),
            prerequisites=FinalResultPrerequisites(),
            use_status="draft",
        )


def test_runner_report_boundary_serializes_blocked_synthetic_guard_state() -> None:
    record = build_runner_report_boundary_record(
        boundary_id="synthetic-pbox-fixture",
        pbox_family=_pbox_family(),
        prerequisites=FinalResultPrerequisites(),
    )

    payload = record.to_mapping()

    assert payload["boundary_protocol"] == RUNNER_REPORT_BOUNDARY_PROTOCOL
    assert payload["paper_facing_requested"] is False
    assert payload["paper_facing_allowed"] is False
    guard = payload["guarded_report"]["guard"]
    assert "G2 Tier-1 envelope/adequacy approval" in guard["missing_prerequisites"]
    assert "signed A-013 grid-error value" in guard["missing_prerequisites"]
    assert "approved capacity convention" in guard["missing_prerequisites"]
    assert "capacity denominator provenance" in guard["missing_prerequisites"]
    assert "manifested output-error endpoint event records" in guard["missing_prerequisites"]
    assert "manifested A-016 scenario consistency" in guard["missing_prerequisites"]


def test_runner_report_boundary_blocks_paper_facing_without_endpoint_record() -> None:
    with pytest.raises(RuntimeError, match="output-error endpoint records"):
        build_runner_report_boundary_record(
            boundary_id="paper-facing-without-endpoints",
            pbox_family=_pbox_family(),
            prerequisites=_complete_prerequisites(),
            use_status="paper-facing",
        )


def test_runner_report_boundary_blocks_paper_facing_without_scientific_gates() -> None:
    with pytest.raises(RuntimeError, match="G2 Tier-1"):
        build_runner_report_boundary_record(
            boundary_id="paper-facing-without-gates",
            pbox_family=_pbox_family(),
            prerequisites=FinalResultPrerequisites(),
            use_status="paper-facing",
            output_error_record=_output_error_record(),
        )


def test_runner_report_boundary_blocks_vertex_output_without_g3_guard() -> None:
    with pytest.raises(RuntimeError, match="G3 vertex-shortcut approval"):
        build_runner_report_boundary_record(
            boundary_id="vertex-without-g3",
            pbox_family=_pbox_family(use_mode=VertexUseMode.G3_APPROVED),
            prerequisites=_complete_prerequisites(g3=False),
            result_kind=PaperFacingResultKind.VERTEX_SHORTCUT,
            use_status="paper-facing",
            output_error_record=_output_error_record(),
        )


def test_runner_report_boundary_rejects_invalid_protocol_override() -> None:
    report = build_guarded_pbox_report(
        pbox_family=_pbox_family(),
        prerequisites=FinalResultPrerequisites(),
    )

    with pytest.raises(ValueError, match="boundary_protocol"):
        from src.pbox_reporting import RunnerReportBoundaryRecord

        RunnerReportBoundaryRecord(
            boundary_id="bad-protocol",
            guarded_report=report,
            boundary_protocol="unguarded-v0",
        )


def test_runner_report_boundary_accepts_complete_paper_facing_fixture() -> None:
    record = build_runner_report_boundary_record(
        boundary_id="complete-paper-facing-fixture",
        pbox_family=_pbox_family(),
        prerequisites=_complete_prerequisites(),
        use_status="paper-facing",
        output_error_record=_output_error_record(),
    )

    payload = record.to_mapping()

    assert payload["paper_facing_requested"] is True
    assert payload["paper_facing_allowed"] is True
    assert payload["guarded_report"]["output_error_record"]["probability_widening"] == "forbidden"

def test_runner_report_boundary_payload_validator_accepts_synthetic_payload() -> None:
    payload = build_runner_report_boundary_record(
        boundary_id="serialized-synthetic-fixture",
        pbox_family=_pbox_family(),
        prerequisites=FinalResultPrerequisites(),
    ).to_mapping()

    assert_runner_report_boundary_payload(payload)


def test_runner_report_boundary_payload_validator_rejects_missing_guard() -> None:
    payload = build_runner_report_boundary_record(
        boundary_id="missing-guard-fixture",
        pbox_family=_pbox_family(),
        prerequisites=FinalResultPrerequisites(),
    ).to_mapping()
    guarded_report = dict(payload["guarded_report"])
    guarded_report.pop("guard")

    with pytest.raises(ValueError, match="guarded_report is missing fields"):
        assert_runner_report_boundary_payload({**payload, "guarded_report": guarded_report})


def test_runner_report_boundary_payload_validator_rejects_lied_allowed_flag() -> None:
    payload = build_runner_report_boundary_record(
        boundary_id="lied-allowed-fixture",
        pbox_family=_pbox_family(),
        prerequisites=FinalResultPrerequisites(),
    ).to_mapping()

    with pytest.raises(ValueError, match="paper_facing_allowed"):
        assert_runner_report_boundary_payload({**payload, "paper_facing_allowed": True})


def test_runner_report_boundary_payload_validator_rejects_missing_endpoint_record() -> None:
    payload = build_runner_report_boundary_record(
        boundary_id="complete-then-stripped-endpoints",
        pbox_family=_pbox_family(),
        prerequisites=_complete_prerequisites(),
        use_status="paper-facing",
        output_error_record=_output_error_record(),
    ).to_mapping()
    guarded_report = dict(payload["guarded_report"])
    guarded_report.pop("output_error_record")

    with pytest.raises(ValueError, match="output_error_record"):
        assert_runner_report_boundary_payload({**payload, "guarded_report": guarded_report})


def test_runner_report_boundary_payload_validator_rejects_tampered_missing_prerequisites() -> None:
    payload = build_runner_report_boundary_record(
        boundary_id="tampered-prerequisite-fixture",
        pbox_family=_pbox_family(),
        prerequisites=FinalResultPrerequisites(),
    ).to_mapping()
    guarded_report = dict(payload["guarded_report"])
    guard = dict(guarded_report["guard"])
    guard["allowed"] = True
    guarded_report["guard"] = guard

    with pytest.raises(ValueError, match="guard.allowed"):
        assert_runner_report_boundary_payload({**payload, "guarded_report": guarded_report})


def test_runner_report_boundary_payload_validator_rejects_stripped_vertex_mode() -> None:
    payload = build_runner_report_boundary_record(
        boundary_id="vertex-mode-stripped-fixture",
        pbox_family=_pbox_family(use_mode=VertexUseMode.G3_APPROVED),
        prerequisites=_complete_prerequisites(g3=True),
        result_kind=PaperFacingResultKind.VERTEX_SHORTCUT,
        use_status="paper-facing",
        output_error_record=_output_error_record(),
    ).to_mapping()
    guarded_report = dict(payload["guarded_report"])
    row = dict(guarded_report["probability_rows"][0])
    row["vertex_use_mode"] = "pre-g3-synthetic"
    guarded_report["probability_rows"] = [row, *guarded_report["probability_rows"][1:]]

    with pytest.raises(RuntimeError, match="G3-approved vertex rows"):
        assert_runner_report_boundary_payload({**payload, "guarded_report": guarded_report})

def test_boundary_payload_validator_rejects_endpoint_prerequisite_without_record() -> None:
    payload = build_runner_report_boundary_record(
        boundary_id="endpoint-claim-without-record",
        pbox_family=_pbox_family(),
        prerequisites=_complete_prerequisites(),
        use_status="synthetic-only",
    ).to_mapping()

    with pytest.raises(ValueError, match="endpoint-record prerequisite"):
        assert_runner_report_boundary_payload(payload)


def test_boundary_payload_validator_rejects_endpoint_record_when_guard_says_absent() -> None:
    payload = build_runner_report_boundary_record(
        boundary_id="endpoint-record-with-absent-guard-claim",
        pbox_family=_pbox_family(),
        prerequisites=FinalResultPrerequisites(),
        output_error_record=_output_error_record(),
    ).to_mapping()

    with pytest.raises(ValueError, match="endpoint-record prerequisite"):
        assert_runner_report_boundary_payload(payload)


def test_decision_result_boundary_blocks_paper_facing_without_gates() -> None:
    with pytest.raises(RuntimeError, match="G2 Tier-1"):
        build_runner_report_boundary_record(
            boundary_id="decision-without-gates",
            pbox_family=_pbox_family(),
            prerequisites=FinalResultPrerequisites(),
            result_kind=PaperFacingResultKind.DECISION_RESULT,
            use_status="paper-facing",
            output_error_record=_output_error_record(),
        )


def test_decision_result_boundary_requires_endpoint_record_when_paper_facing() -> None:
    with pytest.raises(RuntimeError, match="output-error endpoint records"):
        build_runner_report_boundary_record(
            boundary_id="decision-without-endpoints",
            pbox_family=_pbox_family(),
            prerequisites=_complete_prerequisites(),
            result_kind=PaperFacingResultKind.DECISION_RESULT,
            use_status="paper-facing",
        )


def test_decision_result_boundary_accepts_complete_synthetic_fixture_without_g3() -> None:
    payload = build_runner_report_boundary_record(
        boundary_id="complete-decision-fixture",
        pbox_family=_pbox_family(),
        prerequisites=_complete_prerequisites(g3=False),
        result_kind=PaperFacingResultKind.DECISION_RESULT,
        use_status="paper-facing",
        output_error_record=_output_error_record(),
    ).to_mapping()

    assert payload["paper_facing_allowed"] is True
    assert payload["guarded_report"]["result_kind"] == "decision-result"
    assert_runner_report_boundary_payload(payload)


def test_decision_result_boundary_rejects_tampered_result_kind_mismatch() -> None:
    payload = build_runner_report_boundary_record(
        boundary_id="decision-kind-mismatch",
        pbox_family=_pbox_family(),
        prerequisites=_complete_prerequisites(),
        result_kind=PaperFacingResultKind.DECISION_RESULT,
        use_status="paper-facing",
        output_error_record=_output_error_record(),
    ).to_mapping()
    guarded_report = dict(payload["guarded_report"])
    guarded_report["result_kind"] = "pbox-probability"

    with pytest.raises(ValueError, match="guard result_kind"):
        assert_runner_report_boundary_payload({**payload, "guarded_report": guarded_report})
