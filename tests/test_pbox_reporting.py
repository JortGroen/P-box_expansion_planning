from __future__ import annotations

import pytest

from src.pbox import PBoxAlphaResult, ProbabilityEstimate, VertexUseMode
from src.pbox_reporting import (
    RUNNER_REPORT_BOUNDARY_PROTOCOL,
    assert_runner_report_boundary_payload,
    build_guarded_pbox_report,
    build_runner_report_boundary_record,
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
            "event_semantics": {
                "direction_gate": "unwidened_p_net_import_mask",
                "min_consecutive_steps": 4,
                "threshold_pu": 1.0,
            }
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
