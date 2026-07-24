from __future__ import annotations

import math

import pytest

from src.pbox import PBoxAlphaResult, ProbabilityEstimate, VertexUseMode
from src.pbox_decision_reporting import (
    DecisionReportRow,
    assert_guarded_decision_report_payload,
    build_guarded_decision_report,
)
from src.pbox_reporting import build_runner_report_boundary_record
from src.pbox_result_guards import FinalResultPrerequisites, PaperFacingResultKind


def _estimate(probability: float, successes: int = 1) -> ProbabilityEstimate:
    return ProbabilityEstimate(
        probability=probability,
        ci_lower=max(0.0, probability - 0.05),
        ci_upper=min(1.0, probability + 0.05),
        successes=successes,
        sample_count=10,
    )


def _pbox_family() -> dict[float, PBoxAlphaResult]:
    return {
        0.0: PBoxAlphaResult(
            use_mode=VertexUseMode.PRE_G3_SYNTHETIC,
            alpha=0.0,
            rho_lower=0.0,
            rho_upper=1.0,
            lower=_estimate(0.10),
            upper=_estimate(0.30, successes=3),
        )
    }


def _complete_prerequisites() -> FinalResultPrerequisites:
    return FinalResultPrerequisites(
        g2_tier1_envelope_approved=True,
        a013_grid_error_signed=True,
        capacity_convention_approved=True,
        capacity_denominator_provenance="synthetic-capacity-provenance",
        output_error_endpoint_records_manifested=True,
    )


def _output_error_record() -> dict[str, object]:
    return {
        "config": {"event_semantics": {"direction_gate": "unwidened_p_net_import_mask"}},
        "event_count_bounds": {
            "lower_successes": 0,
            "sample_count": 2,
            "upper_successes": 1,
        },
        "probability_bounds": {
            "lower": {
                "ci_lower": 0.0,
                "ci_upper": 0.5,
                "probability": 0.0,
                "sample_count": 2,
                "successes": 0,
            },
            "upper": {
                "ci_lower": 0.1,
                "ci_upper": 0.9,
                "probability": 0.5,
                "sample_count": 2,
                "successes": 1,
            },
        },
        "probability_widening": "forbidden",
        "sample_endpoint_events": [
            {"sample_index": 0, "lower_event": False, "upper_event": False},
            {"sample_index": 1, "lower_event": False, "upper_event": True},
        ],
    }


def _decision_boundary(*, use_status: str = "synthetic-only", complete: bool = False):
    return build_runner_report_boundary_record(
        boundary_id="synthetic-decision-boundary",
        pbox_family=_pbox_family(),
        prerequisites=_complete_prerequisites() if complete else FinalResultPrerequisites(),
        result_kind=PaperFacingResultKind.DECISION_RESULT,
        use_status=use_status,
        output_error_record=_output_error_record() if complete else None,
    ).to_mapping()


def _decision_rows() -> tuple[DecisionReportRow, ...]:
    return (
        DecisionReportRow(
            alpha=0.0,
            metric_name="rho_star",
            lower_value=0.2,
            upper_value=0.6,
            classification="overlapping-monitor",
        ),
    )


def test_guarded_decision_report_accepts_blocked_synthetic_boundary() -> None:
    report = build_guarded_decision_report(
        boundary_payload=_decision_boundary(),
        decision_rows=_decision_rows(),
        report_id="synthetic-decision-report",
    )

    payload = report.to_mapping()

    assert payload["use_status"] == "synthetic-only"
    assert payload["paper_facing_allowed"] is False
    assert payload["decision_rows"][0]["metric_name"] == "rho_star"
    assert_guarded_decision_report_payload(payload)


def test_paper_facing_decision_report_requires_allowed_decision_boundary() -> None:
    with pytest.raises(RuntimeError, match="blocked by"):
        build_guarded_decision_report(
            boundary_payload=_decision_boundary(use_status="paper-facing"),
            decision_rows=_decision_rows(),
            report_id="blocked-paper-facing-decision",
            use_status="paper-facing",
        )


