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
class PVCBSAnchorEvidencePacket:
    """Retrieved CBS Alkmaar PV-capacity anchor evidence with unsigned values."""

    packet_id: str
    data_id: str
    status: str
    download_performed: bool
    raw_data_committed: bool
    approved_route_decision: str
    source_value_packet_id: str
    capacity_route_boundary: str
    pv_param_boundary: str
    pv_orient_boundary: str
    source: Mapping[str, object]
    raw_bundle: Mapping[str, object]
    schema: Mapping[str, object]
    candidate_value_choices_for_pi_review: Mapping[str, object]
    pi_approval_keys_before_executable_use: Sequence[str]
    non_claims: Sequence[str]

    def __post_init__(self) -> None:
        if self.packet_id != "D014-CBS-PV-CAPACITY-ANCHOR-EVIDENCE":
            raise ValueError("CBS PV capacity anchor evidence must identify D014-CBS-PV-CAPACITY-ANCHOR-EVIDENCE")
        if self.data_id != "D-014":
            raise ValueError("CBS PV capacity anchor evidence must identify D-014")
        if self.status != "retrieved_source_evidence_values_unsigned":
            raise ValueError("CBS PV capacity anchor evidence must remain retrieved evidence with unsigned values")
        if self.download_performed is not True:
            raise ValueError("CBS PV capacity anchor evidence must record that source evidence was downloaded")
        if self.raw_data_committed is not False:
            raise ValueError("CBS raw PV capacity evidence must remain ignored/uncommitted")
        if self.approved_route_decision != "PV-CAP-001":
            raise ValueError("CBS PV capacity anchor evidence must be governed by PV-CAP-001")
        if self.source_value_packet_id != "D014-PV-CAPACITY-SOURCE-VALUE-PACKET":
            raise ValueError("CBS evidence must link to the D-014 capacity source/value packet")
        if "II3050/scenario growth factor remains separate" not in self.capacity_route_boundary:
            raise ValueError("CBS evidence must keep II3050 growth separate")
        if "PV-PARAM-001 remains proposed" not in self.pv_param_boundary:
            raise ValueError("CBS evidence must keep PV-PARAM-001 fail-closed")
        if "no roof/building/3DBAG/PV-map retrieval" not in self.pv_orient_boundary:
            raise ValueError("CBS evidence must preserve PV-ORIENT-001 lightweight scope")
        source = _audit_json_mapping(self.source, "source")
        raw_bundle = _audit_json_mapping(self.raw_bundle, "raw_bundle")
        schema = _audit_json_mapping(self.schema, "schema")
        choices = _audit_json_mapping(self.candidate_value_choices_for_pi_review, "candidate_value_choices_for_pi_review")
        approval_keys = tuple(str(item) for item in self.pi_approval_keys_before_executable_use)
        non_claims = tuple(str(item) for item in self.non_claims)
        if source.get("table_id") != "85005NED":
            raise ValueError("CBS evidence must use table 85005NED")
        if not str(raw_bundle.get("path", "")).startswith("data/raw/pv_capacity/"):
            raise ValueError("CBS raw evidence must stay under ignored data/raw/pv_capacity")
        if len(str(raw_bundle.get("sha256", ""))) != 64:
            raise ValueError("CBS raw evidence must record a SHA-256 checksum")
        if int(raw_bundle.get("size_bytes", 0)) <= 0:
            raise ValueError("CBS raw evidence must record a positive file size")
        if schema.get("alkmaar_row_count") != 63:
            raise ValueError("CBS evidence must preserve the full GM0361 row set")
        field_keys = {str(item.get("key")) for item in schema.get("topic_fields", ())}
        required_fields = {
            "Installaties_1",
            "OpgesteldVermogenVanZonnepanelen_2",
            "OpgesteldVermogenOmvormers_3",
            "ProductieVanZonnestroom_4",
        }
        if not required_fields.issubset(field_keys):
            raise ValueError("CBS evidence missing expected topic fields")
        rows = tuple(_audit_json_mapping(item, "exact row candidate") for item in choices.get("exact_row_candidates", ()))
        if not rows:
            raise ValueError("CBS evidence must list exact row candidates for PI review")
        row_roles = {str(item.get("choice_role")) for item in rows}
        if "latest_definitive_all_activity_and_homes_candidate" not in row_roles:
            raise ValueError("CBS evidence must include the latest definitive municipal-total candidate")
        for row in rows:
            if row.get("executable_status") != "candidate_only_unsigned":
                raise ValueError("CBS row candidates must remain unsigned")
        required_keys = {
            "cbs_raw_bundle_sha256",
            "alkmaar_geography_key",
            "cbs_source_period_key",
            "cbs_sector_category_key",
            "cbs_capacity_field_key",
            "capacity_unit_and_dc_ac_convention",
            "ii3050_growth_factor_value",
            "node_allocation_rule",
            "statistical_orientation_tilt_distribution_weights",
            "PV-PARAM-001_or_amended_conversion_decision",
        }
        missing = required_keys.difference(approval_keys)
        if missing:
            raise ValueError(f"CBS evidence missing approval keys: {sorted(missing)}")
        if not any("No executable PV installed-capacity value is approved" in item for item in non_claims):
            raise ValueError("CBS evidence must state no executable capacity value is approved")
        if not any("No CBS period" in item for item in non_claims):
            raise ValueError("CBS evidence must state no CBS row/field convention is final")

        object.__setattr__(self, "source", source)
        object.__setattr__(self, "raw_bundle", raw_bundle)
        object.__setattr__(self, "schema", schema)
        object.__setattr__(self, "candidate_value_choices_for_pi_review", choices)
        object.__setattr__(self, "pi_approval_keys_before_executable_use", approval_keys)
        object.__setattr__(self, "non_claims", non_claims)

    @property
    def missing_approval_keys(self) -> tuple[str, ...]:
        return self.pi_approval_keys_before_executable_use

    def require_executable_capacity_anchor_approval(self) -> None:
        """Always fail until a later signed value artifact replaces this evidence."""
        raise ValueError(
            "D-014 CBS PV capacity anchor values are unsigned; executable PV requires signed period, "
            "sector/category, field, DC/AC convention, II3050 growth factor, allocation, and PV-PARAM approval"
        )

    def identity_record(self) -> dict[str, object]:
        return {
            "packet_id": self.packet_id,
            "data_id": self.data_id,
            "status": self.status,
            "table_id": self.source["table_id"],
            "raw_sha256": self.raw_bundle["sha256"],
            "raw_size_bytes": self.raw_bundle["size_bytes"],
            "alkmaar_row_count": self.schema["alkmaar_row_count"],
            "candidate_row_roles": tuple(
                str(item["choice_role"])
                for item in self.candidate_value_choices_for_pi_review["exact_row_candidates"]
            ),
            "missing_approval_keys": self.missing_approval_keys,
            "executable_capacity_value_approved": False,
        }


