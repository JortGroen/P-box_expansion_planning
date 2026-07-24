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

from src.pbox import PBoxFamily, VertexUseMode, probability_estimate_from_counts
from src.pbox_error import (
    OUTPUT_ERROR_APPLICATION,
    OUTPUT_ERROR_DEPENDENCE,
    OUTPUT_ERROR_LOWER_FORMULA,
    OUTPUT_ERROR_SAMPLING,
    OUTPUT_ERROR_UPPER_FORMULA,
)
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
ALPHA_EVENT_COUNT_ESTIMATOR_PROTOCOL = "e4s1-alpha-event-count-estimator-v1"
ALPHA_EVENT_COUNT_ESTIMATOR_USE_STATUS = "synthetic-estimator-readiness"
ALPHA_EVENT_COUNT_REAL_USE_BLOCKER_PROTOCOL = (
    "e4s1-alpha-estimator-real-use-blockers-v1"
)
ALPHA_EVENT_COUNT_REAL_USE_BLOCKERS: tuple[str, ...] = (
    "missing_real_endpoint_event_manifests",
    "missing_signed_g2_tier1_endpoints",
    "missing_signed_a013_grid_error",
    "missing_capacity_convention_and_provenance",
    "missing_a016_scenario_consistency",
    "missing_g3_monotonicity_approval_if_vertex_shortcut_claimed",
)
OUTPUT_ERROR_ENDPOINT_COUNT_BRIDGE_PROTOCOL = (
    "e5s3-output-error-endpoint-count-bridge-v1"
)
OUTPUT_ERROR_ENDPOINT_COUNT_BRIDGE_USE_STATUS = (
    "synthetic-output-error-endpoint-count-readiness"
)
OUTPUT_ERROR_ENDPOINT_COUNT_REAL_USE_BLOCKER_PROTOCOL = (
    "e5s3-output-error-endpoint-count-real-use-blockers-v1"
)
OUTPUT_ERROR_ENDPOINT_COUNT_PROVENANCE = (
    "precomputed_after_g1_a2_loading_endpoint_event_detection"
)
OUTPUT_ERROR_ENDPOINT_COUNT_PROTOCOL = "g1-a2-output-domain-error"
OUTPUT_ERROR_ENDPOINT_COUNT_BLOCKED_STATUS = "blocked-pending-real-inputs"
OUTPUT_ERROR_ENDPOINT_COUNT_REAL_USE_BLOCKERS: tuple[str, ...] = (
    "missing_real_output_error_endpoint_count_manifest",
    "missing_signed_g2_tier1_endpoints",
    "missing_signed_a013_grid_error",
    "missing_capacity_convention_and_provenance",
    "missing_a016_scenario_consistency",
    "missing_g3_monotonicity_approval_if_vertex_shortcut_claimed",
)
REAL_OUTPUT_ERROR_ENDPOINT_COUNT_MANIFEST_PROTOCOL = (
    "e5s3-real-output-error-endpoint-count-manifest-preflight-v1"
)
REAL_OUTPUT_ERROR_ENDPOINT_COUNT_USE_STATUS = (
    "real-output-error-endpoint-count-manifest-preflight"
)
REAL_OUTPUT_ERROR_ENDPOINT_COUNT_BLOCKER_PROTOCOL = (
    "e5s3-real-output-error-endpoint-count-blockers-v1"
)
REAL_OUTPUT_ERROR_ENDPOINT_COUNT_BLOCKERS: tuple[str, ...] = (
    "missing_real_loading_trajectory_manifest",
    "missing_real_output_error_endpoint_count_manifest",
    "missing_signed_g2_tier1_endpoints",
    "missing_signed_a013_grid_error",
    "missing_capacity_convention_and_provenance",
    "missing_a016_scenario_consistency",
    "missing_g3_monotonicity_approval_if_vertex_shortcut_claimed",
)
_REAL_OUTPUT_ERROR_ENDPOINT_COUNT_REQUIRED_APPROVAL_IDS: dict[str, str] = {
    "a013_grid_error_approval_id": "missing_signed_a013_grid_error",
    "g2_tier1_envelope_approval_id": "missing_signed_g2_tier1_endpoints",
    "capacity_convention_approval_id": "missing_capacity_convention_and_provenance",
    "a016_scenario_consistency_id": "missing_a016_scenario_consistency",
}
_REAL_OUTPUT_ERROR_ENDPOINT_COUNT_REQUIRED_ARTIFACT_REFERENCES: dict[str, str] = {
    "loading_trajectory_manifest_id": "missing_real_loading_trajectory_manifest",
    "output_error_endpoint_count_manifest_id": (
        "missing_real_output_error_endpoint_count_manifest"
    ),
    "capacity_convention_linkage": "missing_capacity_convention_and_provenance",
    "capacity_denominator_provenance": "missing_capacity_convention_and_provenance",
}
_REAL_OUTPUT_ERROR_ENDPOINT_COUNT_NON_CLAIMS: tuple[str, ...] = (
    "real-use preflight only",
    "no probability accepted for paper-facing use by this scaffold",
    "no real P(E)",
    "no capacity-convention choice by Agent B",
    "no A-013 or G2 numerical signoff by Agent B",
    "no G3 vertex claim by Agent B",
    "no manuscript number",
)
_REAL_OUTPUT_ERROR_ENDPOINT_COUNT_STALE_REFERENCE_TOKENS = (
    "blocked",
    "future",
    "pending",
    "placeholder",
    "proposed",
    "synthetic",
    "tbd",
    "todo",
    "unsigned",
    "not-approved",
)
_ALPHA_EVENT_COUNT_ENDPOINT_METADATA_FIELDS = {
    "a013_grid_error_approval_id",
    "a016_scenario_consistency_id",
    "capacity_convention_linkage",
    "capacity_denominator_provenance",
    "direction_gate",
    "endpoint_record_manifest_id",
    "error_sampling",
    "g2_tier1_envelope_approval_id",
    "loading_endpoint_application",
    "probability_widening",
}
_OUTPUT_ERROR_ENDPOINT_COUNT_REFERENCE_FIELDS: tuple[str, ...] = (
    "a013_grid_error_approval_id",
    "a016_scenario_consistency_id",
    "capacity_convention_linkage",
    "capacity_denominator_provenance",
    "g2_tier1_envelope_approval_id",
)
_OUTPUT_ERROR_ENDPOINT_COUNT_STALE_REFERENCE_TOKENS = (
    "pending",
    "placeholder",
    "proposed",
    "tbd",
    "todo",
    "unsigned",
    "not-approved",
)
_OUTPUT_ERROR_ENDPOINT_COUNT_METADATA_FIELDS = (
    _ALPHA_EVENT_COUNT_ENDPOINT_METADATA_FIELDS
    | {
        "a013_grid_error_approval_status",
        "a016_scenario_consistency_status",
        "capacity_convention_status",
        "dependence_assumption",
        "endpoint_count_provenance",
        "g2_tier1_envelope_approval_status",
        "lower_composition_formula",
        "output_error_protocol",
        "upper_composition_formula",
    }
)
_ALPHA_EVENT_COUNT_FORBIDDEN_FIELDS = frozenset(
    {
        "defuzzified_probability",
        "expected_probability",
        "mean_probability",
        "mid_probability",
        "p_hat",
        "p_mid",
        "probability",
        "probability_margin",
        "probability_margin_shift",
        "probability_margin_widening",
        "scalar_probability",
    }
)


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


