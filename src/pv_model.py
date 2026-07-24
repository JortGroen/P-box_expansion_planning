from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np

from src.contracts.net_load import ExecutableInputArtifact
from src.weather_model import (
    LOCAL_TIMEZONE,
    STEP_SECONDS_15MIN,
    WeatherMember,
    assert_same_weather_realization,
    canonical_15min_local_axis_for_year,
    canonical_15min_utc_axis_for_local_year,
    validate_canonical_15min_calendar,
)

SEASON_BY_MONTH = {
    12: "DJF",
    1: "DJF",
    2: "DJF",
    3: "MAM",
    4: "MAM",
    5: "MAM",
    6: "JJA",
    7: "JJA",
    8: "JJA",
    9: "SON",
    10: "SON",
    11: "SON",
}
SEASONS = ("DJF", "MAM", "JJA", "SON")
REQUIRED_COLD_SPELL_TOLERANCE_FIELDS = (
    "signed_decision_id",
    "near_freezing_band_c_min",
    "near_freezing_band_c_max",
    "coldest_7_day_mean_temperature_tolerance_c",
    "coldest_3_day_mean_temperature_tolerance_c",
    "temperature_load_response_metric",
    "cop_response_metric",
    "first_real_acceptance_run_preinspection_signed",
)


@dataclass(frozen=True)
class PVSystemConfig:
    """Explicit deterministic PV conversion parameters for one PV fleet."""

    installed_capacity_kw: float
    performance_ratio: float
    reference_irradiance_w_per_m2: float
    temperature_coefficient_per_c: float
    reference_temperature_c: float
    clip_to_capacity: bool
    config_id: str = "explicit"
    parameter_status: str = "unsigned_scaffold"
    signed_parameter_decision_id: str | None = None
    irradiance_input_basis: str = "weather_member_ghi_w_per_m2"
    plane_of_array_treatment: str = "ghi_used_directly_no_transposition_unsigned_scaffold"

    def __post_init__(self) -> None:
        if not self.config_id:
            raise ValueError("config_id must be non-empty")
        _require_positive_finite(self.installed_capacity_kw, "installed_capacity_kw")
        if not _is_finite(self.performance_ratio) or not 0 < self.performance_ratio <= 1.0:
            raise ValueError("performance_ratio must be finite and in (0, 1]")
        _require_positive_finite(self.reference_irradiance_w_per_m2, "reference_irradiance_w_per_m2")
        _require_finite(self.temperature_coefficient_per_c, "temperature_coefficient_per_c")
        _require_finite(self.reference_temperature_c, "reference_temperature_c")
        if not isinstance(self.clip_to_capacity, bool):
            raise ValueError("clip_to_capacity must be a bool")
        if self.parameter_status not in {
            "unsigned_scaffold",
            "proposed_pending_pi_signoff",
            "approved_for_executable_component_use",
        }:
            raise ValueError("parameter_status must be unsigned, proposed, or approved")
        if self.parameter_status == "approved_for_executable_component_use" and not self.signed_parameter_decision_id:
            raise ValueError("approved PV parameter configs require signed_parameter_decision_id")
        if not self.irradiance_input_basis:
            raise ValueError("irradiance_input_basis must be non-empty")
        if not self.plane_of_array_treatment:
            raise ValueError("plane_of_array_treatment must be non-empty")

    def require_signed_parameters(self) -> None:
        """Raise unless the PV parameter set has PI-signed executable approval."""
        if self.parameter_status != "approved_for_executable_component_use" or not self.signed_parameter_decision_id:
            raise ValueError("PV parameters are unsigned and cannot be used for signed executable PV input")


@dataclass(frozen=True)
class PVCapacitySourcePacket:
    """D-014 installed-capacity source/value packet that remains fail-closed."""

    packet_id: str
    data_id: str
    status: str
    download_performed: bool
    raw_data_committed: bool
    governing_decisions: Mapping[str, object]
    primary_cbs_anchor_source: Mapping[str, object]
    ii3050_growth_factor_source: Mapping[str, object]
    capacity_value_binding_under_review: Mapping[str, object]
    fail_closed_non_claims: Sequence[str]

    def __post_init__(self) -> None:
        if self.packet_id != "D014-PV-CAPACITY-SOURCE-VALUE-PACKET":
            raise ValueError("PV capacity source packet must identify D014-PV-CAPACITY-SOURCE-VALUE-PACKET")
        if self.data_id != "D-014":
            raise ValueError("PV capacity source packet must identify D-014")
        if not str(self.status).startswith("proposed_"):
            raise ValueError("PV capacity source packet must remain proposed until PI approval")
        if self.download_performed is not False:
            raise ValueError("PV capacity source packet must not claim raw retrieval")
        if self.raw_data_committed is not False:
            raise ValueError("PV capacity source packet must not commit raw data")
        governing = _audit_json_mapping(self.governing_decisions, "governing_decisions")
        cbs = _audit_json_mapping(self.primary_cbs_anchor_source, "primary_cbs_anchor_source")
        ii3050 = _audit_json_mapping(self.ii3050_growth_factor_source, "ii3050_growth_factor_source")
        binding = _audit_json_mapping(self.capacity_value_binding_under_review, "capacity_value_binding_under_review")
        non_claims = tuple(str(item) for item in self.fail_closed_non_claims)
        if governing.get("approved_route") != "PV-CAP-001":
            raise ValueError("D-014 capacity packet must be governed by PV-CAP-001")
        if "PV-PARAM-001 remains proposed" not in str(governing.get("conversion_parameters", "")):
            raise ValueError("D-014 capacity packet must keep PV-PARAM-001 proposed")
        if cbs.get("table_id") != "85005NED":
            raise ValueError("D-014 primary CBS anchor must use table 85005NED")
        if cbs.get("planned_raw_path") and not str(cbs["planned_raw_path"]).startswith("data/raw/pv_capacity/"):
            raise ValueError("D-014 raw PV capacity files must stay under ignored data/raw/pv_capacity")
        if ii3050.get("numeric_growth_factor_approved") is not False:
            raise ValueError("D-014 must not approve a numeric II3050 growth factor")
        required = tuple(str(item) for item in binding.get("approval_keys_required_before_executable_use", ()))
        missing = {
            "cbs_source_file_checksum",
            "cbs_capacity_field_key",
            "capacity_unit_and_dc_ac_convention",
            "ii3050_growth_factor_value",
            "node_allocation_rule",
            "PV-PARAM-001_or_amended_conversion_decision",
        }.difference(required)
        if missing:
            raise ValueError(f"D-014 capacity packet missing approval keys: {sorted(missing)}")
        if not any("No numeric PV installed capacity" in item for item in non_claims):
            raise ValueError("D-014 capacity packet must state that no numeric PV capacity is approved")

        object.__setattr__(self, "governing_decisions", governing)
        object.__setattr__(self, "primary_cbs_anchor_source", cbs)
        object.__setattr__(self, "ii3050_growth_factor_source", ii3050)
        object.__setattr__(self, "capacity_value_binding_under_review", binding)
        object.__setattr__(self, "fail_closed_non_claims", non_claims)

    @property
    def missing_approval_keys(self) -> tuple[str, ...]:
        return tuple(
            str(item)
            for item in self.capacity_value_binding_under_review["approval_keys_required_before_executable_use"]
        )

    def require_executable_capacity_approval(self) -> None:
        """Always fail for the proposed packet until a later signed value record replaces it."""
        raise ValueError(
            "D-014 PV capacity values are unsigned; executable PV requires signed CBS source, "
            "II3050 growth factor, capacity convention, node allocation, and PV-PARAM approval"
        )

    def identity_record(self) -> dict[str, object]:
        """Return audit fields for downstream readiness manifests."""
        return {
            "packet_id": self.packet_id,
            "data_id": self.data_id,
            "status": self.status,
            "approved_route": self.governing_decisions["approved_route"],
            "cbs_table_id": self.primary_cbs_anchor_source["table_id"],
            "ii3050_source_id": self.ii3050_growth_factor_source["source_id"],
            "download_performed": self.download_performed,
            "raw_data_committed": self.raw_data_committed,
            "missing_approval_keys": self.missing_approval_keys,
        }