def load_pv_cbs_anchor_evidence_packet(path: str | Path) -> PVCBSAnchorEvidencePacket:
    """Load the retrieved CBS Alkmaar PV-capacity anchor evidence packet."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return PVCBSAnchorEvidencePacket(
        packet_id=str(payload.get("packet_id", "")),
        data_id=str(payload.get("data_id", "")),
        status=str(payload.get("status", "")),
        download_performed=bool(payload.get("download_performed")),
        raw_data_committed=bool(payload.get("raw_data_committed")),
        approved_route_decision=str(payload.get("approved_route_decision", "")),
        source_value_packet_id=str(payload.get("source_value_packet_id", "")),
        capacity_route_boundary=str(payload.get("capacity_route_boundary", "")),
        pv_param_boundary=str(payload.get("pv_param_boundary", "")),
        pv_orient_boundary=str(payload.get("pv_orient_boundary", "")),
        source=payload.get("source", {}),
        raw_bundle=payload.get("raw_bundle", {}),
        schema=payload.get("schema", {}),
        candidate_value_choices_for_pi_review=payload.get("candidate_value_choices_for_pi_review", {}),
        pi_approval_keys_before_executable_use=payload.get("pi_approval_keys_before_executable_use", ()),
        non_claims=payload.get("non_claims", ()),
    )


@dataclass(frozen=True)
class PVII3050GrowthEvidencePacket:
    """Retrieved II3050 PV growth evidence with unsigned scenario choices."""

    packet_id: str
    data_id: str
    status: str
    download_performed: bool
    raw_data_committed: bool
    approved_route_decision: str
    source_value_packet_id: str
    cbs_anchor_evidence_id: str
    capacity_route_boundary: str
    pv_param_boundary: str
    pv_orient_boundary: str
    source: Mapping[str, object]
    raw_bundle: Mapping[str, object]
    table_evidence: Mapping[str, object]
    growth_factor_choices_for_pi_review: Mapping[str, object]
    pi_approval_keys_before_executable_use: Sequence[str]
    non_claims: Sequence[str]

    def __post_init__(self) -> None:
        if self.packet_id != "D014-II3050-PV-GROWTH-EVIDENCE":
            raise ValueError("II3050 growth evidence must identify D014-II3050-PV-GROWTH-EVIDENCE")
        if self.data_id != "D-014":
            raise ValueError("II3050 growth evidence must identify D-014")
        if self.status != "retrieved_source_evidence_values_unsigned":
            raise ValueError("II3050 growth evidence must remain retrieved evidence with unsigned values")
        if self.download_performed is not True:
            raise ValueError("II3050 growth evidence must record that source evidence was downloaded")
        if self.raw_data_committed is not False:
            raise ValueError("II3050 raw growth evidence must remain ignored/uncommitted")
        if self.approved_route_decision != "PV-CAP-001":
            raise ValueError("II3050 growth evidence must be governed by PV-CAP-001")
        if self.source_value_packet_id != "D014-PV-CAPACITY-SOURCE-VALUE-PACKET":
            raise ValueError("II3050 growth evidence must link to the D-014 capacity source/value packet")
        if self.cbs_anchor_evidence_id != "D014-CBS-PV-CAPACITY-ANCHOR-EVIDENCE":
            raise ValueError("II3050 growth evidence must link to the CBS anchor evidence packet")
        if "CBS Alkmaar anchor row" not in self.capacity_route_boundary:
            raise ValueError("II3050 growth evidence must keep the CBS anchor row separate")
        if "PV-PARAM-001 remains proposed" not in self.pv_param_boundary:
            raise ValueError("II3050 growth evidence must keep PV-PARAM-001 fail-closed")
        if "no roof/building/3DBAG/PV-map retrieval" not in self.pv_orient_boundary:
            raise ValueError("II3050 growth evidence must preserve PV-ORIENT-001 lightweight scope")
        source = _audit_json_mapping(self.source, "source")
        raw_bundle = _audit_json_mapping(self.raw_bundle, "raw_bundle")
        table = _audit_json_mapping(self.table_evidence, "table_evidence")
        choices = _audit_json_mapping(self.growth_factor_choices_for_pi_review, "growth_factor_choices_for_pi_review")
        approval_keys = tuple(str(item) for item in self.pi_approval_keys_before_executable_use)
        non_claims = tuple(str(item) for item in self.non_claims)
        if source.get("owner") != "Netbeheer Nederland":
            raise ValueError("II3050 growth evidence source must be Netbeheer Nederland")
        if not str(raw_bundle.get("path", "")).startswith("data/raw/pv_capacity/"):
            raise ValueError("II3050 raw evidence must stay under ignored data/raw/pv_capacity")
        if len(str(raw_bundle.get("sha256", ""))) != 64:
            raise ValueError("II3050 raw evidence must record a SHA-256 checksum")
        if int(raw_bundle.get("size_bytes", 0)) <= 0:
            raise ValueError("II3050 raw evidence must record a positive file size")
        if table.get("row_label") != "Zon PV*" or table.get("unit") != "GW":
            raise ValueError("II3050 evidence must identify the Zon PV* GW row")
        planning_rows = tuple(
            _audit_json_mapping(item, "II3050 planning-year candidate")
            for item in table.get("planning_year_2035_candidates", ())
        )
        if {str(item.get("scenario")) for item in planning_rows} != {"KA", "ND", "IA"}:
            raise ValueError("II3050 evidence must list all 2035 KA/ND/IA candidates")
        for row in planning_rows:
            if row.get("executable_status") != "candidate_only_unsigned":
                raise ValueError("II3050 scenario candidates must remain unsigned")
        required_keys = {
            "ii3050_raw_pdf_sha256",
            "ii3050_scenario_column",
            "ii3050_growth_denominator",
            "ii3050_growth_factor_formula",
            "ii3050_growth_factor_value",
            "scenario_source_consistency_with_ev_hp_inputs",
            "cbs_capacity_field_key",
            "capacity_unit_and_dc_ac_convention",
            "statistical_orientation_tilt_distribution_weights",
            "PV-PARAM-001_or_amended_conversion_decision",
        }
        missing = required_keys.difference(approval_keys)
        if missing:
            raise ValueError(f"II3050 evidence missing approval keys: {sorted(missing)}")
        if not any("No II3050 scenario column" in item for item in non_claims):
            raise ValueError("II3050 evidence must state no scenario column is final")
        if not any("No II3050 growth denominator" in item for item in non_claims):
            raise ValueError("II3050 evidence must state no growth factor is approved")

        object.__setattr__(self, "source", source)
        object.__setattr__(self, "raw_bundle", raw_bundle)
        object.__setattr__(self, "table_evidence", table)
        object.__setattr__(self, "growth_factor_choices_for_pi_review", choices)
        object.__setattr__(self, "pi_approval_keys_before_executable_use", approval_keys)
        object.__setattr__(self, "non_claims", non_claims)

    @property
    def missing_approval_keys(self) -> tuple[str, ...]:
        return self.pi_approval_keys_before_executable_use

    def require_executable_growth_factor_approval(self) -> None:
        """Always fail until a later signed II3050 growth artifact replaces this evidence."""
        raise ValueError(
            "D-014 II3050 PV growth values are unsigned; executable PV requires signed scenario column, "
            "growth denominator, growth formula/value, CBS convention, allocation, and PV-PARAM approval"
        )

    def identity_record(self) -> dict[str, object]:
        return {
            "packet_id": self.packet_id,
            "data_id": self.data_id,
            "status": self.status,
            "raw_sha256": self.raw_bundle["sha256"],
            "raw_size_bytes": self.raw_bundle["size_bytes"],
            "row_label": self.table_evidence["row_label"],
            "unit": self.table_evidence["unit"],
            "planning_year_candidate_scenarios": tuple(
                str(item["scenario"])
                for item in self.table_evidence["planning_year_2035_candidates"]
            ),
            "missing_approval_keys": self.missing_approval_keys,
            "executable_growth_factor_approved": False,
        }


def load_pv_ii3050_growth_evidence_packet(path: str | Path) -> PVII3050GrowthEvidencePacket:
    """Load the retrieved II3050 PV growth evidence packet."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return PVII3050GrowthEvidencePacket(
        packet_id=str(payload.get("packet_id", "")),
        data_id=str(payload.get("data_id", "")),
        status=str(payload.get("status", "")),
        download_performed=bool(payload.get("download_performed")),
        raw_data_committed=bool(payload.get("raw_data_committed")),
        approved_route_decision=str(payload.get("approved_route_decision", "")),
        source_value_packet_id=str(payload.get("source_value_packet_id", "")),
        cbs_anchor_evidence_id=str(payload.get("cbs_anchor_evidence_id", "")),
        capacity_route_boundary=str(payload.get("capacity_route_boundary", "")),
        pv_param_boundary=str(payload.get("pv_param_boundary", "")),
        pv_orient_boundary=str(payload.get("pv_orient_boundary", "")),
        source=payload.get("source", {}),
        raw_bundle=payload.get("raw_bundle", {}),
        table_evidence=payload.get("table_evidence", {}),
        growth_factor_choices_for_pi_review=payload.get("growth_factor_choices_for_pi_review", {}),
        pi_approval_keys_before_executable_use=payload.get("pi_approval_keys_before_executable_use", ()),
        non_claims=payload.get("non_claims", ()),
    )