@dataclass(frozen=True)
class AlphaEventCountRecord:
    """Precomputed lower/upper endpoint event counts for one alpha level."""

    alpha: float
    lower_successes: int
    upper_successes: int
    sample_count: int
    sample_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not math.isfinite(self.alpha) or not 0.0 <= self.alpha <= 1.0:
            raise ValueError("alpha must be finite and in [0, 1]")
        if self.sample_count <= 0:
            raise ValueError("sample_count must be positive")
        if not (
            0 <= self.lower_successes <= self.upper_successes <= self.sample_count
        ):
            raise ValueError(
                "expected 0 <= lower_successes <= upper_successes <= sample_count"
            )
        if len(self.sample_ids) != self.sample_count:
            raise ValueError("sample_ids must match sample_count")
        if len(set(self.sample_ids)) != len(self.sample_ids):
            raise ValueError("sample_ids must be unique within an alpha level")
        if any(
            not isinstance(sample_id, str) or not sample_id.strip()
            for sample_id in self.sample_ids
        ):
            raise ValueError("sample_ids must contain nonempty strings")

    def to_mapping(self) -> dict[str, object]:
        return {
            "alpha": self.alpha,
            "lower_successes": self.lower_successes,
            "sample_count": self.sample_count,
            "sample_ids": list(self.sample_ids),
            "upper_successes": self.upper_successes,
        }


@dataclass(frozen=True)
class AlphaProbabilityEstimatorPacket:
    """Synthetic E4.S1 handoff from endpoint event counts to probability rows."""

    packet_id: str
    event_count_records: tuple[AlphaEventCountRecord, ...]
    endpoint_metadata: Mapping[str, object]
    probability_rows: tuple[dict[str, object], ...]
    confidence_level: float = 0.95
    require_nested: bool = True
    use_status: str = ALPHA_EVENT_COUNT_ESTIMATOR_USE_STATUS
    protocol: str = ALPHA_EVENT_COUNT_ESTIMATOR_PROTOCOL

    def __post_init__(self) -> None:
        if not isinstance(self.packet_id, str) or not self.packet_id.strip():
            raise ValueError("packet_id must be a nonempty string")
        if self.protocol != ALPHA_EVENT_COUNT_ESTIMATOR_PROTOCOL:
            raise ValueError(
                f"protocol must be {ALPHA_EVENT_COUNT_ESTIMATOR_PROTOCOL!r}"
            )
        if self.use_status != ALPHA_EVENT_COUNT_ESTIMATOR_USE_STATUS:
            raise ValueError(
                "alpha probability estimator packets must remain synthetic-only"
            )
        if not 0.0 < self.confidence_level < 1.0:
            raise ValueError("confidence_level must be in (0, 1)")
        _validate_alpha_event_count_records(
            self.event_count_records,
            require_nested=self.require_nested,
        )
        _validate_alpha_event_endpoint_metadata(self.endpoint_metadata)
        expected_rows = probability_rows_from_alpha_event_counts(
            self.event_count_records,
            confidence_level=self.confidence_level,
            require_nested=self.require_nested,
        )
        if self.probability_rows != expected_rows:
            raise ValueError(
                "probability_rows must be derived from event_count_records"
            )

    @property
    def real_use_blocker_manifest(self) -> dict[str, object]:
        return build_alpha_probability_real_use_blocker_manifest(
            manifest_id=f"{self.packet_id}:real-use-blockers"
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "confidence_level": self.confidence_level,
            "endpoint_metadata": dict(self.endpoint_metadata),
            "event_count_records": [
                record.to_mapping() for record in self.event_count_records
            ],
            "invariants": {
                "alpha_indexed_lower_upper_reporting": True,
                "crn_sample_identity": "same ordered sample_ids across alpha rows",
                "defuzzification": "forbidden",
                "endpoint_metadata_required": True,
                "probability_widening": "forbidden",
            },
            "non_claims": [
                "no real trajectories",
                "no real P(E)",
                "no real rho sweep",
                "no capacity choice",
                "no A-013 or G2 numerical signoff",
                "no G3 verdict",
                "no decision-engine recommendation",
                "no manuscript number",
            ],
            "packet_id": self.packet_id,
            "probability_rows": [dict(row) for row in self.probability_rows],
            "protocol": self.protocol,
            "real_use_blocker_manifest": self.real_use_blocker_manifest,
            "require_nested": self.require_nested,
            "use_status": self.use_status,
        }


@dataclass(frozen=True)
class OutputErrorEndpointCountBridgePacket:
    """Synthetic E5.S3 bridge from endpoint counts to alpha probabilities."""

    packet_id: str
    alpha_probability_packet: AlphaProbabilityEstimatorPacket
    endpoint_metadata: Mapping[str, object]
    use_status: str = OUTPUT_ERROR_ENDPOINT_COUNT_BRIDGE_USE_STATUS
    protocol: str = OUTPUT_ERROR_ENDPOINT_COUNT_BRIDGE_PROTOCOL

    def __post_init__(self) -> None:
        if not isinstance(self.packet_id, str) or not self.packet_id.strip():
            raise ValueError("packet_id must be a nonempty string")
        if self.protocol != OUTPUT_ERROR_ENDPOINT_COUNT_BRIDGE_PROTOCOL:
            raise ValueError(
                f"protocol must be {OUTPUT_ERROR_ENDPOINT_COUNT_BRIDGE_PROTOCOL!r}"
            )
        if self.use_status != OUTPUT_ERROR_ENDPOINT_COUNT_BRIDGE_USE_STATUS:
            raise ValueError("output-error endpoint-count bridge must remain synthetic")
        if not isinstance(self.alpha_probability_packet, AlphaProbabilityEstimatorPacket):
            raise TypeError(
                "alpha_probability_packet must be an AlphaProbabilityEstimatorPacket"
            )
        _validate_output_error_endpoint_count_metadata(self.endpoint_metadata)
        if dict(self.endpoint_metadata) != dict(
            self.alpha_probability_packet.endpoint_metadata
        ):
            raise ValueError(
                "bridge endpoint_metadata must match the alpha estimator packet"
            )

    @property
    def real_use_blocker_manifest(self) -> dict[str, object]:
        return build_output_error_endpoint_count_real_use_blocker_manifest(
            manifest_id=f"{self.packet_id}:real-use-blockers"
        )

    def to_mapping(self) -> dict[str, object]:
        probability_packet = self.alpha_probability_packet.to_mapping()
        return {
            "alpha_probability_estimator_packet": probability_packet,
            "endpoint_metadata": dict(self.endpoint_metadata),
            "invariants": {
                "alpha_indexed_lower_upper_reporting": True,
                "crn_sample_identity": "same ordered sample_ids across alpha rows",
                "defuzzification": "forbidden",
                "endpoint_count_provenance": OUTPUT_ERROR_ENDPOINT_COUNT_PROVENANCE,
                "endpoint_error_dependence": OUTPUT_ERROR_DEPENDENCE,
                "loading_endpoint_application": OUTPUT_ERROR_APPLICATION,
                "probability_widening": "forbidden",
                "unwidened_direction_gate": "unwidened_p_net_import_mask",
            },
            "non_claims": [
                "no real trajectories",
                "no real P(E)",
                "no real rho sweep",
                "no capacity choice",
                "no A-013 or G2 numerical signoff",
                "no G3 verdict",
                "no decision-engine recommendation",
                "no manuscript number",
            ],
            "packet_id": self.packet_id,
            "probability_rows": list(probability_packet["probability_rows"]),
            "protocol": self.protocol,
            "real_use_blocker_manifest": self.real_use_blocker_manifest,
            "use_status": self.use_status,
        }