def load_pv_capacity_source_packet(path: str | Path) -> PVCapacitySourcePacket:
    """Load the proposed D-014 PV capacity source/value packet."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return PVCapacitySourcePacket(
        packet_id=str(payload.get("packet_id", "")),
        data_id=str(payload.get("data_id", "")),
        status=str(payload.get("status", "")),
        download_performed=bool(payload.get("download_performed")),
        raw_data_committed=bool(payload.get("raw_data_committed")),
        governing_decisions=payload.get("governing_decisions", {}),
        primary_cbs_anchor_source=payload.get("primary_cbs_anchor_source", {}),
        ii3050_growth_factor_source=payload.get("ii3050_growth_factor_source", {}),
        capacity_value_binding_under_review=payload.get("capacity_value_binding_under_review", {}),
        fail_closed_non_claims=payload.get("fail_closed_non_claims", ()),
    )

@dataclass(frozen=True)
class PVStatisticalOrientationTiltPacket:
    """Proposed D-014 statistical orientation/tilt packet that stays fail-closed."""

    packet_id: str
    data_id: str
    status: str
    download_performed: bool
    raw_data_committed: bool
    first_experiment_scope: Mapping[str, object]
    governing_boundaries: Mapping[str, object]
    source_route_comparison: Sequence[Mapping[str, object]]
    proposed_artifact_interface: Mapping[str, object]
    pi_questions: Sequence[str]
    non_claims: Sequence[str]

    def __post_init__(self) -> None:
        if self.packet_id != "D014-PV-STATISTICAL-ORIENTATION-TILT-PACKET":
            raise ValueError("statistical orientation/tilt packet must identify D014-PV-STATISTICAL-ORIENTATION-TILT-PACKET")
        if self.data_id != "D-014":
            raise ValueError("statistical orientation/tilt packet must identify D-014")
        if not str(self.status).startswith("proposed_"):
            raise ValueError("statistical orientation/tilt packet must remain proposed until PI approval")
        if self.download_performed is not False or self.raw_data_committed is not False:
            raise ValueError("statistical orientation/tilt packet must not claim raw retrieval or committed raw data")
        scope = _audit_json_mapping(self.first_experiment_scope, "first_experiment_scope")
        boundaries = _audit_json_mapping(self.governing_boundaries, "governing_boundaries")
        interface = _audit_json_mapping(self.proposed_artifact_interface, "proposed_artifact_interface")
        routes = tuple(_audit_json_mapping(item, "source_route_comparison item") for item in self.source_route_comparison)
        questions = tuple(str(item) for item in self.pi_questions)
        non_claims = tuple(str(item) for item in self.non_claims)
        if scope.get("statistical_orientation_tilt_classes_only") is not True:
            raise ValueError("first experiment must use statistical orientation/tilt classes only")
        if scope.get("building_or_roof_level_extraction_in_scope") is not False:
            raise ValueError("building or roof-level extraction must stay out of first-experiment scope")
        if scope.get("specific_3dbag_per_roof_workflow_in_first_experiment") is not False:
            raise ValueError("3DBAG per-roof workflow must be deferred from the first experiment")
        if "PV-CAP-001 remains separate" not in str(boundaries.get("capacity_route", "")):
            raise ValueError("packet must keep the D-014 capacity route separate")
        if "PR=0.86/direct-GHI is not approved" not in str(boundaries.get("conversion_parameters", "")):
            raise ValueError("packet must not approve the disputed PV-PARAM route")
        if interface.get("executable_allowed_now") is not False:
            raise ValueError("statistical orientation/tilt artifact must be fail-closed")
        required_keys = tuple(str(item) for item in interface.get("approval_keys_required_before_executable_use", ()))
        missing = {
            "statistical_orientation_tilt_source",
            "class_weight_values",
            "pv_conversion_formula_or_pvlib_route",
            "d014_capacity_value_artifact",
            "node_allocation_rule",
        }.difference(required_keys)
        if missing:
            raise ValueError(f"statistical orientation/tilt packet missing approval keys: {sorted(missing)}")
        route_ids = {str(item.get("source_id")) for item in routes}
        if "3dbag_deferred_roof_geometry" not in route_ids:
            raise ValueError("packet must explicitly defer 3DBAG roof geometry")
        if not any("No statistical class bins or weights are approved" in item for item in non_claims):
            raise ValueError("packet must state that class bins/weights are not approved")

        object.__setattr__(self, "first_experiment_scope", scope)
        object.__setattr__(self, "governing_boundaries", boundaries)
        object.__setattr__(self, "source_route_comparison", routes)
        object.__setattr__(self, "proposed_artifact_interface", interface)
        object.__setattr__(self, "pi_questions", questions)
        object.__setattr__(self, "non_claims", non_claims)

    @property
    def missing_approval_keys(self) -> tuple[str, ...]:
        return tuple(
            str(item)
            for item in self.proposed_artifact_interface["approval_keys_required_before_executable_use"]
        )

    def require_executable_orientation_tilt_approval(self) -> None:
        """Always fail until a signed class table/config replaces this proposal."""
        raise ValueError(
            "D-014 statistical PV orientation/tilt classes are unsigned; executable PV requires signed "
            "class source, bins, weights, capacity convention, allocation, and PV conversion parameters"
        )

    def identity_record(self) -> dict[str, object]:
        """Return audit fields for downstream readiness manifests."""
        return {
            "packet_id": self.packet_id,
            "data_id": self.data_id,
            "status": self.status,
            "statistical_orientation_tilt_classes_only": self.first_experiment_scope[
                "statistical_orientation_tilt_classes_only"
            ],
            "building_or_roof_level_extraction_in_scope": self.first_experiment_scope[
                "building_or_roof_level_extraction_in_scope"
            ],
            "executable_allowed_now": self.proposed_artifact_interface["executable_allowed_now"],
            "missing_approval_keys": self.missing_approval_keys,
        }


def load_pv_statistical_orientation_tilt_packet(path: str | Path) -> PVStatisticalOrientationTiltPacket:
    """Load the proposed D-014 statistical orientation/tilt packet."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return PVStatisticalOrientationTiltPacket(
        packet_id=str(payload.get("packet_id", "")),
        data_id=str(payload.get("data_id", "")),
        status=str(payload.get("status", "")),
        download_performed=bool(payload.get("download_performed")),
        raw_data_committed=bool(payload.get("raw_data_committed")),
        first_experiment_scope=payload.get("first_experiment_scope", {}),
        governing_boundaries=payload.get("governing_boundaries", {}),
        source_route_comparison=payload.get("source_route_comparison", ()),
        proposed_artifact_interface=payload.get("proposed_artifact_interface", {}),
        pi_questions=payload.get("pi_questions", ()),
        non_claims=payload.get("non_claims", ()),
    )