@dataclass(frozen=True)
class PVCapacityValueChoicePacket:
    """PI-facing D-014 capacity equation/value-choice packet that stays fail-closed."""

    packet_id: str
    data_id: str
    status: str
    download_performed: bool
    raw_data_committed: bool
    governing_decisions: Mapping[str, object]
    source_evidence_inputs: Mapping[str, object]
    candidate_operands_for_pi_review: Mapping[str, object]
    candidate_equations_for_local_2035_capacity: Sequence[Mapping[str, object]]
    scenario_consistency_issue: Mapping[str, object]
    capacity_convention_recommendation: Mapping[str, object]
    pi_recommendation: Mapping[str, object]
    pi_approval_keys_before_executable_use: Sequence[str]
    non_claims: Sequence[str]

    def __post_init__(self) -> None:
        if self.packet_id != "D014-PV-CAPACITY-VALUE-CHOICE-PACKET":
            raise ValueError("PV capacity value-choice packet must identify D014-PV-CAPACITY-VALUE-CHOICE-PACKET")
        if self.data_id != "D-014":
            raise ValueError("PV capacity value-choice packet must identify D-014")
        if self.status != "proposed_value_choice_packet_no_executable_values":
            raise ValueError("PV capacity value-choice packet must remain proposed and non-executable")
        if self.download_performed is not False or self.raw_data_committed is not False:
            raise ValueError("PV capacity value-choice packet must not claim new raw retrieval")
        governing = _audit_json_mapping(self.governing_decisions, "governing_decisions")
        evidence = _audit_json_mapping(self.source_evidence_inputs, "source_evidence_inputs")
        operands = _audit_json_mapping(self.candidate_operands_for_pi_review, "candidate_operands_for_pi_review")
        scenario = _audit_json_mapping(self.scenario_consistency_issue, "scenario_consistency_issue")
        convention = _audit_json_mapping(self.capacity_convention_recommendation, "capacity_convention_recommendation")
        recommendation = _audit_json_mapping(self.pi_recommendation, "pi_recommendation")
        equations = tuple(_audit_json_mapping(item, "capacity equation") for item in self.candidate_equations_for_local_2035_capacity)
        approval_keys = tuple(str(item) for item in self.pi_approval_keys_before_executable_use)
        non_claims = tuple(str(item) for item in self.non_claims)
        if governing.get("approved_route") != "PV-CAP-001":
            raise ValueError("capacity value-choice packet must be governed by PV-CAP-001")
        if "A-016" not in str(governing.get("scenario_consistency", "")):
            raise ValueError("capacity value-choice packet must preserve A-016 scenario consistency")
        if "PV-PARAM-001 remains proposed" not in str(governing.get("conversion_parameters", "")):
            raise ValueError("capacity value-choice packet must keep PV-PARAM-001 fail-closed")
        if "no roof/building/3DBAG/PV-map" not in str(governing.get("orientation_scope", "")):
            raise ValueError("capacity value-choice packet must preserve PV-ORIENT-001 scope")
        if evidence.get("cbs_anchor_packet_id") != "D014-CBS-PV-CAPACITY-ANCHOR-EVIDENCE":
            raise ValueError("capacity value-choice packet must cite CBS anchor evidence")
        if evidence.get("ii3050_growth_packet_id") != "D014-II3050-PV-GROWTH-EVIDENCE":
            raise ValueError("capacity value-choice packet must cite II3050 growth evidence")
        if len(str(evidence.get("cbs_raw_sha256", ""))) != 64 or len(str(evidence.get("ii3050_raw_sha256", ""))) != 64:
            raise ValueError("capacity value-choice packet must preserve source evidence checksums")
        cbs_operands = tuple(operands.get("cbs_alkmaar_capacity_operands", ()))
        if not cbs_operands:
            raise ValueError("capacity value-choice packet must list CBS operands")
        if not all(str(item.get("operand_status")) == "candidate_operand_unsigned_not_executable" for item in cbs_operands if isinstance(item, Mapping)):
            raise ValueError("CBS operands must remain unsigned")
        scenario_operands = tuple(operands.get("ii3050_2035_scenario_operands", ()))
        if {str(item.get("scenario")) for item in scenario_operands if isinstance(item, Mapping)} != {"KA", "ND", "IA"}:
            raise ValueError("capacity value-choice packet must list all II3050 2035 scenario operands")
        if not equations or not any(item.get("recommended_for_pi_review") is True for item in equations):
            raise ValueError("capacity value-choice packet must include one unsigned recommendation equation")
        if any(item.get("executable_status") == "approved" for item in equations):
            raise ValueError("capacity equations must not be approved")
        if scenario.get("decision_id") != "A-016" or "blocked_until_A016" not in str(scenario.get("executable_status", "")):
            raise ValueError("capacity value-choice packet must block on A-016 consistency")
        if convention.get("not_approved_by_this_packet") is not True:
            raise ValueError("capacity convention recommendation must remain unsigned")
        if recommendation.get("recommendation_status") != "proposed_unsigned_not_executable":
            raise ValueError("capacity recommendation must remain proposed and unsigned")
        required_keys = {
            "cbs_source_period_key",
            "cbs_sector_category_key",
            "cbs_capacity_field_key",
            "capacity_unit_and_dc_ac_convention",
            "ii3050_scenario_column",
            "ii3050_growth_denominator",
            "ii3050_growth_factor_formula",
            "ii3050_growth_factor_value",
            "scenario_source_consistency_with_ev_hp_inputs",
            "node_allocation_rule",
            "statistical_orientation_tilt_distribution_weights",
            "PV-PARAM-001_or_amended_conversion_decision",
        }
        missing = required_keys.difference(approval_keys)
        if missing:
            raise ValueError(f"capacity value-choice packet missing approval keys: {sorted(missing)}")
        if not any("No final PV capacity value" in item for item in non_claims):
            raise ValueError("capacity value-choice packet must state no final value is approved")
        if not any("No PV generation" in item for item in non_claims):
            raise ValueError("capacity value-choice packet must state no PV generation is produced")

        object.__setattr__(self, "governing_decisions", governing)
        object.__setattr__(self, "source_evidence_inputs", evidence)
        object.__setattr__(self, "candidate_operands_for_pi_review", operands)
        object.__setattr__(self, "candidate_equations_for_local_2035_capacity", equations)
        object.__setattr__(self, "scenario_consistency_issue", scenario)
        object.__setattr__(self, "capacity_convention_recommendation", convention)
        object.__setattr__(self, "pi_recommendation", recommendation)
        object.__setattr__(self, "pi_approval_keys_before_executable_use", approval_keys)
        object.__setattr__(self, "non_claims", non_claims)

    @property
    def missing_approval_keys(self) -> tuple[str, ...]:
        return self.pi_approval_keys_before_executable_use

    def require_executable_capacity_value_approval(self) -> None:
        """Always fail until a signed capacity-value artifact replaces this packet."""
        raise ValueError(
            "D-014 PV capacity value choices are unsigned; executable PV requires signed CBS operand, "
            "II3050 scenario/growth factor, capacity convention, A-016 consistency, allocation, and PV-PARAM approval"
        )

    def identity_record(self) -> dict[str, object]:
        return {
            "packet_id": self.packet_id,
            "data_id": self.data_id,
            "status": self.status,
            "cbs_anchor_packet_id": self.source_evidence_inputs["cbs_anchor_packet_id"],
            "ii3050_growth_packet_id": self.source_evidence_inputs["ii3050_growth_packet_id"],
            "primary_equation_id": self.pi_recommendation["primary_equation_id"],
            "primary_capacity_convention": self.pi_recommendation["primary_capacity_convention"],
            "missing_approval_keys": self.missing_approval_keys,
            "executable_capacity_value_approved": False,
        }


