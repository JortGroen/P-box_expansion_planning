"""Summary-table helpers for synthetic output-error endpoint probability results.

The helpers in this module are B-owned reporting infrastructure for E5.S3. They
turn alpha-indexed endpoint-count results into JSON-stable rows while preserving
lower/upper bounds and rejecting collapsed probability summaries. They do not
produce paper-facing results or choose any G2/A-013/capacity values.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence

from src.pbox_error import OutputErrorAlphaResult

OUTPUT_ERROR_SUMMARY_FORMAT = "output-error-endpoint-summary-v1"
USE_STATUS_SYNTHETIC_ONLY = "synthetic-only"
_FORBIDDEN_COLLAPSED_FIELDS = frozenset(
    {
        "defuzzified_probability",
        "expected_probability",
        "mean_probability",
        "p_hat",
        "p_mid",
        "probability",
    }
)


@dataclass(frozen=True)
class OutputErrorSummaryTable:
    """Serialized, alpha-indexed endpoint-count summary for E5.S3 scaffolds."""

    rows: tuple[dict[str, object], ...]
    summary_format: str = OUTPUT_ERROR_SUMMARY_FORMAT
    use_status: str = USE_STATUS_SYNTHETIC_ONLY

    def __post_init__(self) -> None:
        if self.summary_format != OUTPUT_ERROR_SUMMARY_FORMAT:
            raise ValueError(f"summary_format must be {OUTPUT_ERROR_SUMMARY_FORMAT!r}")
        if self.use_status != USE_STATUS_SYNTHETIC_ONLY:
            raise ValueError("output-error summaries are synthetic-only until real gates are signed")
        assert_output_error_summary_payload(self.to_mapping())

    def to_mapping(self) -> dict[str, object]:
        """Return a JSON-stable payload for future runner/report surfaces."""

        return {
            "rows": [dict(row) for row in self.rows],
            "summary_format": self.summary_format,
            "use_status": self.use_status,
        }


def output_error_summary_rows_from_alpha_results(
    results_by_alpha: Mapping[float, OutputErrorAlphaResult],
) -> tuple[dict[str, object], ...]:
    """Convert alpha-indexed endpoint-count results into summary-table rows."""

    if not results_by_alpha:
        raise ValueError("results_by_alpha must contain at least one alpha level")
    rows = []
    for alpha, result in sorted(results_by_alpha.items()):
        if result.alpha != alpha:
            raise ValueError("mapping key must match OutputErrorAlphaResult.alpha")
        lower = result.probability.lower
        upper = result.probability.upper
        rows.append(
            {
                "alpha": alpha,
                "ci_lower_lower": lower.ci_lower,
                "ci_lower_upper": lower.ci_upper,
                "ci_upper_lower": upper.ci_lower,
                "ci_upper_upper": upper.ci_upper,
                "lower_successes": lower.successes,
                "p_lower": lower.probability,
                "p_upper": upper.probability,
                "probability_widening": "forbidden",
                "sample_count": lower.sample_count,
                "upper_successes": upper.successes,
            }
        )
    return tuple(rows)


def build_output_error_summary_table(
    results_by_alpha: Mapping[float, OutputErrorAlphaResult],
) -> OutputErrorSummaryTable:
    """Build a validated synthetic-only endpoint summary table."""

    return OutputErrorSummaryTable(
        rows=output_error_summary_rows_from_alpha_results(results_by_alpha)
    )


def assert_output_error_summary_payload(payload: Mapping[str, object]) -> None:
    """Validate a serialized endpoint summary table.

    The validator intentionally rejects single-probability fields so future
    reports cannot replace G1-A2 endpoint event counts with a defuzzified or
    post-hoc widened probability.
    """

    _reject_collapsed_probability_fields(payload, name="summary payload")
    _require_mapping_fields(payload, {"rows", "summary_format", "use_status"}, name="summary payload")
    if payload["summary_format"] != OUTPUT_ERROR_SUMMARY_FORMAT:
        raise ValueError(f"summary_format must be {OUTPUT_ERROR_SUMMARY_FORMAT!r}")
    if payload["use_status"] != USE_STATUS_SYNTHETIC_ONLY:
        raise ValueError("output-error summary payloads are synthetic-only")
    rows = _expect_sequence(payload["rows"], name="rows")
    if len(rows) == 0:
        raise ValueError("rows must not be empty")

    previous_alpha: float | None = None
    expected_sample_count: int | None = None
    for index, raw_row in enumerate(rows):
        row = _expect_mapping(raw_row, name="summary row")
        _validate_summary_row(
            row,
            index=index,
            previous_alpha=previous_alpha,
            expected_sample_count=expected_sample_count,
        )
        previous_alpha = float(row["alpha"])
        sample_count = _expect_positive_int(row["sample_count"], name="sample_count")
        if expected_sample_count is None:
            expected_sample_count = sample_count


def _validate_summary_row(
    row: Mapping[str, object],
    *,
    index: int,
    previous_alpha: float | None,
    expected_sample_count: int | None,
) -> None:
    _reject_collapsed_probability_fields(row, name="summary row")
    required = {
        "alpha",
        "ci_lower_lower",
        "ci_lower_upper",
        "ci_upper_lower",
        "ci_upper_upper",
        "lower_successes",
        "p_lower",
        "p_upper",
        "probability_widening",
        "sample_count",
        "upper_successes",
    }
    _require_mapping_fields(row, required, name="summary row")
    alpha = _expect_probability(row["alpha"], name="alpha")
    if previous_alpha is not None and alpha <= previous_alpha:
        raise ValueError("summary rows must be sorted by strictly increasing alpha")
    if row["probability_widening"] != "forbidden":
        raise ValueError("probability_widening must be 'forbidden'")

    sample_count = _expect_positive_int(row["sample_count"], name="sample_count")
    if expected_sample_count is not None and sample_count != expected_sample_count:
        raise ValueError("all alpha rows must use the same sample_count")
    lower_successes = _expect_nonnegative_int(row["lower_successes"], name="lower_successes")
    upper_successes = _expect_nonnegative_int(row["upper_successes"], name="upper_successes")
    if lower_successes > upper_successes:
        raise ValueError("expected lower_successes <= upper_successes")
    if upper_successes > sample_count:
        raise ValueError("successes cannot exceed sample_count")

    p_lower = _expect_probability(row["p_lower"], name="p_lower")
    p_upper = _expect_probability(row["p_upper"], name="p_upper")
    if p_lower > p_upper:
        raise ValueError("expected p_lower <= p_upper")
    # Event probabilities must be count-derived at each alpha; widening belongs
    # on complete trajectories before event detection, not after estimation.
    if not math.isclose(p_lower, lower_successes / sample_count, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("p_lower must equal lower_successes / sample_count")
    if not math.isclose(p_upper, upper_successes / sample_count, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("p_upper must equal upper_successes / sample_count")

    ci_lower_lower = _expect_probability(row["ci_lower_lower"], name="ci_lower_lower")
    ci_lower_upper = _expect_probability(row["ci_lower_upper"], name="ci_lower_upper")
    ci_upper_lower = _expect_probability(row["ci_upper_lower"], name="ci_upper_lower")
    ci_upper_upper = _expect_probability(row["ci_upper_upper"], name="ci_upper_upper")
    if not ci_lower_lower <= p_lower <= ci_lower_upper:
        raise ValueError("lower confidence interval must contain p_lower")
    if not ci_upper_lower <= p_upper <= ci_upper_upper:
        raise ValueError("upper confidence interval must contain p_upper")
    if index == 0 and alpha < 0.0:
        raise ValueError("alpha must be in [0, 1]")


def _reject_collapsed_probability_fields(mapping: Mapping[str, object], *, name: str) -> None:
    forbidden = sorted(_FORBIDDEN_COLLAPSED_FIELDS.intersection(mapping))
    if forbidden:
        raise ValueError(f"{name} contains collapsed probability fields: {forbidden}")


def _require_mapping_fields(mapping: Mapping[str, object], required: set[str], *, name: str) -> None:
    missing = required.difference(mapping)
    if missing:
        raise ValueError(f"{name} is missing fields: {sorted(missing)}")


def _expect_mapping(value: object, *, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return value


def _expect_sequence(value: object, *, name: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{name} must be a sequence")
    return value


def _expect_probability(value: object, *, name: str) -> float:
    probability = float(value)
    if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
        raise ValueError(f"{name} must be finite and in [0, 1]")
    return probability


def _expect_positive_int(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _expect_nonnegative_int(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
    return value
