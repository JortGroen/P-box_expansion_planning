from __future__ import annotations

import math
import pytest

from src.pbox_result_guards import (
    FinalResultPrerequisites,
    PaperFacingResultKind,
    assert_alpha_indexed_probability_report,
    assert_paper_facing_allowed,
    evaluate_paper_facing_guard,
)


def _complete_prerequisites(*, g3: bool = False) -> FinalResultPrerequisites:
    return FinalResultPrerequisites(
        g2_tier1_envelope_approved=True,
        a013_grid_error_signed=True,
        capacity_convention_approved=True,
        capacity_denominator_provenance="synthetic-signed-capacity-convention",
        output_error_endpoint_records_manifested=True,
        a016_scenario_consistency_manifested=True,
        g3_vertex_shortcut_approved=g3,
    )


def test_paper_facing_guard_blocks_default_prerequisite_state() -> None:
    report = evaluate_paper_facing_guard(
        PaperFacingResultKind.PBOX_PROBABILITY,
        FinalResultPrerequisites(),
    )

    assert report.allowed is False
    assert report.missing_prerequisites == (
        "G2 Tier-1 envelope/adequacy approval",
        "signed A-013 grid-error value",
        "approved capacity convention",
        "capacity denominator provenance",
        "manifested output-error endpoint event records",
        "manifested A-016 scenario consistency",
    )
    assert report.to_mapping()["result_kind"] == "pbox-probability"

    with pytest.raises(RuntimeError, match="G2 Tier-1"):
        assert_paper_facing_allowed(
            PaperFacingResultKind.PBOX_PROBABILITY,
            FinalResultPrerequisites(),
        )


def test_paper_facing_guard_allows_probability_and_decision_when_shared_gates_are_complete() -> None:
    prerequisites = _complete_prerequisites()

    probability = evaluate_paper_facing_guard(
        PaperFacingResultKind.PBOX_PROBABILITY,
        prerequisites,
    )
    decision = evaluate_paper_facing_guard(
        PaperFacingResultKind.DECISION_RESULT,
        prerequisites,
    )

    assert probability.allowed is True
    assert probability.missing_prerequisites == ()
    assert decision.allowed is True
    assert decision.missing_prerequisites == ()
    assert_paper_facing_allowed(PaperFacingResultKind.DECISION_RESULT, prerequisites)


def test_vertex_shortcut_guard_requires_g3_in_addition_to_model_error_and_capacity_gates() -> None:
    report = evaluate_paper_facing_guard(
        PaperFacingResultKind.VERTEX_SHORTCUT,
        _complete_prerequisites(g3=False),
    )

    assert report.allowed is False
    assert report.missing_prerequisites == ("G3 vertex-shortcut approval",)

    approved = evaluate_paper_facing_guard(
        PaperFacingResultKind.VERTEX_SHORTCUT,
        _complete_prerequisites(g3=True),
    )
    assert approved.allowed is True


def test_paper_facing_guard_rejects_missing_capacity_provenance_even_when_capacity_flag_is_true() -> None:
    report = evaluate_paper_facing_guard(
        PaperFacingResultKind.PBOX_PROBABILITY,
        FinalResultPrerequisites(
            g2_tier1_envelope_approved=True,
            a013_grid_error_signed=True,
            capacity_convention_approved=True,
            capacity_denominator_provenance=" ",
            output_error_endpoint_records_manifested=True,
            a016_scenario_consistency_manifested=True,
        ),
    )

    assert report.allowed is False
    assert report.missing_prerequisites == ("capacity denominator provenance",)


def test_paper_facing_guard_requires_a016_scenario_consistency_manifest() -> None:
    report = evaluate_paper_facing_guard(
        PaperFacingResultKind.PBOX_PROBABILITY,
        FinalResultPrerequisites(
            g2_tier1_envelope_approved=True,
            a013_grid_error_signed=True,
            capacity_convention_approved=True,
            capacity_denominator_provenance="synthetic-signed-capacity-convention",
            output_error_endpoint_records_manifested=True,
        ),
    )

    assert report.allowed is False
    assert report.missing_prerequisites == ("manifested A-016 scenario consistency",)
    assert report.to_mapping()["prerequisites"]["a016_scenario_consistency_manifested"] is False


def test_alpha_indexed_probability_report_accepts_complete_lower_upper_rows() -> None:
    assert_alpha_indexed_probability_report(
        [
            {
                "alpha": 0.0,
                "p_lower": 0.01,
                "p_upper": 0.03,
                "ci_lower_lower": 0.005,
                "ci_lower_upper": 0.02,
                "ci_upper_lower": 0.02,
                "ci_upper_upper": 0.04,
            },
            {
                "alpha": 0.5,
                "p_lower": 0.015,
                "p_upper": 0.025,
                "ci_lower_lower": 0.01,
                "ci_lower_upper": 0.02,
                "ci_upper_lower": 0.02,
                "ci_upper_upper": 0.03,
            },
        ]
    )


def test_alpha_indexed_probability_report_rejects_collapsed_or_invalid_rows() -> None:
    base = {
        "alpha": 0.0,
        "p_lower": 0.01,
        "p_upper": 0.03,
        "ci_lower_lower": 0.005,
        "ci_lower_upper": 0.02,
        "ci_upper_lower": 0.02,
        "ci_upper_upper": 0.04,
    }

    with pytest.raises(ValueError, match="must not be empty"):
        assert_alpha_indexed_probability_report([])

    with pytest.raises(ValueError, match="missing fields"):
        assert_alpha_indexed_probability_report(
            [{k: v for k, v in base.items() if k != "p_upper"}]
        )

    for field in (
        "defuzzified_probability",
        "expected_probability",
        "mean_probability",
        "p_hat",
        "p_mid",
        "probability",
    ):
        with pytest.raises(ValueError, match="collapse"):
            assert_alpha_indexed_probability_report([{**base, field: 0.02}])

    with pytest.raises(ValueError, match="strictly increasing"):
        assert_alpha_indexed_probability_report([base, dict(base)])

    with pytest.raises(ValueError, match="strictly increasing"):
        assert_alpha_indexed_probability_report([{**base, "alpha": 0.5}, base])

    with pytest.raises(ValueError, match="p_lower <= p_upper"):
        assert_alpha_indexed_probability_report([{**base, "p_lower": 0.04}])

    with pytest.raises(ValueError, match="p_upper"):
        assert_alpha_indexed_probability_report([{**base, "p_upper": math.nan}])

    with pytest.raises(ValueError, match="ci_lower bounds"):
        assert_alpha_indexed_probability_report([{**base, "ci_lower_upper": 0.005}])

    with pytest.raises(ValueError, match="ci_upper bounds"):
        assert_alpha_indexed_probability_report([{**base, "ci_upper_lower": 0.04}])


def test_guard_rejects_untyped_result_kind_and_prerequisites() -> None:
    with pytest.raises(TypeError, match="result_kind"):
        FinalResultPrerequisites().missing_for("pbox-probability")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="prerequisites"):
        evaluate_paper_facing_guard(
            PaperFacingResultKind.PBOX_PROBABILITY,
            {},  # type: ignore[arg-type]
        )