def load_pv_capacity_value_choice_packet(path: str | Path) -> PVCapacityValueChoicePacket:
    """Load the proposed D-014 PV capacity value-choice packet."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return PVCapacityValueChoicePacket(
        packet_id=str(payload.get("packet_id", "")),
        data_id=str(payload.get("data_id", "")),
        status=str(payload.get("status", "")),
        download_performed=bool(payload.get("download_performed")),
        raw_data_committed=bool(payload.get("raw_data_committed")),
        governing_decisions=payload.get("governing_decisions", {}),
        source_evidence_inputs=payload.get("source_evidence_inputs", {}),
        candidate_operands_for_pi_review=payload.get("candidate_operands_for_pi_review", {}),
        candidate_equations_for_local_2035_capacity=payload.get("candidate_equations_for_local_2035_capacity", ()),
        scenario_consistency_issue=payload.get("scenario_consistency_issue", {}),
        capacity_convention_recommendation=payload.get("capacity_convention_recommendation", {}),
        pi_recommendation=payload.get("pi_recommendation", {}),
        pi_approval_keys_before_executable_use=payload.get("pi_approval_keys_before_executable_use", ()),
        non_claims=payload.get("non_claims", ()),
    )


@dataclass(frozen=True)
class PVCapacityApprovalTemplatePacket:
    """Unsigned D-014 template for a future PI-signed executable PV capacity artifact."""

    packet_id: str
    data_id: str
    status: str
    download_performed: bool
    raw_data_committed: bool
    upstream_value_choice_packet: Mapping[str, object]
    approved_route_boundary: Mapping[str, object]
    required_signed_artifact_fields: Mapping[str, object]
    executable_gate: Mapping[str, object]
    recommended_pi_path: Mapping[str, object]
    non_claims: Sequence[str]

    def __post_init__(self) -> None:
        if self.packet_id != "D014-PV-CAPACITY-APPROVAL-TEMPLATE":
            raise ValueError("PV capacity approval template must identify D014-PV-CAPACITY-APPROVAL-TEMPLATE")
        if self.data_id != "D-014":
            raise ValueError("PV capacity approval template must identify D-014")
        if self.status != "proposed_signed_capacity_artifact_template_no_values":
            raise ValueError("PV capacity approval template must remain proposed and value-free")
        if self.download_performed is not False or self.raw_data_committed is not False:
            raise ValueError("PV capacity approval template must not claim retrieval or raw committed data")
        upstream = _audit_json_mapping(self.upstream_value_choice_packet, "upstream_value_choice_packet")
        boundary = _audit_json_mapping(self.approved_route_boundary, "approved_route_boundary")
        required = _audit_json_mapping(self.required_signed_artifact_fields, "required_signed_artifact_fields")
        gate = _audit_json_mapping(self.executable_gate, "executable_gate")
        recommendation = _audit_json_mapping(self.recommended_pi_path, "recommended_pi_path")
        non_claims = tuple(str(item) for item in self.non_claims)

        if upstream.get("packet_id") != "D014-PV-CAPACITY-VALUE-CHOICE-PACKET":
            raise ValueError("capacity approval template must derive from the value-choice packet")
        if len(str(upstream.get("metadata_sha256", ""))) != 64:
            raise ValueError("capacity approval template must record the value-choice metadata SHA-256")
        if upstream.get("recommendation_status") != "proposed_unsigned_not_executable":
            raise ValueError("capacity approval template must preserve unsigned upstream recommendation status")
        if boundary.get("capacity_route_decision") != "PV-CAP-001":
            raise ValueError("capacity approval template must be governed by PV-CAP-001")
        if boundary.get("scenario_consistency_decision") != "A-016":
            raise ValueError("capacity approval template must preserve A-016 scenario consistency")
        if boundary.get("orientation_scope_decision") != "PV-ORIENT-001":
            raise ValueError("capacity approval template must preserve PV-ORIENT-001")
        if "no building/roof/3DBAG/PV-map" not in str(boundary.get("orientation_scope_boundary", "")):
            raise ValueError("capacity approval template must not reopen building-level PV geometry")

        field_groups = {str(key): tuple(str(item) for item in value) for key, value in required.items()}
        required_groups = {
            "artifact_identity",
            "capacity_value",
            "cbs_anchor_operand",
            "ii3050_growth_operand",
            "a016_scenario_consistency",
            "allocation_and_conversion_dependencies",
            "audit_outputs",
        }
        missing_groups = required_groups.difference(field_groups)
        if missing_groups:
            raise ValueError(f"capacity approval template missing field groups: {sorted(missing_groups)}")
        required_fields = {
            "installed_capacity_value",
            "installed_capacity_unit",
            "capacity_convention",
            "cbs_source_period_key",
            "cbs_sector_category_key",
            "cbs_capacity_field_key",
            "ii3050_scenario_column",
            "ii3050_growth_factor_value",
            "scenario_consistency_mapping_id",
            "node_allocation_rule_id",
            "statistical_orientation_tilt_distribution_id",
            "pv_param_decision_id",
            "content_sha256",
        }
        flattened = {item for values in field_groups.values() for item in values}
        missing_fields = required_fields.difference(flattened)
        if missing_fields:
            raise ValueError(f"capacity approval template missing signed fields: {sorted(missing_fields)}")

        if gate.get("accepted_for_executable_pv_capacity_input") is not False:
            raise ValueError("unsigned capacity approval template must not allow executable capacity input")
        if gate.get("signed_capacity_value_approved") is not False:
            raise ValueError("capacity approval template must keep signed capacity approval false")
        if gate.get("requires_pi_signed_decision") is not True:
            raise ValueError("capacity approval template must require a PI-signed decision")
        blocking = tuple(str(item) for item in gate.get("blocking_approval_keys", ()))
        for required_key in (
            "ii3050_growth_factor_value",
            "scenario_source_consistency_with_ev_hp_inputs",
            "node_allocation_rule",
            "PV-PARAM-001_or_amended_conversion_decision",
        ):
            if required_key not in blocking:
                raise ValueError(f"capacity approval template missing blocking key {required_key}")
        if recommendation.get("not_approved_by_this_template") is not True:
            raise ValueError("capacity approval template recommendation must remain unsigned")
        if not any("No final PV installed-capacity value" in item for item in non_claims):
            raise ValueError("capacity approval template must state that no final capacity is approved")
        if not any("No PV generation" in item for item in non_claims):
            raise ValueError("capacity approval template must state that no PV generation is produced")

        object.__setattr__(self, "upstream_value_choice_packet", upstream)
        object.__setattr__(self, "approved_route_boundary", boundary)
        object.__setattr__(self, "required_signed_artifact_fields", MappingProxyType(field_groups))
        object.__setattr__(self, "executable_gate", gate)
        object.__setattr__(self, "recommended_pi_path", recommendation)
        object.__setattr__(self, "non_claims", non_claims)

    @property
    def missing_approval_keys(self) -> tuple[str, ...]:
        return tuple(str(item) for item in self.executable_gate["blocking_approval_keys"])

    def require_signed_capacity_artifact(self) -> None:
        """Always fail until a later PI-signed capacity artifact replaces this template."""
        raise ValueError(
            "D-014 PV capacity approval template is unsigned; executable PV requires a signed capacity "
            "artifact with CBS row, II3050 growth factor, scenario consistency, allocation, and PV-PARAM approvals"
        )

    def identity_record(self) -> dict[str, object]:
        return {
            "packet_id": self.packet_id,
            "data_id": self.data_id,
            "status": self.status,
            "upstream_value_choice_packet_id": self.upstream_value_choice_packet["packet_id"],
            "upstream_value_choice_sha256": self.upstream_value_choice_packet["metadata_sha256"],
            "capacity_route_decision": self.approved_route_boundary["capacity_route_decision"],
            "scenario_consistency_decision": self.approved_route_boundary["scenario_consistency_decision"],
            "orientation_scope_decision": self.approved_route_boundary["orientation_scope_decision"],
            "recommended_equation_id_for_review": self.recommended_pi_path["recommended_equation_id_for_review"],
            "recommended_capacity_label_before_pv_param": self.recommended_pi_path[
                "recommended_capacity_label_before_pv_param"
            ],
            "missing_approval_keys": self.missing_approval_keys,
            "executable_capacity_value_approved": False,
        }


def load_pv_capacity_approval_template_packet(path: str | Path) -> PVCapacityApprovalTemplatePacket:
    """Load the unsigned D-014 PV capacity approval-template packet."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return PVCapacityApprovalTemplatePacket(
        packet_id=str(payload.get("packet_id", "")),
        data_id=str(payload.get("data_id", "")),
        status=str(payload.get("status", "")),
        download_performed=bool(payload.get("download_performed")),
        raw_data_committed=bool(payload.get("raw_data_committed")),
        upstream_value_choice_packet=payload.get("upstream_value_choice_packet", {}),
        approved_route_boundary=payload.get("approved_route_boundary", {}),
        required_signed_artifact_fields=payload.get("required_signed_artifact_fields", {}),
        executable_gate=payload.get("executable_gate", {}),
        recommended_pi_path=payload.get("recommended_pi_path", {}),
        non_claims=payload.get("non_claims", ()),
    )


