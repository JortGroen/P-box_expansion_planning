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
OUTPUT_ERROR_READINESS_MANIFEST_PROTOCOL = "output-error-paper-readiness-v1"
_REQUIRED_OUTPUT_ERROR_READINESS_CHECKS = {
    "a013_approval_or_blocker_id_recorded": "A-013 approval or blocker ID",
    "capacity_convention_linkage_recorded": "capacity convention linkage",
    "capacity_denominator_provenance_recorded": "capacity denominator provenance",
    "endpoint_records_present": "output-error endpoint records",
    "g1_a2_formula_recorded": "G1-A2 endpoint composition formula",
    "g2_tier1_endpoint_approval_or_blocker_id_recorded": (
        "G2 Tier-1 endpoint approval or blocker ID"
    ),
    "independent_error_sampling_forbidden_recorded": (
        "independent error sampling forbidden"
    ),
    "loading_endpoint_application_recorded": (
        "loading endpoints applied before event detection"
    ),
    "probability_widening_forbidden_recorded": "probability widening forbidden",
}


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
    a016_scenario_consistency_manifested: bool = False
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
        if not self.a016_scenario_consistency_manifested:
            missing.append("manifested A-016 scenario consistency")
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
            "a016_scenario_consistency_manifested": (
                self.a016_scenario_consistency_manifested
            ),
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