@dataclass(frozen=True)
class RealOutputErrorEndpointCountManifestPreflight:
    """Fail-closed preflight for future real E5.S3 endpoint-count manifests."""

    manifest_id: str
    alpha_grid: tuple[float, ...]
    event_count_records: tuple[AlphaEventCountRecord, ...]
    endpoint_metadata: Mapping[str, object]
    approval_ids: Mapping[str, object]
    artifact_references: Mapping[str, object]
    threshold_semantics: Mapping[str, object]
    alpha_probability_packet: AlphaProbabilityEstimatorPacket
    use_status: str = REAL_OUTPUT_ERROR_ENDPOINT_COUNT_USE_STATUS
    protocol: str = REAL_OUTPUT_ERROR_ENDPOINT_COUNT_MANIFEST_PROTOCOL

    def __post_init__(self) -> None:
        if not isinstance(self.manifest_id, str) or not self.manifest_id.strip():
            raise ValueError("manifest_id must be a nonempty string")
        if self.protocol != REAL_OUTPUT_ERROR_ENDPOINT_COUNT_MANIFEST_PROTOCOL:
            raise ValueError(
                f"protocol must be {REAL_OUTPUT_ERROR_ENDPOINT_COUNT_MANIFEST_PROTOCOL!r}"
            )
        if self.use_status != REAL_OUTPUT_ERROR_ENDPOINT_COUNT_USE_STATUS:
            raise ValueError("real endpoint-count manifest preflight cannot be relabeled")
        _validate_real_output_error_endpoint_count_inputs(
            alpha_grid=self.alpha_grid,
            event_count_records=self.event_count_records,
            endpoint_metadata=self.endpoint_metadata,
            approval_ids=self.approval_ids,
            artifact_references=self.artifact_references,
            threshold_semantics=self.threshold_semantics,
        )
        if not isinstance(self.alpha_probability_packet, AlphaProbabilityEstimatorPacket):
            raise TypeError(
                "alpha_probability_packet must be an AlphaProbabilityEstimatorPacket"
            )
        if dict(self.alpha_probability_packet.endpoint_metadata) != dict(
            self.endpoint_metadata
        ):
            raise ValueError(
                "alpha_probability_packet endpoint metadata must match the manifest"
            )
        if self.alpha_probability_packet.event_count_records != self.event_count_records:
            raise ValueError("alpha_probability_packet counts must match the manifest")

    @property
    def blocker_manifest(self) -> dict[str, object]:
        return build_real_output_error_endpoint_count_blocker_manifest(
            manifest_id=f"{self.manifest_id}:blockers"
        )

    def to_mapping(self) -> dict[str, object]:
        probability_packet = self.alpha_probability_packet.to_mapping()
        return {
            "alpha_grid": list(self.alpha_grid),
            "alpha_probability_estimator_packet": probability_packet,
            "approval_ids": dict(self.approval_ids),
            "artifact_references": dict(self.artifact_references),
            "blocker_manifest": self.blocker_manifest,
            "endpoint_metadata": dict(self.endpoint_metadata),
            "event_count_records": [
                record.to_mapping() for record in self.event_count_records
            ],
            "invariants": {
                "alpha_indexed_lower_upper_reporting": True,
                "crn_sample_identity": "same ordered sample_ids across alpha rows",
                "defuzzification": "forbidden",
                "endpoint_count_provenance": OUTPUT_ERROR_ENDPOINT_COUNT_PROVENANCE,
                "endpoint_error_dependence": OUTPUT_ERROR_DEPENDENCE,
                "loading_endpoint_application": OUTPUT_ERROR_APPLICATION,
                "probability_widening": "forbidden",
                "unwidened_direction_gate": "unwidened_p_net_import_mask",
            },
            "manifest_id": self.manifest_id,
            "manifest_protocol": self.protocol,
            "non_claims": list(_REAL_OUTPUT_ERROR_ENDPOINT_COUNT_NON_CLAIMS),
            "probability_rows": list(probability_packet["probability_rows"]),
            "ready_for_real_use": False,
            "threshold_semantics": dict(self.threshold_semantics),
            "use_status": self.use_status,
        }


def probability_rows_from_alpha_event_counts(
    event_count_records: Sequence[AlphaEventCountRecord | Mapping[str, object]],
    *,
    confidence_level: float = 0.95,
    require_nested: bool = True,
) -> tuple[dict[str, object], ...]:
    """Convert precomputed endpoint event counts to alpha-indexed rows.

    This helper is deliberately count-only: endpoint events must already have
    been produced from widened loading trajectories. It recomputes probabilities
    and CIs from counts so no downstream report can smuggle in a probability
    margin or a defuzzified scalar.
    """

    _reject_alpha_event_count_collapsed_fields(event_count_records)
    records = tuple(
        _coerce_alpha_event_count_record(record) for record in event_count_records
    )
    _validate_alpha_event_count_records(records, require_nested=require_nested)
    rows: list[dict[str, object]] = []
    for record in sorted(records, key=lambda item: item.alpha):
        lower = probability_estimate_from_counts(
            record.lower_successes,
            record.sample_count,
            confidence_level=confidence_level,
        )
        upper = probability_estimate_from_counts(
            record.upper_successes,
            record.sample_count,
            confidence_level=confidence_level,
        )
        rows.append(
            {
                "alpha": record.alpha,
                "ci_lower_lower": lower.ci_lower,
                "ci_lower_upper": lower.ci_upper,
                "ci_upper_lower": upper.ci_lower,
                "ci_upper_upper": upper.ci_upper,
                "lower_successes": record.lower_successes,
                "p_lower": lower.probability,
                "p_upper": upper.probability,
                "sample_count": record.sample_count,
                "sample_ids": list(record.sample_ids),
                "upper_successes": record.upper_successes,
            }
        )
    assert_alpha_indexed_probability_report(rows)
    return tuple(rows)