@dataclass(frozen=True)
class PVExecutableReadinessBlockersPacket:
    """Fail-closed D-014 manifest of blockers before executable first-experiment PV generation."""

    packet_id: str
    data_id: str
    status: str
    download_performed: bool
    raw_data_committed: bool
    input_metadata: Mapping[str, object]
    readiness_layers: Mapping[str, object]
    executable_gate: Mapping[str, object]
    non_claims: Sequence[str]

    def __post_init__(self) -> None:
        if self.packet_id != "D014-PV-EXECUTABLE-READINESS-BLOCKERS":
            raise ValueError("PV executable readiness blockers packet must identify D014-PV-EXECUTABLE-READINESS-BLOCKERS")
        if self.data_id != "D-014":
            raise ValueError("PV executable readiness blockers packet must identify D-014")
        if self.status != "proposed_fail_closed_executable_pv_readiness_blockers":
            raise ValueError("PV executable readiness blockers packet must remain proposed/fail-closed")
        if self.download_performed is not False or self.raw_data_committed is not False:
            raise ValueError("PV executable readiness blockers packet must not claim retrieval or raw committed data")
        inputs = _audit_json_mapping(self.input_metadata, "input_metadata")
        layers = _audit_json_mapping(self.readiness_layers, "readiness_layers")
        gate = _audit_json_mapping(self.executable_gate, "executable_gate")
        non_claims = tuple(str(item) for item in self.non_claims)
        expected_inputs = {
            "weather_input_artifact",
            "capacity_approval_template",
            "orientation_tilt_value_choice",
            "pv_parameter_packet",
        }
        missing_inputs = expected_inputs.difference(inputs)
        if missing_inputs:
            raise ValueError(f"PV executable blockers packet missing inputs: {sorted(missing_inputs)}")
        input_packets = {
            key: str(_audit_json_mapping(value, key).get("packet_id", ""))
            for key, value in inputs.items()
        }
        if input_packets["capacity_approval_template"] != "D014-PV-CAPACITY-APPROVAL-TEMPLATE":
            raise ValueError("PV executable blockers packet must consume the D-014 capacity approval template")
        if input_packets["orientation_tilt_value_choice"] != "D014-PV-ORIENTATION-TILT-VALUE-CHOICE-PACKET":
            raise ValueError("PV executable blockers packet must consume the orientation/tilt value-choice packet")
        for key, value in inputs.items():
            record = _audit_json_mapping(value, key)
            if len(str(record.get("sha256", ""))) != 64:
                raise ValueError(f"PV executable blockers packet input {key} must record SHA-256")

        required_layers = {
            "weather_source_member",
            "capacity_value",
            "scenario_consistency",
            "orientation_tilt_distribution",
            "pv_conversion_parameters",
            "node_allocation",
            "final_paired_hp_pv_and_cold_spell_acceptance",
        }
        missing_layers = required_layers.difference(layers)
        if missing_layers:
            raise ValueError(f"PV executable blockers packet missing readiness layers: {sorted(missing_layers)}")
        if _audit_json_mapping(layers["weather_source_member"], "weather_source_member").get(
            "component_source_member_ready"
        ) is not True:
            raise ValueError("PV executable blockers packet must preserve accepted source/member weather readiness")
        for key in required_layers - {"weather_source_member"}:
            if _audit_json_mapping(layers[key], key).get("ready") is not False:
                raise ValueError(f"PV executable blockers packet layer {key} must remain blocked")
        if gate.get("executable_pv_generation_authorized") is not False:
            raise ValueError("PV executable blockers packet must not authorize PV generation")
        blockers = tuple(str(item) for item in gate.get("blocking_register_ids", ()))
        for blocker in ("D014-PV-CAPACITY-APPROVAL-TEMPLATE", "A-016", "PV-ORIENT-001", "PV-PARAM-001"):
            if blocker not in blockers:
                raise ValueError(f"PV executable blockers packet missing blocker {blocker}")
        if not any("No final PV capacity value" in item for item in non_claims):
            raise ValueError("PV executable blockers packet must state that no PV values are approved")
        if not any("No PV generation" in item for item in non_claims):
            raise ValueError("PV executable blockers packet must state that no PV generation is produced")
        if not any("No roof, building, 3DBAG" in item for item in non_claims):
            raise ValueError("PV executable blockers packet must preserve PV-ORIENT-001 geometry boundary")
        object.__setattr__(self, "input_metadata", inputs)
        object.__setattr__(self, "readiness_layers", layers)
        object.__setattr__(self, "executable_gate", gate)
        object.__setattr__(self, "non_claims", non_claims)

    @property
    def blocking_register_ids(self) -> tuple[str, ...]:
        return tuple(str(item) for item in self.executable_gate["blocking_register_ids"])

    def require_executable_pv_generation_authorization(self) -> None:
        """Always fail until all PV capacity, parameter, allocation, and pairing gates are signed."""
        raise ValueError(
            "PV executable readiness blockers remain unresolved; generation requires signed capacity, "
            "A-016 scenario consistency, PV-ORIENT, PV-PARAM, allocation, and paired acceptance gates"
        )

    def identity_record(self) -> dict[str, object]:
        return {
            "packet_id": self.packet_id,
            "data_id": self.data_id,
            "status": self.status,
            "component_source_member_artifact_available": self.executable_gate[
                "component_source_member_artifact_available"
            ],
            "executable_pv_generation_authorized": False,
            "blocking_register_ids": self.blocking_register_ids,
            "input_packet_ids": {
                key: _audit_json_mapping(value, key).get("packet_id") for key, value in self.input_metadata.items()
            },
        }


