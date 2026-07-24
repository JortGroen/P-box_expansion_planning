from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import io
import json
from pathlib import Path
import sys
from typing import Any, Sequence
from urllib import parse, request
import zipfile

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.sources import write_metadata

DATA_ID = "D-013"
BUNDLE_ID = "hp001_alkmaar_gm0361_source_route_v1"
MUNICIPALITY_CODE = "GM0361"
MUNICIPALITY_NAME = "Alkmaar"
CHECKPOINT_FILENAME = "hp001_alkmaar_gm0361_retrieval_checkpoint.json"
RETRIEVAL_MANIFEST_FILENAME = "hp001_alkmaar_gm0361_retrieval_manifest.json"
FORMULA_DECISION_PACKET_FILENAME = "hp001_alkmaar_gm0361_scaling_formula_config_decision_packet.json"
VALUE_BINDING_READINESS_FILENAME = "hp001_alkmaar_gm0361_value_binding_readiness_packet.json"
READINESS_APPROVAL_CHECKLIST_FILENAME = "hp001_alkmaar_gm0361_readiness_approval_checklist.json"
EXECUTABLE_VALUE_BINDING_DECISION_PACKET_FILENAME = "hp001_alkmaar_gm0361_executable_value_binding_decision_packet.json"
COMPONENT_OUTPUT_READINESS_BLOCKER_FILENAME = "hp001_component_output_readiness_blocker_packet.json"
DOWNLOAD_TIMEOUT_S = 120.0
PBL_HEAT_TERMS = ("warmte", "heat", "gas", "energie", "energy", "verbruik", "demand", "vraag")
PBL_DHW_TERMS = ("tapwater", "warm_water", "dhw", "water")
PBL_SFH_COLUMNS = ("Vrijstaande_woning", "2_onder_1_kap", "Rijwoning_hoek", "Rijwoning_tussen")
PBL_MFH_COLUMNS = ("Meersgezinswoning_laag_midden", "Meersgezinswoning_hoog")


@dataclass(frozen=True)
class HpScalingSourceSpec:
    key: str
    title: str
    source: str
    url: str
    license_or_terms: str
    planned_raw_path: str
    planned_metadata_path: str
    expected_size_note: str
    expected_runtime_note: str
    role: str
    proposed_fields_or_filters: tuple[str, ...]
    boundary: str


HP_SCALING_SOURCES: tuple[HpScalingSourceSpec, ...] = (
    HpScalingSourceSpec(
        key="cbs_85035ned_dwelling_stock",
        title="CBS StatLine 85035NED dwelling stock by type and region",
        source="CBS StatLine",
        url="https://opendata.cbs.nl/ODataApi/OData/85035NED",
        license_or_terms="CBS open data terms; cite CBS table page and retrieval timestamp",
        planned_raw_path="data/raw/hp_scaling/cbs_85035ned_alkmaar_dwelling_stock.json",
        planned_metadata_path="data/metadata/hp_scaling/cbs_85035ned_alkmaar_dwelling_stock_metadata.json",
        expected_size_note="small filtered OData request for Alkmaar municipality and selected periods",
        expected_runtime_note="expected seconds to a few minutes; no >15 minute run expected",
        role="SFH/MFH dwelling-stock denominator and crosswalk evidence for GM0361",
        proposed_fields_or_filters=(
            "RegioS == GM0361 / Alkmaar",
            "Woningtype includes Eengezinswoningen totaal for SFH",
            "Woningtype includes Meergezinswoningen totaal for MFH",
            "Onderwerp: Beginstand woningvoorraad",
            "latest available period and any signed planning-year proxy period",
        ),
        boundary="Provides stock/type evidence only; it does not provide heat demand, DHW demand, or 2035 HP adoption.",
    ),
    HpScalingSourceSpec(
        key="pbl_startanalyse_2025_alkmaar",
        title="PBL Startanalyse aardgasvrije buurten 2025 Alkmaar municipality ZIP",
        source="PBL Planbureau voor de Leefomgeving",
        url="https://dataportaal.pbl.nl/data/Startanalyse_aardgasvrije_buurten/2025/Gemeentes/Alkmaar.zip",
        license_or_terms="CC BY 4.0 NL according to the PBL data portal",
        planned_raw_path="data/raw/hp_scaling/pbl_startanalyse_2025_alkmaar.zip",
        planned_metadata_path="data/metadata/hp_scaling/pbl_startanalyse_2025_alkmaar_metadata.json",
        expected_size_note="PBL municipality listing reports Alkmaar.zip as 215.1 kB",
        expected_runtime_note="expected seconds; no >15 minute run expected",
        role="local heat-demand, neighbourhood, and pathway/suitability context for Alkmaar",
        proposed_fields_or_filters=(
            "download link with visible filename Alkmaar.zip from the 2025 Gemeentes page",
            "buurt/wijk identifiers and municipality coverage",
            "residential heat-demand fields if present and documented",
            "space/DHW split only if explicit in the public file schema or documentation",
            "Startanalyse strategy/pathway and national-cost indicators as suitability context",
        ),
        boundary="Startanalyse pathway outputs are suitability/pathway evidence unless the PI separately signs a source-use rule for heat-demand scaling.",
    ),
    HpScalingSourceSpec(
        key="cbs_85523ned_heat_pump_context",
        title="CBS StatLine 85523NED heat pumps by sector, capacity, and energy flows",
        source="CBS StatLine",
        url="https://opendata.cbs.nl/ODataApi/OData/85523NED",
        license_or_terms="CBS open data terms; cite CBS table page and retrieval timestamp",
        planned_raw_path="data/raw/hp_scaling/cbs_85523ned_heat_pump_context.json",
        planned_metadata_path="data/metadata/hp_scaling/cbs_85523ned_heat_pump_context_metadata.json",
        expected_size_note="small national/context table request after field filtering",
        expected_runtime_note="expected seconds to a few minutes; no >15 minute run expected",
        role="national/current heat-pump context and uncertainty framing",
        proposed_fields_or_filters=(
            "sector == Woningen where available",
            "air-source and ground/water-source categories",
            "in-use counts, thermal capacity, heat production, and energy-flow fields",
            "periods available through the latest public table version",
        ),
        boundary="Context only for this route; it is not a local Alkmaar 2035 adoption source and cannot make values executable.",
    ),
)

CBS_85035_ENDPOINTS: tuple[str, ...] = ("TableInfos", "DataProperties", "RegioS", "Woningtype", "Woningkenmerk", "Perioden", "TypedDataSet")
CBS_85523_ENDPOINTS: tuple[str, ...] = ("TableInfos", "DataProperties", "Warmtepompen", "Sector", "Perioden", "TypedDataSet")