@dataclass(frozen=True)
class PVOrientationTiltSourceChoicePacket:
    """Proposed source-choice packet for statistical PV orientation/tilt classes."""

    packet_id: str
    data_id: str
    status: str
    download_performed: bool
    raw_data_committed: bool
    approved_scope_decision: str
    first_experiment_scope: Mapping[str, object]
    recommended_source_order_for_pi_review: Sequence[Mapping[str, object]]
    source_candidates: Sequence[Mapping[str, object]]
    proposed_class_artifact_requirements: Mapping[str, object]
    source_backing_summary: Mapping[str, object]
    pi_approval_keys_before_executable_use: Sequence[str]
    non_claims: Sequence[str]

    def __post_init__(self) -> None:
        if self.packet_id != "D014-PV-ORIENTATION-TILT-SOURCE-CHOICE-PACKET":
            raise ValueError("orientation/tilt source-choice packet must identify D014-PV-ORIENTATION-TILT-SOURCE-CHOICE-PACKET")
        if self.data_id != "D-014":
            raise ValueError("orientation/tilt source-choice packet must identify D-014")
        if not str(self.status).startswith("proposed_"):
            raise ValueError("orientation/tilt source-choice packet must remain proposed until PI approval")
        if self.download_performed is not False or self.raw_data_committed is not False:
            raise ValueError("orientation/tilt source-choice packet must not claim raw retrieval or committed raw data")
        if self.approved_scope_decision != "PV-ORIENT-001":
            raise ValueError("orientation/tilt source-choice packet must be governed by PV-ORIENT-001")
        scope = _audit_json_mapping(self.first_experiment_scope, "first_experiment_scope")
        class_requirements = _audit_json_mapping(
            self.proposed_class_artifact_requirements,
            "proposed_class_artifact_requirements",
        )
        backing = _audit_json_mapping(self.source_backing_summary, "source_backing_summary")
        source_order = tuple(
            _audit_json_mapping(item, "recommended_source_order_for_pi_review item")
            for item in self.recommended_source_order_for_pi_review
        )
        candidates = tuple(_audit_json_mapping(item, "source_candidate item") for item in self.source_candidates)
        approval_keys = tuple(str(item) for item in self.pi_approval_keys_before_executable_use)
        non_claims = tuple(str(item) for item in self.non_claims)
        if scope.get("statistical_orientation_tilt_classes_only") is not True:
            raise ValueError("first experiment must remain statistical orientation/tilt classes only")
        if scope.get("roof_or_location_level_extraction_allowed_now") is not False:
            raise ValueError("roof/location-level extraction must remain blocked")
        if scope.get("specific_3dbag_per_roof_workflow_allowed_now") is not False:
            raise ValueError("3DBAG per-roof workflow must remain blocked")
        if class_requirements.get("executable_allowed_now") is not False:
            raise ValueError("orientation/tilt source-choice artifact must be fail-closed")
        required = {
            "orientation_tilt_distribution_source_id",
            "orientation_class_bin_definitions",
            "tilt_class_bin_definitions",
            "class_weight_values",
            "pv_conversion_treatment_for_classes",
            "pv_param_001_or_amended_conversion_decision",
            "d014_capacity_value_artifact",
            "node_allocation_rule",
        }
        missing = required.difference(approval_keys)
        if missing:
            raise ValueError(f"orientation/tilt source-choice packet missing approval keys: {sorted(missing)}")
        candidate_ids = {str(item.get("source_id")) for item in candidates}
        for source_id in (
            "killinger_2018_pv_system_characteristics",
            "utrecht_rooftop_pv_observed_systems",
            "ramadhani_2023_rooftop_uncertainty_method",
            "pvgis_reference",
            "pvlib_conversion_candidate",
            "jrc_dbsm_or_3dbag_deferred_building_level_work",
        ):
            if source_id not in candidate_ids:
                raise ValueError(f"orientation/tilt source-choice packet missing source candidate {source_id}")
        if not any("No source candidate is selected as final" in item for item in non_claims):
            raise ValueError("packet must state that no source candidate is final")
        if not any("No orientation or tilt class bins" in item for item in non_claims):
            raise ValueError("packet must state that no bins or weights are approved")
        if not any("No 3DBAG per-roof" in item for item in non_claims):
            raise ValueError("packet must state that heavy 3DBAG/per-roof work is not implemented")

        object.__setattr__(self, "first_experiment_scope", scope)
        object.__setattr__(self, "recommended_source_order_for_pi_review", source_order)
        object.__setattr__(self, "source_candidates", candidates)
        object.__setattr__(self, "proposed_class_artifact_requirements", class_requirements)
        object.__setattr__(self, "source_backing_summary", backing)
        object.__setattr__(self, "pi_approval_keys_before_executable_use", approval_keys)
        object.__setattr__(self, "non_claims", non_claims)

    @property
    def missing_approval_keys(self) -> tuple[str, ...]:
        return self.pi_approval_keys_before_executable_use

    def require_executable_source_choice_approval(self) -> None:
        """Always fail until a signed statistical orientation/tilt source choice replaces this packet."""
        raise ValueError(
            "D-014 PV orientation/tilt source, class bins, weights, capacity artifact, allocation, "
            "and PV conversion treatment are unsigned"
        )

    def identity_record(self) -> dict[str, object]:
        return {
            "packet_id": self.packet_id,
            "data_id": self.data_id,
            "status": self.status,
            "approved_scope_decision": self.approved_scope_decision,
            "statistical_orientation_tilt_classes_only": self.first_experiment_scope[
                "statistical_orientation_tilt_classes_only"
            ],
            "roof_or_location_level_extraction_allowed_now": self.first_experiment_scope[
                "roof_or_location_level_extraction_allowed_now"
            ],
            "executable_allowed_now": self.proposed_class_artifact_requirements["executable_allowed_now"],
            "source_candidate_ids": tuple(str(item["source_id"]) for item in self.source_candidates),
            "missing_approval_keys": self.missing_approval_keys,
        }


def load_pv_orientation_tilt_source_choice_packet(path: str | Path) -> PVOrientationTiltSourceChoicePacket:
    """Load the proposed D-014 orientation/tilt source-choice packet."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return PVOrientationTiltSourceChoicePacket(
        packet_id=str(payload.get("packet_id", "")),
        data_id=str(payload.get("data_id", "")),
        status=str(payload.get("status", "")),
        download_performed=bool(payload.get("download_performed")),
        raw_data_committed=bool(payload.get("raw_data_committed")),
        approved_scope_decision=str(payload.get("approved_scope_decision", "")),
        first_experiment_scope=payload.get("first_experiment_scope", {}),
        recommended_source_order_for_pi_review=payload.get("recommended_source_order_for_pi_review", ()),
        source_candidates=payload.get("source_candidates", ()),
        proposed_class_artifact_requirements=payload.get("proposed_class_artifact_requirements", {}),
        source_backing_summary=payload.get("source_backing_summary", {}),
        pi_approval_keys_before_executable_use=payload.get("pi_approval_keys_before_executable_use", ()),
        non_claims=payload.get("non_claims", ()),
    )



@dataclass(frozen=True)
class PVOrientationTiltValueChoicePacket:
    """Proposed statistical PV orientation/tilt class values that remain fail-closed."""

    packet_id: str
    data_id: str
    status: str
    download_performed: bool
    raw_data_committed: bool
    approved_scope_decision: str
    source_choice_packet_id: str
    capacity_route_boundary: str
    pv_param_boundary: str
    first_experiment_scope: Mapping[str, object]
    angle_conventions_for_review: Mapping[str, object]
    source_backing_summary: Mapping[str, object]
    candidate_class_sets: Sequence[Mapping[str, object]]
    pi_recommendation_for_review: Mapping[str, object]
    pi_approval_keys_before_executable_use: Sequence[str]
    non_claims: Sequence[str]

    def __post_init__(self) -> None:
        if self.packet_id != "D014-PV-ORIENTATION-TILT-VALUE-CHOICE-PACKET":
            raise ValueError("orientation/tilt value-choice packet must identify D014-PV-ORIENTATION-TILT-VALUE-CHOICE-PACKET")
        if self.data_id != "D-014":
            raise ValueError("orientation/tilt value-choice packet must identify D-014")
        if not str(self.status).startswith("proposed_"):
            raise ValueError("orientation/tilt value-choice packet must remain proposed until PI approval")
        if self.download_performed is not False or self.raw_data_committed is not False:
            raise ValueError("orientation/tilt value-choice packet must not claim raw retrieval or committed raw data")
        if self.approved_scope_decision != "PV-ORIENT-001":
            raise ValueError("orientation/tilt value-choice packet must be governed by PV-ORIENT-001")
        if self.source_choice_packet_id != "D014-PV-ORIENTATION-TILT-SOURCE-CHOICE-PACKET":
            raise ValueError("orientation/tilt value-choice packet must link to the source-choice packet")
        if "PV-CAP-001/D-014 capacity remains separate" not in self.capacity_route_boundary:
            raise ValueError("orientation/tilt values must keep D-014 capacity separate")
        if "PV-PARAM-001 remains proposed" not in self.pv_param_boundary:
            raise ValueError("orientation/tilt values must keep PV-PARAM-001 fail-closed")
        scope = _audit_json_mapping(self.first_experiment_scope, "first_experiment_scope")
        conventions = _audit_json_mapping(self.angle_conventions_for_review, "angle_conventions_for_review")
        backing = _audit_json_mapping(self.source_backing_summary, "source_backing_summary")
        recommendation = _audit_json_mapping(self.pi_recommendation_for_review, "pi_recommendation_for_review")
        class_sets = tuple(_audit_json_mapping(item, "candidate_class_set item") for item in self.candidate_class_sets)
        approval_keys = tuple(str(item) for item in self.pi_approval_keys_before_executable_use)
        non_claims = tuple(str(item) for item in self.non_claims)
        if scope.get("statistical_orientation_tilt_classes_only") is not True:
            raise ValueError("first experiment must remain statistical orientation/tilt classes only")
        if scope.get("roof_or_location_level_extraction_allowed_now") is not False:
            raise ValueError("roof/location-level extraction must remain blocked")
        if scope.get("specific_3dbag_per_roof_workflow_allowed_now") is not False:
            raise ValueError("3DBAG per-roof workflow must remain blocked")
        if conventions.get("executable_status") != "unsigned_pi_choice_required":
            raise ValueError("orientation/tilt conventions must remain unsigned")
        required = {
            "orientation_tilt_distribution_source_id",
            "source_value_trace_or_approved_assumption_id",
            "azimuth_angle_convention",
            "tilt_angle_convention",
            "representative_angle_values",
            "class_weight_values",
            "class_weight_sum_tolerance",
            "pv_conversion_treatment_for_classes",
            "pv_param_001_or_amended_conversion_decision",
            "d014_capacity_value_artifact",
            "capacity_unit_and_dc_ac_convention",
            "node_allocation_rule",
        }
        missing = required.difference(approval_keys)
        if missing:
            raise ValueError(f"orientation/tilt value-choice packet missing approval keys: {sorted(missing)}")
        class_set_ids = {str(item.get("class_set_id")) for item in class_sets}
        if "killinger_empirical_extraction_pending_v1" not in class_set_ids:
            raise ValueError("value-choice packet must keep the Killinger extraction route explicit")
        if "pi_prior_5_class_symmetric_rooftop_candidate_v1" not in class_set_ids:
            raise ValueError("value-choice packet must include the unsigned PI-prior fallback candidate")
        if recommendation.get("do_not_use_as_final_without_signature") is not True:
            raise ValueError("value-choice packet must not allow final use without signature")
        if not any("No statistical orientation/tilt class set is approved" in item for item in non_claims):
            raise ValueError("packet must state that no class set is final")
        if not any("Numeric class weights" in item and "unsigned" in item for item in non_claims):
            raise ValueError("packet must state that numeric values are unsigned")
        if not any("No 3DBAG per-roof" in item for item in non_claims):
            raise ValueError("packet must state that heavy 3DBAG/per-roof work is not implemented")

        for class_set in class_sets:
            status = str(class_set.get("value_status", ""))
            if "approved" in status or "executable" in status.replace("not_executable", ""):
                raise ValueError("candidate class values must not claim approval or executable status")
            rows = tuple(_audit_json_mapping(row, "candidate class row") for row in class_set.get("class_table", ()))
            if rows:
                weight_sum = 0.0
                for row in rows:
                    weight = float(row.get("capacity_weight_fraction", "nan"))
                    if not np.isfinite(weight) or weight < 0:
                        raise ValueError("candidate class weights must be finite and nonnegative")
                    weight_sum += weight
                    tilt = float(row.get("representative_tilt_degrees", "nan"))
                    if not np.isfinite(tilt) or not 0 <= tilt <= 90:
                        raise ValueError("candidate representative tilt must be between 0 and 90 degrees")
                    if "assumption-only" not in str(row.get("source_value_trace", "")) and "extracted" not in str(row.get("source_value_trace", "")):
                        raise ValueError("candidate class rows must trace to a source or explicit assumption")
                if abs(weight_sum - 1.0) > 1e-9:
                    raise ValueError("candidate class weights must sum to one")
                declared = class_set.get("class_weight_sum")
                if declared is not None and abs(float(declared) - weight_sum) > 1e-9:
                    raise ValueError("declared class_weight_sum must match candidate rows")

        object.__setattr__(self, "first_experiment_scope", scope)
        object.__setattr__(self, "angle_conventions_for_review", conventions)
        object.__setattr__(self, "source_backing_summary", backing)
        object.__setattr__(self, "candidate_class_sets", class_sets)
        object.__setattr__(self, "pi_recommendation_for_review", recommendation)
        object.__setattr__(self, "pi_approval_keys_before_executable_use", approval_keys)
        object.__setattr__(self, "non_claims", non_claims)

    @property
    def missing_approval_keys(self) -> tuple[str, ...]:
        return self.pi_approval_keys_before_executable_use

    def require_executable_orientation_tilt_values_approval(self) -> None:
        """Always fail until signed orientation/tilt values replace this packet."""
        raise ValueError(
            "D-014 PV orientation/tilt values are unsigned; executable PV requires signed source, "
            "bins, representative angles, weights, capacity artifact, allocation, and conversion treatment"
        )

    def identity_record(self) -> dict[str, object]:
        return {
            "packet_id": self.packet_id,
            "data_id": self.data_id,
            "status": self.status,
            "approved_scope_decision": self.approved_scope_decision,
            "source_choice_packet_id": self.source_choice_packet_id,
            "statistical_orientation_tilt_classes_only": self.first_experiment_scope[
                "statistical_orientation_tilt_classes_only"
            ],
            "roof_or_location_level_extraction_allowed_now": self.first_experiment_scope[
                "roof_or_location_level_extraction_allowed_now"
            ],
            "candidate_class_set_ids": tuple(str(item["class_set_id"]) for item in self.candidate_class_sets),
            "missing_approval_keys": self.missing_approval_keys,
            "executable_allowed_now": False,
        }


def load_pv_orientation_tilt_value_choice_packet(path: str | Path) -> PVOrientationTiltValueChoicePacket:
    """Load the proposed D-014 orientation/tilt value-choice packet."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return PVOrientationTiltValueChoicePacket(
        packet_id=str(payload.get("packet_id", "")),
        data_id=str(payload.get("data_id", "")),
        status=str(payload.get("status", "")),
        download_performed=bool(payload.get("download_performed")),
        raw_data_committed=bool(payload.get("raw_data_committed")),
        approved_scope_decision=str(payload.get("approved_scope_decision", "")),
        source_choice_packet_id=str(payload.get("source_choice_packet_id", "")),
        capacity_route_boundary=str(payload.get("capacity_route_boundary", "")),
        pv_param_boundary=str(payload.get("pv_param_boundary", "")),
        first_experiment_scope=payload.get("first_experiment_scope", {}),
        angle_conventions_for_review=payload.get("angle_conventions_for_review", {}),
        source_backing_summary=payload.get("source_backing_summary", {}),
        candidate_class_sets=payload.get("candidate_class_sets", ()),
        pi_recommendation_for_review=payload.get("pi_recommendation_for_review", {}),
        pi_approval_keys_before_executable_use=payload.get("pi_approval_keys_before_executable_use", ()),
        non_claims=payload.get("non_claims", ()),
    )


