"""Guarded synthetic decision-report records for B-owned E6 outputs.

This module keeps decision-layer summaries behind the same guarded p-box
runner/report boundary used for probability rows. It is scaffold-only: future
paper-facing decision reports must first pass the p-box/output-error gates, and
this helper does not run experiments or produce manuscript numbers.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence

from src.pbox_reporting import assert_runner_report_boundary_payload

DECISION_REPORT_PROTOCOL = "guarded-decision-report-v1"


@dataclass(frozen=True)
class DecisionReportRow:
    """One alpha-indexed lower/upper synthetic decision metric row."""

    alpha: float
    metric_name: str
    lower_value: float
    upper_value: float
    classification: str
    unit: str = "dimensionless"

    def __post_init__(self) -> None:
        if not math.isfinite(self.alpha) or not 0.0 <= self.alpha <= 1.0:
            raise ValueError("alpha must be finite and in [0, 1]")
        if not self.metric_name.strip():
            raise ValueError("metric_name must be nonempty")
        if not self.classification.strip():
            raise ValueError("classification must be nonempty")
        if not self.unit.strip():
            raise ValueError("unit must be nonempty")
        for name, value in (("lower_value", self.lower_value), ("upper_value", self.upper_value)):
            if not _is_finite_or_never_satisfied_inf(value, self.classification):
                raise ValueError(f"{name} must be finite unless classification is never-satisfied")
        if self.lower_value > self.upper_value:
            raise ValueError("lower_value must be <= upper_value")

    def to_mapping(self) -> dict[str, object]:
        return {
            "alpha": self.alpha,
            "classification": self.classification,
            "lower_value": self.lower_value,
            "metric_name": self.metric_name,
            "unit": self.unit,
            "upper_value": self.upper_value,
        }


@dataclass(frozen=True)
class GuardedDecisionReport:
    """Synthetic decision report tied to the guarded p-box boundary."""

    boundary_payload: Mapping[str, object]
    decision_rows: tuple[DecisionReportRow, ...]
    report_id: str
    use_status: str = "synthetic-only"
    protocol: str = DECISION_REPORT_PROTOCOL

    def __post_init__(self) -> None:
        if self.protocol != DECISION_REPORT_PROTOCOL:
            raise ValueError(f"protocol must be {DECISION_REPORT_PROTOCOL!r}")
        if self.use_status not in {"synthetic-only", "paper-facing"}:
            raise ValueError("use_status must be 'synthetic-only' or 'paper-facing'")
        if not self.report_id.strip():
            raise ValueError("report_id must be nonempty")
        _validate_decision_rows(self.decision_rows)
        assert_runner_report_boundary_payload(self.boundary_payload)
        guarded_report = _expect_mapping(
            self.boundary_payload["guarded_report"], name="boundary guarded_report"
        )
        if guarded_report["result_kind"] != "decision-result":
            raise ValueError("decision reports require a decision-result boundary payload")
        boundary_use_status = str(guarded_report["use_status"])
        if boundary_use_status != self.use_status:
            raise ValueError("decision report use_status must match boundary payload")
        boundary_requested = bool(self.boundary_payload["paper_facing_requested"])
        boundary_allowed = bool(self.boundary_payload["paper_facing_allowed"])
        if self.use_status == "paper-facing" and not (boundary_requested and boundary_allowed):
            raise RuntimeError("paper-facing decision report requires an allowed decision-result boundary")

    def to_mapping(self) -> dict[str, object]:
        return {
            "boundary_payload": dict(self.boundary_payload),
            "decision_rows": [row.to_mapping() for row in self.decision_rows],
            "paper_facing_allowed": self.use_status == "paper-facing"
            and bool(self.boundary_payload["paper_facing_allowed"]),
            "protocol": self.protocol,
            "report_id": self.report_id,
            "use_status": self.use_status,
        }


def build_guarded_decision_report(
    *,
    boundary_payload: Mapping[str, object],
    decision_rows: Sequence[DecisionReportRow],
    report_id: str,
    use_status: str = "synthetic-only",
) -> GuardedDecisionReport:
    return GuardedDecisionReport(
        boundary_payload=boundary_payload,
        decision_rows=tuple(decision_rows),
        report_id=report_id,
        use_status=use_status,
    )


def assert_guarded_decision_report_payload(payload: Mapping[str, object]) -> None:
    """Validate a serialized guarded decision-report payload."""

    required = {
        "boundary_payload",
        "decision_rows",
        "paper_facing_allowed",
        "protocol",
        "report_id",
        "use_status",
    }
    missing = required.difference(payload)
    if missing:
        raise ValueError(f"decision report payload is missing fields: {sorted(missing)}")
    if payload["protocol"] != DECISION_REPORT_PROTOCOL:
        raise ValueError(f"protocol must be {DECISION_REPORT_PROTOCOL!r}")
    rows = _expect_sequence(payload["decision_rows"], name="decision_rows")
    decision_rows = tuple(_row_from_mapping(row) for row in rows)
    report = GuardedDecisionReport(
        boundary_payload=_expect_mapping(payload["boundary_payload"], name="boundary_payload"),
        decision_rows=decision_rows,
        report_id=str(payload["report_id"]),
        use_status=str(payload["use_status"]),
        protocol=str(payload["protocol"]),
    )
    expected_allowed = report.use_status == "paper-facing" and bool(
        report.boundary_payload["paper_facing_allowed"]
    )
    if payload["paper_facing_allowed"] != expected_allowed:
        raise ValueError("paper_facing_allowed must match decision boundary state")


def _validate_decision_rows(rows: Sequence[DecisionReportRow]) -> None:
    if not rows:
        raise ValueError("decision_rows must not be empty")
    seen: set[tuple[float, str]] = set()
    for row in rows:
        key = (row.alpha, row.metric_name)
        if key in seen:
            raise ValueError("decision rows must be unique by alpha and metric_name")
        seen.add(key)


def _row_from_mapping(row: object) -> DecisionReportRow:
    mapping = _expect_mapping(row, name="decision row")
    forbidden = {"defuzzified_probability", "p_hat", "scalar_decision_probability"}
    present_forbidden = forbidden.intersection(mapping)
    if present_forbidden:
        raise ValueError(f"decision rows must not contain collapsed fields: {sorted(present_forbidden)}")
    required = {"alpha", "classification", "lower_value", "metric_name", "unit", "upper_value"}
    missing = required.difference(mapping)
    if missing:
        raise ValueError(f"decision row is missing fields: {sorted(missing)}")
    return DecisionReportRow(
        alpha=float(mapping["alpha"]),
        metric_name=str(mapping["metric_name"]),
        lower_value=float(mapping["lower_value"]),
        upper_value=float(mapping["upper_value"]),
        classification=str(mapping["classification"]),
        unit=str(mapping["unit"]),
    )


def _is_finite_or_never_satisfied_inf(value: float, classification: str) -> bool:
    if math.isfinite(value):
        return True
    return value == math.inf and classification == "never-satisfied"


def _expect_mapping(value: object, *, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return value


def _expect_sequence(value: object, *, name: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{name} must be a sequence")
    return value