def build_hp_scaling_retrieval_plan() -> dict[str, Any]:
    """Return the no-download HP-001 Alkmaar source-binding plan."""
    created_utc = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "data_id": DATA_ID,
        "bundle_id": BUNDLE_ID,
        "created_utc": created_utc,
        "status": "approved retrieval/checksum route; no values executable",
        "download_performed": False,
        "geography": {
            "municipality_name": MUNICIPALITY_NAME,
            "municipality_code": MUNICIPALITY_CODE,
            "service_area_status": "approved retrieval proxy; final scaling interpretation unsigned",
        },
        "public_source_policy": {
            "public_sources_only": True,
            "private_thesis_policy": "The PI-supplied private student thesis may be used only as confidential source-discovery guidance; it is not cited, quoted, committed, or used as value provenance.",
        },
        "sources": [asdict(source) for source in HP_SCALING_SOURCES],
        "hp001_component_traceability": [
            {"component_id": "sfh_space", "building_class": "SFH", "end_use": "space", "when2heat_shape_column": "NL_heat_profile_space_SFH", "when2heat_cop_column": "NL_COP_ASHP_radiator", "annual_twh_source_status": "unsigned_local_value_pending"},
            {"component_id": "mfh_space", "building_class": "MFH", "end_use": "space", "when2heat_shape_column": "NL_heat_profile_space_MFH", "when2heat_cop_column": "NL_COP_ASHP_radiator", "annual_twh_source_status": "unsigned_local_value_pending"},
            {"component_id": "sfh_dhw", "building_class": "SFH", "end_use": "water", "when2heat_shape_column": "NL_heat_profile_water_SFH", "when2heat_cop_column": "NL_COP_ASHP_water", "annual_twh_source_status": "unsigned_local_value_pending"},
            {"component_id": "mfh_dhw", "building_class": "MFH", "end_use": "water", "when2heat_shape_column": "NL_heat_profile_water_MFH", "when2heat_cop_column": "NL_COP_ASHP_water", "annual_twh_source_status": "unsigned_local_value_pending"},
        ],
        "value_route": {
            "local_heat_demand": "Future value proposal should extract or document public local heat-demand evidence first, then preserve space and DHW separately if the schema supports that interpretation.",
            "suitability_pathway": "PBL Startanalyse pathway/cost outputs are kept separate from demand and adoption; they can justify scenario plausibility only after PI source-use approval.",
            "unsigned_2035_adoption": "2035 HP adoption/electrification fractions or counts require a separate PI-signed scenario source before annual TWh values enter executable config.",
        },
        "checksum_workflow": {
            "future_command": r".\.venv\Scripts\python.exe data\get_hp_scaling.py --download --resume",
            "checkpoint_path": "data/metadata/hp_scaling/hp001_alkmaar_gm0361_retrieval_checkpoint.json",
            "checkpoint_behavior": "After each source is retrieved, record URL, byte size, SHA-256, retrieval timestamp, and next pending source. Resume skips any source whose raw file still matches the checkpoint checksum.",
            "atomic_write_behavior": "Downloads write .tmp files under data/raw/hp_scaling, checksum them, then atomically replace the final raw path.",
        },
        "long_run_notice": {
            "required_before_launch_if_expected_runtime_exceeds_15_minutes": True,
            "current_assessment": "Planned public-source retrievals are small filtered CBS OData requests and one 215.1 kB PBL ZIP, so the route does not currently require a long-run notice before retrieval.",
        },
        "blocked_or_out_of_scope": [
            "No executable annual TWh values are created.",
            "No D-004 acceptance or paired-weather cold-spell check is run.",
            "No net-load, event, P(E), threshold, capacity-screen, or manuscript-result analysis is run.",
            "No commercial heat is included in the primary route.",
        ],
    }


def build_hp001_scaling_formula_config_decision_packet() -> dict[str, Any]:
    """Return the remaining HP-001 scaling decisions without executable values."""
    return {
        "data_id": DATA_ID,
        "decision_packet_id": "E2-S3-HP001-SCALING-FORMULA-CONFIG",
        "created_utc": _utc_now(),
        "status": "proposed decision packet; annual HP TWh values not executable",
        "already_approved": {
            "indicator_mapping": {
                "approval_ids": ("D013-PBL-MAPPING", "A-015"),
                "scope": "Mapping only: _w/_u and H22/H23/H24 residential space/DHW/total meanings in [GJ/weq/jaar].",
            },
            "hp001_boundary": "Residential SFH/MFH space heat plus domestic hot water; commercial heat excluded.",
        },
        "remaining_decisions": [
            {
                "key": "value_column",
                "recommended_choice": "Referentie_2030",
                "source": "PBL Startanalyse 2025 Alkmaar, Alkmaar_strategie.csv",
                "reason": "Reference heat-demand column rather than a strategy/pathway optimization output.",
                "approval_required_before_executable_values": True,
            },
            {
                "key": "denominator",
                "recommended_choice": "I11_woningequivalenten [Woning]",
                "source": "PBL Startanalyse 2025 Alkmaar, Alkmaar_strategie.csv",
                "reason": "Matches the [GJ/weq/jaar] intensity basis for residential rows under A-015.",
                "approval_required_before_executable_values": True,
            },
            {
                "key": "unit_conversion",
                "recommended_choice": "divide summed GJ/year by 3,600,000 to obtain TWh/year",
                "source": "SI energy conversion; 1 TWh = 3,600,000 GJ",
                "reason": "Keeps PBL useful-thermal intensity units explicit before When2Heat annual-TWh scaling.",
                "approval_required_before_executable_values": True,
            },
            {
                "key": "sfh_mfh_split",
                "recommended_choice": "CBS 85035NED count-share split between Eengezinswoningen totaal and Meergezinswoningen totaal",
                "source": "CBS 85035NED Alkmaar GM0361 dwelling stock/type evidence",
                "reason": "Uses the cleanest signed denominator candidate without adding an area-as-heat proxy.",
                "sensitivity_option": "Area-weighted split using CBS average floor area, if separately signed.",
                "approval_required_before_executable_values": True,
            },
            {
                "key": "adoption_electrification",
                "recommended_choice": "separate signed 2035 HP service fraction/count scenario",
                "source": "pending PI-selected source or author-specified scenario",
                "reason": "Keeps local heat demand separate from 2035 HP adoption/electrification and DHW service boundary.",
                "approval_required_before_executable_values": True,
            },
        ],
        "fail_closed_config_contract": {
            "config_type": "src.hp_model.HP001LocalScalingConfig",
            "required_approval_keys": [
                "value_column",
                "denominator",
                "unit_conversion",
                "sfh_mfh_split",
                "adoption_electrification",
            ],
            "builder": "src.hp_model.hp001_components_from_local_scaling_config",
            "guard": "src.hp_model.require_signed_hp001_local_scaling_config",
            "behavior": "The builder raises until every required approval key has a non-empty signed approval ID.",
        },
        "formula_under_review": {
            "local_heat_twh_by_end_use": "sum_b intensity_GJ_per_weq_year[b,end_use] * I11_woningequivalenten_woning[b] / 3_600_000",
            "space_indicator": "H23_Vraag_RV_w",
            "water_indicator": "H24_Vraag_TW_w",
            "diagnostic_total_indicator": "H22_Vraag_totaal_w",
            "class_allocation": "H_local_TWh[class,end_use] = H_local_TWh[end_use] * w_class[class]",
            "hp_served_twh": "H_HP_TWh[class,end_use,scenario] = H_local_TWh[class,end_use] * f_HP_service[class,end_use,scenario]",
        },
        "non_claims": [
            "No annual HP TWh values are executable.",
            "No 2035 HP adoption/electrification value is signed.",
            "No D-004/cold-spell acceptance, net-load, event, P(E), threshold, capacity-screen, manuscript, or probability analysis is run.",
        ],
    }