@dataclass(frozen=True)
class PVGenerationProfile:
    """PV generation produced from one validated paired weather member."""

    weather_member_id: str
    weather_source: str
    shared_weather_driver_id: str
    timestamps_utc: Sequence[datetime]
    timestamps_local: Sequence[datetime]
    generation_kw: Sequence[float]
    config: PVSystemConfig
    weather_identity: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        timestamps_utc = tuple(_coerce_aware_datetime(item, "timestamps_utc").astimezone(UTC) for item in self.timestamps_utc)
        timestamps_local = tuple(_coerce_aware_datetime(item, "timestamps_local") for item in self.timestamps_local)
        if len(timestamps_utc) < 2:
            raise ValueError("PV profile must contain at least two timestamps")
        if len(timestamps_utc) != len(timestamps_local):
            raise ValueError("UTC and local timestamp counts must match")
        _validate_strictly_chronological(timestamps_utc, "PV profile")
        for utc_timestamp, local_timestamp in zip(timestamps_utc, timestamps_local, strict=True):
            if local_timestamp.astimezone(UTC) != utc_timestamp:
                raise ValueError("UTC and local timestamps must represent the same instants")
        generation = _as_float_vector(self.generation_kw, "generation_kw")
        if len(generation) != len(timestamps_utc):
            raise ValueError("generation_kw must match the timestamp count")
        if (generation < 0).any():
            raise ValueError("generation_kw must be non-negative")
        weather_identity = _audit_json_mapping(self.weather_identity, "weather_identity")
        if weather_identity:
            if weather_identity.get("member_id") != self.weather_member_id:
                raise ValueError("weather_identity member_id must match weather_member_id")
            if weather_identity.get("shared_weather_driver_id") != self.shared_weather_driver_id:
                raise ValueError("weather_identity shared_weather_driver_id must match shared_weather_driver_id")

        object.__setattr__(self, "timestamps_utc", timestamps_utc)
        object.__setattr__(self, "timestamps_local", timestamps_local)
        object.__setattr__(self, "generation_kw", generation)
        object.__setattr__(self, "weather_identity", weather_identity)

    @property
    def n_timesteps(self) -> int:
        return len(self.timestamps_utc)

    @property
    def cadence_seconds(self) -> int:
        return _constant_cadence_seconds(self.timestamps_utc)

    @property
    def cadence_hours(self) -> float:
        return self.cadence_seconds / 3600.0

    def annual_energy_kwh(self) -> float:
        return float(np.sum(self.generation_kw) * self.cadence_hours)

    def peak_kw(self) -> float:
        return float(np.max(self.generation_kw))

    def peak_timestamp_local(self) -> datetime:
        return self.timestamps_local[int(np.argmax(self.generation_kw))]

    @property
    def weather_content_sha256(self) -> str | None:
        value = self.weather_identity.get("content_sha256")
        return None if value is None else str(value)

    def identity_record(self) -> dict[str, object]:
        """Return PV output identity fields for later HP/PV pairing checks."""
        record = {
            "member_id": self.weather_member_id,
            "weather_member_id": self.weather_member_id,
            "source": self.weather_source,
            "weather_source": self.weather_source,
            "shared_weather_driver_id": self.shared_weather_driver_id,
            "content_sha256": self.weather_content_sha256,
            "weather_content_sha256": self.weather_content_sha256,
            "first_timestamp_utc": self.timestamps_utc[0].isoformat(),
            "last_timestamp_utc": self.timestamps_utc[-1].isoformat(),
            "n_timesteps": self.n_timesteps,
            "cadence_seconds": self.cadence_seconds,
            "config_id": self.config.config_id,
        }
        for key in (
            "source_member_acceptance_id",
            "weather_input_artifact_status",
            "calendar_id",
            "pvgis_realized_weather_path",
            "pvgis_role",
        ):
            if key in self.weather_identity:
                record[key] = self.weather_identity[key]
        return record


