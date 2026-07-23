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
        g3_vertex_shortcut_approved=g3,
    )


def _output_error_record() -> dict[str, object]:
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
            "sample_count": 10,
            "upper_successes": 3,
        },
        "probability_bounds": {
            "lower": {"probability": 0.1},
            "upper": {"probability": 0.3},
        },
        "probability_widening": "forbidden",
        "sample_endpoint_events": [],
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