def build_hp001_value_binding_readiness_packet() -> dict[str, Any]:
    """Return unsigned HP-001 value-binding evidence without executable values."""
    return {
        "data_id": DATA_ID,
        "decision_packet_id": "E2-S3-HP001-VALUE-BINDING-READINESS",
        "created_utc": _utc_now(),
        "status": "proposed value-binding draft; not approved for executable HP loads",
        "approval_state": {
            "approved_indicator_mapping_ids": ("D013-PBL-MAPPING", "A-015"),
            "required_before_executable_binding": [
                "value_column",
                "denominator",
                "unit_conversion",
                "sfh_mfh_split",
                "adoption_electrification",
            ],
            "approval_ids": {},
            "missing_approval_keys": [
                "value_column",
                "denominator",
                "unit_conversion",
                "sfh_mfh_split",
                "adoption_electrification",
            ],
            "executable_binding_allowed": False,
        },
        "source_inputs_under_review": {
            "pbl_source": "D-013 PBL Startanalyse 2025 Alkmaar, Alkmaar_strategie.csv",
            "value_column": "Referentie_2030",
            "denominator_column": "I11_woningequivalenten [Woning]",
            "space_indicator": "H23_Vraag_RV_w",
            "water_indicator": "H24_Vraag_TW_w",
            "diagnostic_total_indicator": "H22_Vraag_totaal_w",
            "cbs_source": "D-013 CBS StatLine 85035NED Alkmaar GM0361 dwelling stock/type evidence",
            "sfh_mfh_split_rule": "cbs_85035ned_count_share",
            "gj_to_twh_divisor": 3_600_000.0,
            "adoption_electrification_scenario": "unsigned_2035_hp_service_fraction_or_count_pending",
        },
        "local_heat_demand_diagnostics_unsigned": {
            "weq_summed": 67_422,
            "space_heat_twh": 0.362059444,
            "water_heat_twh": 0.097897778,
            "residential_total_diagnostic_twh": 0.634250556,
            "diagnostic_note": "H22 exceeds H23+H24, so other residential heat/end-use categories remain outside HP-001 unless separately approved.",
        },
        "component_value_drafts_unsigned_before_2035_adoption": [
            {
                "component_id": "sfh_space",
                "building_class": "SFH",
                "end_use": "space",
                "annual_heat_twh": 0.221155323,
                "shape_column": "NL_heat_profile_space_SFH",
                "cop_column": "NL_COP_ASHP_radiator",
                "annual_twh_status": "unsigned_local_heat_demand_before_2035_adoption",
            },
            {
                "component_id": "mfh_space",
                "building_class": "MFH",
                "end_use": "space",
                "annual_heat_twh": 0.140904121,
                "shape_column": "NL_heat_profile_space_MFH",
                "cop_column": "NL_COP_ASHP_radiator",
                "annual_twh_status": "unsigned_local_heat_demand_before_2035_adoption",
            },
            {
                "component_id": "sfh_water",
                "building_class": "SFH",
                "end_use": "water",
                "annual_heat_twh": 0.059798509,
                "shape_column": "NL_heat_profile_water_SFH",
                "cop_column": "NL_COP_ASHP_water",
                "annual_twh_status": "unsigned_local_heat_demand_before_2035_adoption",
            },
            {
                "component_id": "mfh_water",
                "building_class": "MFH",
                "end_use": "water",
                "annual_heat_twh": 0.038099269,
                "shape_column": "NL_heat_profile_water_MFH",
                "cop_column": "NL_COP_ASHP_water",
                "annual_twh_status": "unsigned_local_heat_demand_before_2035_adoption",
            },
        ],
        "future_binding_contract": {
            "config_type": "src.hp_model.HP001LocalScalingConfig",
            "adapter": "src.hp_model.hp001_local_scaling_config_from_value_binding_record",
            "guard": "src.hp_model.require_signed_hp001_local_scaling_config",
            "required_status_before_config": "approved_for_executable_value_binding",
            "required_approval_keys": [
                "value_column",
                "denominator",
                "unit_conversion",
                "sfh_mfh_split",
                "adoption_electrification",
            ],
        },
        "non_claims": [
            "No annual HP TWh values are executable.",
            "No 2035 HP adoption/electrification value is signed.",
            "No D-004/cold-spell acceptance, net-load, event, P(E), threshold, capacity-screen, manuscript, or probability analysis is run.",
        ],
    }