@dataclass(frozen=True)
class PVGISReference:
    """Seasonal PVGIS reference for calibration or validation, not sampling."""

    source_id: str
    seasonal_energy_kwh: Mapping[str, float]
    annual_energy_kwh: float | None = None
    peak_month: int | None = None
    typical_year_use: str = "calibration_or_validation_only"

    def __post_init__(self) -> None:
        if not self.source_id:
            raise ValueError("source_id must be non-empty")
        seasonal = {season: float(self.seasonal_energy_kwh[season]) for season in SEASONS}
        for season, value in seasonal.items():
            if not _is_finite(value) or value < 0:
                raise ValueError(f"{season} reference energy must be finite and non-negative")
        annual = sum(seasonal.values()) if self.annual_energy_kwh is None else float(self.annual_energy_kwh)
        if not _is_finite(annual) or annual < 0:
            raise ValueError("annual_energy_kwh must be finite and non-negative")
        if self.peak_month is not None and int(self.peak_month) not in range(1, 13):
            raise ValueError("peak_month must be in 1..12")
        if self.typical_year_use != "calibration_or_validation_only":
            raise ValueError("PVGIS typical-year references must not be sampled as realized weather paths")

        object.__setattr__(self, "seasonal_energy_kwh", seasonal)
        object.__setattr__(self, "annual_energy_kwh", annual)
        object.__setattr__(self, "peak_month", None if self.peak_month is None else int(self.peak_month))


@dataclass(frozen=True)
class PVGISSanityCheck:
    """Result of a PV profile check against PVGIS seasonal/peak expectations."""

    passed: bool
    seasonal_relative_error: Mapping[str, float]
    annual_relative_error: float
    profile_peak_month: int
    peak_timing_passed: bool
    failed_reasons: tuple[str, ...]

    def raise_for_failure(self) -> None:
        if not self.passed:
            raise ValueError("; ".join(self.failed_reasons))


@dataclass(frozen=True)
class PVWeatherInputArtifact:
    """Accepted WEATHER-001 source/member index for PV component-input gating."""

    data_id: str
    selection_id: str
    status: str
    source_member_acceptance_id: str
    weather_contract: str
    accepted_for_source_member_use: bool
    ready_for_executable_input_gate: bool
    realized_weather_path: str
    pvgis_role: str
    pvgis_realized_weather_path: bool
    required_identity_fields_for_hp_pv_pairing: Sequence[str]
    calendar_contract: Mapping[str, object]
    members: Sequence[Mapping[str, object]]
    blocked_acceptance_gates: Mapping[str, object]
    readiness_scope: str = "source_member_component_input_only_not_final_integrated"
    ready_for_source_member_component_input_gate: bool = True
    evidence_artifacts: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.data_id != "D-004":
            raise ValueError("PV weather input artifact must identify D-004")
        if not self.selection_id:
            raise ValueError("selection_id must be non-empty")
        if not self.source_member_acceptance_id:
            raise ValueError("source_member_acceptance_id must be non-empty")
        if self.weather_contract != "WEATHER-001":
            raise ValueError("PV weather input artifact must use WEATHER-001")
        if self.accepted_for_source_member_use is not True:
            raise ValueError("PV weather input artifact must be accepted for source/member use")
        if self.ready_for_executable_input_gate is not True:
            raise ValueError("PV weather input artifact must be ready for executable-input gating")
        if self.pvgis_realized_weather_path is not False:
            raise ValueError("PVGIS must remain outside the realized weather path")
        if self.readiness_scope != "source_member_component_input_only_not_final_integrated":
            raise ValueError("PV weather input artifact must be scoped to source/member component readiness")
        if self.ready_for_source_member_component_input_gate is not True:
            raise ValueError("PV weather input artifact must be ready for source/member component input only")
        required_fields = tuple(str(item) for item in self.required_identity_fields_for_hp_pv_pairing)
        required = {
            "member_id",
            "shared_weather_driver_id",
            "source",
            "first_timestamp_utc",
            "last_timestamp_utc",
            "n_timesteps",
            "cadence_seconds",
            "content_sha256",
        }
        if not required.issubset(required_fields):
            raise ValueError("PV weather input artifact lacks required HP/PV identity fields")
        members = tuple(_audit_json_mapping(item, "weather_input_artifact member") for item in self.members)
        if not members:
            raise ValueError("PV weather input artifact must include at least one member")
        calendar_contract = _audit_json_mapping(self.calendar_contract, "calendar_contract")
        blocked_gates = _audit_json_mapping(self.blocked_acceptance_gates, "blocked_acceptance_gates")
        evidence_artifacts = _audit_json_mapping(self.evidence_artifacts, "evidence_artifacts")
        for gate in ("final_paired_hp_pv_acceptance", "cold_spell_acceptance", "integrated_analysis"):
            gate_record = blocked_gates.get(gate)
            if not isinstance(gate_record, Mapping) or gate_record.get("blocked") is not True:
                raise ValueError(f"PV weather input artifact must keep {gate} blocked")
        for member in members:
            _validate_weather_input_member_record(member, acceptance_id=self.source_member_acceptance_id)
            if int(member["cadence_seconds"]) != int(calendar_contract.get("cadence_seconds", 0)):
                raise ValueError("member cadence_seconds must match the artifact calendar contract")

        object.__setattr__(self, "required_identity_fields_for_hp_pv_pairing", required_fields)
        object.__setattr__(self, "calendar_contract", calendar_contract)
        object.__setattr__(self, "members", members)
        object.__setattr__(self, "blocked_acceptance_gates", blocked_gates)
        object.__setattr__(self, "evidence_artifacts", evidence_artifacts)

    def member_for_year(self, year: int) -> Mapping[str, object]:
        """Return the accepted member record for a UTC calendar year."""
        for member in self.members:
            if int(member["year"]) == int(year):
                return member
        raise KeyError(f"no D-004 weather input member for year {year}")

    def member_for_id(self, member_id: str) -> Mapping[str, object]:
        """Return the accepted member record for a WEATHER-001 member ID."""
        for member in self.members:
            if member["member_id"] == member_id:
                return member
        raise KeyError(f"no D-004 weather input member for member_id {member_id!r}")


