from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping, Sequence
from urllib import parse, request
import zipfile

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.sources import write_metadata
from src.hp_model import (
    hp001_profile_rebuild_preflight_blockers,
    require_hp001_profile_rebuild_preflight_manifest,
)

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
VALUE_BINDING_DECISION_CANDIDATES_FILENAME = "hp001_alkmaar_gm0361_value_binding_decision_candidates_blocker.json"
COLD_SPELL_ACCEPTANCE_DECISION_PACKET_FILENAME = "hp001_d004_cold_spell_acceptance_decision_packet.json"
PROFILE_ARTIFACT_CONSUMPTION_MANIFEST_TEMPLATE_FILENAME = "hp001_profile_artifact_consumption_manifest_template.json"
PROFILE_REBUILD_PREFLIGHT_TEMPLATE_FILENAME = "hp001_profile_artifact_rebuild_preflight_template.json"
PROFILE_REBUILD_RUNNER_OUTPUT_FILENAME = "hp001_profile_rebuild_runner_blocker_manifest.json"

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



def build_hp001_cold_spell_acceptance_decision_packet() -> dict[str, Any]:
    """Return the proposed HP/D-004 cold-spell tolerance decision packet."""
    return {
        "data_ids": ["D-003", "D-004"],
        "decision_packet_id": "E2-S3-HP001-COLD-SPELL-ACCEPTANCE-READINESS",
        "design_id": "E2-S3-COLD-SPELL-ACCEPTANCE-DESIGN",
        "created_utc": _utc_now(),
        "status": "proposed tolerance decision packet; no real paired acceptance run",
        "approved_foundation": {
            "d003_shape_cop_boundary": "HP-001 approves Dutch residential SFH/MFH space and DHW When2Heat shape/COP columns for internal source use.",
            "d004_source_member_use": "D004-SOURCE-MEMBER-ACCEPTANCE approves D-004 source/member use for internal first-screen work only.",
            "weather_contract": "WEATHER-001 requires HP and PV profiles to carry the same member_id, shared_weather_driver_id, source/provenance, content hash, and UTC/local calendar identity.",
            "cold_spell_design": "E2-S3-COLD-SPELL-ACCEPTANCE-DESIGN approves the diagnostic families but leaves numerical tolerances unsigned.",
        },
        "gate_separation": [
            {
                "gate": "source/member identity",
                "question": "Does the accepted D-004 member artifact preserve KNMI/PVGIS provenance and member checksums?",
                "status": "approved for internal first-screen use only by D004-SOURCE-MEMBER-ACCEPTANCE",
            },
            {
                "gate": "paired HP/PV weather equality",
                "question": "Do HP and PV outputs report the exact same WEATHER-001 realization before diagnostics are inspected?",
                "required_fields": [
                    "member_id",
                    "shared_weather_driver_id",
                    "source",
                    "first_timestamp_utc",
                    "last_timestamp_utc",
                    "n_timesteps",
                    "cadence_seconds",
                    "content_sha256",
                ],
                "status": "unsigned for final paired acceptance",
            },
            {
                "gate": "cold-spell numerical tolerances",
                "question": "Which explicit tolerances convert cold-window and near-freezing diagnostics into pass/fail evidence?",
                "status": "unsigned; this packet asks for PI decision only",
            },
        ],
        "diagnostics_to_report_before_final_acceptance": {
            "coldest_windows": [
                "coldest rolling 3-day mean temperature window with HP peak, max inside/outside load, mean/min COP",
                "coldest rolling 7-day mean temperature window with HP peak, max inside/outside load, mean/min COP",
            ],
            "near_freezing_defrost_risk": [
                "number of 15-minute steps inside the signed near-freezing temperature band around 0 degrees C",
                "mean/max HP load and mean/min COP inside that band",
                "maximum adjacent-step HP load change touching that band, normalized by annual HP peak load",
            ],
            "component_traceability": "report SFH/MFH and space/DHW source/COP columns separately before aggregation",
            "calendar_traceability": "report UTC/local first/last timestamp, timestep count, cadence, and WEATHER-001 identity records for HP and PV",
        },
        "pi_approval_options": [
            {
                "option": "A",
                "label": "approve fixture-runner structure only",
                "effect": "keeps code fail-closed and defers all numerical pass/fail tolerances; not enough for final D-004/HP acceptance",
            },
            {
                "option": "B",
                "label": "sign explicit numerical tolerance set",
                "fields_to_sign": [
                    "cold_window_days, proposed diagnostic windows: [3, 7]",
                    "near_freezing_band_c around 0 degrees C, for example [-1, 1] or [-2, 2]",
                    "max_outside_to_inside_peak_ratio for coldest-window load concentration",
                    "max_near_freezing_step_change_fraction_of_peak for defrost-risk discontinuity screening",
                    "whether coldest-window mean COP must be no higher than near-freezing mean COP",
                ],
                "effect": "allows a later real paired D-004/When2Heat acceptance run after annual/profile prerequisites are also met",
            },
            {
                "option": "C",
                "label": "amend or escalate tolerance design",
                "effect": "requires a new methods/register update before real acceptance can run",
            },
        ],
        "fail_closed_runner": {
            "runner": "src.hp_model.evaluate_hp001_cold_spell_acceptance",
            "tolerance_config": "src.hp_model.ColdSpellAcceptanceTolerances",
            "identity_check": "src.weather_model.assert_same_weather_realization",
            "unsigned_behavior": "raises before pass/fail diagnostics if cold_spell_tolerances approval_id is blank",
            "mismatch_behavior": "raises before tolerance evaluation if HP and PV WEATHER-001 identity records differ",
            "fixture_scope": "unit tests use synthetic profiles and fixture approval IDs only; no real D-004 acceptance result is produced",
        },
        "remaining_blockers_before_integrated_hp_use": [
            "signed annual HP value binding and 2035 adoption/electrification",
            "A-016 scenario-source consistency approval for the integrated EV/HP/PV 2035 case",
            "real paired HP/PV WEATHER-001 identity equality evidence over accepted D-004 members",
            "PI-signed cold-spell numerical tolerances",
            "real acceptance run and manifest after the above are signed",
        ],
        "non_claims": [
            "No annual HP TWh values are executable.",
            "No 2035 HP adoption/electrification value is signed.",
            "No D-004 paired-weather or cold-spell acceptance is signed or run.",
            "No net-load, event, P(E), threshold, capacity-screen, manuscript, or probability analysis is run.",
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
            "required_approval_state": {
                "executable_binding_allowed": True,
                "missing_approval_keys": [],
                "required_before_executable_binding": annual_keys,
                "approved_indicator_mapping_ids_must_include": ["D013-PBL-MAPPING", "A-015"],
                "component_annual_twh_status": "approved_for_executable_value_binding",
            },
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


def build_hp001_value_binding_decision_candidates_packet(
    *,
    raw_dir: Path,
    metadata_dir: Path,
    adoption_fractions: Sequence[float] = (0.25, 0.5, 0.75),
) -> dict[str, Any]:
    """Build unsigned HP-001 annual value-binding candidates or fail closed.

    The real-source path verifies D-013 raw artifacts against the retrieval
    manifest before extracting candidate values. Missing ignored raw files are
    represented as an explicit blocker packet rather than by reusing stale
    committed numbers.
    """
    source_artifacts, blocker_ids = _hp001_required_value_binding_raw_sources(raw_dir, metadata_dir)
    base_payload: dict[str, Any] = {
        "data_ids": ["D-003", "D-004", "D-013"],
        "decision_packet_id": "E2-S3-HP001-VALUE-BINDING-DECISION-CANDIDATES",
        "created_utc": _utc_now(),
        "status": "blocked_missing_or_unverified_d013_raw_sources; no value candidates emitted",
        "raw_dir": raw_dir.as_posix(),
        "metadata_dir": metadata_dir.as_posix(),
        "source_artifacts": source_artifacts,
        "blocker_ids": blocker_ids,
        "approved_foundation": {
            "hp001_boundary": "Residential SFH/MFH space heat plus domestic hot water; commercial heat excluded.",
            "indicator_mapping": {
                "approval_ids": ["D013-PBL-MAPPING", "A-015"],
                "scope": "Mapping only: _w residential, H23 space heat, H24 domestic hot water, H22 total diagnostic, unit [GJ/weq/jaar].",
            },
        },
        "source_columns": _hp001_value_binding_source_columns(),
        "equations": _hp001_value_binding_equations(),
        "approval_state": _unsigned_hp001_value_binding_approval_state(),
        "required_approval_ids_before_executable_config": [
            "value_column",
            "denominator",
            "unit_conversion",
            "sfh_mfh_split",
            "adoption_electrification",
            "scenario_source_consistency",
            "d004_paired_weather_acceptance",
            "cold_spell_tolerances",
        ],
        "non_claims": _hp001_value_binding_non_claims(),
    }
    if blocker_ids:
        base_payload.update(
            {
                "candidate_component_values_unsigned_before_2035_adoption": [],
                "adoption_electrification_options_unsigned": [],
                "unsigned_candidate_binding_record": _blocked_unsigned_value_binding_record(),
            }
        )
        return base_payload

    artifact_by_key = {artifact["source_key"]: artifact for artifact in source_artifacts}
    pbl = _extract_pbl_hp001_heat_demand_candidates(
        Path(artifact_by_key["pbl_startanalyse_2025_alkmaar"]["path"]),
        value_column="Referentie_2030",
        denominator_column="I11_woningequivalenten [Woning]",
    )
    cbs = _extract_cbs_hp001_count_share(
        Path(artifact_by_key["cbs_85035ned_dwelling_stock"]["path"])
    )
    components = _hp001_candidate_components_from_demands(pbl, cbs)
    adoption_options = _hp001_adoption_options(components, adoption_fractions)
    candidate_record = _unsigned_candidate_binding_record(components)
    base_payload.update(
        {
            "status": "proposed_value_binding_decision_candidates_not_executable",
            "blocker_ids": [
                "value_column_unsigned",
                "denominator_unsigned",
                "unit_conversion_unsigned",
                "sfh_mfh_split_unsigned",
                "adoption_electrification_unsigned",
                "scenario_source_consistency_unsigned",
                "d004_paired_weather_acceptance_unsigned",
                "cold_spell_tolerances_unsigned",
            ],
            "local_heat_demand_diagnostics_unsigned": pbl,
            "sfh_mfh_split_diagnostics_unsigned": cbs,
            "candidate_component_values_unsigned_before_2035_adoption": components,
            "adoption_electrification_options_unsigned": adoption_options,
            "recommended_pi_option_unsigned": {
                "value_column": "Referentie_2030",
                "denominator": "I11_woningequivalenten [Woning]",
                "unit_conversion": "divide GJ/year by 3,600,000 to obtain TWh/year",
                "sfh_mfh_split": "CBS 85035NED count-share split",
                "adoption_electrification": "PI must select or provide a signed 2035 HP service fraction or equivalent count route; numeric options here are scenario candidates only.",
            },
            "unsigned_candidate_binding_record": candidate_record,
        }
    )
    return base_payload


def write_hp001_value_binding_decision_candidates_packet(
    *,
    metadata_dir: Path,
    raw_dir: Path,
) -> Path:
    """Write the proposed or blocked HP-001 value-binding candidate packet."""
    target_dir = metadata_dir / "hp_scaling"
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / VALUE_BINDING_DECISION_CANDIDATES_FILENAME
    payload = build_hp001_value_binding_decision_candidates_packet(
        raw_dir=raw_dir,
        metadata_dir=metadata_dir,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_hp001_cold_spell_acceptance_decision_packet(metadata_dir: Path) -> Path:
    """Write the proposed HP/D-004 cold-spell tolerance decision packet."""
    target_dir = metadata_dir / "hp_scaling"
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / COLD_SPELL_ACCEPTANCE_DECISION_PACKET_FILENAME
    payload = build_hp001_cold_spell_acceptance_decision_packet()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def build_hp001_profile_artifact_consumption_manifest_template() -> dict[str, Any]:
    """Return a fail-closed template for future HP profile artifact consumption."""
    annual_keys = [
        "value_column",
        "denominator",
        "unit_conversion",
        "sfh_mfh_split",
        "adoption_electrification",
    ]
    final_keys = annual_keys + [
        "scenario_source_consistency",
        "d004_paired_weather_acceptance",
        "cold_spell_tolerances",
    ]
    return {
        "manifest_id": "E2-S3-HP001-PROFILE-ARTIFACT-CONSUMPTION-MANIFEST",
        "created_utc": _utc_now(),
        "status": "proposed_template_not_approved_for_integrated_consumption",
        "purpose": "Define the metadata a future HP profile artifact must carry before any integrated consumer may use it.",
        "future_required_status": "approved_for_integrated_hp_profile_consumption",
        "profile_artifact": {
            "path": "data/processed/hp_profiles/<future_signed_hp001_profile>.npz",
            "sha256": "<future profile artifact SHA-256>",
            "n_timesteps": 35040,
            "cadence_seconds": 900,
            "electric_power_unit": "kW",
            "thermal_power_unit": "kW",
            "first_timestamp_utc": "<future WEATHER-001 member first UTC timestamp>",
            "last_timestamp_utc": "<future WEATHER-001 member last UTC timestamp>",
        },
        "weather_identity": {
            "shared_weather_driver_id": "<future accepted D-004 shared_weather_driver_id>",
            "member_id": "<future accepted D-004 member_id>",
            "source": "<future accepted D-004 source/provenance label>",
            "content_sha256": "<future WEATHER-001 member content SHA-256>",
            "n_timesteps": 35040,
            "cadence_seconds": 900,
            "identity_rule": "Must match the PV profile member exactly before integrated use.",
        },
        "component_traceability": [
            {"building_class": "SFH", "end_use": "space", "heat_column": "NL_heat_profile_space_SFH", "cop_column": "NL_COP_ASHP_radiator", "annual_heat_demand_twh": "<future signed value>", "provenance": {"annual_scaling_status": "signed", "annual_scaling_approval_id": "<future approval>"}},
            {"building_class": "MFH", "end_use": "space", "heat_column": "NL_heat_profile_space_MFH", "cop_column": "NL_COP_ASHP_radiator", "annual_heat_demand_twh": "<future signed value>", "provenance": {"annual_scaling_status": "signed", "annual_scaling_approval_id": "<future approval>"}},
            {"building_class": "SFH", "end_use": "water", "heat_column": "NL_heat_profile_water_SFH", "cop_column": "NL_COP_ASHP_water", "annual_heat_demand_twh": "<future signed value>", "provenance": {"annual_scaling_status": "signed", "annual_scaling_approval_id": "<future approval>"}},
            {"building_class": "MFH", "end_use": "water", "heat_column": "NL_heat_profile_water_MFH", "cop_column": "NL_COP_ASHP_water", "annual_heat_demand_twh": "<future signed value>", "provenance": {"annual_scaling_status": "signed", "annual_scaling_approval_id": "<future approval>"}},
        ],
        "approval_ids": {},
        "missing_approval_keys": final_keys,
        "validator": "src.hp_model.require_hp001_profile_artifact_consumption_manifest",
        "non_claims": [
            "No annual HP TWh values are executable.",
            "No 2035 HP adoption/electrification value is signed.",
            "No D-004 paired-weather or cold-spell acceptance is signed or run.",
            "No net-load, event, P(E), threshold, capacity-screen, manuscript, or probability analysis is run.",
        ],
    }


def build_hp001_profile_rebuild_preflight_template() -> dict[str, Any]:
    """Return a fail-closed template for a future HP profile rebuild request."""
    readiness = build_hp001_readiness_approval_checklist_packet()
    required_approval_keys = readiness["fail_closed_handoff"]["required_final_approval_keys"]
    return {
        "packet_id": "E2-S3-HP001-PROFILE-REBUILD-PREFLIGHT",
        "created_utc": _utc_now(),
        "status": "proposed_rebuild_preflight_template_not_executable",
        "future_required_manifest_status": "approved_for_hp001_profile_rebuild_preflight",
        "purpose": "Define the signed metadata a future HP profile rebuild/checksum run must carry before generating HP artifacts.",
        "validator": "src.hp_model.require_hp001_profile_rebuild_preflight_manifest",
        "approved_foundation": readiness["approved_foundation"],
        "required_approval_keys_before_rebuild": required_approval_keys,
        "preflight_manifest_template": {
            "status": "approved_for_hp001_profile_rebuild_preflight",
            "approval_ids": {key: f"<future signed {key} approval id>" for key in required_approval_keys},
            "source_artifacts": {
                "when2heat_source": {
                    "data_id": "D-003",
                    "path": "data/raw/when2heat/<future checked When2Heat file>",
                    "sha256": "<future D-003 SHA-256>",
                    "provenance": "When2Heat/OPSD 2023-07-27 CSV accepted by PI",
                },
                "weather_member": {
                    "data_id": "D-004",
                    "path": "data/processed/weather_pv/<future WEATHER-001 member artifact>",
                    "sha256": "<future WEATHER-001 member SHA-256>",
                    "provenance": "D-004 accepted paired weather member",
                },
                "value_binding_record": {
                    "data_id": "D-013",
                    "path": "data/metadata/hp_scaling/<future signed value-binding record>.json",
                    "sha256": "<future value-binding record SHA-256>",
                    "provenance": "PI-signed HP-001 annual value/adoption binding",
                },
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
            "output_plan": {
                "profile_artifact_path": "data/processed/hp_profiles/<future_signed_hp001_profile>.npz",
                "profile_manifest_path": "data/metadata/hp_scaling/<future_signed_hp001_profile_manifest>.json",
                "checksum_manifest_path": "data/metadata/hp_scaling/<future_signed_hp001_profile_checksum_manifest>.json",
                "n_timesteps": 35040,
                "cadence_seconds": 900,
                "component_count": 4,
                "electric_power_unit": "kW",
            },
            "unresolved_blocker_ids": [],
        },
        "current_blockers": [
            "annual HP TWh values and 2035 adoption/electrification/service fractions are unsigned",
            "A-016 scenario-source consistency is not signed for a real integrated case",
            "D-004 final paired-weather acceptance is not signed",
            "cold-spell numerical tolerances and real acceptance evidence are unsigned",
            "no real HP profile artifact rebuild/checksum command has approved source artifacts",
        ],
        "non_claims": [
            "No HP profile artifact is generated or approved.",
            "No executable annual HP values are created.",
            "No D-004 paired-weather or cold-spell final acceptance is signed or run.",
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


def write_hp001_profile_artifact_consumption_manifest_template(metadata_dir: Path) -> Path:
    """Write the proposed future HP profile consumption manifest template."""
    target_dir = metadata_dir / "hp_scaling"
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / PROFILE_ARTIFACT_CONSUMPTION_MANIFEST_TEMPLATE_FILENAME
    payload = build_hp001_profile_artifact_consumption_manifest_template()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path



def write_hp001_profile_rebuild_preflight_template(metadata_dir: Path) -> Path:
    """Write the proposed future HP profile rebuild/checksum preflight template."""
    target_dir = metadata_dir / "hp_scaling"
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / PROFILE_REBUILD_PREFLIGHT_TEMPLATE_FILENAME
    payload = build_hp001_profile_rebuild_preflight_template()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _extract_profile_rebuild_preflight_manifest(payload: object) -> tuple[dict[str, Any], str]:
    if not isinstance(payload, dict):
        return {}, "invalid_json_payload"
    nested = payload.get("preflight_manifest_template")
    if isinstance(nested, dict):
        return nested, "template_packet_preflight_manifest_template"
    return payload, "direct_preflight_manifest"


def build_hp001_profile_rebuild_runner_manifest(
    preflight_manifest_path: Path,
    *,
    output_manifest_path: Path | None = None,
    request_id: str = "hp001_profile_rebuild_preflight_check",
    repository_root: Path = Path("."),
) -> dict[str, Any]:
    """Return the metadata-only HP profile rebuild preflight runner result."""
    raw_payload = json.loads(preflight_manifest_path.read_text(encoding="utf-8"))
    preflight_manifest, input_kind = _extract_profile_rebuild_preflight_manifest(raw_payload)
    blocker_ids = list(hp001_profile_rebuild_preflight_blockers(preflight_manifest))
    accepted = not blocker_ids
    if accepted:
        # Keep this runner as a handoff gate only; future profile generation must
        # call a separate signed artifact builder after this manifest passes.
        require_hp001_profile_rebuild_preflight_manifest(preflight_manifest)

    return {
        "packet_id": "E2-S3-HP001-PROFILE-REBUILD-RUNNER-SCAFFOLD",
        "created_utc": _utc_now(),
        "request_id": str(request_id).strip() or "hp001_profile_rebuild_preflight_check",
        "status": "accepted_preflight_handoff_no_profile_generation" if accepted else "blocked_fail_closed_no_profile_rebuild",
        "accepted_for_profile_rebuild_handoff": accepted,
        "profile_generation_performed": False,
        "validator": "data.get_hp_scaling.build_hp001_profile_rebuild_runner_manifest",
        "preflight_validator": "src.hp_model.require_hp001_profile_rebuild_preflight_manifest",
        "input_manifest": {
            "path": preflight_manifest_path.as_posix(),
            "sha256": _sha256_path(preflight_manifest_path),
            "size_bytes": preflight_manifest_path.stat().st_size,
            "kind": input_kind,
            "preflight_status": str(preflight_manifest.get("status", "")) if isinstance(preflight_manifest, dict) else "",
        },
        "output_manifest_path": output_manifest_path.as_posix() if output_manifest_path is not None else None,
        "blocker_ids": blocker_ids,
        "blocker_count": len(blocker_ids),
        "intended_handoff_shape": _hp001_profile_rebuild_handoff_shape(preflight_manifest) if accepted else None,
        "code_identity": _hp001_runner_code_identity(repository_root),
        "non_claims": [
            "No HP profile artifact is generated or approved.",
            "No executable annual HP values are created.",
            "No 2035 HP adoption/electrification/service fraction is approved.",
            "No D-004 paired-weather or cold-spell final acceptance is signed or run.",
            "No net-load, event, P(E), threshold, capacity-screen, manuscript, or probability analysis is run.",
        ],
    }


def write_hp001_profile_rebuild_runner_manifest(
    preflight_manifest_path: Path,
    output_manifest_path: Path,
    *,
    request_id: str = "hp001_profile_rebuild_preflight_check",
    repository_root: Path = Path("."),
) -> Path:
    """Write the fail-closed runner result for a future HP profile rebuild request."""
    output_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_hp001_profile_rebuild_runner_manifest(
        preflight_manifest_path,
        output_manifest_path=output_manifest_path,
        request_id=request_id,
        repository_root=repository_root,
    )
    output_manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_manifest_path


def write_default_hp001_profile_rebuild_runner_manifest(
    metadata_dir: Path,
    *,
    preflight_manifest_path: Path | None = None,
    request_id: str = "hp001_profile_rebuild_preflight_check",
    repository_root: Path = Path("."),
) -> Path:
    """Write the runner output for the committed or supplied preflight manifest."""
    target_dir = metadata_dir / "hp_scaling"
    target_dir.mkdir(parents=True, exist_ok=True)
    input_path = preflight_manifest_path or target_dir / PROFILE_REBUILD_PREFLIGHT_TEMPLATE_FILENAME
    output_path = target_dir / PROFILE_REBUILD_RUNNER_OUTPUT_FILENAME
    return write_hp001_profile_rebuild_runner_manifest(
        input_path,
        output_path,
        request_id=request_id,
        repository_root=repository_root,
    )


def _hp001_profile_rebuild_handoff_shape(preflight_manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_artifacts": preflight_manifest.get("source_artifacts", {}),
        "weather_identity": preflight_manifest.get("weather_identity", {}),
        "paired_pv_weather_identity": preflight_manifest.get("paired_pv_weather_identity", {}),
        "output_plan": preflight_manifest.get("output_plan", {}),
        "next_runner_boundary": "future signed HP profile artifact builder; not implemented by this scaffold",
    }


def _hp001_runner_code_identity(repository_root: Path) -> dict[str, Any]:
    root = repository_root.resolve()
    tracked_files = ("data/get_hp_scaling.py", "src/hp_model.py")
    return {
        "git_head": _git_head(root),
        "tracked_file_sha256": {
            path: _sha256_path(root / path) for path in tracked_files if (root / path).exists()
        },
    }


def _git_head(repository_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip() or "unknown"

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


def _hp001_required_value_binding_raw_sources(
    raw_dir: Path,
    metadata_dir: Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    required_keys = {"cbs_85035ned_dwelling_stock", "pbl_startanalyse_2025_alkmaar"}
    retrieval_manifest_path = metadata_dir / "hp_scaling" / RETRIEVAL_MANIFEST_FILENAME
    blocker_ids: list[str] = []
    manifest_by_key: dict[str, dict[str, Any]] = {}
    if retrieval_manifest_path.exists():
        manifest = json.loads(retrieval_manifest_path.read_text(encoding="utf-8"))
        manifest_by_key = {
            str(source.get("source_key", "")).strip(): source
            for source in manifest.get("sources", [])
            if str(source.get("source_key", "")).strip()
        }
    else:
        blocker_ids.append("retrieval_manifest_missing")

    artifacts: list[dict[str, Any]] = []
    for spec in HP_SCALING_SOURCES:
        if spec.key not in required_keys:
            continue
        raw_path = raw_dir / Path(spec.planned_raw_path).name
        manifest_entry = manifest_by_key.get(spec.key)
        if manifest_entry is None:
            blocker_ids.append(f"retrieval_manifest_source_missing:{spec.key}")
        artifact: dict[str, Any] = {
            "source_key": spec.key,
            "data_id": DATA_ID,
            "path": raw_path.as_posix(),
            "url": spec.url,
            "role": spec.role,
            "license_or_terms": spec.license_or_terms,
            "planned_raw_path": spec.planned_raw_path,
            "manifest_path": retrieval_manifest_path.as_posix(),
            "verified_against_retrieval_manifest": False,
        }
        if not raw_path.exists():
            blocker_ids.append(f"source_artifact_missing:{spec.key}")
            artifacts.append(artifact)
            continue
        size_bytes = raw_path.stat().st_size
        sha256_file = _sha256_path(raw_path)
        artifact.update({"size_bytes": size_bytes, "sha256_file": sha256_file})
        if manifest_entry is not None:
            if int(manifest_entry.get("size_bytes", -1)) != size_bytes:
                blocker_ids.append(f"source_artifact_size_mismatch:{spec.key}")
            if str(manifest_entry.get("sha256_file", "")).strip() != sha256_file:
                blocker_ids.append(f"source_artifact_checksum_mismatch:{spec.key}")
            if int(manifest_entry.get("size_bytes", -1)) == size_bytes and str(
                manifest_entry.get("sha256_file", "")
            ).strip() == sha256_file:
                artifact["verified_against_retrieval_manifest"] = True
        artifacts.append(artifact)
    return artifacts, list(dict.fromkeys(blocker_ids))


def _hp001_value_binding_source_columns() -> dict[str, Any]:
    return {
        "pbl_startanalyse_2025": {
            "archive_member": "Alkmaar_strategie.csv",
            "delimiter": ";",
            "decimal": ",",
            "value_column_candidate": "Referentie_2030",
            "denominator_column_candidate": "I11_woningequivalenten [Woning]",
            "indicator_column": "Code_Indicator",
            "unit_column": "Eenheid",
            "space_indicator": "H23_Vraag_RV_w",
            "water_indicator": "H24_Vraag_TW_w",
            "diagnostic_total_indicator": "H22_Vraag_totaal_w",
            "approved_inferred_unit": "[GJ/weq/jaar]",
            "mapping_approval_boundary": "D013-PBL-MAPPING/A-015 approves indicator semantics only, not value-column use, denominator use, unit conversion, annual values, or adoption.",
        },
        "cbs_85035ned": {
            "period_candidate": "2026JJ00",
            "count_column": "BeginstandWoningvoorraad_1",
            "sfh_woningtype": "ZW10290",
            "mfh_woningtype": "ZW10340",
            "split_rule_candidate": "SFH/MFH count share by Alkmaar dwelling stock type",
        },
    }


def _hp001_value_binding_equations() -> dict[str, str]:
    return {
        "local_heat_gj_per_year_by_end_use": "sum_b intensity_GJ_per_weq_year[b,end_use] * I11_woningequivalenten_woning[b]",
        "local_heat_twh_per_year_by_end_use": "local_heat_gj_per_year_by_end_use / 3_600_000",
        "class_allocation_before_adoption": "component_TWh[class,end_use] = end_use_TWh[end_use] * CBS_count_share[class]",
        "hp_served_candidate_after_adoption": "hp_component_TWh[class,end_use,scenario] = component_TWh[class,end_use] * candidate_2035_service_fraction",
    }


def _unsigned_hp001_value_binding_approval_state() -> dict[str, Any]:
    annual_keys = [
        "value_column",
        "denominator",
        "unit_conversion",
        "sfh_mfh_split",
        "adoption_electrification",
    ]
    return {
        "approved_indicator_mapping_ids": ["D013-PBL-MAPPING", "A-015"],
        "required_before_executable_binding": annual_keys,
        "approval_ids": {},
        "missing_approval_keys": annual_keys,
        "executable_binding_allowed": False,
    }


def _hp001_value_binding_non_claims() -> list[str]:
    return [
        "No annual HP TWh values are approved or executable.",
        "No 2035 HP adoption/electrification/service fraction is signed.",
        "No A-016 scenario-source consistency approval is signed for HP integrated use.",
        "No D-004 paired-weather or cold-spell final acceptance is signed or run.",
        "No HP profile artifact, component output, net-load, event, P(E), threshold, capacity-screen, manuscript, or probability result is produced.",
    ]


def _blocked_unsigned_value_binding_record() -> dict[str, Any]:
    return {
        "status": "blocked_missing_or_unverified_d013_raw_sources_not_approved_for_executable_use",
        "approval_state": _unsigned_hp001_value_binding_approval_state(),
        "source_inputs_under_review": {
            "value_column": "Referentie_2030",
            "denominator_column": "I11_woningequivalenten [Woning]",
            "gj_to_twh_divisor": 3_600_000.0,
            "sfh_mfh_split_rule": "cbs_85035ned_count_share",
            "adoption_electrification_scenario": "unsigned_2035_hp_service_fraction_or_count_pending",
        },
        "component_value_drafts_unsigned_before_2035_adoption": [],
    }


def _unsigned_candidate_binding_record(components: Sequence[dict[str, Any]]) -> dict[str, Any]:
    return {
        "decision_packet_id": "E2-S3-HP001-VALUE-BINDING-DECISION-CANDIDATES",
        "status": "proposed_candidate_values_not_approved_for_executable_use",
        "approval_state": _unsigned_hp001_value_binding_approval_state(),
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
        "component_value_drafts_unsigned_before_2035_adoption": list(components),
    }


def _extract_pbl_hp001_heat_demand_candidates(
    pbl_zip_path: Path,
    *,
    value_column: str,
    denominator_column: str,
) -> dict[str, Any]:
    with zipfile.ZipFile(pbl_zip_path) as archive:
        member = next(
            (name for name in archive.namelist() if name.endswith("Alkmaar_strategie.csv")),
            None,
        )
        if member is None:
            raise ValueError("PBL ZIP does not contain Alkmaar_strategie.csv")
        rows = list(
            csv.DictReader(
                io.StringIO(archive.read(member).decode("utf-8-sig")),
                delimiter=";",
            )
        )
    fieldnames = set(rows[0]) if rows else set()
    required_columns = {"Code_Indicator", "Eenheid", value_column, denominator_column}
    missing = required_columns - fieldnames
    if missing:
        raise ValueError(f"PBL Alkmaar_strategie.csv missing required columns: {tuple(sorted(missing))}")
    indicators = {
        "space": "H23_Vraag_RV_w",
        "water": "H24_Vraag_TW_w",
        "residential_total_diagnostic": "H22_Vraag_totaal_w",
    }
    outputs: dict[str, Any] = {
        "source_member": member,
        "value_column": value_column,
        "denominator_column": denominator_column,
        "gj_to_twh_divisor": 3_600_000.0,
        "indicators": {},
    }
    for label, indicator in indicators.items():
        selected = [row for row in rows if str(row.get("Code_Indicator", "")).strip() == indicator]
        total_weq = sum(_parse_decimal_number(row[denominator_column]) for row in selected)
        total_gj = sum(
            _parse_decimal_number(row[value_column]) * _parse_decimal_number(row[denominator_column])
            for row in selected
        )
        units = sorted({str(row.get("Eenheid", "")).strip() for row in selected if str(row.get("Eenheid", "")).strip()})
        outputs["indicators"][label] = {
            "code_indicator": indicator,
            "row_count": len(selected),
            "unit_values": units,
            "denominator_sum_weq": total_weq,
            "thermal_demand_gj_per_year": total_gj,
            "thermal_demand_twh_per_year": total_gj / 3_600_000.0,
        }
    space_twh = outputs["indicators"]["space"]["thermal_demand_twh_per_year"]
    water_twh = outputs["indicators"]["water"]["thermal_demand_twh_per_year"]
    total_twh = outputs["indicators"]["residential_total_diagnostic"]["thermal_demand_twh_per_year"]
    outputs["diagnostic_note"] = (
        "H22 is retained as a residential-total diagnostic; any gap from H23+H24 remains outside HP-001 "
        "unless the PI signs an amended boundary."
    )
    outputs["diagnostic_total_minus_space_water_twh"] = total_twh - space_twh - water_twh
    return outputs


def _extract_cbs_hp001_count_share(cbs_json_path: Path) -> dict[str, Any]:
    payload = json.loads(cbs_json_path.read_text(encoding="utf-8"))
    odata = payload.get("odata", {}) if isinstance(payload, dict) else {}
    rows = odata.get("TypedDataSet", {}).get("response", {}).get("value", [])
    type_rows = odata.get("Woningtype", {}).get("response", {}).get("value", [])
    type_titles = {
        str(row.get("Key", "")).strip(): str(row.get("Title", "")).strip()
        for row in type_rows
        if isinstance(row, dict)
    }
    period = "2026JJ00"
    count_column = "BeginstandWoningvoorraad_1"
    mapping = {"SFH": "ZW10290", "MFH": "ZW10340"}
    counts: dict[str, float] = {}
    for building_class, code in mapping.items():
        matches = [
            row for row in rows
            if str(row.get("Woningtype", "")).strip() == code
            and str(row.get("Perioden", "")).strip() == period
        ]
        if len(matches) != 1:
            raise ValueError(f"CBS 85035NED fixture/source expected one {building_class} {period} row")
        counts[building_class] = _parse_decimal_number(matches[0][count_column])
    total = sum(counts.values())
    if total <= 0:
        raise ValueError("CBS SFH/MFH count denominator must be positive")
    return {
        "table": "85035NED",
        "period": period,
        "count_column": count_column,
        "woningtype_crosswalk": {
            building_class: {"code": code, "title": type_titles.get(code, code)}
            for building_class, code in mapping.items()
        },
        "counts": counts,
        "shares": {building_class: count / total for building_class, count in counts.items()},
        "total_count": total,
    }


def _hp001_candidate_components_from_demands(
    pbl: Mapping[str, Any],
    cbs: Mapping[str, Any],
) -> list[dict[str, Any]]:
    indicators = pbl["indicators"]
    shares = cbs["shares"]
    component_specs = [
        ("sfh_space", "SFH", "space", "NL_heat_profile_space_SFH", "NL_COP_ASHP_radiator"),
        ("mfh_space", "MFH", "space", "NL_heat_profile_space_MFH", "NL_COP_ASHP_radiator"),
        ("sfh_water", "SFH", "water", "NL_heat_profile_water_SFH", "NL_COP_ASHP_water"),
        ("mfh_water", "MFH", "water", "NL_heat_profile_water_MFH", "NL_COP_ASHP_water"),
    ]
    components: list[dict[str, Any]] = []
    for component_id, building_class, end_use, shape_column, cop_column in component_specs:
        base_twh = float(indicators[end_use]["thermal_demand_twh_per_year"])
        component_twh = base_twh * float(shares[building_class])
        components.append(
            {
                "component_id": component_id,
                "building_class": building_class,
                "end_use": end_use,
                "annual_heat_twh": component_twh,
                "shape_column": shape_column,
                "cop_column": cop_column,
                "annual_twh_status": "unsigned_candidate_local_heat_demand_before_2035_adoption",
                "provenance": {
                    "source_status": "D-013 raw artifacts checksum-verified locally for candidate extraction",
                    "value_column": "Referentie_2030",
                    "denominator_column": "I11_woningequivalenten [Woning]",
                    "class_split_rule": "cbs_85035ned_count_share",
                    "unit_conversion": "GJ/year divided by 3,600,000",
                },
            }
        )
    return components


def _hp001_adoption_options(
    components: Sequence[dict[str, Any]],
    adoption_fractions: Sequence[float],
) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    for fraction in adoption_fractions:
        value = float(fraction)
        if value <= 0 or value > 1:
            raise ValueError("candidate adoption/service fractions must be in (0, 1]")
        options.append(
            {
                "scenario_label": f"candidate_service_fraction_{value:g}",
                "service_fraction": value,
                "status": "unsigned_scenario_candidate_not_executable",
                "source_provenance": "PI scenario candidate only; no public 2035 adoption source is signed by this packet.",
                "component_values_after_fraction": [
                    {
                        "component_id": component["component_id"],
                        "building_class": component["building_class"],
                        "end_use": component["end_use"],
                        "annual_heat_twh_after_fraction": float(component["annual_heat_twh"]) * value,
                    }
                    for component in components
                ],
            }
        )
    return options


def _parse_decimal_number(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return 0.0
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    return float(text)

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
    parser.add_argument("--write-value-binding-candidates", action="store_true", help="Write checksum-verified or fail-closed HP-001 value-binding decision candidates without approving values.")
    parser.add_argument("--write-cold-spell-acceptance-packet", action="store_true", help="Write the proposed HP/D-004 cold-spell tolerance decision packet without running acceptance.")
    parser.add_argument("--write-profile-consumption-template", action="store_true", help="Write the proposed HP-001 profile artifact consumption manifest template without approving values.")
    parser.add_argument("--write-profile-rebuild-preflight", action="store_true", help="Write the proposed HP-001 profile rebuild/checksum preflight template without creating load artifacts.")
    parser.add_argument("--run-profile-rebuild-preflight", action="store_true", help="Run the metadata-only HP-001 profile rebuild preflight and write a blocker/output manifest.")
    parser.add_argument("--profile-rebuild-preflight-manifest", default=None, help="Preflight manifest or committed template packet to validate for a future HP profile rebuild.")
    parser.add_argument("--profile-rebuild-runner-output", default=None, help="Output path for the HP profile rebuild runner blocker/output manifest.")
    parser.add_argument("--request-id", default="hp001_profile_rebuild_preflight_check", help="Request identity recorded in runner/checkpoint metadata.")
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
    elif args.write_value_binding_candidates:
        path = write_hp001_value_binding_decision_candidates_packet(
            metadata_dir=Path(args.metadata_dir),
            raw_dir=Path(args.raw_dir),
        )
    elif args.write_cold_spell_acceptance_packet:
        path = write_hp001_cold_spell_acceptance_decision_packet(Path(args.metadata_dir))
    elif args.write_profile_consumption_template:
        path = write_hp001_profile_artifact_consumption_manifest_template(Path(args.metadata_dir))
    elif args.write_profile_rebuild_preflight:
        path = write_hp001_profile_rebuild_preflight_template(Path(args.metadata_dir))
    elif args.run_profile_rebuild_preflight:
        metadata_dir = Path(args.metadata_dir)
        preflight_manifest = Path(args.profile_rebuild_preflight_manifest) if args.profile_rebuild_preflight_manifest else None
        output_path = Path(args.profile_rebuild_runner_output) if args.profile_rebuild_runner_output else metadata_dir / "hp_scaling" / PROFILE_REBUILD_RUNNER_OUTPUT_FILENAME
        path = write_hp001_profile_rebuild_runner_manifest(
            preflight_manifest or metadata_dir / "hp_scaling" / PROFILE_REBUILD_PREFLIGHT_TEMPLATE_FILENAME,
            output_path,
            request_id=args.request_id,
            repository_root=Path("."),
        )
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