def build_hp001_readiness_approval_checklist_packet() -> dict[str, Any]:
    """Return the remaining HP-001 approvals before integrated HP use."""
    annual_value_keys = [
        "value_column",
        "denominator",
        "unit_conversion",
        "sfh_mfh_split",
        "adoption_electrification",
    ]
    weather_acceptance_keys = [
        "d004_paired_weather_acceptance",
        "cold_spell_tolerances",
    ]
    scenario_consistency_keys = [
        "scenario_source_consistency",
    ]
    return {
        "data_ids": ["D-003", "D-004", "D-013"],
        "decision_packet_id": "E2-S3-HP001-READINESS-APPROVAL-CHECKLIST",
        "created_utc": _utc_now(),
        "status": "proposed approval checklist only; executable annual HP values and final paired-weather acceptance remain unsigned",
        "approved_foundation": {
            "hp001_boundary": "Residential SFH/MFH space heat plus domestic hot water using approved D-003 When2Heat shape/COP columns; COM heat excluded.",
            "indicator_mapping": "D013-PBL-MAPPING/A-015 approves only the PBL residential indicator mapping.",
            "d004_source_member_use": "D004-SOURCE-MEMBER-ACCEPTANCE approves D-004 source/member use for internal first-screen work only.",
            "weather_contract": "WEATHER-001 requires HP/PV to consume the same shared weather member identity and calendar.",
            "cold_spell_design": "E2-S3-COLD-SPELL-ACCEPTANCE-DESIGN approves the diagnostic design but not numerical tolerances.",
            "scenario_consistency": "A-016 approves the scenario-consistency requirement, but the HP integrated-use binding remains unsigned until an explicit scenario_source_consistency approval ID is recorded.",
        },
        "approval_groups": {
            "annual_value_binding": annual_value_keys,
            "scenario_consistency": scenario_consistency_keys,
            "weather_acceptance": weather_acceptance_keys,
        },
        "required_approvals": [
            {"key": "value_column", "candidate": "Referentie_2030", "current_status": "unsigned", "blocks": "Using PBL values as local annual heat-demand input."},
            {"key": "denominator", "candidate": "I11_woningequivalenten [Woning]", "current_status": "unsigned", "blocks": "Multiplying PBL intensities by dwelling-equivalent counts."},
            {"key": "unit_conversion", "candidate": "GJ/year divided by 3,600,000 to obtain TWh/year", "current_status": "unsigned", "blocks": "Converting candidate thermal demand into annual TWh scales."},
            {"key": "sfh_mfh_split", "candidate": "CBS 85035NED count-share allocation between SFH and MFH", "current_status": "unsigned", "blocks": "Assigning local space/DHW heat demand to HP-001 building classes."},
            {"key": "adoption_electrification", "candidate": "separate signed 2035 HP service/adoption/electrification scenario", "current_status": "unsigned", "blocks": "Converting local residential heat demand into 2035 heat-pump-served demand."},
            {"key": "scenario_source_consistency", "candidate": "A-016 EV/HP/PV 2035 scenario-source consistency approval", "current_status": "unsigned for final integrated HP use", "blocks": "Using HP annual values in a coherent integrated 2035 case with EV and PV source branches."},
            {"key": "d004_paired_weather_acceptance", "candidate": "exact WEATHER-001 member identity/calendar equality before HP/PV paired diagnostics", "current_status": "unsigned for final paired acceptance", "blocks": "Treating HP and PV profiles as driven by an accepted same-weather realization."},
            {"key": "cold_spell_tolerances", "candidate": "future signed numerical coldest-window and near-freezing diagnostic tolerances", "current_status": "unsigned", "blocks": "Accepting When2Heat-derived HP behavior under the selected D-004 cold-weather members."},
        ],
        "fail_closed_handoff": {
            "value_binding_adapter": "src.hp_model.hp001_local_scaling_config_from_value_binding_record",
            "value_binding_required_status": "approved_for_executable_value_binding",
            "annual_scaling_guard": "src.hp_model.require_signed_hp001_local_scaling_config",
            "final_readiness_guard": "src.hp_model.require_hp001_final_readiness_approvals",
            "required_final_approval_keys": annual_value_keys + scenario_consistency_keys + weather_acceptance_keys,
        },
        "next_pi_decision": (
            "Approve or amend the five annual value-binding choices, then record explicit "
            "A-016 scenario-source consistency for the integrated case, and separately "
            "approve final D-004 paired-weather acceptance evidence and cold-spell "
            "tolerances before HP profiles enter integrated analysis."
        ),
        "non_claims": [
            "No annual HP TWh values are executable.",
            "No 2035 HP adoption/electrification value is signed.",
            "No A-016 scenario-source consistency approval for HP integrated use is signed.",
            "No D-004 paired-weather or cold-spell acceptance is signed.",
            "No net-load, event, P(E), threshold, capacity-screen, manuscript, or probability analysis is run.",
        ],
    }




def build_hp001_executable_value_binding_decision_packet() -> dict[str, Any]:
    """Return the proposed approval template for executable value binding."""
    value_binding = build_hp001_value_binding_readiness_packet()
    readiness = build_hp001_readiness_approval_checklist_packet()
    annual_keys = list(readiness["approval_groups"]["annual_value_binding"])
    weather_keys = list(readiness["approval_groups"]["weather_acceptance"])
    scenario_keys = list(readiness["approval_groups"]["scenario_consistency"])
    return {
        "data_ids": ["D-003", "D-004", "D-013"],
        "decision_packet_id": "E2-S3-HP001-EXECUTABLE-VALUE-BINDING-PACKET",
        "created_utc": _utc_now(),
        "status": "proposed executable-value-binding decision packet; approval template only",
        "evidence_already_present": {
            "d003_shape_cop_boundary": "HP-001 approves D-003 Dutch residential SFH/MFH space and DHW shape/COP columns for internal source use.",
            "d013_retrieval_checksum": "D-013 CBS/PBL raw public files have retrieval/checksum metadata recorded; raw files remain ignored.",
            "d013_indicator_mapping": "D013-PBL-MAPPING/A-015 approves the PBL residential indicator mapping only.",
            "scenario_consistency": "A-016 requires EV/HP/PV 2035 source-year, planning-year, scenario-label, and scaling/adoption branch consistency before integrated use.",
            "d004_source_member": "D004-SOURCE-MEMBER-ACCEPTANCE approves source/member use for internal first-screen work only.",
            "weather_contract": "WEATHER-001 requires common HP/PV member identity, shared_weather_driver_id, source/provenance, and UTC/local calendar.",
        },
        "pi_approval_request": [
            {"key": "value_column", "requested_decision": "Approve or amend use of PBL Referentie_2030 as the value column."},
            {"key": "denominator", "requested_decision": "Approve or amend use of PBL I11_woningequivalenten [Woning] as the denominator."},
            {"key": "unit_conversion", "requested_decision": "Approve or amend GJ/year divided by 3,600,000 to obtain TWh/year."},
            {"key": "sfh_mfh_split", "requested_decision": "Approve or amend CBS 85035NED count-share allocation for SFH/MFH."},
            {"key": "adoption_electrification", "requested_decision": "Provide or approve a 2035 HP service/adoption/electrification scenario for space and DHW."},
            {"key": "scenario_source_consistency", "requested_decision": "Record an explicit A-016 scenario-source consistency approval for the integrated EV/HP/PV 2035 case."},
            {"key": "d004_paired_weather_acceptance", "requested_decision": "Approve later paired HP/PV evidence using exact WEATHER-001 identity/calendar equality."},
            {"key": "cold_spell_tolerances", "requested_decision": "Approve later numerical coldest-window and near-freezing cold-spell tolerances before the real check."},
        ],
        "unsigned_candidate_binding_record": {
            "status": "proposed_template_not_approved_for_executable_use",
            "approval_state": {
                "approved_indicator_mapping_ids": ["D013-PBL-MAPPING", "A-015"],
                "required_before_executable_binding": annual_keys,
                "approval_ids": {},
                "missing_approval_keys": annual_keys,
                "executable_binding_allowed": False,
            },
            "source_inputs_under_review": value_binding["source_inputs_under_review"],
            "component_value_drafts_unsigned_before_2035_adoption": value_binding[
                "component_value_drafts_unsigned_before_2035_adoption"
            ],
            "local_heat_demand_diagnostics_unsigned": value_binding[
                "local_heat_demand_diagnostics_unsigned"
            ],
        },
        "final_readiness_dependency": {
            "annual_value_binding_keys": annual_keys,
            "scenario_consistency_keys": scenario_keys,
            "weather_acceptance_keys": weather_keys,
            "all_required_before_integrated_hp_use": annual_keys + scenario_keys + weather_keys,
            "guard": "src.hp_model.require_hp001_final_readiness_approvals",
        },
        "future_executable_handoff_if_pi_signs": {
            "required_record_status": "approved_for_executable_value_binding",
            "adapter": "src.hp_model.hp001_local_scaling_config_from_value_binding_record",
            "annual_scaling_guard": "src.hp_model.require_signed_hp001_local_scaling_config",
            "component_builder": "src.hp_model.hp001_components_from_local_scaling_config",
            "still_not_enough_for_integrated_use": "Annual value-binding approval does not by itself sign A-016 scenario-source consistency, D-004 paired-weather acceptance, or cold-spell tolerances.",
        },
        "non_claims": [
            "No annual HP TWh values are executable.",
            "No 2035 HP adoption/electrification value is signed.",
            "No A-016 scenario-source consistency approval for HP integrated use is signed.",
            "No D-004 paired-weather or cold-spell acceptance is signed or run.",
            "No net-load, event, P(E), threshold, capacity-screen, manuscript, or probability analysis is run.",
        ],
    }