def build_alpha_probability_estimator_packet(
    *,
    packet_id: str,
    event_count_records: Sequence[AlphaEventCountRecord | Mapping[str, object]],
    endpoint_metadata: Mapping[str, object],
    confidence_level: float = 0.95,
    require_nested: bool = True,
) -> AlphaProbabilityEstimatorPacket:
    """Build the synthetic/fail-closed E4.S1 probability-estimator packet."""

    records = tuple(
        _coerce_alpha_event_count_record(record) for record in event_count_records
    )
    rows = probability_rows_from_alpha_event_counts(
        records,
        confidence_level=confidence_level,
        require_nested=require_nested,
    )
    return AlphaProbabilityEstimatorPacket(
        packet_id=packet_id,
        event_count_records=records,
        endpoint_metadata=endpoint_metadata,
        probability_rows=rows,
        confidence_level=confidence_level,
        require_nested=require_nested,
    )


def build_alpha_probability_real_use_blocker_manifest(
    *, manifest_id: str
) -> dict[str, object]:
    """Return blocker keys for future real E4 probability-estimator use."""

    if not isinstance(manifest_id, str) or not manifest_id.strip():
        raise ValueError("manifest_id must be a nonempty string")
    return {
        "blockers": list(ALPHA_EVENT_COUNT_REAL_USE_BLOCKERS),
        "manifest_id": manifest_id,
        "manifest_protocol": ALPHA_EVENT_COUNT_REAL_USE_BLOCKER_PROTOCOL,
        "non_claims": [
            "no real trajectories accepted by this scaffold",
            "no real P(E)",
            "no capacity convention choice",
            "no A-013 or G2 numerical signoff",
            "no G3 verdict",
            "no manuscript number",
        ],
        "ready_for_real_use": False,
        "use_status": "real-use-blocker",
    }


def build_output_error_endpoint_count_bridge_packet(
    *,
    packet_id: str,
    event_count_records: Sequence[AlphaEventCountRecord | Mapping[str, object]],
    endpoint_metadata: Mapping[str, object],
    confidence_level: float = 0.95,
    require_nested: bool = True,
) -> OutputErrorEndpointCountBridgePacket:
    """Bridge G1-A2 endpoint event counts into the alpha estimator scaffold."""

    _validate_output_error_endpoint_count_metadata(endpoint_metadata)
    probability_packet = build_alpha_probability_estimator_packet(
        packet_id=f"{packet_id}:alpha-probability-estimator",
        event_count_records=event_count_records,
        endpoint_metadata=endpoint_metadata,
        confidence_level=confidence_level,
        require_nested=require_nested,
    )
    return OutputErrorEndpointCountBridgePacket(
        packet_id=packet_id,
        alpha_probability_packet=probability_packet,
        endpoint_metadata=endpoint_metadata,
    )


def build_output_error_endpoint_count_real_use_blocker_manifest(
    *, manifest_id: str
) -> dict[str, object]:
    """Return blocker keys for future real E5.S3 endpoint-count bridge use."""

    if not isinstance(manifest_id, str) or not manifest_id.strip():
        raise ValueError("manifest_id must be a nonempty string")
    return {
        "blockers": list(OUTPUT_ERROR_ENDPOINT_COUNT_REAL_USE_BLOCKERS),
        "manifest_id": manifest_id,
        "manifest_protocol": OUTPUT_ERROR_ENDPOINT_COUNT_REAL_USE_BLOCKER_PROTOCOL,
        "non_claims": [
            "no real trajectories accepted by this scaffold",
            "no real P(E)",
            "no capacity convention choice",
            "no A-013 or G2 numerical signoff",
            "no G3 verdict",
            "no manuscript number",
        ],
        "ready_for_real_use": False,
        "use_status": "real-use-blocker",
    }


def build_real_output_error_endpoint_count_manifest_preflight(
    *,
    manifest_id: str,
    alpha_grid: Sequence[float],
    event_count_records: Sequence[AlphaEventCountRecord | Mapping[str, object]],
    endpoint_metadata: Mapping[str, object],
    approval_ids: Mapping[str, object],
    artifact_references: Mapping[str, object],
    threshold_semantics: Mapping[str, object],
    confidence_level: float = 0.95,
) -> RealOutputErrorEndpointCountManifestPreflight:
    """Build a fail-closed preflight for future real endpoint-count manifests."""

    grid = _coerce_alpha_grid(alpha_grid)
    records = tuple(
        _coerce_alpha_event_count_record(record) for record in event_count_records
    )
    _validate_real_output_error_endpoint_count_inputs(
        alpha_grid=grid,
        event_count_records=records,
        endpoint_metadata=endpoint_metadata,
        approval_ids=approval_ids,
        artifact_references=artifact_references,
        threshold_semantics=threshold_semantics,
    )
    probability_packet = build_alpha_probability_estimator_packet(
        packet_id=f"{manifest_id}:alpha-probability-estimator",
        event_count_records=records,
        endpoint_metadata=endpoint_metadata,
        confidence_level=confidence_level,
        require_nested=True,
    )
    return RealOutputErrorEndpointCountManifestPreflight(
        manifest_id=manifest_id,
        alpha_grid=grid,
        event_count_records=records,
        endpoint_metadata=endpoint_metadata,
        approval_ids=approval_ids,
        artifact_references=artifact_references,
        threshold_semantics=threshold_semantics,
        alpha_probability_packet=probability_packet,
    )


def build_real_output_error_endpoint_count_blocker_manifest(
    *, manifest_id: str
) -> dict[str, object]:
    """Return the fail-closed blocker packet for future real endpoint-count use."""

    if not isinstance(manifest_id, str) or not manifest_id.strip():
        raise ValueError("manifest_id must be a nonempty string")
    return {
        "blocker_keys": list(REAL_OUTPUT_ERROR_ENDPOINT_COUNT_BLOCKERS),
        "blockers": {
            "missing_real_loading_trajectory_manifest": (
                "real LoadingTrajectoryResult manifest is missing"
            ),
            "missing_real_output_error_endpoint_count_manifest": (
                "real output-error endpoint-count manifest is missing"
            ),
            "missing_signed_g2_tier1_endpoints": (
                "signed G2 Tier-1 endpoint envelope is missing"
            ),
            "missing_signed_a013_grid_error": (
                "signed A-013 grid-error value/form is missing"
            ),
            "missing_capacity_convention_and_provenance": (
                "capacity convention and denominator provenance are missing"
            ),
            "missing_a016_scenario_consistency": (
                "A-016 scenario consistency manifest is missing"
            ),
            "missing_g3_monotonicity_approval_if_vertex_shortcut_claimed": (
                "G3 approval is missing if vertex shortcut output is claimed"
            ),
        },
        "manifest_id": manifest_id,
        "manifest_protocol": REAL_OUTPUT_ERROR_ENDPOINT_COUNT_BLOCKER_PROTOCOL,
        "non_claims": list(_REAL_OUTPUT_ERROR_ENDPOINT_COUNT_NON_CLAIMS),
        "ready_for_real_use": False,
        "use_status": "real-use-blocker",
    }