@dataclass(frozen=True)
class OutputErrorPaperReadinessManifest:
    """Fail-closed blocker manifest for future output-error paper use."""

    manifest_id: str
    result_kind: PaperFacingResultKind
    prerequisites: FinalResultPrerequisites
    output_error_checks: Mapping[str, bool]
    use_status: str = "synthetic-readiness"

    def __post_init__(self) -> None:
        if not isinstance(self.manifest_id, str) or not self.manifest_id.strip():
            raise ValueError("manifest_id must be a nonempty string")
        if not isinstance(self.result_kind, PaperFacingResultKind):
            raise TypeError("result_kind must be a PaperFacingResultKind")
        if not isinstance(self.prerequisites, FinalResultPrerequisites):
            raise TypeError("prerequisites must be a FinalResultPrerequisites")
        if self.use_status not in {"synthetic-readiness", "paper-facing-readiness"}:
            raise ValueError(
                "use_status must be 'synthetic-readiness' or 'paper-facing-readiness'"
            )
        _validate_output_error_readiness_checks(self.output_error_checks)

    @property
    def blockers(self) -> tuple[str, ...]:
        """Return the deterministic blocker checklist for this result surface."""

        blockers = list(self.prerequisites.missing_for(self.result_kind))
        blockers.extend(
            label
            for key, label in _REQUIRED_OUTPUT_ERROR_READINESS_CHECKS.items()
            if not self.output_error_checks[key]
        )
        return tuple(blockers)

    @property
    def ready_for_paper(self) -> bool:
        """Whether the manifest is unblocked for paper-facing output."""

        return len(self.blockers) == 0

    def to_mapping(self) -> dict[str, object]:
        """Return a JSON-stable readiness payload for runner/report preflights."""

        blockers = self.blockers
        return {
            "blockers": list(blockers),
            "manifest_id": self.manifest_id,
            "manifest_protocol": OUTPUT_ERROR_READINESS_MANIFEST_PROTOCOL,
            "non_claims": [
                "no real trajectories",
                "no real P(E)",
                "no capacity-convention choice",
                "no A-013 or G2 numerical signoff",
                "no manuscript number",
            ],
            "output_error_checks": dict(self.output_error_checks),
            "ready_for_paper": len(blockers) == 0,
            "required_output_error_checks": dict(
                _REQUIRED_OUTPUT_ERROR_READINESS_CHECKS
            ),
            "result_kind": self.result_kind.value,
            "prerequisites": self.prerequisites.to_mapping(),
            "use_status": self.use_status,
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


def build_output_error_readiness_manifest(
    *,
    manifest_id: str,
    result_kind: PaperFacingResultKind = PaperFacingResultKind.PBOX_PROBABILITY,
    prerequisites: FinalResultPrerequisites,
    output_error_checks: Mapping[str, bool],
    use_status: str = "synthetic-readiness",
) -> OutputErrorPaperReadinessManifest:
    """Build a fail-closed readiness manifest instead of a result number."""

    return OutputErrorPaperReadinessManifest(
        manifest_id=manifest_id,
        result_kind=result_kind,
        prerequisites=prerequisites,
        output_error_checks=output_error_checks,
        use_status=use_status,
    )


def assert_output_error_readiness_manifest_payload(
    payload: Mapping[str, object],
) -> None:
    """Validate a serialized output-error readiness/blocker manifest.

    The validator recomputes readiness from the prerequisite snapshot and
    output-error checklist so a future runner cannot flip one flag and turn a
    blocker packet into a paper-facing result.
    """

    _reject_forbidden_result_fields(payload)
    required = {
        "blockers",
        "manifest_id",
        "manifest_protocol",
        "output_error_checks",
        "ready_for_paper",
        "required_output_error_checks",
        "result_kind",
        "prerequisites",
        "use_status",
    }
    missing = required.difference(payload)
    if missing:
        raise ValueError(f"readiness manifest is missing fields: {sorted(missing)}")
    if payload["manifest_protocol"] != OUTPUT_ERROR_READINESS_MANIFEST_PROTOCOL:
        raise ValueError(
            f"manifest_protocol must be {OUTPUT_ERROR_READINESS_MANIFEST_PROTOCOL!r}"
        )
    if not isinstance(payload["manifest_id"], str) or not payload["manifest_id"].strip():
        raise ValueError("manifest_id must be a nonempty string")
    if not isinstance(payload["ready_for_paper"], bool):
        raise TypeError("ready_for_paper must be a boolean")
    try:
        result_kind = PaperFacingResultKind(str(payload["result_kind"]))
    except ValueError as exc:
        raise ValueError("result_kind must be a known paper-facing result kind") from exc
    if payload["use_status"] not in {"synthetic-readiness", "paper-facing-readiness"}:
        raise ValueError(
            "use_status must be 'synthetic-readiness' or 'paper-facing-readiness'"
        )
    output_error_checks = _expect_bool_mapping(
        payload["output_error_checks"], name="output_error_checks"
    )
    required_checks = dict(_REQUIRED_OUTPUT_ERROR_READINESS_CHECKS)
    if payload["required_output_error_checks"] != required_checks:
        raise ValueError("required_output_error_checks must match the protocol")
    prerequisites = _prerequisites_from_mapping(payload["prerequisites"])
    expected = build_output_error_readiness_manifest(
        manifest_id=str(payload["manifest_id"]),
        result_kind=result_kind,
        prerequisites=prerequisites,
        output_error_checks=output_error_checks,
        use_status=str(payload["use_status"]),
    )
    blockers = _expect_string_sequence(payload["blockers"], name="blockers")
    if tuple(blockers) != expected.blockers:
        raise ValueError("blockers must exactly match prerequisite and output-error checks")
    if payload["ready_for_paper"] != expected.ready_for_paper:
        raise ValueError("ready_for_paper must exactly reflect blockers")


def _has_capacity_provenance(value: str | None) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_output_error_readiness_checks(checks: Mapping[str, bool]) -> None:
    if not isinstance(checks, Mapping):
        raise TypeError("output_error_checks must be a mapping")
    required = set(_REQUIRED_OUTPUT_ERROR_READINESS_CHECKS)
    missing = required.difference(checks)
    if missing:
        raise ValueError(f"output_error_checks is missing fields: {sorted(missing)}")
    unknown = set(checks).difference(required)
    if unknown:
        raise ValueError(f"output_error_checks has unknown fields: {sorted(unknown)}")
    for key, value in checks.items():
        if not isinstance(value, bool):
            raise TypeError(f"output_error_checks {key} must be a boolean")


def _prerequisites_from_mapping(value: object) -> FinalResultPrerequisites:
    if not isinstance(value, Mapping):
        raise TypeError("prerequisites must be a mapping")
    required = set(FinalResultPrerequisites().to_mapping())
    missing = required.difference(value)
    if missing:
        raise ValueError(f"prerequisites is missing fields: {sorted(missing)}")
    return FinalResultPrerequisites(
        g2_tier1_envelope_approved=_expect_bool(
            value["g2_tier1_envelope_approved"],
            name="g2_tier1_envelope_approved",
        ),
        a013_grid_error_signed=_expect_bool(
            value["a013_grid_error_signed"],
            name="a013_grid_error_signed",
        ),
        capacity_convention_approved=_expect_bool(
            value["capacity_convention_approved"],
            name="capacity_convention_approved",
        ),
        capacity_denominator_provenance=(
            None
            if value["capacity_denominator_provenance"] is None
            else str(value["capacity_denominator_provenance"])
        ),
        output_error_endpoint_records_manifested=_expect_bool(
            value["output_error_endpoint_records_manifested"],
            name="output_error_endpoint_records_manifested",
        ),
        a016_scenario_consistency_manifested=_expect_bool(
            value["a016_scenario_consistency_manifested"],
            name="a016_scenario_consistency_manifested",
        ),
        g3_vertex_shortcut_approved=_expect_bool(
            value["g3_vertex_shortcut_approved"],
            name="g3_vertex_shortcut_approved",
        ),
    )


def _expect_bool_mapping(value: object, *, name: str) -> Mapping[str, bool]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    _validate_output_error_readiness_checks(value)
    return value  # type: ignore[return-value]


def _expect_bool(value: object, *, name: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")
    return value


def _expect_string_sequence(value: object, *, name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{name} must be a sequence")
    if any(not isinstance(item, str) for item in value):
        raise TypeError(f"{name} must contain strings")
    return tuple(value)


def _reject_forbidden_result_fields(value: object) -> None:
    if isinstance(value, Mapping):
        collapsed = sorted(_FORBIDDEN_COLLAPSED_PROBABILITY_FIELDS.intersection(value))
        if collapsed:
            raise ValueError(
                "readiness manifests must not contain result probability fields: "
                f"{collapsed}"
            )
        for nested in value.values():
            _reject_forbidden_result_fields(nested)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for nested in value:
            _reject_forbidden_result_fields(nested)