def build_hp001_component_output_readiness_blocker_packet() -> dict[str, Any]:
    """Return the fail-closed HP component-output blocker packet for IC-1."""
    readiness = build_hp001_readiness_approval_checklist_packet()
    required_approval_keys = readiness["fail_closed_handoff"]["required_final_approval_keys"]
    component_templates = [
        {
            "building_class": "SFH",
            "end_use": "space",
            "heat_column": "NL_heat_profile_space_SFH",
            "cop_column": "NL_COP_ASHP_radiator",
            "annual_heat_demand_twh": "<future signed positive value>",
            "provenance": {
                "annual_scaling_status": "signed",
                "annual_scaling_approval_id": "<future signed annual approval>",
            },
        },
        {
            "building_class": "MFH",
            "end_use": "space",
            "heat_column": "NL_heat_profile_space_MFH",
            "cop_column": "NL_COP_ASHP_radiator",
            "annual_heat_demand_twh": "<future signed positive value>",
            "provenance": {
                "annual_scaling_status": "signed",
                "annual_scaling_approval_id": "<future signed annual approval>",
            },
        },
        {
            "building_class": "SFH",
            "end_use": "water",
            "heat_column": "NL_heat_profile_water_SFH",
            "cop_column": "NL_COP_ASHP_water",
            "annual_heat_demand_twh": "<future signed positive value>",
            "provenance": {
                "annual_scaling_status": "signed",
                "annual_scaling_approval_id": "<future signed annual approval>",
            },
        },
        {
            "building_class": "MFH",
            "end_use": "water",
            "heat_column": "NL_heat_profile_water_MFH",
            "cop_column": "NL_COP_ASHP_water",
            "annual_heat_demand_twh": "<future signed positive value>",
            "provenance": {
                "annual_scaling_status": "signed",
                "annual_scaling_approval_id": "<future signed annual approval>",
            },
        },
    ]
    return {
        "packet_id": "E2-S3-HP001-COMPONENT-OUTPUT-READINESS-BLOCKER",
        "created_utc": _utc_now(),
        "status": "proposed_blocker_packet_not_executable",
        "future_required_manifest_status": "approved_for_ic1_component_output_consumption",
        "purpose": "Give future IC-1 integration a concise HP preflight manifest that fails closed until real HP component outputs are safe to consume.",
        "validator": "src.hp_model.require_hp001_component_output_readiness_manifest",
        "approved_foundation": readiness["approved_foundation"],
        "required_approval_keys_before_ic1_consumption": required_approval_keys,
        "preflight_manifest_template": {
            "status": "approved_for_ic1_component_output_consumption",
            "approval_ids": {key: f"<future signed {key} approval id>" for key in required_approval_keys},
            "profile_artifact": {
                "path": "data/processed/hp_profiles/<future_signed_hp001_component_output>.npz",
                "sha256": "<future 64-character SHA-256>",
                "n_timesteps": 35040,
                "cadence_seconds": 900,
                "electric_power_unit": "kW",
            },
            "weather_identity": {
                "shared_weather_driver_id": "<future accepted D-004 shared_weather_driver_id>",
                "member_id": "<future accepted D-004 member_id>",
                "source": "<future accepted D-004 source/provenance label>",
                "content_sha256": "<future WEATHER-001 member content SHA-256>",
                "n_timesteps": 35040,
                "cadence_seconds": 900,
            },
            "paired_pv_weather_identity": {
                "shared_weather_driver_id": "<must match HP weather_identity>",
                "member_id": "<must match HP weather_identity>",
                "source": "<must match HP weather_identity>",
                "content_sha256": "<must match HP weather_identity>",
                "n_timesteps": 35040,
                "cadence_seconds": 900,
            },
            "component_traceability": component_templates,
            "unresolved_blocker_ids": [],
        },
        "current_blockers": [
            "annual HP TWh values and 2035 adoption/electrification/service fractions are unsigned",
            "A-016 scenario-source consistency is not signed for a real integrated case",
            "D-004 final paired-weather acceptance is not signed",
            "cold-spell numerical tolerances and real acceptance evidence are unsigned",
            "no real HP component-output artifact path or checksum exists",
        ],
        "non_claims": [
            "No executable annual HP values are created.",
            "No HP component-output artifact is created or approved.",
            "No D-004 paired-weather or cold-spell final acceptance is signed or run.",
            "No net-load, event, P(E), threshold, capacity-screen, manuscript, or probability analysis is run.",
        ],
    }


def write_hp001_component_output_readiness_blocker_packet(metadata_dir: Path) -> Path:
    """Write the proposed HP component-output readiness blocker packet."""
    target_dir = metadata_dir / "hp_scaling"
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / COMPONENT_OUTPUT_READINESS_BLOCKER_FILENAME
    payload = build_hp001_component_output_readiness_blocker_packet()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path