def assert_alpha_probability_estimator_packet(payload: Mapping[str, object]) -> None:
    """Validate a serialized synthetic alpha probability-estimator packet."""

    _reject_alpha_event_count_collapsed_fields(payload)
    required = {
        "confidence_level",
        "endpoint_metadata",
        "event_count_records",
        "invariants",
        "packet_id",
        "probability_rows",
        "protocol",
        "real_use_blocker_manifest",
        "require_nested",
        "use_status",
    }
    _require_mapping_fields(payload, required, name="alpha estimator packet")
    if payload["protocol"] != ALPHA_EVENT_COUNT_ESTIMATOR_PROTOCOL:
        raise ValueError(
            f"protocol must be {ALPHA_EVENT_COUNT_ESTIMATOR_PROTOCOL!r}"
        )
    if payload["use_status"] != ALPHA_EVENT_COUNT_ESTIMATOR_USE_STATUS:
        raise ValueError(
            "alpha probability estimator packets must remain synthetic-only"
        )
    if not isinstance(payload["require_nested"], bool):
        raise TypeError("require_nested must be boolean")
    confidence_level = float(payload["confidence_level"])
    records = tuple(
        _coerce_alpha_event_count_record(
            _expect_mapping(record, name="event_count_record")
        )
        for record in _expect_sequence(
            payload["event_count_records"], name="event_count_records"
        )
    )
    expected = build_alpha_probability_estimator_packet(
        packet_id=str(payload["packet_id"]),
        event_count_records=records,
        endpoint_metadata=_expect_mapping(
            payload["endpoint_metadata"], name="endpoint_metadata"
        ),
        confidence_level=confidence_level,
        require_nested=bool(payload["require_nested"]),
    )
    rows = tuple(
        dict(_expect_mapping(row, name="probability_row"))
        for row in _expect_sequence(
            payload["probability_rows"], name="probability_rows"
        )
    )
    if rows != expected.probability_rows:
        raise ValueError("probability_rows must be recomputable from event counts")
    if payload["real_use_blocker_manifest"] != expected.real_use_blocker_manifest:
        raise ValueError("real_use_blocker_manifest must match protocol blockers")
    invariants = _expect_mapping(payload["invariants"], name="invariants")
    if invariants.get("defuzzification") != "forbidden":
        raise ValueError("defuzzification must remain forbidden")
    if invariants.get("probability_widening") != "forbidden":
        raise ValueError("probability widening must remain forbidden")
    if invariants.get("alpha_indexed_lower_upper_reporting") is not True:
        raise ValueError("alpha-indexed lower/upper reporting must be true")


def assert_output_error_endpoint_count_bridge_packet(
    payload: Mapping[str, object],
) -> None:
    """Validate a serialized synthetic E5.S3 endpoint-count bridge packet."""

    _reject_alpha_event_count_collapsed_fields(payload)
    required = {
        "alpha_probability_estimator_packet",
        "endpoint_metadata",
        "invariants",
        "packet_id",
        "probability_rows",
        "protocol",
        "real_use_blocker_manifest",
        "use_status",
    }
    _require_mapping_fields(payload, required, name="output-error bridge packet")
    if payload["protocol"] != OUTPUT_ERROR_ENDPOINT_COUNT_BRIDGE_PROTOCOL:
        raise ValueError(
            f"protocol must be {OUTPUT_ERROR_ENDPOINT_COUNT_BRIDGE_PROTOCOL!r}"
        )
    if payload["use_status"] != OUTPUT_ERROR_ENDPOINT_COUNT_BRIDGE_USE_STATUS:
        raise ValueError("output-error endpoint-count bridge must remain synthetic")

    endpoint_metadata = _expect_mapping(
        payload["endpoint_metadata"], name="endpoint_metadata"
    )
    _validate_output_error_endpoint_count_metadata(endpoint_metadata)
    alpha_packet = _expect_mapping(
        payload["alpha_probability_estimator_packet"],
        name="alpha_probability_estimator_packet",
    )
    assert_alpha_probability_estimator_packet(alpha_packet)
    if dict(alpha_packet["endpoint_metadata"]) != dict(endpoint_metadata):
        raise ValueError(
            "bridge endpoint_metadata must match the alpha estimator packet"
        )
    rows = tuple(
        dict(_expect_mapping(row, name="probability_row"))
        for row in _expect_sequence(payload["probability_rows"], name="probability_rows")
    )
    if rows != tuple(dict(row) for row in alpha_packet["probability_rows"]):
        raise ValueError(
            "bridge probability_rows must be supplied by the alpha estimator packet"
        )
    expected_blockers = build_output_error_endpoint_count_real_use_blocker_manifest(
        manifest_id=f"{payload['packet_id']}:real-use-blockers"
    )
    if payload["real_use_blocker_manifest"] != expected_blockers:
        raise ValueError("real_use_blocker_manifest must match E5.S3 blockers")

    invariants = _expect_mapping(payload["invariants"], name="invariants")
    expected_invariants = {
        "alpha_indexed_lower_upper_reporting": True,
        "crn_sample_identity": "same ordered sample_ids across alpha rows",
        "defuzzification": "forbidden",
        "endpoint_count_provenance": OUTPUT_ERROR_ENDPOINT_COUNT_PROVENANCE,
        "endpoint_error_dependence": OUTPUT_ERROR_DEPENDENCE,
        "loading_endpoint_application": OUTPUT_ERROR_APPLICATION,
        "probability_widening": "forbidden",
        "unwidened_direction_gate": "unwidened_p_net_import_mask",
    }
    if dict(invariants) != expected_invariants:
        raise ValueError("bridge invariants must match the E5.S3 protocol")



