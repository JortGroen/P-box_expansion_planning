"""Guarded reporting records for B-owned p-box outputs.

This module is synthetic/reporting infrastructure only. It gives future runner
or report surfaces a small typed path that combines alpha-indexed p-box rows,
output-error endpoint records, and final-result guards before anything is
allowed to present as paper-facing.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence

from src.pbox import PBoxFamily, VertexUseMode
from src.pbox_ac_promotion import assert_selective_ac_promotion_payload
from src.pbox_result_guards import (
    FinalResultPrerequisites,
    PaperFacingGuardReport,
    PaperFacingResultKind,
    assert_alpha_indexed_probability_report,
    evaluate_paper_facing_guard,
)

UseStatus = str
RUNNER_REPORT_BOUNDARY_PROTOCOL = "guarded-pbox-report-v1"


@dataclass(frozen=True)
class GuardedPBoxReport:
    """Stable report record for alpha-indexed p-box probability rows."""

    result_kind: PaperFacingResultKind
    guard: PaperFacingGuardReport
    probability_rows: tuple[dict[str, object], ...]
    use_status: UseStatus = "synthetic-only"
    output_error_record: Mapping[str, object] | None = None
    selective_ac_promotion_metadata: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.result_kind, PaperFacingResultKind):
            raise TypeError("result_kind must be a PaperFacingResultKind")
        if self.use_status not in {"synthetic-only", "paper-facing"}:
            raise ValueError("use_status must be 'synthetic-only' or 'paper-facing'")
        assert_alpha_indexed_probability_report(self.probability_rows)
        if self.output_error_record is not None:
            _validate_output_error_record(self.output_error_record)
        if self.selective_ac_promotion_metadata is not None:
            _validate_selective_ac_metadata_record(
                self.selective_ac_promotion_metadata,
                output_error_record=self.output_error_record,
                probability_rows=self.probability_rows,
            )
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
        if self.selective_ac_promotion_metadata is not None:
            record["selective_ac_promotion_metadata"] = dict(
                self.selective_ac_promotion_metadata
            )
        return record


@dataclass(frozen=True)
class RunnerReportBoundaryRecord:
    """Manifest-like boundary payload for future runner/report integration."""

    boundary_id: str
    guarded_report: GuardedPBoxReport
    boundary_protocol: str = RUNNER_REPORT_BOUNDARY_PROTOCOL

    def __post_init__(self) -> None:
        if not isinstance(self.boundary_id, str) or not self.boundary_id.strip():
            raise ValueError("boundary_id must be a nonempty string")
        if self.boundary_protocol != RUNNER_REPORT_BOUNDARY_PROTOCOL:
            raise ValueError(
                f"boundary_protocol must be {RUNNER_REPORT_BOUNDARY_PROTOCOL!r}"
            )

    def to_mapping(self) -> dict[str, object]:
        """Return the stable payload expected at the runner/report boundary."""

        report = self.guarded_report.to_mapping()
        paper_facing_requested = self.guarded_report.use_status == "paper-facing"
        return {
            "boundary_id": self.boundary_id,
            "boundary_protocol": self.boundary_protocol,
            "guarded_report": report,
            "paper_facing_allowed": (
                paper_facing_requested and self.guarded_report.guard.allowed
            ),
            "paper_facing_requested": paper_facing_requested,
        }


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
    selective_ac_promotion_metadata: Mapping[str, object] | None = None,
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
        selective_ac_promotion_metadata=selective_ac_promotion_metadata,
    )


def build_runner_report_boundary_record(
    *,
    boundary_id: str,
    pbox_family: PBoxFamily,
    prerequisites: FinalResultPrerequisites,
    result_kind: PaperFacingResultKind = PaperFacingResultKind.PBOX_PROBABILITY,
    use_status: UseStatus = "synthetic-only",
    output_error_record: Mapping[str, object] | None = None,
    selective_ac_promotion_metadata: Mapping[str, object] | None = None,
) -> RunnerReportBoundaryRecord:
    """Build the guarded p-box payload future runner/report code should emit.

    The boundary record keeps the gate decision beside the p-box rows, so a
    downstream report cannot silently drop G2/A-013/capacity/G3 blockers while
    still displaying a plausible alpha-indexed table.
    """

    return RunnerReportBoundaryRecord(
        boundary_id=boundary_id,
        guarded_report=build_guarded_pbox_report(
            pbox_family=pbox_family,
            prerequisites=prerequisites,
            result_kind=result_kind,
            use_status=use_status,
            output_error_record=output_error_record,
            selective_ac_promotion_metadata=selective_ac_promotion_metadata,
        ),
    )



def assert_runner_report_boundary_payload(payload: Mapping[str, object]) -> None:
    """Validate a serialized guarded p-box runner/report boundary payload.

    This is the defensive counterpart to `build_runner_report_boundary_record`:
    future reporting code may receive plain mappings, so the guard decision,
    alpha rows, endpoint record, and vertex-mode evidence must survive
    serialization instead of being trusted by convention.
    """

    required = {
        "boundary_id",
        "boundary_protocol",
        "guarded_report",
        "paper_facing_allowed",
        "paper_facing_requested",
    }
    _require_mapping_fields(payload, required, name="boundary payload")
    if payload["boundary_protocol"] != RUNNER_REPORT_BOUNDARY_PROTOCOL:
        raise ValueError(
            f"boundary_protocol must be {RUNNER_REPORT_BOUNDARY_PROTOCOL!r}"
        )
    if not isinstance(payload["boundary_id"], str) or not payload["boundary_id"].strip():
        raise ValueError("boundary_id must be a nonempty string")
    if not isinstance(payload["paper_facing_requested"], bool):
        raise TypeError("paper_facing_requested must be a boolean")
    if not isinstance(payload["paper_facing_allowed"], bool):
        raise TypeError("paper_facing_allowed must be a boolean")
    guarded_report = _expect_mapping(payload["guarded_report"], name="guarded_report")
    _validate_guarded_report_mapping(guarded_report)
    guard = _expect_mapping(guarded_report["guard"], name="guard")
    guard_allowed = bool(guard["allowed"])
    requested = bool(payload["paper_facing_requested"])
    expected_allowed = requested and guard_allowed
    if payload["paper_facing_allowed"] != expected_allowed:
        raise ValueError("paper_facing_allowed must exactly reflect requested and guard state")
    if requested:
        if guarded_report["use_status"] != "paper-facing":
            raise ValueError("paper_facing_requested requires use_status='paper-facing'")
        if "output_error_record" not in guarded_report:
            raise ValueError(
                "paper-facing boundary payload requires output_error_record"
            )
        if not guard_allowed:
            missing = guard.get("missing_prerequisites", [])
            raise RuntimeError(f"paper-facing boundary payload is blocked by: {missing}")
    elif guarded_report["use_status"] == "paper-facing":
        raise ValueError("paper-facing use_status must set paper_facing_requested=true")


def _validate_guarded_report_mapping(report: Mapping[str, object]) -> None:
    required = {"guard", "probability_rows", "result_kind", "use_status"}
    _require_mapping_fields(report, required, name="guarded_report")
    if report["use_status"] not in {"synthetic-only", "paper-facing"}:
        raise ValueError("use_status must be 'synthetic-only' or 'paper-facing'")
    try:
        result_kind = PaperFacingResultKind(str(report["result_kind"]))
    except ValueError as exc:
        raise ValueError("result_kind must be a known paper-facing result kind") from exc
    guard = _expect_mapping(report["guard"], name="guard")
    _validate_guard_mapping(guard, result_kind=result_kind)
    rows = _expect_sequence(report["probability_rows"], name="probability_rows")
    row_mappings = tuple(_expect_mapping(row, name="probability row") for row in rows)
    assert_alpha_indexed_probability_report(row_mappings)
    has_endpoint_record = "output_error_record" in report
    output_error_record = None
    if has_endpoint_record:
        output_error_record = _expect_mapping(
            report["output_error_record"], name="output_error_record"
        )
        _validate_output_error_record(output_error_record)
    if "selective_ac_promotion_metadata" in report:
        _validate_selective_ac_metadata_record(
            _expect_mapping(
                report["selective_ac_promotion_metadata"],
                name="selective_ac_promotion_metadata",
            ),
            output_error_record=output_error_record,
            probability_rows=row_mappings,
        )
    prerequisites = _expect_mapping(
        guard["prerequisites"], name="guard.prerequisites"
    )
    if prerequisites["output_error_endpoint_records_manifested"] != has_endpoint_record:
        raise ValueError(
            "guard endpoint-record prerequisite must match output_error_record presence"
        )
    if result_kind is PaperFacingResultKind.VERTEX_SHORTCUT:
        for row in row_mappings:
            if row.get("vertex_use_mode") != VertexUseMode.G3_APPROVED.value:
                raise RuntimeError(
                    "vertex boundary payload requires G3-approved vertex rows"
                )


def _validate_selective_ac_metadata_record(
    metadata: Mapping[str, object],
    *,
    output_error_record: Mapping[str, object] | None,
    probability_rows: Sequence[Mapping[str, object]],
) -> None:
    assert_selective_ac_promotion_payload(metadata)
    if output_error_record is None:
        raise ValueError(
            "selective_ac_promotion_metadata requires output_error_record"
        )

    reported_alpha_grid = tuple(float(row["alpha"]) for row in probability_rows)
    metadata_alpha_grid = tuple(
        float(alpha)
        for alpha in _expect_sequence(
            metadata["alpha_grid"], name="selective_ac_promotion_metadata.alpha_grid"
        )
    )
    if metadata_alpha_grid != reported_alpha_grid:
        raise ValueError(
            "selective_ac_promotion_metadata alpha_grid must match probability_rows"
        )

    event_counts = _expect_mapping(
        output_error_record["event_count_bounds"],
        name="output_error_record.event_count_bounds",
    )
    sample_count = _expect_nonnegative_int(
        event_counts.get("sample_count"), name="output_error_record.sample_count"
    )
    metadata_sample_count = _expect_nonnegative_int(
        metadata["sample_count"], name="selective_ac_promotion_metadata.sample_count"
    )
    if metadata_sample_count != sample_count:
        raise ValueError(
            "selective_ac_promotion_metadata sample_count must match output_error_record"
        )

    endpoint_events = {
        int(event["sample_index"]): event
        for event in (
            _expect_mapping(raw_event, name="sample_endpoint_event")
            for raw_event in _expect_sequence(
                output_error_record["sample_endpoint_events"],
                name="output_error_record.sample_endpoint_events",
            )
        )
    }
    for raw_candidate in _expect_sequence(
        metadata["candidates"], name="selective_ac_promotion_metadata.candidates"
    ):
        candidate = _expect_mapping(raw_candidate, name="selective_ac_promotion_candidate")
        sample_index = int(candidate["sample_index"])
        endpoint_event = endpoint_events.get(sample_index)
        if endpoint_event is None:
            raise ValueError(
                "selective_ac_promotion_metadata candidate sample_index must reference an endpoint record"
            )
        # Candidate metadata must replay the same endpoint-event facts; otherwise
        # a future report could promote a sample identity using diagnostics from
        # a different output-error realization.
        if candidate["lower_event"] != endpoint_event["lower_event"]:
            raise ValueError(
                "selective_ac_promotion_metadata lower_event must match endpoint record"
            )
        if candidate["upper_event"] != endpoint_event["upper_event"]:
            raise ValueError(
                "selective_ac_promotion_metadata upper_event must match endpoint record"
            )


def _validate_guard_mapping(
    guard: Mapping[str, object], *, result_kind: PaperFacingResultKind
) -> None:
    required = {"allowed", "missing_prerequisites", "prerequisites", "result_kind"}
    _require_mapping_fields(guard, required, name="guard")
    if guard["result_kind"] != result_kind.value:
        raise ValueError("guard result_kind must match guarded_report result_kind")
    if not isinstance(guard["allowed"], bool):
        raise TypeError("guard.allowed must be a boolean")
    missing = _expect_sequence(
        guard["missing_prerequisites"], name="guard.missing_prerequisites"
    )
    if any(not isinstance(item, str) for item in missing):
        raise TypeError("guard.missing_prerequisites must contain strings")
    if bool(guard["allowed"]) != (len(missing) == 0):
        raise ValueError("guard.allowed must exactly reflect missing_prerequisites")
    prerequisites = _expect_mapping(guard["prerequisites"], name="guard.prerequisites")
    required_prerequisites = {
        "a013_grid_error_signed",
        "capacity_convention_approved",
        "capacity_denominator_provenance",
        "g2_tier1_envelope_approved",
        "g3_vertex_shortcut_approved",
        "output_error_endpoint_records_manifested",
    }
    _require_mapping_fields(
        prerequisites,
        required_prerequisites,
        name="guard.prerequisites",
    )


def _require_mapping_fields(
    mapping: Mapping[str, object], required: set[str], *, name: str
) -> None:
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
    event_counts = _expect_mapping(
        record["event_count_bounds"], name="output_error_record.event_count_bounds"
    )
    probability_bounds = _expect_mapping(
        record["probability_bounds"], name="output_error_record.probability_bounds"
    )
    sample_events = _expect_sequence(
        record["sample_endpoint_events"],
        name="output_error_record.sample_endpoint_events",
    )
    lower_successes = _expect_nonnegative_int(
        event_counts.get("lower_successes"), name="lower_successes"
    )
    upper_successes = _expect_nonnegative_int(
        event_counts.get("upper_successes"), name="upper_successes"
    )
    sample_count = _expect_nonnegative_int(
        event_counts.get("sample_count"), name="sample_count"
    )
    if sample_count == 0:
        raise ValueError("output_error_record sample_count must be positive")
    if lower_successes > upper_successes:
        raise ValueError("output_error_record expected lower_successes <= upper_successes")
    if upper_successes > sample_count:
        raise ValueError("output_error_record successes cannot exceed sample_count")
    if len(sample_events) != sample_count:
        raise ValueError("output_error_record sample events must match sample_count")

    lower_probability = _validate_probability_estimate_record(
        _expect_mapping(probability_bounds.get("lower"), name="probability_bounds.lower"),
        expected_successes=lower_successes,
        expected_sample_count=sample_count,
        name="probability_bounds.lower",
    )
    upper_probability = _validate_probability_estimate_record(
        _expect_mapping(probability_bounds.get("upper"), name="probability_bounds.upper"),
        expected_successes=upper_successes,
        expected_sample_count=sample_count,
        name="probability_bounds.upper",
    )
    if lower_probability > upper_probability:
        raise ValueError("output_error_record expected lower probability <= upper probability")

    observed_lower = 0
    observed_upper = 0
    for expected_index, event in enumerate(sample_events):
        event_mapping = _expect_mapping(event, name="sample_endpoint_event")
        if event_mapping.get("sample_index") != expected_index:
            raise ValueError("output_error_record sample_index values must be consecutive")
        lower_event = event_mapping.get("lower_event")
        upper_event = event_mapping.get("upper_event")
        if not isinstance(lower_event, bool) or not isinstance(upper_event, bool):
            raise TypeError("sample endpoint events must use boolean event flags")
        # Lower endpoint events are a subset of upper endpoint events under the
        # conservative loading envelope; otherwise the serialized record cannot
        # support lower/upper p-box interpretation.
        if lower_event and not upper_event:
            raise ValueError("sample endpoint lower_event cannot exceed upper_event")
        observed_lower += int(lower_event)
        observed_upper += int(upper_event)
    if (observed_lower, observed_upper) != (lower_successes, upper_successes):
        raise ValueError("output_error_record event counts must match sample events")


def _validate_probability_estimate_record(
    estimate: Mapping[str, object],
    *,
    expected_successes: int,
    expected_sample_count: int,
    name: str,
) -> float:
    required = {"ci_lower", "ci_upper", "probability", "sample_count", "successes"}
    _require_mapping_fields(estimate, required, name=name)
    successes = _expect_nonnegative_int(estimate["successes"], name=f"{name}.successes")
    sample_count = _expect_nonnegative_int(
        estimate["sample_count"], name=f"{name}.sample_count"
    )
    if successes != expected_successes or sample_count != expected_sample_count:
        raise ValueError(f"{name} must match endpoint event counts")
    probability = _expect_probability(estimate["probability"], name=f"{name}.probability")
    expected_probability = successes / sample_count
    if not math.isclose(probability, expected_probability, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError(f"{name}.probability must equal successes / sample_count")
    ci_lower = _expect_probability(estimate["ci_lower"], name=f"{name}.ci_lower")
    ci_upper = _expect_probability(estimate["ci_upper"], name=f"{name}.ci_upper")
    if not ci_lower <= probability <= ci_upper:
        raise ValueError(f"{name} confidence interval must contain probability")
    return probability


def _expect_probability(value: object, *, name: str) -> float:
    probability = float(value)
    if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
        raise ValueError(f"{name} must be finite and in [0, 1]")
    return probability


def _expect_nonnegative_int(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be a nonnegative integer")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
    return value