def write_hp001_executable_value_binding_decision_packet(metadata_dir: Path) -> Path:
    """Write the proposed executable value-binding decision packet."""
    target_dir = metadata_dir / "hp_scaling"
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / EXECUTABLE_VALUE_BINDING_DECISION_PACKET_FILENAME
    payload = build_hp001_executable_value_binding_decision_packet()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_hp001_readiness_approval_checklist_packet(metadata_dir: Path) -> Path:
    """Write the proposed HP-001 approval checklist for PI review."""
    target_dir = metadata_dir / "hp_scaling"
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / READINESS_APPROVAL_CHECKLIST_FILENAME
    payload = build_hp001_readiness_approval_checklist_packet()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path

def write_hp001_value_binding_readiness_packet(metadata_dir: Path) -> Path:
    """Write the unsigned next-step value-binding packet for PI review."""
    target_dir = metadata_dir / "hp_scaling"
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / VALUE_BINDING_READINESS_FILENAME
    payload = build_hp001_value_binding_readiness_packet()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_hp001_scaling_formula_config_decision_packet(metadata_dir: Path) -> Path:
    """Write the proposed remaining-choice packet without executable values."""
    target_dir = metadata_dir / "hp_scaling"
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / FORMULA_DECISION_PACKET_FILENAME
    payload = build_hp001_scaling_formula_config_decision_packet()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_hp_scaling_retrieval_plan(metadata_dir: Path) -> Path:
    """Write D-013 metadata and the no-download route plan for PI review."""
    write_metadata(DATA_ID, metadata_dir)
    target_dir = metadata_dir / "hp_scaling"
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{BUNDLE_ID}_plan.json"
    payload = build_hp_scaling_retrieval_plan()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json_url(url: str, *, timeout_s: float) -> dict[str, Any]:
    with request.urlopen(url, timeout=timeout_s) as response:
        return json.loads(response.read().decode("utf-8"))


def _read_url_bytes(url: str, *, timeout_s: float) -> bytes:
    with request.urlopen(url, timeout=timeout_s) as response:
        return response.read()


def _write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_bytes(payload)
    temp_path.replace(path)


def _odata_url(base_url: str, endpoint: str, query: dict[str, str] | None = None) -> str:
    if not query:
        return f"{base_url}/{endpoint}"
    return f"{base_url}/{endpoint}?{parse.urlencode(query)}"


def _cbs_table_payload(spec: HpScalingSourceSpec) -> dict[str, Any]:
    if spec.key == "cbs_85035ned_dwelling_stock":
        endpoints = CBS_85035_ENDPOINTS
        data_query = {"$filter": f"RegioS eq '{MUNICIPALITY_CODE}'"}
    elif spec.key == "cbs_85523ned_heat_pump_context":
        endpoints = CBS_85523_ENDPOINTS
        data_query = None
    else:
        raise ValueError(f"{spec.key} is not a CBS source")
    payload: dict[str, Any] = {"retrieved_endpoint": spec.url, "retrieved_at_utc": _utc_now(), "odata": {}}
    for endpoint in endpoints:
        query = data_query if endpoint == "TypedDataSet" else None
        url = _odata_url(spec.url, endpoint, query)
        payload["odata"][endpoint] = {"url": url, "response": _read_json_url(url, timeout_s=DOWNLOAD_TIMEOUT_S)}
    return payload


def _summarize_cbs_payload(spec: HpScalingSourceSpec, payload: dict[str, Any]) -> dict[str, Any]:
    odata = payload["odata"]
    table_info = odata["TableInfos"]["response"]["value"][0]
    typed_rows = odata["TypedDataSet"]["response"]["value"]
    dimension_keys = {"ID", "RegioS", "Woningtype", "Woningkenmerk", "Perioden", "Warmtepompen", "Sector"}
    summary: dict[str, Any] = {
        "table_identifier": table_info.get("Identifier"),
        "table_title": table_info.get("Title"),
        "table_modified": table_info.get("Modified"),
        "records_retrieved": len(typed_rows),
        "data_columns": sorted(key for row in typed_rows[:1] for key in row if key not in dimension_keys),
    }
    if spec.key == "cbs_85035ned_dwelling_stock":
        regions = odata["RegioS"]["response"]["value"]
        summary.update(
            {
                "alkmaar_region_titles": [row.get("Title") for row in regions if row.get("Key", "").strip() == MUNICIPALITY_CODE],
                "woningtype_titles": {row["Key"].strip(): row["Title"] for row in odata["Woningtype"]["response"]["value"]},
                "woningkenmerk_titles": {row["Key"].strip(): row["Title"] for row in odata["Woningkenmerk"]["response"]["value"]},
                "periods": [row["Key"] for row in odata["Perioden"]["response"]["value"]],
                "sfh_mfh_crosswalk": {"SFH": "Eengezinswoningen totaal", "MFH": "Meergezinswoningen totaal"},
            }
        )
    elif spec.key == "cbs_85523ned_heat_pump_context":
        summary.update(
            {
                "warmtepompen_titles": {row["Key"].strip(): row["Title"] for row in odata["Warmtepompen"]["response"]["value"]},
                "sector_titles": {row["Key"].strip(): row["Title"] for row in odata["Sector"]["response"]["value"]},
                "period_count": len(odata["Perioden"]["response"]["value"]),
                "context_only": True,
            }
        )
    return summary