def assert_real_output_error_endpoint_count_manifest_preflight(
    payload: Mapping[str, object],
) -> None:
    """Validate a serialized real endpoint-count preflight payload."""

    _reject_alpha_event_count_collapsed_fields(payload)
    required = {
        "alpha_grid",
        "alpha_probability_estimator_packet",
        "approval_ids",
        "artifact_references",
        "blocker_manifest",
        "endpoint_metadata",
        "event_count_records",
        "invariants",
        "manifest_id",
        "manifest_protocol",
        "non_claims",
        "probability_rows",
        "ready_for_real_use",
        "threshold_semantics",
        "use_status",
    }
    _require_mapping_fields(payload, required, name="real endpoint-count preflight")
    if payload["manifest_protocol"] != REAL_OUTPUT_ERROR_ENDPOINT_COUNT_MANIFEST_PROTOCOL:
        raise ValueError(
            f"manifest_protocol must be {REAL_OUTPUT_ERROR_ENDPOINT_COUNT_MANIFEST_PROTOCOL!r}"
        )
    if payload["use_status"] != REAL_OUTPUT_ERROR_ENDPOINT_COUNT_USE_STATUS:
        raise ValueError("real endpoint-count preflight cannot be relabeled")
    if payload["ready_for_real_use"] is not False:
        raise ValueError("real endpoint-count preflight must fail closed today")
    if tuple(_expect_sequence(payload["non_claims"], name="non_claims")) != (
        _REAL_OUTPUT_ERROR_ENDPOINT_COUNT_NON_CLAIMS
    ):
        raise ValueError("real endpoint-count non_claims must match the protocol")

    alpha_grid = _coerce_alpha_grid(
        _expect_sequence(payload["alpha_grid"], name="alpha_grid")
    )
    records = tuple(
        _coerce_alpha_event_count_record(
            _expect_mapping(record, name="event_count_record")
        )
        for record in _expect_sequence(
            payload["event_count_records"], name="event_count_records"
        )
    )
    endpoint_metadata = _expect_mapping(
        payload["endpoint_metadata"], name="endpoint_metadata"
    )
    approval_ids = _expect_mapping(payload["approval_ids"], name="approval_ids")
    artifact_references = _expect_mapping(
        payload["artifact_references"], name="artifact_references"
    )
    threshold_semantics = _expect_mapping(
        payload["threshold_semantics"], name="threshold_semantics"
    )
    _validate_real_output_error_endpoint_count_inputs(
        alpha_grid=alpha_grid,
        event_count_records=records,
        endpoint_metadata=endpoint_metadata,
        approval_ids=approval_ids,
        artifact_references=artifact_references,
        threshold_semantics=threshold_semantics,
    )
    alpha_packet = _expect_mapping(
        payload["alpha_probability_estimator_packet"],
        name="alpha_probability_estimator_packet",
    )
    assert_alpha_probability_estimator_packet(alpha_packet)
    if dict(alpha_packet["endpoint_metadata"]) != dict(endpoint_metadata):
        raise ValueError("alpha estimator endpoint metadata must match preflight")
    rows = tuple(
        dict(_expect_mapping(row, name="probability_row"))
        for row in _expect_sequence(payload["probability_rows"], name="probability_rows")
    )
    if rows != tuple(dict(row) for row in alpha_packet["probability_rows"]):
        raise ValueError("probability_rows must come from the alpha estimator packet")
    expected_blockers = build_real_output_error_endpoint_count_blocker_manifest(
        manifest_id=f"{payload['manifest_id']}:blockers"
    )
    if payload["blocker_manifest"] != expected_blockers:
        raise ValueError("blocker_manifest must match the real endpoint-count protocol")
    expected_invariants = {
        "alpha_indexed_lower_upper_reporting": True,
        "crn_sample_identity": "same ordered sample_ids across alpha rows",
        "defuzzification": "forbidden",
        "endpoint_count_provenance": OUTPUT_ERROR_ENDPOINT_COUNT_PROVENANCE,
        "endpoint_error_dependence": OUTPUT_ERROR_DEPENDENCE,
        "loading_endpoint_application": OUTPUT_ERROR_APPLICATION,
        "probability_widening": "forbidden",
        "unwidened_direction_gate": "unwidened_p_net_import_mask",
    }
    if (
        dict(_expect_mapping(payload["invariants"], name="invariants"))
        != expected_invariants
    ):
        raise ValueError("real endpoint-count invariants must match the protocol")


def _coerce_alpha_event_count_record(
    record: AlphaEventCountRecord | Mapping[str, object],
) -> AlphaEventCountRecord:
    if isinstance(record, AlphaEventCountRecord):
        return record
    mapping = _expect_mapping(record, name="event_count_record")
    required = {
        "alpha",
        "lower_successes",
        "sample_count",
        "sample_ids",
        "upper_successes",
    }
    _require_mapping_fields(mapping, required, name="event_count_record")
    return AlphaEventCountRecord(
        alpha=float(mapping["alpha"]),
        lower_successes=_expect_nonnegative_int(
            mapping["lower_successes"], name="lower_successes"
        ),
        upper_successes=_expect_nonnegative_int(
            mapping["upper_successes"], name="upper_successes"
        ),
        sample_count=_expect_nonnegative_int(
            mapping["sample_count"], name="sample_count"
        ),
        sample_ids=tuple(
            str(sample_id)
            for sample_id in _expect_sequence(mapping["sample_ids"], name="sample_ids")
        ),
    )


def _coerce_alpha_grid(alpha_grid: Sequence[float]) -> tuple[float, ...]:
    if isinstance(alpha_grid, (str, bytes)) or not isinstance(alpha_grid, Sequence):
        raise TypeError("alpha_grid must be a sequence")
    grid = tuple(float(alpha) for alpha in alpha_grid)
    if not grid:
        raise ValueError("alpha_grid must not be empty")
    if any(not math.isfinite(alpha) or not 0.0 <= alpha <= 1.0 for alpha in grid):
        raise ValueError("alpha_grid values must be finite and in [0, 1]")
    if tuple(sorted(grid)) != grid or len(set(grid)) != len(grid):
        raise ValueError("alpha_grid must be strictly increasing")
    return grid


def _validate_real_output_error_endpoint_count_inputs(
    *,
    alpha_grid: tuple[float, ...],
    event_count_records: Sequence[AlphaEventCountRecord],
    endpoint_metadata: Mapping[str, object],
    approval_ids: Mapping[str, object],
    artifact_references: Mapping[str, object],
    threshold_semantics: Mapping[str, object],
) -> None:
    _validate_alpha_event_count_records(event_count_records, require_nested=True)
    record_alphas = tuple(
        record.alpha
        for record in sorted(event_count_records, key=lambda item: item.alpha)
    )
    if record_alphas != alpha_grid:
        raise ValueError("event_count_records must match the required alpha_grid")
    _validate_real_output_error_endpoint_count_metadata(endpoint_metadata)
    _validate_real_endpoint_count_approval_ids(approval_ids)
    _validate_real_endpoint_count_artifact_references(artifact_references)
    _validate_real_endpoint_count_threshold_semantics(threshold_semantics)
    _require_reference_match(
        approval_ids,
        "a013_grid_error_approval_id",
        endpoint_metadata,
        "a013_grid_error_approval_id",
    )
    _require_reference_match(
        approval_ids,
        "g2_tier1_envelope_approval_id",
        endpoint_metadata,
        "g2_tier1_envelope_approval_id",
    )
    _require_reference_match(
        approval_ids,
        "a016_scenario_consistency_id",
        endpoint_metadata,
        "a016_scenario_consistency_id",
    )
    _require_reference_match(
        artifact_references,
        "capacity_convention_linkage",
        endpoint_metadata,
        "capacity_convention_linkage",
    )
    _require_reference_match(
        artifact_references,
        "capacity_denominator_provenance",
        endpoint_metadata,
        "capacity_denominator_provenance",
    )
    _require_reference_match(
        artifact_references,
        "output_error_endpoint_count_manifest_id",
        endpoint_metadata,
        "endpoint_record_manifest_id",
    )
    if threshold_semantics["direction_gate"] != endpoint_metadata["direction_gate"]:
        raise ValueError("threshold direction_gate must match endpoint metadata")


