"""Guarded reporting records for B-owned p-box outputs.

This module is synthetic/reporting infrastructure only. It gives future runner
or report surfaces a small typed path that combines alpha-indexed p-box rows,
output-error endpoint records, and final-result guards before anything is
allowed to present as paper-facing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from src.pbox import PBoxFamily, VertexUseMode
from src.pbox_result_guards import (
    FinalResultPrerequisites,
    PaperFacingGuardReport,
    PaperFacingResultKind,
    assert_alpha_indexed_probability_report,
    evaluate_paper_facing_guard,
)

UseStatus = str


@dataclass(frozen=True)
class GuardedPBoxReport:
    """Stable report record for alpha-indexed p-box probability rows."""

    result_kind: PaperFacingResultKind
    guard: PaperFacingGuardReport
    probability_rows: tuple[dict[str, object], ...]
    use_status: UseStatus = "synthetic-only"
    output_error_record: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.result_kind, PaperFacingResultKind):
            raise TypeError("result_kind must be a PaperFacingResultKind")
        if self.use_status not in {"synthetic-only", "paper-facing"}:
            raise ValueError("use_status must be 'synthetic-only' or 'paper-facing'")
        assert_alpha_indexed_probability_report(self.probability_rows)
        if self.output_error_record is not None:
            _validate_output_error_record(self.output_error_record)
        if self.use_status == "paper-facing":
            if not self.guard.allowed:
                missing = "; ".join(self.guard.missing_prerequisites)
                raise RuntimeError(
                    f"paper-facing {self.result_kind.value} is blocked by: {missing}"
                )
            if self.output_error_record is None:
                raise RuntimeError(
                    "paper-facing p-box outputs require manifested output-error endpoint records"
                )

    def to_mapping(self) -> dict[str, object]:
        """Return a JSON-stable report/manifest payload."""

        record: dict[str, object] = {
            "guard": self.guard.to_mapping(),
            "probability_rows": [dict(row) for row in self.probability_rows],
            "result_kind": self.result_kind.value,
            "use_status": self.use_status,
        }
        if self.output_error_record is not None:
            record["output_error_record"] = dict(self.output_error_record)
        return record


def probability_rows_from_pbox_family(
    pbox_family: PBoxFamily,
) -> tuple[dict[str, object], ...]:
    """Convert a p-box family to alpha-indexed lower/upper report rows."""

    if not pbox_family:
        raise ValueError("pbox_family must not be empty")
    rows = tuple(
        {
            "alpha": result.alpha,
            "ci_lower_lower": result.lower.ci_lower,
            "ci_lower_upper": result.lower.ci_upper,
            "ci_upper_lower": result.upper.ci_lower,
            "ci_upper_upper": result.upper.ci_upper,
            "p_lower": result.lower.probability,
            "p_upper": result.upper.probability,
            "rho_lower": result.rho_lower,
            "rho_upper": result.rho_upper,
            "vertex_use_mode": result.use_mode.value,
        }
        for result in sorted(pbox_family.values(), key=lambda item: item.alpha)
    )
    assert_alpha_indexed_probability_report(rows)
    return rows


def build_guarded_pbox_report(
    *,
    pbox_family: PBoxFamily,
    prerequisites: FinalResultPrerequisites,
    result_kind: PaperFacingResultKind = PaperFacingResultKind.PBOX_PROBABILITY,
    use_status: UseStatus = "synthetic-only",
    output_error_record: Mapping[str, object] | None = None,
) -> GuardedPBoxReport:
    """Build a guarded record for synthetic or future paper-facing reporting.

    The paper-facing path intentionally requires both the prerequisite guard and
    an endpoint-count record. This prevents a valid-looking p-box table from
    bypassing G1-A2 by omitting the loading-endpoint evidence trail.
    """

    if not isinstance(prerequisites, FinalResultPrerequisites):
        raise TypeError("prerequisites must be a FinalResultPrerequisites")
    if (
        result_kind is PaperFacingResultKind.VERTEX_SHORTCUT
        and use_status == "paper-facing"
    ):
        _assert_g3_approved_vertex_family(pbox_family)
    guard = evaluate_paper_facing_guard(result_kind, prerequisites)
    return GuardedPBoxReport(
        result_kind=result_kind,
        guard=guard,
        probability_rows=probability_rows_from_pbox_family(pbox_family),
        use_status=use_status,
        output_error_record=output_error_record,
    )


def _assert_g3_approved_vertex_family(pbox_family: PBoxFamily) -> None:
    for result in pbox_family.values():
        if result.use_mode is not VertexUseMode.G3_APPROVED:
            raise RuntimeError(
                "paper-facing vertex reports require p-box rows produced in G3-approved mode"
            )


def _validate_output_error_record(record: Mapping[str, object]) -> None:
    required = {
        "config",
        "event_count_bounds",
        "probability_bounds",
        "probability_widening",
        "sample_endpoint_events",
    }
    missing = required.difference(record)
    if missing:
        raise ValueError(f"output_error_record is missing fields: {sorted(missing)}")
    if record["probability_widening"] != "forbidden":
        raise ValueError(
            "output_error_record must preserve probability_widening='forbidden'"
        )
