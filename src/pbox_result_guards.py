"""Paper-facing guardrails for p-box and decision-result outputs.

These helpers are governance scaffolds for Agent B-owned math outputs. They do
not run experiments or inspect real trajectories; they make final-result gates
explicit before a p-box probability, decision result, or vertex shortcut output
can be presented as paper-facing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence

_FORBIDDEN_COLLAPSED_PROBABILITY_FIELDS = frozenset(
    {
        "defuzzified_probability",
        "expected_probability",
        "mean_probability",
        "p_hat",
        "p_mid",
        "probability",
    }
)


class PaperFacingResultKind(str, Enum):
    """B-owned result surfaces that need final-result prerequisite checks."""

    PBOX_PROBABILITY = "pbox-probability"
    DECISION_RESULT = "decision-result"
    VERTEX_SHORTCUT = "vertex-shortcut"


@dataclass(frozen=True)
class FinalResultPrerequisites:
    """Explicit prerequisite state for paper-facing B-owned outputs."""

    g2_tier1_envelope_approved: bool = False
    a013_grid_error_signed: bool = False
    capacity_convention_approved: bool = False
    capacity_denominator_provenance: str | None = None
    output_error_endpoint_records_manifested: bool = False
    g3_vertex_shortcut_approved: bool = False

    def missing_for(self, result_kind: PaperFacingResultKind) -> tuple[str, ...]:
        """Return unresolved gates that block the requested paper-facing output."""

        if not isinstance(result_kind, PaperFacingResultKind):
            raise TypeError("result_kind must be a PaperFacingResultKind")
        missing = []
        if not self.g2_tier1_envelope_approved:
            missing.append("G2 Tier-1 envelope/adequacy approval")
        if not self.a013_grid_error_signed:
            missing.append("signed A-013 grid-error value")
        if not self.capacity_convention_approved:
            missing.append("approved capacity convention")
        if not _has_capacity_provenance(self.capacity_denominator_provenance):
            missing.append("capacity denominator provenance")
        if not self.output_error_endpoint_records_manifested:
            missing.append("manifested output-error endpoint event records")
        if (
            result_kind is PaperFacingResultKind.VERTEX_SHORTCUT
            and not self.g3_vertex_shortcut_approved
        ):
            missing.append("G3 vertex-shortcut approval")
        return tuple(missing)

    def to_mapping(self) -> dict[str, object]:
        """Return a manifest/report-friendly prerequisite snapshot."""

        return {
            "a013_grid_error_signed": self.a013_grid_error_signed,
            "capacity_convention_approved": self.capacity_convention_approved,
            "capacity_denominator_provenance": self.capacity_denominator_provenance,
            "g2_tier1_envelope_approved": self.g2_tier1_envelope_approved,
            "g3_vertex_shortcut_approved": self.g3_vertex_shortcut_approved,
            "output_error_endpoint_records_manifested": (
                self.output_error_endpoint_records_manifested
            ),
        }


@dataclass(frozen=True)
class PaperFacingGuardReport:
    """Decision record for one attempted paper-facing result surface."""

    result_kind: PaperFacingResultKind
    allowed: bool
    missing_prerequisites: tuple[str, ...]
    prerequisites: Mapping[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.result_kind, PaperFacingResultKind):
            raise TypeError("result_kind must be a PaperFacingResultKind")
        if self.allowed != (len(self.missing_prerequisites) == 0):
            raise ValueError("allowed must exactly reflect missing_prerequisites")

    def to_mapping(self) -> dict[str, object]:
        """Return a stable record suitable for reports or future manifests."""

        return {
            "allowed": self.allowed,
            "missing_prerequisites": list(self.missing_prerequisites),
            "prerequisites": dict(self.prerequisites),
            "result_kind": self.result_kind.value,
        }


def evaluate_paper_facing_guard(
    result_kind: PaperFacingResultKind,
    prerequisites: FinalResultPrerequisites,
) -> PaperFacingGuardReport:
    """Evaluate paper-facing eligibility without throwing on blocked outputs."""

    if not isinstance(prerequisites, FinalResultPrerequisites):
        raise TypeError("prerequisites must be a FinalResultPrerequisites")
    missing = prerequisites.missing_for(result_kind)
    return PaperFacingGuardReport(
        result_kind=result_kind,
        allowed=len(missing) == 0,
        missing_prerequisites=missing,
        prerequisites=prerequisites.to_mapping(),
    )


def assert_paper_facing_allowed(
    result_kind: PaperFacingResultKind,
    prerequisites: FinalResultPrerequisites,
) -> None:
    """Raise when a B-owned output is still scaffold-only/pre-result.

    The guard keeps final p-box/decision/vertex presentation tied to signed
    model-error and capacity prerequisites instead of allowing a synthetic math
    artifact to become a manuscript result by omission.
    """

    report = evaluate_paper_facing_guard(result_kind, prerequisites)
    if not report.allowed:
        missing = "; ".join(report.missing_prerequisites)
        raise RuntimeError(f"paper-facing {result_kind.value} is blocked by: {missing}")


def assert_alpha_indexed_probability_report(
    probability_rows: Sequence[Mapping[str, object]],
) -> None:
    """Reject collapsed or incomplete p-box probability presentation rows."""

    if not probability_rows:
        raise ValueError("probability_rows must not be empty")
    required = {
        "alpha",
        "p_lower",
        "p_upper",
        "ci_lower_lower",
        "ci_lower_upper",
        "ci_upper_lower",
        "ci_upper_upper",
    }
    previous_alpha: float | None = None
    for row in probability_rows:
        missing = required.difference(row)
        if missing:
            raise ValueError(f"probability row is missing fields: {sorted(missing)}")
        collapsed_fields = sorted(_FORBIDDEN_COLLAPSED_PROBABILITY_FIELDS.intersection(row))
        if collapsed_fields:
            raise ValueError(
                "paper-facing probability rows must not collapse the p-box: "
                f"{collapsed_fields}"
            )
        values = {name: float(row[name]) for name in required}
        for name, value in values.items():
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be finite and in [0, 1]")
        alpha = values["alpha"]
        # Strict ordering makes serialized alpha-cut tables deterministic and
        # prevents duplicate rows from being mistaken for separate evidence.
        if previous_alpha is not None and alpha <= previous_alpha:
            raise ValueError("alpha rows must be strictly increasing")
        previous_alpha = alpha
        if values["p_lower"] > values["p_upper"]:
            raise ValueError("expected p_lower <= p_upper")
        if not values["ci_lower_lower"] <= values["p_lower"] <= values["ci_lower_upper"]:
            raise ValueError("expected ci_lower bounds to contain p_lower")
        if not values["ci_upper_lower"] <= values["p_upper"] <= values["ci_upper_upper"]:
            raise ValueError("expected ci_upper bounds to contain p_upper")


def _has_capacity_provenance(value: str | None) -> bool:
    return isinstance(value, str) and bool(value.strip())