def _summarize_pbl_zip(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        members = [
            {"filename": info.filename, "compress_size": info.compress_size, "file_size": info.file_size}
            for info in archive.infolist()
            if not info.is_dir()
        ]
        csv_summaries: list[dict[str, Any]] = []
        for info in archive.infolist():
            if info.is_dir() or not info.filename.lower().endswith(".csv"):
                continue
            raw = archive.read(info)
            sample = raw[:65536]
            text = raw.decode("utf-8-sig", errors="replace")
            first_line = text.splitlines()[0] if text.splitlines() else ""
            delimiter = ";" if first_line.count(";") >= first_line.count(",") else ","
            columns = first_line.split(delimiter) if first_line else []
            csv_summaries.append(
                {
                    "filename": info.filename,
                    "delimiter_guess": delimiter,
                    "column_count": len(columns),
                    "columns": columns,
                    "sampled_bytes": len(sample),
                    "full_file_rows_inspected": _count_csv_rows(text, delimiter),
                    "column_classification": _classify_pbl_columns(columns),
                    "indicator_unit_summary": _summarize_pbl_indicator_units(text, delimiter),
                }
            )
    return {
        "zip_member_count": len(members),
        "zip_members": members,
        "csv_summaries": csv_summaries,
        "schema_inspection_scope": "ZIP directory plus full small CSV schema/indicator-unit inspection; no annual values produced",
    }


def _count_csv_rows(text: str, delimiter: str) -> int:
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    row_count = sum(1 for _ in reader)
    return max(0, row_count - 1)


def _classify_pbl_columns(columns: Sequence[str]) -> dict[str, object]:
    lower_by_column = {column: column.lower() for column in columns}
    return {
        "sfh_candidate_columns": [column for column in columns if column in PBL_SFH_COLUMNS],
        "mfh_candidate_columns": [column for column in columns if column in PBL_MFH_COLUMNS],
        "residential_stock_columns": [
            column
            for column, lower in lower_by_column.items()
            if "woning" in lower and ("aantal" in lower or "totaal" in lower or "type" in lower)
        ],
        "strategy_or_pathway_columns": [
            column
            for column in columns
            if column.startswith(("Strategie_", "Variant_", "Referentie_", "Laagste_Nationale_Kosten"))
        ],
        "heat_or_energy_candidate_columns": [
            column
            for column, lower in lower_by_column.items()
            if any(term in lower for term in PBL_HEAT_TERMS) and not _is_pbl_administrative_energy_label(lower)
        ],
        "dhw_candidate_columns": [
            column for column, lower in lower_by_column.items() if any(term in lower for term in PBL_DHW_TERMS)
        ],
    }


def _is_pbl_administrative_energy_label(lower_column: str) -> bool:
    return "energieregio" in lower_column or "energielabel" in lower_column


def _summarize_pbl_indicator_units(text: str, delimiter: str) -> dict[str, object]:
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    fieldnames = reader.fieldnames or []
    if "Code_Indicator" not in fieldnames and "Eenheid" not in fieldnames:
        return {"available": False}
    pairs: set[tuple[str, str]] = set()
    heat_pairs: set[tuple[str, str]] = set()
    for row in reader:
        code = str(row.get("Code_Indicator", "")).strip()
        unit = str(row.get("Eenheid", "")).strip()
        if not code and not unit:
            continue
        pair = (code, unit)
        pairs.add(pair)
        combined = f"{code} {unit}".lower()
        if any(term in combined for term in PBL_HEAT_TERMS):
            heat_pairs.add(pair)
    return {
        "available": True,
        "pair_count": len(pairs),
        "pairs": [{"code_indicator": code, "unit": unit} for code, unit in sorted(pairs)],
        "heat_or_energy_pair_count": len(heat_pairs),
        "heat_or_energy_pairs": [
            {"code_indicator": code, "unit": unit} for code, unit in sorted(heat_pairs)
        ],
        "source_use_boundary": "indicator/unit evidence only; no value extraction or adoption interpretation",
    }


def _planned_metadata_path(spec: HpScalingSourceSpec, metadata_dir: Path) -> Path:
    path = Path(spec.planned_metadata_path)
    if path.is_absolute():
        return path
    parts = path.parts
    if len(parts) >= 2 and parts[0] == "data" and parts[1] == "metadata":
        return metadata_dir.joinpath(*parts[2:])
    return metadata_dir / "hp_scaling" / path.name


def _write_source_metadata(
    *,
    spec: HpScalingSourceSpec,
    metadata_dir: Path,
    raw_path: Path,
    retrieved_url: str,
    schema_summary: dict[str, Any],
    download_performed: bool = True,
    status: str = "retrieved/checksummed for PI review; HP scaling values remain unsigned",
    schema_refresh_network_performed: bool | None = None,
) -> Path:
    metadata_path = _planned_metadata_path(spec, metadata_dir)
    payload = {
        "data_id": DATA_ID,
        "bundle_id": BUNDLE_ID,
        "source_key": spec.key,
        "source_spec": asdict(spec),
        "retrieved_url": retrieved_url,
        "retrieved_at_utc": _utc_now(),
        "raw_path": raw_path.as_posix(),
        "size_bytes": raw_path.stat().st_size,
        "sha256_file": _sha256_path(raw_path),
        "download_performed": download_performed,
        "schema_summary": schema_summary,
        "status": status,
        "non_claims": [
            "No annual HP TWh values are executable.",
            "No 2035 HP adoption value is signed.",
            "No D-004 acceptance, net-load, event, P(E), threshold, capacity-screen, or manuscript analysis is run.",
        ],
    }
    if schema_refresh_network_performed is not None:
        payload["schema_refresh_network_performed"] = schema_refresh_network_performed
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return metadata_path


def _write_checkpoint(checkpoint_path: Path, *, completed_sources: list[dict[str, Any]], next_source_key: str | None, status: str) -> None:
    payload = {
        "data_id": DATA_ID,
        "bundle_id": BUNDLE_ID,
        "status": status,
        "updated_at_utc": _utc_now(),
        "completed_sources": completed_sources,
        "next_source_key": next_source_key,
        "resume_command": r".\.venv\Scripts\python.exe data\get_hp_scaling.py --download --resume",
    }
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _checkpoint_completed(checkpoint_path: Path) -> dict[str, dict[str, Any]]:
    if not checkpoint_path.exists():
        return {}
    payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    return {entry["source_key"]: entry for entry in payload.get("completed_sources", [])}


def _completed_entry_matches(entry: dict[str, Any], raw_path: Path) -> bool:
    return raw_path.exists() and raw_path.stat().st_size == entry.get("size_bytes") and _sha256_path(raw_path) == entry.get("sha256_file")


def retrieve_hp_scaling_sources(*, raw_dir: Path, metadata_dir: Path, resume: bool = False) -> Path:
    """Retrieve/checksum approved D-013 public sources without producing values."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    hp_metadata_dir = metadata_dir / "hp_scaling"
    hp_metadata_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = hp_metadata_dir / CHECKPOINT_FILENAME
    completed_by_key = _checkpoint_completed(checkpoint_path) if resume else {}
    completed_sources: list[dict[str, Any]] = []
    metadata_paths: list[str] = []
    for index, spec in enumerate(HP_SCALING_SOURCES):
        raw_path = raw_dir / Path(spec.planned_raw_path).name
        checkpoint_entry = completed_by_key.get(spec.key)
        if resume and checkpoint_entry and _completed_entry_matches(checkpoint_entry, raw_path):
            completed_sources.append(checkpoint_entry)
            metadata_paths.append(checkpoint_entry["metadata_path"])
            continue
        if checkpoint_entry and not _completed_entry_matches(checkpoint_entry, raw_path):
            raise ValueError(f"Checkpoint mismatch for {spec.key}; remove or refresh raw file before resume")
        _write_checkpoint(checkpoint_path, completed_sources=completed_sources, next_source_key=spec.key, status="in_progress")
        if spec.key.startswith("cbs_"):
            source_payload = _cbs_table_payload(spec)
            raw_bytes = json.dumps(source_payload, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8")
            _write_atomic(raw_path, raw_bytes)
            schema_summary = _summarize_cbs_payload(spec, source_payload)
            retrieved_url = spec.url
        elif spec.key == "pbl_startanalyse_2025_alkmaar":
            raw_bytes = _read_url_bytes(spec.url, timeout_s=DOWNLOAD_TIMEOUT_S)
            _write_atomic(raw_path, raw_bytes)
            schema_summary = _summarize_pbl_zip(raw_path)
            retrieved_url = spec.url
        else:
            raise ValueError(f"Unsupported D-013 source key: {spec.key}")
        metadata_path = _write_source_metadata(spec=spec, metadata_dir=metadata_dir, raw_path=raw_path, retrieved_url=retrieved_url, schema_summary=schema_summary)
        entry = {
            "source_key": spec.key,
            "raw_path": raw_path.as_posix(),
            "metadata_path": metadata_path.as_posix(),
            "retrieved_url": retrieved_url,
            "size_bytes": raw_path.stat().st_size,
            "sha256_file": _sha256_path(raw_path),
            "completed_at_utc": _utc_now(),
        }
        completed_sources.append(entry)
        metadata_paths.append(metadata_path.as_posix())
        next_key = HP_SCALING_SOURCES[index + 1].key if index + 1 < len(HP_SCALING_SOURCES) else None
        _write_checkpoint(checkpoint_path, completed_sources=completed_sources, next_source_key=next_key, status="complete" if next_key is None else "in_progress")
    plan = build_hp_scaling_retrieval_plan()
    manifest_path = hp_metadata_dir / RETRIEVAL_MANIFEST_FILENAME
    manifest_payload = {
        "data_id": DATA_ID,
        "bundle_id": BUNDLE_ID,
        "created_at_utc": _utc_now(),
        "download_performed": True,
        "status": "D-013 sources retrieved/checksummed for PI review; values unsigned",
        "sources": completed_sources,
        "metadata_paths": metadata_paths,
        "checkpoint_path": checkpoint_path.as_posix(),
        "raw_files_ignored": True,
        "public_source_policy": plan["public_source_policy"],
        "hp001_component_traceability": plan["hp001_component_traceability"],
        "non_claims": [
            "No annual HP TWh values are executable.",
            "No 2035 HP adoption value is signed.",
            "No D-004 acceptance, paired-weather acceptance, net-load, event, P(E), threshold, capacity-screen, or manuscript analysis is run.",
        ],
    }
    manifest_path.write_text(json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path


def inspect_existing_hp_scaling_sources(*, raw_dir: Path, metadata_dir: Path) -> Path:
    """Refresh schema metadata from already retrieved D-013 raw files without network."""
    hp_metadata_dir = metadata_dir / "hp_scaling"
    hp_metadata_dir.mkdir(parents=True, exist_ok=True)
    refreshed: list[str] = []
    for spec in HP_SCALING_SOURCES:
        raw_path = raw_dir / Path(spec.planned_raw_path).name
        if not raw_path.exists():
            raise FileNotFoundError(f"Missing D-013 raw file for inspection: {raw_path}")
        if spec.key.startswith("cbs_"):
            source_payload = json.loads(raw_path.read_text(encoding="utf-8"))
            schema_summary = _summarize_cbs_payload(spec, source_payload)
        elif spec.key == "pbl_startanalyse_2025_alkmaar":
            schema_summary = _summarize_pbl_zip(raw_path)
        else:
            raise ValueError(f"Unsupported D-013 source key: {spec.key}")
        refreshed.append(
            _write_source_metadata(
                spec=spec,
                metadata_dir=metadata_dir,
                raw_path=raw_path,
                retrieved_url=spec.url,
                schema_summary=schema_summary,
                status="schema refreshed from existing raw file; HP scaling values remain unsigned",
                schema_refresh_network_performed=False,
            ).as_posix()
        )
    packet_path = hp_metadata_dir / "hp001_alkmaar_gm0361_schema_inspection_packet.json"
    packet = {
        "data_id": DATA_ID,
        "bundle_id": BUNDLE_ID,
        "created_at_utc": _utc_now(),
        "status": "schema inspection refreshed from existing raw files; values unsigned",
        "metadata_paths": refreshed,
        "raw_files_ignored": True,
        "network_performed": False,
        "non_claims": [
            "No annual HP TWh values are executable.",
            "No 2035 HP adoption value is signed.",
            "No D-004 acceptance, paired-weather acceptance, net-load, event, P(E), threshold, capacity-screen, or manuscript analysis is run.",
        ],
    }
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return packet_path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write or execute the HP-001 Alkmaar local scaling source route.")
    parser.add_argument("--metadata-dir", default="data/metadata")
    parser.add_argument("--write-plan", action="store_true", help="Write the approved retrieval/checksum/value route without downloading data.")
    parser.add_argument("--write-formula-packet", action="store_true", help="Write the proposed HP-001 formula/config decision packet without executable values.")
    parser.add_argument("--write-value-binding-packet", action="store_true", help="Write the proposed HP-001 value-binding readiness packet without executable values.")
    parser.add_argument("--write-readiness-checklist", action="store_true", help="Write the proposed HP-001 final-readiness approval checklist without executable values.")
    parser.add_argument("--write-executable-value-binding-packet", action="store_true", help="Write the proposed HP-001 executable value-binding decision packet without approving values.")
    parser.add_argument("--write-component-output-readiness-blocker", action="store_true", help="Write the proposed HP-001 IC-1 component-output readiness blocker packet without creating load artifacts.")
    parser.add_argument("--download", action="store_true", help="Retrieve/checksum the approved D-013 public sources; no values are produced.")
    parser.add_argument("--inspect-existing", action="store_true", help="Refresh schema metadata from existing ignored D-013 raw files without network or values.")
    parser.add_argument("--resume", action="store_true", help="Skip completed sources whose raw files match checkpoint byte size and SHA-256.")
    parser.add_argument("--raw-dir", default="data/raw/hp_scaling")
    args = parser.parse_args(argv)
    if args.download:
        path = retrieve_hp_scaling_sources(raw_dir=Path(args.raw_dir), metadata_dir=Path(args.metadata_dir), resume=args.resume)
    elif args.inspect_existing:
        path = inspect_existing_hp_scaling_sources(raw_dir=Path(args.raw_dir), metadata_dir=Path(args.metadata_dir))
    elif args.write_value_binding_packet:
        path = write_hp001_value_binding_readiness_packet(Path(args.metadata_dir))
    elif args.write_readiness_checklist:
        path = write_hp001_readiness_approval_checklist_packet(Path(args.metadata_dir))
    elif args.write_executable_value_binding_packet:
        path = write_hp001_executable_value_binding_decision_packet(Path(args.metadata_dir))
    elif args.write_component_output_readiness_blocker:
        path = write_hp001_component_output_readiness_blocker_packet(Path(args.metadata_dir))
    elif args.write_formula_packet:
        path = write_hp001_scaling_formula_config_decision_packet(Path(args.metadata_dir))
    else:
        path = write_hp_scaling_retrieval_plan(Path(args.metadata_dir))
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