def load_pv_weather_input_artifact(path: str | Path) -> PVWeatherInputArtifact:
    """Load an accepted WEATHER-001 source/member index for PV input readiness."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return PVWeatherInputArtifact(
        data_id=str(payload.get("data_id", "")),
        selection_id=str(payload.get("selection_id", "")),
        status=str(payload.get("status", "")),
        source_member_acceptance_id=str(payload.get("source_member_acceptance_id", "")),
        weather_contract=str(payload.get("weather_contract", "")),
        accepted_for_source_member_use=payload.get("accepted_for_source_member_use"),
        ready_for_executable_input_gate=payload.get("ready_for_executable_input_gate"),
        realized_weather_path=str(payload.get("realized_weather_path", "")),
        pvgis_role=str(payload.get("pvgis_role", "")),
        pvgis_realized_weather_path=payload.get("pvgis_realized_weather_path"),
        required_identity_fields_for_hp_pv_pairing=payload.get("required_identity_fields_for_hp_pv_pairing", ()),
        calendar_contract=payload.get("calendar_contract", {}),
        members=payload.get("members", ()),
        blocked_acceptance_gates=payload.get("blocked_acceptance_gates", {}),
        readiness_scope=str(payload.get("readiness_scope", "")),
        ready_for_source_member_component_input_gate=payload.get("ready_for_source_member_component_input_gate"),
        evidence_artifacts=payload.get("evidence_artifacts", {}),
    )


def build_pv_ic1_executable_input_artifact(
    artifact: PVWeatherInputArtifact,
    *,
    year: int,
    node_ids: Sequence[str],
    manifest_path: str | None = None,
    artifact_id: str | None = None,
    source_id: str | None = None,
    version_id: str | None = None,
    ic1_calendar_id: str | None = None,
) -> ExecutableInputArtifact:
    """Convert D-004 PV/weather source-member metadata into an IC-1 artifact.

    The bridge is metadata-only: it preserves the source/member acceptance
    evidence and blocked final gates, but it does not sign paired HP/PV
    validation, map historical weather onto a planning calendar, approve PV
    parameters, assemble net load, or run event analysis.
    """
    assert_pv_weather_artifact_allows_consumer_use(artifact, intended_use="source_member_component_input")
    member = artifact.member_for_year(year)
    source_calendar_id = str(member["calendar_id"])
    target_calendar_id = source_calendar_id if ic1_calendar_id is None else str(ic1_calendar_id)
    evidence_path = _default_weather_input_artifact_path(artifact)
    manifest = evidence_path if manifest_path is None else manifest_path
    deferred_gates = tuple(
        gate
        for gate, value in sorted(artifact.blocked_acceptance_gates.items())
        if isinstance(value, Mapping) and value.get("blocked") is True
    )
    provenance = {
        "weather_contract": artifact.weather_contract,
        "source_member_acceptance_id": artifact.source_member_acceptance_id,
        "weather_input_artifact_status": artifact.status,
        "readiness_scope": artifact.readiness_scope,
        "ready_for_executable_input_gate_scope": "source_member_component_input_only_not_final_integrated",
        "selection_id": artifact.selection_id,
        "source_calendar_id": source_calendar_id,
        "source_cadence_seconds": int(member["cadence_seconds"]),
        "source_n_timesteps": int(member["n_timesteps"]),
        "source_first_timestamp_utc": str(member["first_timestamp_utc"]),
        "source_last_timestamp_utc": str(member["last_timestamp_utc"]),
        "content_sha256": str(member["content_sha256"]),
        "shared_weather_driver_id": str(member["shared_weather_driver_id"]),
        "realized_weather_path": artifact.realized_weather_path,
        "pvgis_role": artifact.pvgis_role,
        "pvgis_realized_weather_path": artifact.pvgis_realized_weather_path,
        "deferred_acceptance_gates": deferred_gates,
        "pv_parameter_decision_status": "PV-PARAM-001 proposed; executable PV parameters unsigned",
        "no_net_load_or_event_analysis": True,
    }
    if target_calendar_id != source_calendar_id:
        provenance["ic1_calendar_id"] = target_calendar_id
        provenance["calendar_mapping_status"] = "caller_supplied_not_d004_signed_by_this_helper"
    # Source/member acceptance is intentionally narrower than final paired or
    # integrated readiness; keep the deferred gates visible to IC-1 consumers.
    return ExecutableInputArtifact(
        artifact_id=artifact_id or f"{artifact.selection_id}:pv_weather:{year}",
        kind="pv",
        artifact_status="unsigned",
        version_id=version_id or artifact.selection_id,
        source_id=source_id or f"D-004:{artifact.selection_id}:WEATHER-001:pv",
        member_id=str(member["member_id"]),
        calendar_id=target_calendar_id,
        node_ids=tuple(node_ids),
        signed_register_ids=("WEATHER-001", "D004-MC-001", "D004-SOURCE-MEMBER-ACCEPTANCE"),
        timestep_seconds=int(member["cadence_seconds"]),
        shared_weather_driver_id=str(member["shared_weather_driver_id"]),
        manifest_path=manifest,
        provenance=provenance,
        blocking_register_ids=(
            "PV-PARAM-001",
            "FINAL-PAIRED-HP-PV-ACCEPTANCE",
            "COLD-SPELL-ACCEPTANCE",
        ),
    )


def build_pv_paired_readiness_preflight_packet(
    artifact: PVWeatherInputArtifact,
    *,
    parameter_config: PVSystemConfig | None = None,
    hp_weather_identity: Mapping[str, object] | WeatherMember | None = None,
    cold_spell_metadata: Mapping[str, object] | None = None,
) -> Mapping[str, object]:
    """Return a fail-closed PV/weather packet for later paired HP/PV review.

    This packet is deliberately metadata-only: it can show that D-004 source
    members are accepted and that HP/PV weather identity is structurally
    checkable, but it cannot sign PV parameters, cold-spell tolerances, or final
    paired acceptance by itself.
    """
    assert_pv_weather_artifact_allows_consumer_use(artifact, intended_use="source_member_component_input")
    pv_parameters_signed = False
    pv_parameter_status = "missing_unsigned"
    signed_pv_parameter_decision_id = None
    if parameter_config is not None:
        pv_parameter_status = parameter_config.parameter_status
        signed_pv_parameter_decision_id = parameter_config.signed_parameter_decision_id
        try:
            parameter_config.require_signed_parameters()
        except ValueError:
            pv_parameters_signed = False
        else:
            pv_parameters_signed = True

    hp_identity_record = _identity_record_or_none(hp_weather_identity)
    hp_pv_identity_equal = False
    hp_pv_identity_check = "missing_hp_weather_identity"
    compared_member_id = None
    if hp_identity_record is not None:
        compared_member_id = str(hp_identity_record.get("member_id", ""))
        try:
            member = assert_weather_member_matches_input_artifact(hp_identity_record, artifact)
            assert_same_weather_realization(member, hp_identity_record)
        except (KeyError, ValueError) as exc:
            hp_pv_identity_check = f"blocked: {exc}"
        else:
            hp_pv_identity_equal = True
            hp_pv_identity_check = "exact_weather_001_identity_calendar_content_match"

    cold_spell = _audit_json_mapping(cold_spell_metadata or {}, "cold_spell_metadata")
    cold_spell_tolerances_status = str(cold_spell.get("numerical_tolerances_status", "pending_unsigned"))
    cold_spell_tolerances_signed = (
        cold_spell_tolerances_status == "approved_with_signed_tolerances"
        and bool(cold_spell.get("signed_decision_id"))
    )

    blockers: list[str] = []
    if not pv_parameters_signed:
        blockers.append("PV-PARAM-001")
    if not hp_pv_identity_equal:
        blockers.append("FINAL-PAIRED-HP-PV-ACCEPTANCE")
    if not cold_spell_tolerances_signed:
        blockers.append("COLD-SPELL-ACCEPTANCE")

    return MappingProxyType(
        {
            "packet_id": f"{artifact.selection_id}:pv_paired_readiness_preflight",
            "data_id": artifact.data_id,
            "weather_contract": artifact.weather_contract,
            "source_member_acceptance_id": artifact.source_member_acceptance_id,
            "source_member_readiness_scope": artifact.readiness_scope,
            "source_member_ready": artifact.accepted_for_source_member_use,
            "realized_weather_path": artifact.realized_weather_path,
            "pvgis_role": artifact.pvgis_role,
            "pvgis_realized_weather_path": artifact.pvgis_realized_weather_path,
            "pv_parameter_decision_id": "PV-PARAM-001",
            "pv_parameter_status": pv_parameter_status,
            "signed_pv_parameter_decision_id": signed_pv_parameter_decision_id,
            "pv_parameters_signed_for_component_use": pv_parameters_signed,
            "hp_weather_identity_supplied": hp_identity_record is not None,
            "compared_member_id": compared_member_id,
            "hp_pv_weather_identity_equal": hp_pv_identity_equal,
            "hp_pv_identity_check": hp_pv_identity_check,
            "required_identity_fields_for_hp_pv_pairing": artifact.required_identity_fields_for_hp_pv_pairing,
            "cold_spell_acceptance_design_id": "E2-S3-COLD-SPELL-ACCEPTANCE-DESIGN",
            "cold_spell_tolerances_status": cold_spell_tolerances_status,
            "cold_spell_tolerances_signed": cold_spell_tolerances_signed,
            "cold_spell_metadata": dict(cold_spell),
            "ready_for_final_paired_hp_pv_acceptance_run": not blockers,
            "final_paired_hp_pv_acceptance_signed_by_this_packet": False,
            "blocking_register_ids": tuple(blockers),
            "out_of_scope": (
                "no net-load",
                "no event detection",
                "no P(E)",
                "no capacity screen",
                "no threshold analysis",
                "no manuscript results",
            ),
        }
    )


def build_pv_final_acceptance_gate_packet(
    artifact: PVWeatherInputArtifact,
    *,
    parameter_config: PVSystemConfig | None,
    hp_weather_identities: Sequence[Mapping[str, object] | WeatherMember],
    cold_spell_metadata: Mapping[str, object],
    member_ids: Sequence[str],
) -> Mapping[str, object]:
    """Return the exact fail-closed gate record for a future paired run.

    The helper can make prerequisites auditable, but it never signs final paired
    acceptance and never runs HP/PV, cold-spell, net-load, or event analysis.
    """
    assert_pv_weather_artifact_allows_consumer_use(artifact, intended_use="source_member_component_input")
    requested_member_ids = tuple(str(item) for item in member_ids)
    if not requested_member_ids:
        raise ValueError("member_ids must identify the future paired-acceptance member subset")
    if len(set(requested_member_ids)) != len(requested_member_ids):
        raise ValueError("member_ids must not contain duplicates")

    pv_parameters_signed = False
    pv_parameter_status = "missing_unsigned"
    signed_pv_parameter_decision_id = None
    if parameter_config is not None:
        pv_parameter_status = parameter_config.parameter_status
        signed_pv_parameter_decision_id = parameter_config.signed_parameter_decision_id
        try:
            parameter_config.require_signed_parameters()
        except ValueError:
            pv_parameters_signed = False
        else:
            pv_parameters_signed = parameter_config.signed_parameter_decision_id == "PV-PARAM-001"

    hp_records = tuple(_identity_record_or_none(item) for item in hp_weather_identities)
    if any(item is None for item in hp_records):
        raise ValueError("hp_weather_identities must not contain None")
    hp_by_member_id = {str(record["member_id"]): record for record in hp_records if record is not None}
    paired_identity_results: list[dict[str, object]] = []
    for member_id in requested_member_ids:
        try:
            artifact_member = artifact.member_for_id(member_id)
        except KeyError as exc:
            paired_identity_results.append({"member_id": member_id, "passed": False, "reason": str(exc)})
            continue
        hp_record = hp_by_member_id.get(member_id)
        if hp_record is None:
            paired_identity_results.append({"member_id": member_id, "passed": False, "reason": "missing_hp_identity"})
            continue
        try:
            assert_weather_member_matches_input_artifact(hp_record, artifact, member_id=member_id)
            assert_same_weather_realization(artifact_member, hp_record)
        except ValueError as exc:
            paired_identity_results.append({"member_id": member_id, "passed": False, "reason": str(exc)})
        else:
            paired_identity_results.append(
                {
                    "member_id": member_id,
                    "passed": True,
                    "shared_weather_driver_id": artifact_member["shared_weather_driver_id"],
                    "content_sha256": artifact_member["content_sha256"],
                    "calendar_id": artifact_member["calendar_id"],
                }
            )
    hp_pv_identity_equal = all(item["passed"] is True for item in paired_identity_results)

    cold_spell = _audit_json_mapping(cold_spell_metadata, "cold_spell_metadata")
    missing_cold_spell_fields = tuple(
        field for field in REQUIRED_COLD_SPELL_TOLERANCE_FIELDS if field not in cold_spell
    )
    cold_spell_tolerances_signed = (
        str(cold_spell.get("numerical_tolerances_status", "")) == "approved_with_signed_tolerances"
        and bool(cold_spell.get("signed_decision_id"))
        and cold_spell.get("first_real_acceptance_run_preinspection_signed") is True
        and not missing_cold_spell_fields
    )

    blockers: list[str] = []
    if not pv_parameters_signed:
        blockers.append("PV-PARAM-001")
    if not hp_pv_identity_equal:
        blockers.append("FINAL-PAIRED-HP-PV-ACCEPTANCE")
    if not cold_spell_tolerances_signed:
        blockers.append("COLD-SPELL-ACCEPTANCE")

    return MappingProxyType(
        {
            "packet_id": f"{artifact.selection_id}:pv_final_acceptance_gate",
            "data_id": artifact.data_id,
            "weather_contract": artifact.weather_contract,
            "source_member_acceptance_id": artifact.source_member_acceptance_id,
            "source_member_readiness_scope": artifact.readiness_scope,
            "member_ids": requested_member_ids,
            "pv_parameter_decision_id": "PV-PARAM-001",
            "pv_parameter_status": pv_parameter_status,
            "signed_pv_parameter_decision_id": signed_pv_parameter_decision_id,
            "pv_parameters_signed_for_component_use": pv_parameters_signed,
            "paired_identity_results": tuple(paired_identity_results),
            "hp_pv_weather_identity_equal": hp_pv_identity_equal,
            "cold_spell_acceptance_design_id": "E2-S3-COLD-SPELL-ACCEPTANCE-DESIGN",
            "required_cold_spell_tolerance_fields": REQUIRED_COLD_SPELL_TOLERANCE_FIELDS,
            "missing_cold_spell_tolerance_fields": missing_cold_spell_fields,
            "cold_spell_tolerances_signed": cold_spell_tolerances_signed,
            "ready_for_first_real_paired_acceptance_run": not blockers,
            "final_paired_hp_pv_acceptance_signed_by_this_packet": False,
            "blocking_register_ids": tuple(blockers),
            "out_of_scope": (
                "no net-load",
                "no event detection",
                "no P(E)",
                "no threshold analysis",
                "no capacity screen",
                "no manuscript results",
            ),
        }
    )

def assert_pv_weather_artifact_allows_consumer_use(
    artifact: PVWeatherInputArtifact,
    *,
    intended_use: str,
) -> None:
    """Raise when a consumer asks the source/member artifact to satisfy a blocked gate."""
    if intended_use == "source_member_component_input":
        return
    gate = artifact.blocked_acceptance_gates.get(intended_use)
    if isinstance(gate, Mapping) and gate.get("blocked") is True:
        raise ValueError(f"PV weather artifact cannot satisfy blocked gate {intended_use}")
    raise ValueError(f"PV weather artifact does not authorize intended_use {intended_use!r}")


def assert_weather_member_matches_input_artifact(
    weather: WeatherMember | Mapping[str, object],
    artifact: PVWeatherInputArtifact,
    *,
    year: int | None = None,
    member_id: str | None = None,
) -> Mapping[str, object]:
    """Raise unless a WEATHER-001 record is one accepted D-004 input member."""
    identity = weather.identity_record() if isinstance(weather, WeatherMember) else dict(weather)
    if year is not None:
        member = artifact.member_for_year(year)
    else:
        lookup_id = member_id or str(identity.get("member_id", ""))
        member = artifact.member_for_id(lookup_id)
    for key in artifact.required_identity_fields_for_hp_pv_pairing:
        if identity.get(key) != member.get(key):
            raise ValueError(f"weather input artifact mismatch on {key}")
    for key in ("first_timestamp_local", "last_timestamp_local"):
        if key in identity and identity.get(key) != member.get(key):
            raise ValueError(f"weather input artifact mismatch on {key}")
    return member


def generate_pv_profile_from_input_artifact(
    weather: WeatherMember,
    config: PVSystemConfig,
    artifact: PVWeatherInputArtifact,
    *,
    year: int | None = None,
    intended_use: str = "source_member_component_input",
) -> PVGenerationProfile:
    """Generate PV only after the weather member matches the accepted artifact."""
    assert_pv_weather_artifact_allows_consumer_use(artifact, intended_use=intended_use)
    member = assert_weather_member_matches_input_artifact(weather, artifact, year=year)
    profile = generate_pv_profile(weather, config)
    identity = dict(profile.weather_identity)
    identity.update(
        {
            "source_member_acceptance_id": artifact.source_member_acceptance_id,
            "weather_input_artifact_status": artifact.status,
            "calendar_id": member["calendar_id"],
            "pvgis_realized_weather_path": artifact.pvgis_realized_weather_path,
            "pvgis_role": artifact.pvgis_role,
        }
    )
    return PVGenerationProfile(
        weather_member_id=profile.weather_member_id,
        weather_source=profile.weather_source,
        shared_weather_driver_id=profile.shared_weather_driver_id,
        timestamps_utc=profile.timestamps_utc,
        timestamps_local=profile.timestamps_local,
        generation_kw=profile.generation_kw,
        config=config,
        weather_identity=identity,
    )


def generate_pv_profile(weather: WeatherMember, config: PVSystemConfig) -> PVGenerationProfile:
    """Generate PV power in kW from paired irradiance and temperature channels."""
    temperature_factor = 1.0 + config.temperature_coefficient_per_c * (
        weather.temperature_c - config.reference_temperature_c
    )
    # Extreme temperatures must reduce output to zero at worst; otherwise a
    # pathological coefficient/input pair could silently turn PV into demand.
    temperature_factor = np.maximum(temperature_factor, 0.0)
    generation_kw = (
        config.installed_capacity_kw
        * config.performance_ratio
        * (weather.ghi_w_per_m2 / config.reference_irradiance_w_per_m2)
        * temperature_factor
    )
    generation_kw = np.maximum(generation_kw, 0.0)
    if config.clip_to_capacity:
        generation_kw = np.minimum(generation_kw, config.installed_capacity_kw)
    return PVGenerationProfile(
        weather_member_id=weather.member_id,
        weather_source=weather.source,
        shared_weather_driver_id=weather.shared_weather_driver_id,
        timestamps_utc=weather.timestamps_utc,
        timestamps_local=weather.timestamps_local,
        generation_kw=generation_kw.astype(np.float64),
        config=config,
        weather_identity=weather.identity_record(),
    )


def seasonal_energy_kwh(profile: PVGenerationProfile) -> dict[str, float]:
    """Return PV energy by meteorological season using local timestamps."""
    totals = dict.fromkeys(SEASONS, 0.0)
    cadence_hours = profile.cadence_hours
    for value_kw, timestamp in zip(profile.generation_kw, profile.timestamps_local, strict=True):
        season = SEASON_BY_MONTH[timestamp.month]
        totals[season] += float(value_kw) * cadence_hours
    return {season: float(totals[season]) for season in SEASONS}


def summarize_pv_profile(profile: PVGenerationProfile) -> dict[str, object]:
    """Return commit-safe PV profile summary statistics."""
    peak_timestamp = profile.peak_timestamp_local()
    return {
        "weather_member_id": profile.weather_member_id,
        "weather_source": profile.weather_source,
        "shared_weather_driver_id": profile.shared_weather_driver_id,
        "n_timesteps": profile.n_timesteps,
        "cadence_seconds": profile.cadence_seconds,
        "annual_energy_kwh": profile.annual_energy_kwh(),
        "seasonal_energy_kwh": seasonal_energy_kwh(profile),
        "peak_kw": profile.peak_kw(),
        "peak_timestamp_local": peak_timestamp.isoformat(),
        "peak_month": peak_timestamp.month,
        "config_id": profile.config.config_id,
        "weather_content_sha256": profile.weather_content_sha256,
        "weather_identity_record": profile.identity_record(),
    }


def check_profile_against_pvgis_reference(
    profile: PVGenerationProfile,
    reference: PVGISReference,
    *,
    max_relative_seasonal_error: float,
    max_relative_annual_error: float | None = None,
    allowed_peak_months: Sequence[int] | None = None,
) -> PVGISSanityCheck:
    """Compare seasonal totals and peak timing against a PVGIS reference."""
    if max_relative_seasonal_error < 0:
        raise ValueError("max_relative_seasonal_error must be non-negative")
    if max_relative_annual_error is not None and max_relative_annual_error < 0:
        raise ValueError("max_relative_annual_error must be non-negative")

    profile_seasonal = seasonal_energy_kwh(profile)
    relative_by_season = {
        season: _relative_error(profile_seasonal[season], reference.seasonal_energy_kwh[season])
        for season in SEASONS
    }
    failed: list[str] = [
        f"{season} seasonal relative error {relative_by_season[season]:.6g} exceeds {max_relative_seasonal_error:.6g}"
        for season in SEASONS
        if relative_by_season[season] > max_relative_seasonal_error
    ]
    annual_error = _relative_error(profile.annual_energy_kwh(), reference.annual_energy_kwh)
    if max_relative_annual_error is not None and annual_error > max_relative_annual_error:
        failed.append(f"annual relative error {annual_error:.6g} exceeds {max_relative_annual_error:.6g}")

    peak_month = profile.peak_timestamp_local().month
    allowed_months = _allowed_peak_months(reference, allowed_peak_months)
    peak_timing_passed = True
    if allowed_months:
        peak_timing_passed = peak_month in allowed_months
        if not peak_timing_passed:
            failed.append(f"peak month {peak_month} outside allowed PVGIS months {sorted(allowed_months)}")

    return PVGISSanityCheck(
        passed=not failed,
        seasonal_relative_error=relative_by_season,
        annual_relative_error=annual_error,
        profile_peak_month=peak_month,
        peak_timing_passed=peak_timing_passed,
        failed_reasons=tuple(failed),
    )


def parse_pvgis_monthly_reference(
    payload: bytes | str | Mapping[str, Any],
    *,
    source_id: str,
) -> PVGISReference:
    """Parse PVGIS monthly JSON into a seasonal reference object."""
    if isinstance(payload, bytes):
        parsed = json.loads(payload.decode("utf-8"))
    elif isinstance(payload, str):
        parsed = json.loads(payload)
    else:
        parsed = dict(payload)
    outputs = parsed.get("outputs")
    if not isinstance(outputs, Mapping):
        raise ValueError("PVGIS payload lacks outputs")
    monthly = outputs.get("monthly")
    if isinstance(monthly, Mapping):
        rows = monthly.get("fixed") or monthly.get("monthly")
    else:
        rows = monthly
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise ValueError("PVGIS monthly output lacks a row sequence")

    by_month: dict[int, float] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("PVGIS monthly row must be an object")
        month = int(row["month"])
        if month not in range(1, 13):
            raise ValueError("PVGIS monthly row has invalid month")
        if "E_m" in row:
            energy = float(row["E_m"])
        elif "E" in row:
            energy = float(row["E"])
        else:
            raise ValueError("PVGIS monthly row lacks E_m or E")
        if not _is_finite(energy) or energy < 0:
            raise ValueError("PVGIS monthly energy must be finite and non-negative")
        by_month[month] = energy
    if set(by_month) != set(range(1, 13)):
        raise ValueError("PVGIS monthly output must contain all 12 months")

    seasonal = dict.fromkeys(SEASONS, 0.0)
    for month, energy in by_month.items():
        seasonal[SEASON_BY_MONTH[month]] += energy
    peak_month = max(by_month, key=lambda month: by_month[month])
    return PVGISReference(
        source_id=source_id,
        seasonal_energy_kwh=seasonal,
        annual_energy_kwh=sum(by_month.values()),
        peak_month=peak_month,
    )


def _default_weather_input_artifact_path(artifact: PVWeatherInputArtifact) -> str:
    raw_path = artifact.evidence_artifacts.get("weather_input_artifact")
    if isinstance(raw_path, str) and raw_path:
        return raw_path
    return f"data/metadata/weather_pv/{artifact.selection_id}_weather_input_artifact.json"


def _identity_record_or_none(
    identity: Mapping[str, object] | WeatherMember | None,
) -> Mapping[str, object] | None:
    if identity is None:
        return None
    if isinstance(identity, WeatherMember):
        return identity.identity_record()
    return _audit_json_mapping(identity, "hp_weather_identity")


def _validate_weather_input_member_record(member: Mapping[str, object], *, acceptance_id: str) -> None:
    required = (
        "year",
        "member_id",
        "shared_weather_driver_id",
        "source",
        "content_sha256",
        "calendar_id",
        "cadence_seconds",
        "n_timesteps",
        "first_timestamp_utc",
        "last_timestamp_utc",
        "source_member_acceptance_id",
        "accepted_for_source_member_use",
        "final_paired_hp_pv_acceptance",
        "cold_spell_acceptance",
    )
    missing = [key for key in required if key not in member]
    if missing:
        raise ValueError(f"weather input artifact member missing fields: {missing}")
    if member["source_member_acceptance_id"] != acceptance_id:
        raise ValueError("member source_member_acceptance_id must match the artifact")
    if member["accepted_for_source_member_use"] is not True:
        raise ValueError("member must be accepted for source/member use")
    if member["final_paired_hp_pv_acceptance"] is not False:
        raise ValueError("member must not imply final paired HP/PV acceptance")
    if member["cold_spell_acceptance"] is not False:
        raise ValueError("member must not imply cold-spell acceptance")
    if len(str(member["content_sha256"])) != 64:
        raise ValueError("member content_sha256 must be a SHA-256 hex digest")
    if int(member["cadence_seconds"]) != STEP_SECONDS_15MIN:
        raise ValueError("member cadence_seconds must be 900")
    if int(member["n_timesteps"]) <= 0:
        raise ValueError("member n_timesteps must be positive")


def _audit_json_mapping(raw: Mapping[str, object], label: str) -> Mapping[str, object]:
    if not isinstance(raw, Mapping):
        raise ValueError(f"{label} must be a mapping")
    copied = dict(sorted((str(key), value) for key, value in raw.items()))
    try:
        json.dumps(copied, sort_keys=True, separators=(",", ":"))
    except TypeError as exc:
        raise ValueError(f"{label} must be JSON-serializable") from exc
    return MappingProxyType(copied)


def _coerce_aware_datetime(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{name} entries must be datetimes")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} entries must be timezone-aware")
    return value


def _validate_strictly_chronological(values: Sequence[datetime], label: str) -> None:
    for previous, current in zip(values, values[1:]):
        if current <= previous:
            raise ValueError(f"{label} timestamps must be complete and chronological")


def _constant_cadence_seconds(values: Sequence[datetime]) -> int:
    deltas = {int((current - previous).total_seconds()) for previous, current in zip(values, values[1:])}
    if len(deltas) != 1:
        raise ValueError("Timestamps must have one constant cadence")
    cadence = deltas.pop()
    if cadence <= 0:
        raise ValueError("Timestamp cadence must be positive")
    return cadence


def _as_float_vector(values: Sequence[float], name: str) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1:
        raise ValueError(f"{name} must be a one-dimensional vector")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} contains missing or non-finite values")
    copied = array.astype(np.float64, copy=True)
    copied.setflags(write=False)
    return copied


def _require_positive_finite(value: float, name: str) -> None:
    _require_finite(value, name)
    if float(value) <= 0:
        raise ValueError(f"{name} must be positive")


def _require_finite(value: float, name: str) -> None:
    if not _is_finite(float(value)):
        raise ValueError(f"{name} must be finite")


def _is_finite(value: float | None) -> bool:
    return value is not None and np.isfinite(float(value))


def _relative_error(actual: float, expected: float) -> float:
    actual_float = float(actual)
    expected_float = float(expected)
    if expected_float == 0:
        return 0.0 if actual_float == 0 else float("inf")
    return abs(actual_float - expected_float) / abs(expected_float)


def _allowed_peak_months(
    reference: PVGISReference,
    allowed_peak_months: Sequence[int] | None,
) -> set[int]:
    if allowed_peak_months is not None:
        months = {int(month) for month in allowed_peak_months}
    elif reference.peak_month is not None:
        months = {reference.peak_month}
    else:
        months = set()
    invalid = sorted(month for month in months if month not in range(1, 13))
    if invalid:
        raise ValueError(f"allowed_peak_months contains invalid months: {invalid}")
    return months