def _validate_real_output_error_endpoint_count_metadata(
    metadata: Mapping[str, object]
) -> None:
    _validate_alpha_event_endpoint_metadata(metadata)
    required = _ALPHA_EVENT_COUNT_ENDPOINT_METADATA_FIELDS | {
        "dependence_assumption",
        "endpoint_count_provenance",
        "lower_composition_formula",
        "output_error_protocol",
        "upper_composition_formula",
    }
    _require_mapping_fields(metadata, required, name="real_endpoint_count_metadata")
    if metadata["endpoint_count_provenance"] != OUTPUT_ERROR_ENDPOINT_COUNT_PROVENANCE:
        raise ValueError(
            "endpoint counts must be from loading endpoints before event detection"
        )
    if metadata["output_error_protocol"] != OUTPUT_ERROR_ENDPOINT_COUNT_PROTOCOL:
        raise ValueError("endpoint counts must use the G1-A2 output-error protocol")
    if metadata["dependence_assumption"] != OUTPUT_ERROR_DEPENDENCE:
        raise ValueError("endpoint counts must preserve arbitrary unknown dependence")
    if metadata["lower_composition_formula"] != OUTPUT_ERROR_LOWER_FORMULA:
        raise ValueError("lower composition formula must match G1-A2")
    if metadata["upper_composition_formula"] != OUTPUT_ERROR_UPPER_FORMULA:
        raise ValueError("upper composition formula must match G1-A2")
    for key, value in metadata.items():
        if key.endswith("_status"):
            _expect_real_clean_reference(value, name=key)
    for field in _OUTPUT_ERROR_ENDPOINT_COUNT_REFERENCE_FIELDS:
        _expect_real_clean_reference(metadata[field], name=field)


def _validate_real_endpoint_count_approval_ids(approval_ids: Mapping[str, object]) -> None:
    _require_mapping_fields(
        approval_ids,
        set(_REAL_OUTPUT_ERROR_ENDPOINT_COUNT_REQUIRED_APPROVAL_IDS),
        name="approval_ids",
    )
    for field in _REAL_OUTPUT_ERROR_ENDPOINT_COUNT_REQUIRED_APPROVAL_IDS:
        _expect_real_clean_reference(approval_ids[field], name=field)


def _validate_real_endpoint_count_artifact_references(
    artifact_references: Mapping[str, object]
) -> None:
    _require_mapping_fields(
        artifact_references,
        set(_REAL_OUTPUT_ERROR_ENDPOINT_COUNT_REQUIRED_ARTIFACT_REFERENCES),
        name="artifact_references",
    )
    for field in _REAL_OUTPUT_ERROR_ENDPOINT_COUNT_REQUIRED_ARTIFACT_REFERENCES:
        _expect_real_clean_reference(artifact_references[field], name=field)


def _validate_real_endpoint_count_threshold_semantics(
    threshold_semantics: Mapping[str, object]
) -> None:
    _require_mapping_fields(
        threshold_semantics,
        {
            "comparator",
            "direction_gate",
            "event_scope",
            "min_consecutive_steps",
            "threshold_pu",
            "timestep_seconds",
        },
        name="threshold_semantics",
    )
    if threshold_semantics["comparator"] != "strict_greater_than":
        raise ValueError("threshold comparator must be strict_greater_than")
    if threshold_semantics["direction_gate"] != "unwidened_p_net_import_mask":
        raise ValueError("threshold direction_gate must use unwidened P_net")
    if threshold_semantics["event_scope"] != "full_planning_year":
        raise ValueError("threshold event_scope must be full_planning_year")
    if threshold_semantics["threshold_pu"] != 1.0:
        raise ValueError("threshold_pu must match G0-A3 primary 1.0 p.u. event")
    if threshold_semantics["min_consecutive_steps"] != 4:
        raise ValueError("min_consecutive_steps must match the four-step event")
    if threshold_semantics["timestep_seconds"] != 900:
        raise ValueError("timestep_seconds must record 15-minute cadence")


