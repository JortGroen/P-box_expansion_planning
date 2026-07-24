from __future__ import annotations

import pytest

from src.pbox import ProbabilityEstimate
from src.pbox_error import (
    EndpointEventEvaluation,
    OutputErrorAlphaResult,
    OutputErrorProbabilityResult,
)
from src.pbox_error_reporting import (
    OUTPUT_ERROR_SUMMARY_FORMAT,
    assert_output_error_summary_payload,
    build_output_error_summary_table,
    output_error_summary_rows_from_alpha_results,
)


def _estimate(successes: int, sample_count: int) -> ProbabilityEstimate:
    probability = successes / sample_count
    return ProbabilityEstimate(
        probability=probability,
        ci_lower=max(0.0, probability - 0.1),
        ci_upper=min(1.0, probability + 0.1),
        successes=successes,
        sample_count=sample_count,
    )


def _alpha_result(alpha: float, *, lower_successes: int, upper_successes: int, sample_count: int = 4) -> OutputErrorAlphaResult:
    samples = tuple(
        EndpointEventEvaluation(
            sample_index=index,
            lower_event=index < lower_successes,
            upper_event=index < upper_successes,
            lower_episode_count=int(index < lower_successes),
            upper_episode_count=int(index < upper_successes),
            lower_longest_run_steps=4 if index < lower_successes else 0,
            upper_longest_run_steps=4 if index < upper_successes else 0,
        )
        for index in range(sample_count)
    )
    return OutputErrorAlphaResult(
        alpha=alpha,
        probability=OutputErrorProbabilityResult(
            lower=_estimate(lower_successes, sample_count),
            upper=_estimate(upper_successes, sample_count),
            samples=samples,
        ),
    )


def _valid_payload() -> dict[str, object]:
    table = build_output_error_summary_table(
        {
            0.5: _alpha_result(0.5, lower_successes=1, upper_successes=3),
            0.0: _alpha_result(0.0, lower_successes=0, upper_successes=2),
            1.0: _alpha_result(1.0, lower_successes=2, upper_successes=4),
        }
    )
    return table.to_mapping()


def test_summary_rows_preserve_alpha_indexed_endpoint_counts() -> None:
    rows = output_error_summary_rows_from_alpha_results(
        {
            1.0: _alpha_result(1.0, lower_successes=2, upper_successes=4),
            0.0: _alpha_result(0.0, lower_successes=0, upper_successes=2),
        }
    )

    assert [row["alpha"] for row in rows] == [0.0, 1.0]
    assert rows[0]["p_lower"] == 0.0
    assert rows[0]["p_upper"] == 0.5
    assert rows[1]["lower_successes"] == 2
    assert rows[1]["upper_successes"] == 4
    assert {row["probability_widening"] for row in rows} == {"forbidden"}


def test_summary_payload_is_json_stable_and_validated() -> None:
    payload = _valid_payload()

    assert payload["summary_format"] == OUTPUT_ERROR_SUMMARY_FORMAT
    assert payload["use_status"] == "synthetic-only"
    assert_output_error_summary_payload(payload)


@pytest.mark.parametrize(
    "field",
    [
        "defuzzified_probability",
        "expected_probability",
        "mean_probability",
        "p_hat",
        "p_mid",
        "probability",
    ],
)
def test_summary_payload_rejects_collapsed_probability_fields(field: str) -> None:
    payload = _valid_payload()
    payload[field] = 0.5

    with pytest.raises(ValueError, match="collapsed probability"):
        assert_output_error_summary_payload(payload)


def test_summary_row_rejects_collapsed_probability_field() -> None:
    payload = _valid_payload()
    payload["rows"][0]["p_hat"] = 0.5

    with pytest.raises(ValueError, match="collapsed probability"):
        assert_output_error_summary_payload(payload)


def test_summary_payload_rejects_probability_widening() -> None:
    payload = _valid_payload()
    payload["rows"][0]["probability_widening"] = "posthoc-margin"

    with pytest.raises(ValueError, match="probability_widening"):
        assert_output_error_summary_payload(payload)


def test_summary_payload_rejects_probability_not_derived_from_counts() -> None:
    payload = _valid_payload()
    payload["rows"][0]["p_upper"] = 0.75

    with pytest.raises(ValueError, match="p_upper must equal"):
        assert_output_error_summary_payload(payload)


def test_summary_payload_rejects_lower_count_exceeding_upper_count() -> None:
    payload = _valid_payload()
    payload["rows"][0]["lower_successes"] = 3
    payload["rows"][0]["p_lower"] = 0.75

    with pytest.raises(ValueError, match="lower_successes <= upper_successes"):
        assert_output_error_summary_payload(payload)


def test_summary_payload_rejects_mixed_sample_counts_across_alpha_rows() -> None:
    payload = _valid_payload()
    payload["rows"][1]["sample_count"] = 5

    with pytest.raises(ValueError, match="same sample_count"):
        assert_output_error_summary_payload(payload)


def test_summary_payload_rejects_unsorted_or_duplicate_alpha_rows() -> None:
    payload = _valid_payload()
    payload["rows"][1]["alpha"] = 0.0

    with pytest.raises(ValueError, match="strictly increasing alpha"):
        assert_output_error_summary_payload(payload)


def test_summary_builder_rejects_mismatched_alpha_key() -> None:
    with pytest.raises(ValueError, match="mapping key"):
        output_error_summary_rows_from_alpha_results(
            {0.25: _alpha_result(0.5, lower_successes=1, upper_successes=2)}
        )