def test_paper_facing_decision_report_accepts_complete_guarded_boundary() -> None:
    report = build_guarded_decision_report(
        boundary_payload=_decision_boundary(use_status="paper-facing", complete=True),
        decision_rows=_decision_rows(),
        report_id="complete-paper-facing-decision",
        use_status="paper-facing",
    )

    payload = report.to_mapping()

    assert payload["paper_facing_allowed"] is True
    assert_guarded_decision_report_payload(payload)


def test_decision_report_rejects_probability_boundary_kind() -> None:
    probability_boundary = build_runner_report_boundary_record(
        boundary_id="probability-boundary",
        pbox_family=_pbox_family(),
        prerequisites=FinalResultPrerequisites(),
    ).to_mapping()

    with pytest.raises(ValueError, match="decision-result boundary"):
        build_guarded_decision_report(
            boundary_payload=probability_boundary,
            decision_rows=_decision_rows(),
            report_id="wrong-boundary-kind",
        )


def test_decision_report_rejects_use_status_mismatch() -> None:
    with pytest.raises(ValueError, match="use_status"):
        build_guarded_decision_report(
            boundary_payload=_decision_boundary(),
            decision_rows=_decision_rows(),
            report_id="use-status-mismatch",
            use_status="paper-facing",
        )


def test_decision_rows_preserve_alpha_indexed_lower_upper_bounds() -> None:
    never = DecisionReportRow(
        alpha=1.0,
        metric_name="rho_star",
        lower_value=math.inf,
        upper_value=math.inf,
        classification="never-satisfied",
    )

    assert never.to_mapping()["upper_value"] == math.inf

    with pytest.raises(ValueError, match="lower_value"):
        DecisionReportRow(
            alpha=0.0,
            metric_name="rho_star",
            lower_value=math.inf,
            upper_value=math.inf,
            classification="inside-envelope",
        )

    with pytest.raises(ValueError, match="lower_value must be <= upper_value"):
        DecisionReportRow(
            alpha=0.0,
            metric_name="rho_star",
            lower_value=0.8,
            upper_value=0.4,
            classification="outside-envelope",
        )


def test_decision_payload_rejects_collapsed_or_tampered_rows() -> None:
    payload = build_guarded_decision_report(
        boundary_payload=_decision_boundary(),
        decision_rows=_decision_rows(),
        report_id="serialized-decision-report",
    ).to_mapping()

    for field in (
        "defuzzified_probability",
        "expected_probability",
        "mean_probability",
        "p_hat",
        "p_mid",
        "probability",
        "scalar_decision_probability",
    ):
        bad_row = dict(payload["decision_rows"][0])
        bad_row[field] = 0.2
        with pytest.raises(ValueError, match="collapsed fields"):
            assert_guarded_decision_report_payload({**payload, "decision_rows": [bad_row]})

    with pytest.raises(ValueError, match="paper_facing_allowed"):
        assert_guarded_decision_report_payload({**payload, "paper_facing_allowed": True})


def test_decision_payload_rejects_duplicate_alpha_metric_rows() -> None:
    row = _decision_rows()[0]

    with pytest.raises(ValueError, match="strictly increasing"):
        build_guarded_decision_report(
            boundary_payload=_decision_boundary(),
            decision_rows=(row, row),
            report_id="duplicate-decision-rows",
        )


def test_decision_payload_rejects_out_of_order_alpha_metric_rows() -> None:
    rows = (
        DecisionReportRow(
            alpha=0.5,
            metric_name="rho_star",
            lower_value=0.2,
            upper_value=0.6,
            classification="overlapping-monitor",
        ),
        DecisionReportRow(
            alpha=0.0,
            metric_name="rho_star",
            lower_value=0.1,
            upper_value=0.5,
            classification="overlapping-monitor",
        ),
    )

    with pytest.raises(ValueError, match="strictly increasing"):
        build_guarded_decision_report(
            boundary_payload=_decision_boundary(),
            decision_rows=rows,
            report_id="out-of-order-decision-rows",
        )