def load_pv_executable_readiness_blockers_packet(path: str | Path) -> PVExecutableReadinessBlockersPacket:
    """Load the fail-closed executable PV readiness-blocker packet."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return PVExecutableReadinessBlockersPacket(
        packet_id=str(payload.get("packet_id", "")),
        data_id=str(payload.get("data_id", "")),
        status=str(payload.get("status", "")),
        download_performed=bool(payload.get("download_performed")),
        raw_data_committed=bool(payload.get("raw_data_committed")),
        input_metadata=payload.get("input_metadata", {}),
        readiness_layers=payload.get("readiness_layers", {}),
        executable_gate=payload.get("executable_gate", {}),
        non_claims=payload.get("non_claims", ()),
    )


@dataclass(frozen=True)
class PVExecutablePreflightGuardPacket:
    """Fail-closed preflight result for attempts to request executable PV generation."""

    packet_id: str
    data_id: str
    status: str
    download_performed: bool
    raw_data_committed: bool
    input_blocker_manifest: Mapping[str, object]
    preflight_checks: Mapping[str, object]
    token_policy: Mapping[str, object]
    executable_gate: Mapping[str, object]
    non_claims: Sequence[str]

    def __post_init__(self) -> None:
        if self.packet_id != "D014-PV-EXECUTABLE-PREFLIGHT-GUARD":
            raise ValueError("PV executable preflight guard must identify D014-PV-EXECUTABLE-PREFLIGHT-GUARD")
        if self.data_id != "D-014":
            raise ValueError("PV executable preflight guard must identify D-014")
        if self.status != "proposed_fail_closed_preflight_no_generation":
            raise ValueError("PV executable preflight guard must remain proposed/fail-closed")
        if self.download_performed is not False or self.raw_data_committed is not False:
            raise ValueError("PV executable preflight guard must not claim retrieval or raw committed data")
        blocker = _audit_json_mapping(self.input_blocker_manifest, "input_blocker_manifest")
        checks = _audit_json_mapping(self.preflight_checks, "preflight_checks")
        token_policy = _audit_json_mapping(self.token_policy, "token_policy")
        gate = _audit_json_mapping(self.executable_gate, "executable_gate")
        non_claims = tuple(str(item) for item in self.non_claims)
        if blocker.get("packet_id") != "D014-PV-EXECUTABLE-READINESS-BLOCKERS":
            raise ValueError("PV executable preflight guard must consume the readiness-blocker manifest")
        if len(str(blocker.get("metadata_sha256", ""))) != 64:
            raise ValueError("PV executable preflight guard must record the blocker manifest SHA-256")
        if checks.get("component_source_member_artifact_available") is not True:
            raise ValueError("PV executable preflight guard must preserve weather source/member readiness")
        if checks.get("executable_pv_generation_authorized") is not False:
            raise ValueError("PV executable preflight guard must keep executable generation unauthorized")
        if checks.get("all_required_blockers_present") is not True:
            raise ValueError("PV executable preflight guard must record all required blockers")
        unsafe_tokens = tuple(str(item) for item in token_policy.get("unsafe_tokens_for_executable_outputs", ()))
        for token in ("TODO", "TBD", "placeholder", "synthetic", "proposed", "unsigned", "not-approved"):
            if token not in unsafe_tokens:
                raise ValueError(f"PV executable preflight guard missing unsafe token policy entry {token}")
        if token_policy.get("policy_result") != "blocked_metadata_only_no_executable_output":
            raise ValueError("PV executable preflight guard must produce only a blocked metadata result")
        if gate.get("preflight_ready_for_executable_pv_generation") is not False:
            raise ValueError("PV executable preflight guard must not pass executable preflight")
        if gate.get("result_if_invoked") != "abort_with_blocker_manifest":
            raise ValueError("PV executable preflight guard must abort with the blocker manifest")
        blockers = tuple(str(item) for item in gate.get("blocking_register_ids", ()))
        for blocker_id in ("D014-PV-CAPACITY-APPROVAL-TEMPLATE", "A-016", "PV-ORIENT-001", "PV-PARAM-001"):
            if blocker_id not in blockers:
                raise ValueError(f"PV executable preflight guard missing blocker {blocker_id}")
        if not any("No executable PV preflight passes" in item for item in non_claims):
            raise ValueError("PV executable preflight guard must state that no executable preflight passes")
        if not any("No PV generation" in item for item in non_claims):
            raise ValueError("PV executable preflight guard must state that no PV generation is produced")

        object.__setattr__(self, "input_blocker_manifest", blocker)
        object.__setattr__(self, "preflight_checks", checks)
        object.__setattr__(self, "token_policy", token_policy)
        object.__setattr__(self, "executable_gate", gate)
        object.__setattr__(self, "non_claims", non_claims)

    @property
    def blocking_register_ids(self) -> tuple[str, ...]:
        return tuple(str(item) for item in self.executable_gate["blocking_register_ids"])

    def require_executable_preflight_passed(self) -> None:
        """Always fail while the preflight packet represents unresolved blockers."""
        raise ValueError(
            "PV executable preflight did not pass; unresolved D-014/PV-PARAM/PV-ORIENT/A-016/"
            "allocation/paired-weather blockers must be signed before PV generation"
        )

    def identity_record(self) -> dict[str, object]:
        return {
            "packet_id": self.packet_id,
            "data_id": self.data_id,
            "status": self.status,
            "input_blocker_packet_id": self.input_blocker_manifest["packet_id"],
            "input_blocker_sha256": self.input_blocker_manifest["metadata_sha256"],
            "preflight_ready_for_executable_pv_generation": False,
            "result_if_invoked": self.executable_gate["result_if_invoked"],
            "blocking_register_ids": self.blocking_register_ids,
        }


def load_pv_executable_preflight_guard_packet(path: str | Path) -> PVExecutablePreflightGuardPacket:
    """Load the fail-closed executable PV preflight guard packet."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return PVExecutablePreflightGuardPacket(
        packet_id=str(payload.get("packet_id", "")),
        data_id=str(payload.get("data_id", "")),
        status=str(payload.get("status", "")),
        download_performed=bool(payload.get("download_performed")),
        raw_data_committed=bool(payload.get("raw_data_committed")),
        input_blocker_manifest=payload.get("input_blocker_manifest", {}),
        preflight_checks=payload.get("preflight_checks", {}),
        token_policy=payload.get("token_policy", {}),
        executable_gate=payload.get("executable_gate", {}),
        non_claims=payload.get("non_claims", ()),
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
class PVParamConversionSourceChoicePacket:
    """Proposed PV-PARAM conversion route choices that remain fail-closed."""

    packet_id: str
    data_id: str
    status: str
    download_performed: bool
    raw_data_committed: bool
    governing_decisions: Mapping[str, object]
    input_dependencies: Mapping[str, object]
    conversion_source_candidates: Sequence[Mapping[str, object]]
    recommendation_for_pi_review: Mapping[str, object]
    executable_gate: Mapping[str, object]
    pi_approval_keys_before_executable_use: Sequence[str]
    non_claims: Sequence[str]

    def __post_init__(self) -> None:
        if self.packet_id != "D014-PV-PARAM-CONVERSION-SOURCE-CHOICE-PACKET":
            raise ValueError("PV-PARAM conversion source-choice packet must identify D014-PV-PARAM-CONVERSION-SOURCE-CHOICE-PACKET")
        if self.data_id != "D-014":
            raise ValueError("PV-PARAM conversion source-choice packet must identify D-014")
        if not str(self.status).startswith("proposed_"):
            raise ValueError("PV-PARAM conversion source-choice packet must remain proposed until PI approval")
        if self.download_performed is not False or self.raw_data_committed is not False:
            raise ValueError("PV-PARAM conversion source-choice packet must not claim raw retrieval or committed raw data")
        governing = _audit_json_mapping(self.governing_decisions, "governing_decisions")
        dependencies = _audit_json_mapping(self.input_dependencies, "input_dependencies")
        recommendation = _audit_json_mapping(self.recommendation_for_pi_review, "recommendation_for_pi_review")
        gate = _audit_json_mapping(self.executable_gate, "executable_gate")
        candidates = tuple(_audit_json_mapping(item, "conversion_source_candidate") for item in self.conversion_source_candidates)
        approval_keys = tuple(str(item) for item in self.pi_approval_keys_before_executable_use)
        non_claims = tuple(str(item) for item in self.non_claims)

        if "PV-PARAM-001 remains proposed" not in str(governing.get("pv_param_decision_status", "")):
            raise ValueError("PV-PARAM conversion source-choice packet must keep PV-PARAM-001 proposed")
        if "PV-ORIENT-001 statistical" not in str(governing.get("orientation_scope", "")):
            raise ValueError("PV-PARAM conversion source-choice packet must preserve PV-ORIENT-001 statistical scope")
        if "no building/roof/3DBAG/PV-map" not in str(governing.get("orientation_scope", "")):
            raise ValueError("PV-PARAM conversion source-choice packet must defer heavy roof/building geometry")
        if "PV-CAP-001/D-014 capacity remains separate" not in str(governing.get("capacity_route", "")):
            raise ValueError("PV-PARAM conversion source-choice packet must keep capacity separate")
        if "PVGIS remains qualitative" not in str(governing.get("weather_basis", "")):
            raise ValueError("PV-PARAM conversion source-choice packet must preserve the PVGIS boundary")
        if "D014-PV-ORIENTATION-TILT-VALUE-CHOICE-PACKET" not in str(dependencies.get("orientation_tilt_values", "")):
            raise ValueError("PV-PARAM conversion source-choice packet must depend on signed orientation/tilt values")
        if gate.get("executable_allowed_now") is not False:
            raise ValueError("PV-PARAM conversion source-choice packet must not allow executable conversion")
        if gate.get("result_if_invoked") != "abort_until_signed_pv_param_conversion_choice":
            raise ValueError("PV-PARAM conversion source-choice packet must abort until signed")
        blocker_ids = tuple(str(item) for item in gate.get("blocking_register_ids", ()))
        for blocker in ("PV-PARAM-001_or_signed_amendment", "PV-ORIENT-001_values", "A-016"):
            if blocker not in blocker_ids:
                raise ValueError(f"PV-PARAM conversion source-choice packet missing blocker {blocker}")
        candidate_ids = {str(item.get("candidate_id")) for item in candidates}
        required_candidates = {
            "pvlib_statistical_orientation_tilt_poa_candidate",
            "pvgis_reference_calibration_sanity_candidate",
            "direct_ghi_pr_scalar_candidate",
        }
        missing_candidates = required_candidates.difference(candidate_ids)
        if missing_candidates:
            raise ValueError(f"PV-PARAM conversion source-choice packet missing candidates: {sorted(missing_candidates)}")
        for candidate in candidates:
            status = str(candidate.get("candidate_status", ""))
            if "unsigned" not in status or "not_executable" not in status:
                raise ValueError("PV-PARAM conversion candidates must remain unsigned and not executable")
        required_keys = {
            "pv_param_decision_id_or_signed_amendment",
            "conversion_formula_id",
            "orientation_tilt_value_packet_id",
            "transposition_model_or_direct_ghi_simplification",
            "performance_ratio_or_loss_model_source",
            "temperature_model_and_coefficients",
            "clipping_rule_and_capacity_convention",
            "d014_capacity_approval_artifact",
            "a016_scenario_consistency_mapping",
        }
        missing_keys = required_keys.difference(approval_keys)
        if missing_keys:
            raise ValueError(f"PV-PARAM conversion source-choice packet missing approval keys: {sorted(missing_keys)}")
        if recommendation.get("do_not_use_as_final_without_signature") is not True:
            raise ValueError("PV-PARAM conversion source-choice packet must not allow final use without signature")
        if not any("No PV conversion formula is approved" in item for item in non_claims):
            raise ValueError("PV-PARAM conversion source-choice packet must state no formula is approved")
        if not any("No PR=0.86" in item and "signed" in item for item in non_claims):
            raise ValueError("PV-PARAM conversion source-choice packet must keep PR/direct-GHI unsigned")
        if not any("No roof, building, 3DBAG" in item for item in non_claims):
            raise ValueError("PV-PARAM conversion source-choice packet must defer heavy geometry")

        object.__setattr__(self, "governing_decisions", governing)
        object.__setattr__(self, "input_dependencies", dependencies)
        object.__setattr__(self, "conversion_source_candidates", candidates)
        object.__setattr__(self, "recommendation_for_pi_review", recommendation)
        object.__setattr__(self, "executable_gate", gate)
        object.__setattr__(self, "pi_approval_keys_before_executable_use", approval_keys)
        object.__setattr__(self, "non_claims", non_claims)

    @property
    def missing_approval_keys(self) -> tuple[str, ...]:
        return self.pi_approval_keys_before_executable_use

    def require_executable_conversion_approval(self) -> None:
        """Always fail until the PI signs a PV-PARAM conversion route."""
        raise ValueError(
            "PV-PARAM conversion source choice is unsigned; executable PV requires signed conversion formula, "
            "orientation/tilt values, capacity artifact, scenario consistency, and allocation"
        )

    def identity_record(self) -> dict[str, object]:
        return {
            "packet_id": self.packet_id,
            "data_id": self.data_id,
            "status": self.status,
            "candidate_ids": tuple(str(item["candidate_id"]) for item in self.conversion_source_candidates),
            "blocking_register_ids": tuple(str(item) for item in self.executable_gate["blocking_register_ids"]),
            "missing_approval_keys": self.missing_approval_keys,
            "executable_allowed_now": False,
        }