def _expect_real_clean_reference(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    reference = value
    if not reference.strip():
        raise ValueError(f"{name} must be a nonempty string")
    lowered = reference.lower()
    stale = [
        token
        for token in _REAL_OUTPUT_ERROR_ENDPOINT_COUNT_STALE_REFERENCE_TOKENS
        if token in lowered
    ]
    if stale:
        raise ValueError(f"{name} contains stale or unsigned token(s): {stale}")
    return reference


def _require_reference_match(
    left: Mapping[str, object],
    left_key: str,
    right: Mapping[str, object],
    right_key: str,
) -> None:
    if str(left[left_key]) != str(right[right_key]):
        raise ValueError(f"{left_key} must match {right_key}")

def _validate_alpha_event_count_records(
    records: Sequence[AlphaEventCountRecord], *, require_nested: bool
) -> None:
    if not records:
        raise ValueError("event_count_records must not be empty")
    ordered = tuple(sorted(records, key=lambda item: item.alpha))
    alphas = tuple(record.alpha for record in ordered)
    if len(set(alphas)) != len(alphas):
        raise ValueError("alpha rows must be unique")
    reference_sample_count = ordered[0].sample_count
    reference_sample_ids = ordered[0].sample_ids
    previous_lower = ordered[0].lower_successes / ordered[0].sample_count
    previous_upper = ordered[0].upper_successes / ordered[0].sample_count
    for record in ordered:
        if record.sample_count != reference_sample_count:
            raise ValueError("all alpha rows must use the same sample_count")
        if record.sample_ids != reference_sample_ids:
            raise ValueError("all alpha rows must use the same ordered sample_ids")
        lower_probability = record.lower_successes / record.sample_count
        upper_probability = record.upper_successes / record.sample_count
        if require_nested:
            if (
                lower_probability < previous_lower
                or upper_probability > previous_upper
            ):
                raise ValueError("alpha probability rows must be nested")
        previous_lower = lower_probability
        previous_upper = upper_probability


def _validate_alpha_event_endpoint_metadata(metadata: Mapping[str, object]) -> None:
    _require_mapping_fields(
        metadata,
        _ALPHA_EVENT_COUNT_ENDPOINT_METADATA_FIELDS,
        name="endpoint_metadata",
    )
    for field in _ALPHA_EVENT_COUNT_ENDPOINT_METADATA_FIELDS:
        if not isinstance(metadata[field], str) or not str(metadata[field]).strip():
            raise ValueError(f"endpoint_metadata {field} must be a nonempty string")
    if metadata["loading_endpoint_application"] != OUTPUT_ERROR_APPLICATION:
        raise ValueError("endpoint metadata must apply endpoints before event detection")
    if metadata["direction_gate"] != "unwidened_p_net_import_mask":
        raise ValueError(
            "endpoint metadata must preserve the unwidened P_net direction gate"
        )
    if metadata["probability_widening"] != "forbidden":
        raise ValueError("endpoint metadata must forbid probability widening")
    if metadata["error_sampling"] != OUTPUT_ERROR_SAMPLING:
        raise ValueError("endpoint metadata must forbid independent error sampling")



def _validate_output_error_endpoint_count_metadata(metadata: Mapping[str, object]) -> None:
    _validate_alpha_event_endpoint_metadata(metadata)
    _require_mapping_fields(
        metadata,
        _OUTPUT_ERROR_ENDPOINT_COUNT_METADATA_FIELDS,
        name="output_error_endpoint_count_metadata",
    )
    for field in _OUTPUT_ERROR_ENDPOINT_COUNT_METADATA_FIELDS:
        if not isinstance(metadata[field], str) or not str(metadata[field]).strip():
            raise ValueError(
                f"output_error_endpoint_count_metadata {field} must be a nonempty string"
            )
    if metadata["endpoint_count_provenance"] != OUTPUT_ERROR_ENDPOINT_COUNT_PROVENANCE:
        raise ValueError(
            "endpoint counts must come from G1-A2 loading endpoints before event detection"
        )
    if metadata["output_error_protocol"] != OUTPUT_ERROR_ENDPOINT_COUNT_PROTOCOL:
        raise ValueError("endpoint counts must use the G1-A2 output-error protocol")
    if metadata["dependence_assumption"] != OUTPUT_ERROR_DEPENDENCE:
        raise ValueError("endpoint counts must preserve arbitrary unknown dependence")
    if metadata["lower_composition_formula"] != OUTPUT_ERROR_LOWER_FORMULA:
        raise ValueError("lower endpoint formula must match G1-A2")
    if metadata["upper_composition_formula"] != OUTPUT_ERROR_UPPER_FORMULA:
        raise ValueError("upper endpoint formula must match G1-A2")
    for field in _OUTPUT_ERROR_ENDPOINT_COUNT_REFERENCE_FIELDS:
        lowered = str(metadata[field]).lower()
        stale = [
            token
            for token in _OUTPUT_ERROR_ENDPOINT_COUNT_STALE_REFERENCE_TOKENS
            if token in lowered
        ]
        if stale:
            raise ValueError(f"{field} contains stale or unsigned token(s): {stale}")
    for field in (
        "a013_grid_error_approval_status",
        "a016_scenario_consistency_status",
        "capacity_convention_status",
        "g2_tier1_envelope_approval_status",
    ):
        # This bridge is pre-real-use by design; signed real approval metadata
        # must enter through a later runner manifest, not a synthetic fixture.
        if metadata[field] != OUTPUT_ERROR_ENDPOINT_COUNT_BLOCKED_STATUS:
            raise ValueError(
                f"{field} must remain {OUTPUT_ERROR_ENDPOINT_COUNT_BLOCKED_STATUS!r}"
            )


def _reject_alpha_event_count_collapsed_fields(value: object) -> None:
    if isinstance(value, Mapping):
        collapsed = sorted(_ALPHA_EVENT_COUNT_FORBIDDEN_FIELDS.intersection(value))
        if collapsed:
            raise ValueError(
                "alpha probability estimator must not contain collapsed fields: "
                f"{collapsed}"
            )
        for nested in value.values():
            _reject_alpha_event_count_collapsed_fields(nested)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for nested in value:
            _reject_alpha_event_count_collapsed_fields(nested)


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
        "a016_scenario_consistency_manifested",
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
    _validate_output_error_config_record(
        _expect_mapping(record["config"], name="output_error_record.config")
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


def _validate_output_error_config_record(config: Mapping[str, object]) -> None:
    required = {
        "a013_grid_error_approval_id",
        "capacity_convention_linkage",
        "capacity_denominator_provenance",
        "composition_formula",
        "dependence_assumption",
        "envelope",
        "envelope_source",
        "error_application",
        "error_sampling",
        "event_semantics",
        "g2_tier1_envelope_approval_id",
        "grid_error_source",
        "probability_widening",
        "tier1_error_source",
        "use_status",
    }
    _require_mapping_fields(config, required, name="output_error_record.config")
    for field in (
        "a013_grid_error_approval_id",
        "capacity_convention_linkage",
        "capacity_denominator_provenance",
        "envelope_source",
        "g2_tier1_envelope_approval_id",
        "grid_error_source",
        "tier1_error_source",
        "use_status",
    ):
        if not isinstance(config[field], str) or not str(config[field]).strip():
            raise ValueError(
                f"output_error_record.config {field} must be a nonempty string"
            )

    envelope = _expect_mapping(
        config["envelope"], name="output_error_record.config.envelope"
    )
    _require_mapping_fields(
        envelope,
        {"epsilon_grid", "epsilon_tier1_minus", "epsilon_tier1_plus"},
        name="output_error_record.config.envelope",
    )
    formula = _expect_mapping(
        config["composition_formula"],
        name="output_error_record.config.composition_formula",
    )
    if formula.get("lower") != OUTPUT_ERROR_LOWER_FORMULA:
        raise ValueError(
            "output_error_record.config lower composition_formula must match G1-A2"
        )
    if formula.get("upper") != OUTPUT_ERROR_UPPER_FORMULA:
        raise ValueError(
            "output_error_record.config upper composition_formula must match G1-A2"
        )
    if config["error_application"] != OUTPUT_ERROR_APPLICATION:
        raise ValueError(
            "output_error_record.config must apply loading endpoints before event detection"
        )
    if config["dependence_assumption"] != OUTPUT_ERROR_DEPENDENCE:
        raise ValueError(
            "output_error_record.config must preserve arbitrary unknown dependence"
        )
    if config["error_sampling"] != OUTPUT_ERROR_SAMPLING:
        raise ValueError(
            "output_error_record.config must forbid independent error sampling"
        )
    if config["probability_widening"] != "forbidden":
        raise ValueError("output_error_record.config must forbid probability widening")

    event_semantics = _expect_mapping(
        config["event_semantics"], name="output_error_record.config.event_semantics"
    )
    _require_mapping_fields(
        event_semantics,
        {
            "comparator",
            "direction_gate",
            "min_consecutive_steps",
            "threshold_pu",
            "timestep_seconds",
        },
        name="output_error_record.config.event_semantics",
    )
    if event_semantics["comparator"] != "strict_greater_than":
        raise ValueError(
            "output_error_record.config event comparator must be strict_greater_than"
        )
    if event_semantics["direction_gate"] != "unwidened_p_net_import_mask":
        raise ValueError(
            "output_error_record.config direction gate must use unwidened P_net"
        )


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