def load_pv_param_conversion_source_choice_packet(path: str | Path) -> PVParamConversionSourceChoicePacket:
    """Load the proposed D-014 PV-PARAM conversion source-choice packet."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return PVParamConversionSourceChoicePacket(
        packet_id=str(payload.get("packet_id", "")),
        data_id=str(payload.get("data_id", "")),
        status=str(payload.get("status", "")),
        download_performed=bool(payload.get("download_performed")),
        raw_data_committed=bool(payload.get("raw_data_committed")),
        governing_decisions=payload.get("governing_decisions", {}),
        input_dependencies=payload.get("input_dependencies", {}),
        conversion_source_candidates=payload.get("conversion_source_candidates", ()),
        recommendation_for_pi_review=payload.get("recommendation_for_pi_review", {}),
        executable_gate=payload.get("executable_gate", {}),
        pi_approval_keys_before_executable_use=payload.get("pi_approval_keys_before_executable_use", ()),
        non_claims=payload.get("non_claims", ()),
    )



@dataclass(frozen=True)
class PVFirstExperimentApprovalPacket:
    """Fail-closed PI decision packet for first-experiment PV readiness."""

    packet_id: str
    data_id: str
    status: str
    download_performed: bool
    raw_data_committed: bool
    input_metadata: Mapping[str, object]
    first_experiment_scope: Mapping[str, object]
    separated_decision_layers: Mapping[str, object]
    pi_approval_keys_before_executable_use: Sequence[str]
    executable_gate: Mapping[str, object]
    non_claims: Sequence[str]

    def __post_init__(self) -> None:
        if self.packet_id != "D014-PV-FIRST-EXPERIMENT-APPROVAL-PACKET":
            raise ValueError("first-experiment PV approval packet must identify D014-PV-FIRST-EXPERIMENT-APPROVAL-PACKET")
        if self.data_id != "D-014":
            raise ValueError("first-experiment PV approval packet must identify D-014")
        if not str(self.status).startswith("proposed_"):
            raise ValueError("first-experiment PV approval packet must remain proposed until PI approval")
        if self.download_performed is not False or self.raw_data_committed is not False:
            raise ValueError("first-experiment PV approval packet must not claim raw retrieval or committed raw data")
        inputs = _audit_json_mapping(self.input_metadata, "input_metadata")
        scope = _audit_json_mapping(self.first_experiment_scope, "first_experiment_scope")
        layers = _audit_json_mapping(self.separated_decision_layers, "separated_decision_layers")
        gate = _audit_json_mapping(self.executable_gate, "executable_gate")
        approval_keys = tuple(str(item) for item in self.pi_approval_keys_before_executable_use)
        non_claims = tuple(str(item) for item in self.non_claims)

        required_inputs = {
            "capacity_approval_template": "D014-PV-CAPACITY-APPROVAL-TEMPLATE",
            "orientation_tilt_source_choice": "D014-PV-ORIENTATION-TILT-SOURCE-CHOICE-PACKET",
            "orientation_tilt_value_choice": "D014-PV-ORIENTATION-TILT-VALUE-CHOICE-PACKET",
            "pv_param_conversion_source_choice": "D014-PV-PARAM-CONVERSION-SOURCE-CHOICE-PACKET",
            "executable_preflight_guard": "D014-PV-EXECUTABLE-PREFLIGHT-GUARD",
        }
        for key, packet_id in required_inputs.items():
            record = _audit_json_mapping(inputs.get(key, {}), f"input_metadata.{key}")
            if record.get("packet_id") != packet_id:
                raise ValueError(f"first-experiment PV approval packet input {key} must reference {packet_id}")
            if len(str(record.get("sha256", ""))) != 64:
                raise ValueError(f"first-experiment PV approval packet input {key} must record SHA-256")
        if scope.get("building_roof_location_level_geometry_allowed") is not False:
            raise ValueError("first-experiment PV approval packet must block roof/building/location geometry")
        if scope.get("specific_3dbag_or_pv_map_workflow_allowed") is not False:
            raise ValueError("first-experiment PV approval packet must block 3DBAG/PV-map workflow")
        required_layers = {
            "installed_capacity_route",
            "orientation_tilt_distribution",
            "irradiance_to_power_conversion",
            "node_allocation",
        }
        missing_layers = required_layers.difference(layers)
        if missing_layers:
            raise ValueError(f"first-experiment PV approval packet missing separated layers: {sorted(missing_layers)}")
        if gate.get("executable_pv_generation_authorized") is not False:
            raise ValueError("first-experiment PV approval packet must not authorize executable PV generation")
        blockers = tuple(str(item) for item in gate.get("blocking_register_ids", ()))
        for blocker in ("PV-PARAM-001_or_signed_amendment", "PV-ORIENT-001_values", "A-016"):
            if blocker not in blockers:
                raise ValueError(f"first-experiment PV approval packet missing blocker {blocker}")
        required_keys = {
            "signed_d014_capacity_artifact",
            "signed_statistical_orientation_tilt_bins_representative_angles_and_weights",
            "signed_pv_param_conversion_formula_or_amendment",
            "signed_node_allocation_rule",
            "signed_final_paired_hp_pv_acceptance_prerequisite",
        }
        missing_keys = required_keys.difference(approval_keys)
        if missing_keys:
            raise ValueError(f"first-experiment PV approval packet missing approval keys: {sorted(missing_keys)}")
        if not any("No PV capacity value" in item and "orientation/tilt" in item for item in non_claims):
            raise ValueError("first-experiment PV approval packet must state no values are approved")
        if not any("No building, roof" in item for item in non_claims):
            raise ValueError("first-experiment PV approval packet must defer heavy geometry")

        object.__setattr__(self, "input_metadata", inputs)
        object.__setattr__(self, "first_experiment_scope", scope)
        object.__setattr__(self, "separated_decision_layers", layers)
        object.__setattr__(self, "pi_approval_keys_before_executable_use", approval_keys)
        object.__setattr__(self, "executable_gate", gate)
        object.__setattr__(self, "non_claims", non_claims)

    @property
    def missing_approval_keys(self) -> tuple[str, ...]:
        return self.pi_approval_keys_before_executable_use

    def require_executable_first_experiment_pv_approval(self) -> None:
        """Always fail until all first-experiment PV approvals are signed."""
        raise ValueError(
            "First-experiment PV approval packet is unsigned; executable PV requires signed capacity, "
            "statistical orientation/tilt values, PV-PARAM conversion, A-016 mapping, allocation, and paired acceptance"
        )

    def identity_record(self) -> dict[str, object]:
        return {
            "packet_id": self.packet_id,
            "data_id": self.data_id,
            "status": self.status,
            "input_packet_ids": {
                key: _audit_json_mapping(value, f"input_metadata.{key}")["packet_id"]
                for key, value in self.input_metadata.items()
            },
            "blocking_register_ids": tuple(str(item) for item in self.executable_gate["blocking_register_ids"]),
            "missing_approval_keys": self.missing_approval_keys,
            "executable_pv_generation_authorized": False,
        }


def load_pv_first_experiment_approval_packet(path: str | Path) -> PVFirstExperimentApprovalPacket:
    """Load the proposed first-experiment PV approval packet."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return PVFirstExperimentApprovalPacket(
        packet_id=str(payload.get("packet_id", "")),
        data_id=str(payload.get("data_id", "")),
        status=str(payload.get("status", "")),
        download_performed=bool(payload.get("download_performed")),
        raw_data_committed=bool(payload.get("raw_data_committed")),
        input_metadata=payload.get("input_metadata", {}),
        first_experiment_scope=payload.get("first_experiment_scope", {}),
        separated_decision_layers=payload.get("separated_decision_layers", {}),
        pi_approval_keys_before_executable_use=payload.get("pi_approval_keys_before_executable_use", ()),
        executable_gate=payload.get("executable_gate", {}),
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
