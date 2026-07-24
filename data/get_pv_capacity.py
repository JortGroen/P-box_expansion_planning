from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib import parse, request

D014_PACKET_NAME = "d014_pv_capacity_source_value_packet.json"
D014_PACKET_ID = "D014-PV-CAPACITY-SOURCE-VALUE-PACKET"
D014_CBS_ANCHOR_EVIDENCE_NAME = "d014_cbs_85005ned_alkmaar_gm0361_anchor_evidence.json"
D014_CBS_ANCHOR_EVIDENCE_ID = "D014-CBS-PV-CAPACITY-ANCHOR-EVIDENCE"
D014_STATISTICAL_ORIENTATION_TILT_NAME = "d014_pv_statistical_orientation_tilt_packet.json"
D014_STATISTICAL_ORIENTATION_TILT_ID = "D014-PV-STATISTICAL-ORIENTATION-TILT-PACKET"
D014_ORIENTATION_TILT_SOURCE_CHOICE_NAME = "d014_pv_orientation_tilt_source_choice_packet.json"
D014_ORIENTATION_TILT_SOURCE_CHOICE_ID = "D014-PV-ORIENTATION-TILT-SOURCE-CHOICE-PACKET"
D014_ORIENTATION_TILT_VALUE_CHOICE_NAME = "d014_pv_orientation_tilt_value_choice_packet.json"
D014_ORIENTATION_TILT_VALUE_CHOICE_ID = "D014-PV-ORIENTATION-TILT-VALUE-CHOICE-PACKET"
D014_DATA_ID = "D-014"
CBS_TABLE_ID = "85005NED"
CBS_ODATA_BASE = f"https://opendata.cbs.nl/ODataApi/OData/{CBS_TABLE_ID}"
CBS_DATA_OVERHEID_PAGE = (
    "https://data.overheid.nl/en/dataset/16612-zonnestroom--vermogen-en-vermogensklasse--"
    "bedrijven-en-woningen--regio"
)
CBS_STATLINE_PAGE = "https://www.cbs.nl/nl-nl/cijfers/detail/85005NED"
II3050_REPORT_URL = "https://www.netbeheernederland.nl/publicatie/ii3050-eindrapport"
II3050_APPENDICES_URL = "https://www.netbeheernederland.nl/publicatie/bijlagen-ii3050-eindrapport"
THREEDBAG_API_DOCS_URL = "https://api.3dbag.nl/api.html"
THREEDBAG_COPYRIGHT_URL = "https://docs.3dbag.nl/en/copyright/"
PVGIS_API_DOCS_URL = "https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5/api-non-interactive-service_en"
PVLIB_MODELCHAIN_URL = "https://pvlib-python.readthedocs.io/en/stable/user_guide/modeling_topics/modelchain.html"
KILLINGER_2018_DOI_URL = "https://doi.org/10.1016/j.solener.2018.08.051"
KILLINGER_2018_UU_URL = "https://research-portal.uu.nl/en/publications/on-the-search-for-representative-characteristics-of-pv-systems-da/"
RAMADHANI_2023_DOI_URL = "https://doi.org/10.1016/j.seja.2023.100036"
UTRECHT_PV_FORECASTING_DOI_URL = "https://doi.org/10.1016/j.renene.2021.09.067"
JRC_DBSM_NATURE_URL = "https://www.nature.com/articles/s41560-025-01947-x"
ALKMAAR_GM_CODE = "GM0361"
PLANNING_YEAR = 2035


def build_cbs_odata_url(entity: str, params: Mapping[str, object] | None = None) -> str:
    """Build a CBS 85005NED OData URL without making a network request."""
    if not entity or "/" in entity or "?" in entity:
        raise ValueError("entity must be a simple CBS OData entity name")
    url = f"{CBS_ODATA_BASE}/{entity}"
    if not params:
        return url
    return f"{url}?{parse.urlencode(params)}"


def build_d014_cbs_anchor_query_urls() -> dict[str, str]:
    """Return the exact CBS OData queries for the Alkmaar PV-capacity anchor."""
    return {
        "table_infos": build_cbs_odata_url("TableInfos"),
        "data_properties": build_cbs_odata_url("DataProperties"),
        "periods": build_cbs_odata_url("Perioden"),
        "sector_and_capacity_class_codes": build_cbs_odata_url("SectorEnVermogensklasse"),
        "alkmaar_region": build_cbs_odata_url("RegioS", {"$filter": "Key eq 'GM0361'"}),
        "alkmaar_rows": build_cbs_odata_url("TypedDataSet", {"$filter": "RegioS eq 'GM0361'"}),
    }


def fetch_d014_cbs_anchor_raw_bundle(timeout_seconds: int = 30) -> dict[str, Any]:
    """Fetch the small CBS OData evidence bundle for Alkmaar without choosing a value."""
    urls = build_d014_cbs_anchor_query_urls()
    responses: dict[str, Any] = {}
    for key, url in urls.items():
        with request.urlopen(url, timeout=timeout_seconds) as response:
            responses[key] = json.loads(response.read().decode("utf-8-sig"))
    return {
        "source_bundle_id": "d014_cbs_85005ned_alkmaar_gm0361_anchor_raw_v1",
        "retrieved_utc": _now_utc_iso(),
        "table_id": CBS_TABLE_ID,
        "alkmaar_geography_key": ALKMAAR_GM_CODE,
        "query_urls": urls,
        "responses": responses,
    }


def write_d014_cbs_anchor_raw_bundle(
    raw_dir: str | Path = "data/raw/pv_capacity",
    *,
    timeout_seconds: int = 30,
) -> Path:
    """Retrieve and write the ignored raw CBS Alkmaar evidence bundle."""
    directory = Path(raw_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / D014_CBS_ANCHOR_EVIDENCE_NAME
    bundle = fetch_d014_cbs_anchor_raw_bundle(timeout_seconds=timeout_seconds)
    path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def build_d014_cbs_capacity_anchor_evidence_packet(raw_bundle_path: str | Path) -> dict[str, Any]:
    """Build the committed metadata packet from an ignored CBS raw bundle.

    The packet exposes exact source rows for PI review. It intentionally does
    not choose the period, field, DC/AC convention, II3050 growth factor, or
    executable installed-capacity value.
    """
    raw_path = Path(raw_bundle_path)
    raw_bytes = raw_path.read_bytes()
    raw_bundle = json.loads(raw_bytes.decode("utf-8"))
    responses = raw_bundle["responses"]
    table_info = responses["table_infos"]["value"][0]
    data_properties = responses["data_properties"]["value"]
    periods = responses["periods"]["value"]
    sectors = responses["sector_and_capacity_class_codes"]["value"]
    region_rows = responses["alkmaar_region"]["value"]
    alkmaar_rows = responses["alkmaar_rows"]["value"]
    fields = [item for item in data_properties if item.get("Type") == "Topic"]
    period_by_key = {item["Key"]: item for item in periods}
    sector_by_key = {item["Key"]: item for item in sectors}

    def row_choice(row: Mapping[str, Any], role: str) -> dict[str, Any]:
        period = period_by_key[str(row["Perioden"])]
        sector = sector_by_key[str(row["SectorEnVermogensklasse"])]
        return {
            "choice_role": role,
            "row_id": row["ID"],
            "period_key": row["Perioden"],
            "period_title": str(period.get("Title", "")).strip(),
            "period_status": period.get("Status"),
            "sector_key": row["SectorEnVermogensklasse"],
            "sector_title": sector.get("Title"),
            "installations_count": row.get("Installaties_1"),
            "panel_capacity_kwp": row.get("OpgesteldVermogenVanZonnepanelen_2"),
            "inverter_capacity_kw": row.get("OpgesteldVermogenOmvormers_3"),
            "production_million_kwh": row.get("ProductieVanZonnestroom_4"),
            "executable_status": "candidate_only_unsigned",
        }

    def find_row(period_key: str, sector_key: str) -> Mapping[str, Any]:
        for row in alkmaar_rows:
            if row["Perioden"] == period_key and row["SectorEnVermogensklasse"] == sector_key:
                return row
        raise ValueError(f"missing CBS row for {period_key} {sector_key}")

    candidate_rows = [
        row_choice(find_row("2023JJ00", "E007161"), "latest_definitive_all_activity_and_homes_candidate"),
        row_choice(find_row("2023JJ00", "E007037"), "latest_definitive_homes_only_sensitivity_candidate"),
        row_choice(find_row("2025JJ00", "E007161"), "latest_available_provisional_all_activity_and_homes_candidate"),
        row_choice(find_row("2025JJ00", "E007037"), "latest_available_provisional_homes_only_sensitivity_candidate"),
    ]
    return {
        "packet_id": D014_CBS_ANCHOR_EVIDENCE_ID,
        "data_id": D014_DATA_ID,
        "status": "retrieved_source_evidence_values_unsigned",
        "created_utc": _now_utc_iso(),
        "download_performed": True,
        "raw_data_committed": False,
        "approved_route_decision": "PV-CAP-001",
        "source_value_packet_id": D014_PACKET_ID,
        "capacity_route_boundary": "CBS Alkmaar anchor evidence only; II3050/scenario growth factor remains separate and unsigned",
        "pv_param_boundary": "PV-PARAM-001 remains proposed/fail-closed; this packet does not approve PR=0.86, direct-GHI, plane-of-array conversion, or PV output",
        "pv_orient_boundary": "PV-ORIENT-001 lightweight statistical orientation/tilt scope preserved; no roof/building/3DBAG/PV-map retrieval",
        "source": {
            "table_id": CBS_TABLE_ID,
            "title": table_info.get("Title"),
            "owner": "Centraal Bureau voor de Statistiek",
            "license": "CC-BY 4.0 per data.overheid dataset page recorded in D-014; verify again before publication use",
            "odata_root": CBS_ODATA_BASE,
            "statline_page": CBS_STATLINE_PAGE,
            "data_overheid_page": CBS_DATA_OVERHEID_PAGE,
            "modified": table_info.get("Modified"),
            "period_coverage": table_info.get("Period"),
            "frequency": table_info.get("Frequency"),
            "summary": table_info.get("Summary"),
        },
        "raw_bundle": {
            "path": raw_path.as_posix(),
            "sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "size_bytes": len(raw_bytes),
            "retrieved_utc": raw_bundle.get("retrieved_utc"),
            "query_urls": raw_bundle.get("query_urls"),
        },
        "schema": {
            "topic_fields": [
                {
                    "key": item.get("Key"),
                    "title": item.get("Title"),
                    "unit": item.get("Unit"),
                    "description": item.get("Description"),
                    "role_for_d014": (
                        "candidate_capacity_field" if item.get("Key") in {"OpgesteldVermogenVanZonnepanelen_2", "OpgesteldVermogenOmvormers_3"}
                        else "diagnostic_or_not_municipal_capacity_anchor"
                    ),
                }
                for item in fields
            ],
            "periods": periods,
            "sector_and_capacity_class_codes": sectors,
            "alkmaar_region_rows": region_rows,
            "alkmaar_row_count": len(alkmaar_rows),
        },
        "candidate_value_choices_for_pi_review": {
            "period_candidates": [
                "2023JJ00 latest definitive full-year candidate",
                "2025JJ00 latest available nader voorlopige candidate only if PI accepts provisional values",
                "2024JJ00 provisional diagnostic or sensitivity candidate",
            ],
            "sector_category_candidates": [
                "E007161 all economic activity and homes as the municipal total anchor candidate",
                "E007037 homes-only sensitivity if PV is restricted to residential nodes",
                "T001081 business/economic activity context only unless PI signs a split",
                "A050176/A050177/A050178/A050179 size/placement categories for diagnostics or later allocation, not automatic totals",
            ],
            "capacity_field_candidates": [
                "OpgesteldVermogenVanZonnepanelen_2 in kWp: panel/DC peak-capacity candidate",
                "OpgesteldVermogenOmvormers_3 in kW: inverter/AC grid-facing candidate, available for Alkmaar from 2022 onward",
                "Installaties_1 count: diagnostic/allocation plausibility only",
                "ProductieVanZonnestroom_4 million kWh: not available at municipal rows in the retrieved evidence",
            ],
            "exact_row_candidates": candidate_rows,
            "all_retrieved_alkmaar_rows": alkmaar_rows,
        },
        "pi_approval_keys_before_executable_use": [
            "cbs_raw_bundle_sha256",
            "alkmaar_geography_key",
            "cbs_source_period_key",
            "cbs_sector_category_key",
            "cbs_capacity_field_key",
            "capacity_unit_and_dc_ac_convention",
            "ii3050_source_file_or_page_checksum",
            "ii3050_scenario_column",
            "ii3050_growth_factor_value",
            "node_allocation_rule",
            "statistical_orientation_tilt_distribution_source",
            "statistical_orientation_tilt_distribution_weights",
            "PV-PARAM-001_or_amended_conversion_decision",
        ],
        "non_claims": [
            "No executable PV installed-capacity value is approved.",
            "No CBS period, sector/category row, capacity field, unit convention, or DC/AC convention is selected as final.",
            "No II3050 scenario column or growth factor is retrieved or approved by this packet.",
            "No per-node PV allocation is approved.",
            "No statistical orientation/tilt values or PV-PARAM conversion treatment are approved.",
            "No roof, building, 3DBAG, or PV-map geometry source is retrieved or used.",
            "No net-load, event detection, P(E), threshold analysis, capacity screen, manuscript result, or final PV output is produced.",
        ],
    }


def retrieve_d014_cbs_capacity_anchor_evidence(
    *,
    metadata_dir: str | Path = "data/metadata",
    raw_dir: str | Path = "data/raw/pv_capacity",
    timeout_seconds: int = 30,
) -> Path:
    """Retrieve CBS Alkmaar source evidence and write committed metadata."""
    raw_path = write_d014_cbs_anchor_raw_bundle(raw_dir, timeout_seconds=timeout_seconds)
    directory = Path(metadata_dir) / "weather_pv"
    directory.mkdir(parents=True, exist_ok=True)
    metadata_path = directory / D014_CBS_ANCHOR_EVIDENCE_NAME
    metadata_path.write_text(
        json.dumps(build_d014_cbs_capacity_anchor_evidence_packet(raw_path), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return metadata_path


def build_d014_pv_capacity_source_value_packet() -> dict[str, Any]:
    """Return the proposed D-014 source/value packet without raw retrieval.

    The packet is intentionally fail-closed: it identifies concrete sources and
    schema/value decisions for PI review but does not select or compute an
    executable installed-capacity value.
    """
    cbs_filter_template = (
        "RegioS eq 'GM0361' and Perioden eq '<PERIOD_KEY>' and "
        "SectorEnVermogensklasse eq '<SECTOR_AND_SIZE_KEY>'"
    )
    return {
        "packet_id": D014_PACKET_ID,
        "data_id": D014_DATA_ID,
        "created_utc": _now_utc_iso(),
        "status": "proposed_source_value_packet_no_raw_download_no_executable_values",
        "download_performed": False,
        "raw_data_committed": False,
        "governing_decisions": {
            "approved_route": "PV-CAP-001",
            "conversion_parameters": "PV-PARAM-001 remains proposed and fail-closed",
            "scenario_consistency": "A-016 requires scenario-source consistency before executable integrated analysis",
        },
        "approved_route_semantics": {
            "capacity_route": (
                "Anchor current/local PV installed capacity to CBS Alkmaar photovoltaic capacity, "
                "then scale to the frozen 2035 planning layer with a signed II3050/scenario growth factor."
            ),
            "pv_param_boundary": (
                "PV-PARAM-001 decides the irradiance-to-kW conversion once signed installed_capacity_kw "
                "is supplied; per PV-ORIENT-001, first-experiment orientation/tilt must come from a "
                "signed typical/statistical distribution rather than per-roof geometry. It does not decide "
                "the CBS source year, II3050 growth factor, capacity convention, or node allocation."
            ),
        },
        "primary_cbs_anchor_source": {
            "source_id": "cbs_85005ned_alkmaar_pv_capacity_anchor",
            "table_id": CBS_TABLE_ID,
            "title": "Zonnestroom; vermogen en vermogensklasse, bedrijven en woningen, regio",
            "owner": "Centraal Bureau voor de Statistiek",
            "license": "CC-BY 4.0 per data.overheid dataset page; verify again at retrieval time",
            "source_pages": {
                "data_overheid": CBS_DATA_OVERHEID_PAGE,
                "statline": CBS_STATLINE_PAGE,
                "odata_root": CBS_ODATA_BASE,
            },
            "planned_raw_path": f"data/raw/pv_capacity/d014_cbs_{CBS_TABLE_ID.lower()}_alkmaar_gm0361.json",
            "planned_metadata_path": (
                f"data/metadata/weather_pv/d014_cbs_{CBS_TABLE_ID.lower()}_alkmaar_gm0361_metadata.json"
            ),
            "planned_checkpoint_path": "data/metadata/weather_pv/d014_pv_capacity_retrieval_checkpoint.json",
            "schema_probe_urls": {
                "table_infos": build_cbs_odata_url("TableInfos"),
                "data_properties": build_cbs_odata_url("DataProperties"),
                "sector_and_capacity_class_codes": build_cbs_odata_url("SectorEnVermogensklasse"),
                "regions": build_cbs_odata_url("RegioS"),
                "periods": build_cbs_odata_url("Perioden"),
            },
            "alkmaar_row_filter_template": cbs_filter_template,
            "alkmaar_row_query_template": build_cbs_odata_url(
                "TypedDataSet",
                {
                    "$filter": cbs_filter_template,
                },
            ),
            "geography_candidates": [
                {
                    "key": ALKMAAR_GM_CODE,
                    "label": "Alkmaar municipality",
                    "recommendation": "primary local anchor for consistency with EV-007A, D-004, and HP local-scaling proxy",
                }
            ],
            "period_candidates_for_pi_review": [
                {
                    "period_key": "latest_definitive_full_year_from_Perioden",
                    "recommendation": "preferred anchor because CBS notes 2019-2023 definitive in the current table description",
                    "blocked_until_schema_inspection": True,
                },
                {
                    "period_key": "latest_available_full_year_from_Perioden",
                    "recommendation": "sensitivity only if PI accepts provisional/nader voorlopige values",
                    "blocked_until_pi_approval": True,
                },
            ],
            "field_candidates_for_schema_inspection": [
                {
                    "concept": "panelvermogen_kwp_or_mwp",
                    "description": "CBS installed panel capacity / paneelvermogen field; recommended default if PI wants DC peak capacity",
                    "executable_status": "candidate_key_must_be_confirmed_from_DataProperties",
                },
                {
                    "concept": "omvormervermogen_kw_or_mw",
                    "description": "CBS installed inverter capacity / omvormervermogen field; candidate if PI wants AC or grid-facing convention",
                    "executable_status": "candidate_key_must_be_confirmed_from_DataProperties",
                },
                {
                    "concept": "aantal_installaties",
                    "description": "installation-count field for diagnostics and allocation plausibility only, not a capacity substitute",
                    "executable_status": "diagnostic_only",
                },
            ],
            "sector_size_candidates_for_pi_review": [
                "all sectors and all PV size classes as primary municipal anchor",
                "residential/woningen only as sensitivity if the PV layer is restricted to residential load nodes",
                "small <=15 kWp versus large >15 kWp split as allocation diagnostic, not automatic node allocation",
            ],
        },
        "ii3050_growth_factor_source": {
            "source_id": "ii3050_edition2_pv_growth_factor_2035",
            "owner": "Netbeheer Nederland",
            "license": "public web publication/citation route; no raw redistributed file in this packet",
            "source_pages": {
                "main_report": II3050_REPORT_URL,
                "appendices": II3050_APPENDICES_URL,
            },
            "planned_raw_path": "data/raw/pv_capacity/d014_ii3050_eindrapport_bijlagen.pdf",
            "planned_metadata_path": "data/metadata/weather_pv/d014_ii3050_pv_growth_factor_metadata.json",
            "candidate_table": "II3050 edition 2 appendices, Table A.1, row 'Zon PV* GW' for 2035 scenario columns",
            "growth_factor_formula_under_review": (
                "growth_factor_2035 = ii3050_selected_2035_pv_gw / ii3050_reference_or_anchor_year_pv_gw"
            ),
            "pi_choices_required": [
                "select II3050 scenario column or scenario family for the 2035 planning layer",
                "select denominator for scaling: II3050 reference year, CBS anchor year, or a documented crosswalk",
                "decide whether the growth factor applies uniformly to Alkmaar or needs a local/regional modifier",
            ],
            "numeric_growth_factor_approved": False,
        },
        "capacity_value_binding_under_review": {
            "candidate_formula": (
                "installed_capacity_kw = cbs_alkmaar_capacity_kw_selected_convention * signed_ii3050_growth_factor_2035"
            ),
            "capacity_convention_candidates": [
                "panelvermogen/DC kWp converted to kW-like installed_capacity_kw for PV-PARAM only if PI signs DC convention",
                "omvormervermogen/AC kW as grid-facing installed_capacity_kw only if PI signs AC convention",
                "dual-record DC and AC capacities with a signed DC/AC mapping before conversion",
            ],
            "allocation_candidates": [
                "uniform or load-proportional allocation across eligible load nodes, unsigned and not recommended without spatial evidence",
                "CBS/DEGO/Zonnedakje or building evidence for later spatial allocation only if concrete data and license are registered",
                "typical/statistical orientation-and-tilt distribution for first-experiment PV conversion under PV-ORIENT-001; source, bins, weights, and formula treatment remain unsigned",
            ],
            "approval_keys_required_before_executable_use": [
                "cbs_source_file_checksum",
                "alkmaar_geography_key",
                "cbs_source_period_key",
                "cbs_capacity_field_key",
                "capacity_unit_and_dc_ac_convention",
                "ii3050_source_file_or_page_checksum",
                "ii3050_scenario_column",
                "ii3050_growth_factor_value",
                "node_allocation_rule",
                "statistical_orientation_tilt_distribution_source",
                "statistical_orientation_tilt_distribution_weights",
                "PV-PARAM-001_or_amended_conversion_decision",
            ],
        },
        "optional_geometry_allocation_workflow": {
            "primary_status": "deferred_until_after_first_real_experiment",
            "first_experiment_scope": "use signed typical/statistical orientation-and-tilt distribution only; no per-building or per-roof geometry",
            "recommended_next_packet": "statistical orientation/tilt distribution packet before executable PV-PARAM-001 use",
            "sources": [
                {
                    "source_id": "3dbag_roof_geometry",
                    "role": "future post-first-experiment roof-plane tilt/aspect/orientation workflow only; not the first-experiment route",
                    "url": THREEDBAG_API_DOCS_URL,
                    "license": "CC BY 4.0 per 3DBAG documentation; credit required",
                    "boundary": "does not provide installed PV capacity totals or approve PV-PARAM conversion",
                },
                {
                    "source_id": "dego_or_zonnedakje_source_discovery",
                    "role": "optional spatial allocation/source discovery if downloadable Alkmaar data, license, and provenance are registered",
                    "boundary": "not primary executable source in this packet",
                },
            ],
        },
        "retrieval_plan_after_pi_approval": {
            "estimated_wall_time": "under 15 minutes for CBS OData JSON and one II3050 PDF/page checksum under normal network conditions",
            "long_run_notice_required_now": False,
            "checkpoint_resume_behavior": (
                "write one checkpoint record after each source: planned URL, output path, size, sha256, retrieval UTC, "
                "and source schema hash; resume skips files whose size and sha256 match the checkpoint"
            ),
            "planned_commands": [
                "./.venv/Scripts/python.exe data/get_pv_capacity.py --write-d014-source-value-packet",
                "future after PI approval: ./.venv/Scripts/python.exe data/get_pv_capacity.py --retrieve-approved-d014-sources --resume",
            ],
            "long_run_notice_if_scope_expands": "LONG-RUN NOTICE\nTask: E2.S4 D-014 PV capacity source retrieval\nProcess: retrieve CBS 85005NED Alkmaar records, II3050 appendices, and approved statistical orientation/tilt source metadata; do not retrieve per-roof geometry before the first real experiment\nEstimated wall time: <estimate from pilot; send before launch if above 15 minutes>\nResource impact: network plus small local JSON/PDF writes; no raw files committed\nCheckpoint plan: data/metadata/weather_pv/d014_pv_capacity_retrieval_checkpoint.json after each source\nResume procedure: rerun data/get_pv_capacity.py --retrieve-approved-d014-sources --resume; verified checksums are skipped",
        },
        "fail_closed_non_claims": [
            "No raw D-014 data has been downloaded by this packet.",
            "No numeric PV installed capacity is approved.",
            "No CBS period, field, unit, or DC/AC convention is approved.",
            "No II3050 scenario column or growth factor value is approved.",
            "No per-node PV allocation is approved.",
            "No statistical orientation/tilt source, bins, weights, or conversion treatment are approved.",
            "PV-PARAM-001 remains proposed and the simple PR=0.86/direct-GHI route is not approved by this packet.",
            "No net-load, event detection, P(E), threshold analysis, capacity screen, or manuscript result is run.",
        ],
    }


def build_d014_pv_statistical_orientation_tilt_packet() -> dict[str, Any]:
    """Return a proposed lightweight orientation/tilt workflow packet.

    The first real experiment should not require per-building roof extraction.
    This packet proposes a statistical class route that remains fail-closed
    until its source, class definitions, weights, and conversion model are signed.
    """
    approval_keys = [
        "statistical_orientation_tilt_source",
        "orientation_class_bins",
        "tilt_class_bins",
        "class_weight_values",
        "capacity_weighting_convention",
        "dc_ac_capacity_convention",
        "pv_conversion_formula_or_pvlib_route",
        "losses_temperature_clipping_parameters",
        "pvgis_or_other_sanity_criteria",
        "d014_capacity_value_artifact",
        "node_allocation_rule",
    ]
    return {
        "packet_id": D014_STATISTICAL_ORIENTATION_TILT_ID,
        "data_id": D014_DATA_ID,
        "created_utc": _now_utc_iso(),
        "status": "proposed_statistical_orientation_tilt_packet_no_raw_download_no_executable_values",
        "download_performed": False,
        "raw_data_committed": False,
        "first_experiment_scope": {
            "statistical_orientation_tilt_classes_only": True,
            "building_or_roof_level_extraction_in_scope": False,
            "specific_3dbag_per_roof_workflow_in_first_experiment": False,
            "future_improvement": "A later sensitivity may use 3DBAG or similar roof-plane extraction after explicit PI approval, retrieval/checksum registration, and a longer-run plan.",
        },
        "governing_boundaries": {
            "capacity_route": "PV-CAP-001 remains separate: CBS Alkmaar PV-capacity anchor scaled to 2035 with signed II3050/scenario growth factor.",
            "capacity_values": "No numeric D-014 capacity, growth factor, DC/AC convention, or node allocation is approved here.",
            "conversion_parameters": "PV-PARAM-001 remains proposed/fail-closed; PR=0.86/direct-GHI is not approved by this packet.",
            "weather_route": "WEATHER-001 and D004-SOURCE-MEMBER-ACCEPTANCE provide the realized KNMI weather members; PVGIS remains sanity/provenance only.",
        },
        "source_route_comparison": [
            {
                "source_id": "pvgis_reference_or_literature_class_template",
                "role": "candidate source for typical/statistical orientation and tilt class definitions or sanity checks",
                "url": PVGIS_API_DOCS_URL,
                "can_support": [
                    "reference PV geometry/configuration context",
                    "qualitative seasonal and peak sanity checks after class weights are signed",
                ],
                "cannot_support": [
                    "realized WEATHER-001 path",
                    "installed capacity total",
                    "Alkmaar building-level orientation distribution without another signed source",
                ],
            },
            {
                "source_id": "pvlib_or_equivalent_conversion_route",
                "role": "candidate future implementation route for class-based plane-of-array conversion if approved",
                "url": PVLIB_MODELCHAIN_URL,
                "can_support": [
                    "transparent class-wise conversion once tilt, azimuth, losses, and weather inputs are signed",
                    "replacement for the disputed direct-GHI/PR proposal if the PI chooses it",
                ],
                "cannot_support": [
                    "source data or class weights",
                    "installed capacity or node allocation",
                ],
            },
            {
                "source_id": "cbs_85005ned_and_ii3050_capacity_route",
                "role": "capacity total and 2035 scaling route only, not geometry",
                "url": CBS_ODATA_BASE,
                "can_support": [
                    "local Alkmaar capacity anchor and diagnostic installation counts after D-014 retrieval/value approval",
                    "capacity to distribute across signed statistical classes",
                ],
                "cannot_support": [
                    "orientation or tilt class weights",
                    "PV conversion performance parameters",
                ],
            },
            {
                "source_id": "3dbag_deferred_roof_geometry",
                "role": "future improvement only, not first-experiment input",
                "url": THREEDBAG_API_DOCS_URL,
                "can_support": [
                    "later roof-plane sensitivity or validation if PI approves a heavier workflow",
                ],
                "cannot_support": [
                    "first real experiment orientation/tilt extraction",
                    "installed PV capacity total or conversion parameters by itself",
                ],
            },
        ],
        "proposed_artifact_interface": {
            "artifact_id": "d014_pv_statistical_orientation_tilt_config",
            "executable_allowed_now": False,
            "required_fields_before_executable_use": [
                "approval_status",
                "approval_ids",
                "class_table",
                "orientation_basis_degrees",
                "tilt_basis_degrees",
                "class_weight_basis",
                "weights_sum_to_one",
                "installed_capacity_kw_input_reference",
                "capacity_convention",
                "pv_conversion_config_id",
                "source_provenance",
            ],
            "class_table_required_columns": [
                "class_id",
                "azimuth_degrees_from_south_or_declared_basis",
                "tilt_degrees",
                "capacity_weight_fraction",
                "source_or_assumption_id",
            ],
            "approval_keys_required_before_executable_use": approval_keys,
        },
        "pi_approval_keys_before_executable_use": approval_keys,
        "pi_questions": [
            "Which source should define the statistical orientation/tilt class bins and weights for the first experiment?",
            "Should class weights be capacity-weighted, installation-count-weighted, or area-weighted?",
            "Should PV-PARAM-001 be amended from direct GHI to a class-wise plane-of-array route before first executable PV use?",
            "Can node allocation be deferred to a simple signed capacity-allocation rule separate from orientation/tilt classes?",
        ],
        "non_claims": [
            "No statistical class bins or weights are approved.",
            "No 3DBAG, building-level, roof-level, or location-level geometry extraction is implemented for the first experiment.",
            "No raw D-014 capacity, PV-map, or geometry data was downloaded.",
            "No numeric PV capacity, capacity convention, per-node allocation, PR=0.86, or final conversion formula is approved.",
            "No net-load, event detection, P(E), threshold run, capacity screen, manuscript result, or final paired HP/PV acceptance is produced.",
        ],
    }


def build_d014_pv_orientation_tilt_source_choice_packet() -> dict[str, Any]:
    """Return a proposed source-choice packet for statistical PV geometry.

    This packet identifies candidate evidence for a typical/statistical
    orientation-and-tilt distribution. It does not select numeric class bins,
    class weights, conversion treatment, capacity values, or allocation.
    """
    approval_keys = [
        "orientation_tilt_distribution_source_id",
        "source_access_and_license_or_citation_boundary",
        "orientation_class_bin_definitions",
        "tilt_class_bin_definitions",
        "class_weight_values",
        "class_weight_basis_capacity_installation_area_or_assumption",
        "azimuth_angle_convention",
        "tilt_angle_convention",
        "pv_conversion_treatment_for_classes",
        "pv_param_001_or_amended_conversion_decision",
        "d014_capacity_value_artifact",
        "node_allocation_rule",
    ]
    return {
        "packet_id": D014_ORIENTATION_TILT_SOURCE_CHOICE_ID,
        "data_id": D014_DATA_ID,
        "created_utc": _now_utc_iso(),
        "status": "proposed_source_choice_packet_no_raw_download_no_executable_values",
        "download_performed": False,
        "raw_data_committed": False,
        "approved_scope_decision": "PV-ORIENT-001",
        "first_experiment_scope": {
            "statistical_orientation_tilt_classes_only": True,
            "heavy_building_level_pv_map_deferred": True,
            "roof_or_location_level_extraction_allowed_now": False,
            "specific_3dbag_per_roof_workflow_allowed_now": False,
        },
        "recommended_source_order_for_pi_review": [
            {
                "rank": 1,
                "source_id": "killinger_2018_pv_system_characteristics",
                "recommendation": "primary empirical source candidate if the needed country/cluster distribution parameters are accessible and citable",
                "source_backing": "published PV-system metadata analysis across Europe and other regions; includes tilt, azimuth, capacity, yield, and distribution-function approximations",
                "assumption_boundary": "must still extract or cite the exact Netherlands-relevant class parameters before executable use",
            },
            {
                "rank": 2,
                "source_id": "utrecht_rooftop_pv_observed_systems",
                "recommendation": "local Dutch plausibility and validation context, not primary weights unless the PI accepts the small/regional sample",
                "source_backing": "published study of rooftop PV systems in Utrecht province with observed orientation and tilt ranges/distribution figure",
                "assumption_boundary": "may not represent Alkmaar or 2035 fleet composition without PI judgement",
            },
            {
                "rank": 3,
                "source_id": "ramadhani_2023_rooftop_uncertainty_method",
                "recommendation": "method template for statistical azimuth/tilt uncertainty if empirical Netherlands weights are unavailable",
                "source_backing": "open-access rooftop-facet uncertainty study using distributions for hosting-capacity modelling",
                "assumption_boundary": "Swedish roof-facet evidence is not a Dutch installed-PV distribution; using it would be an explicit transfer assumption",
            },
            {
                "rank": 4,
                "source_id": "pi_declared_simple_class_prior",
                "recommendation": "fallback only if the PI wants a transparent assumption rather than more source work before the first experiment",
                "source_backing": "assumption-only until PI signs bins and weights",
                "assumption_boundary": "must be labelled as expert/PI prior, not empirical source evidence",
            },
        ],
        "source_candidates": [
            {
                "source_id": "killinger_2018_pv_system_characteristics",
                "title": "On the search for representative characteristics of PV systems",
                "url": KILLINGER_2018_DOI_URL,
                "secondary_url": KILLINGER_2018_UU_URL,
                "source_type": "peer_reviewed_empirical_pv_system_metadata",
                "can_support": [
                    "typical/statistical tilt and azimuth distribution source candidate",
                    "capacity/yield metadata context for weighting decisions",
                    "distribution-function route rather than per-building geometry",
                ],
                "cannot_support": [
                    "Alkmaar-specific installed capacity total",
                    "node allocation",
                    "automatic executable bins or weights before extraction and PI signoff",
                ],
                "current_packet_role": "source candidate only; no values extracted",
            },
            {
                "source_id": "utrecht_rooftop_pv_observed_systems",
                "title": "Operational day-ahead solar power forecasting for aggregated PV systems with a varying spatial distribution",
                "url": UTRECHT_PV_FORECASTING_DOI_URL,
                "source_type": "peer_reviewed_dutch_regional_observed_pv_context",
                "can_support": [
                    "Dutch rooftop PV orientation/tilt plausibility checks",
                    "sanity bounds for class choices if the PI signs use of a small regional sample",
                ],
                "cannot_support": [
                    "national or Alkmaar fleet-wide class weights by itself",
                    "capacity convention or 2035 scaling",
                    "building-level extraction under PV-ORIENT-001",
                ],
                "current_packet_role": "local context candidate only; no values extracted",
            },
            {
                "source_id": "ramadhani_2023_rooftop_uncertainty_method",
                "title": "On the properties of residential rooftop azimuth and tilt uncertainties for photovoltaic power generation modeling and hosting capacity analysis",
                "url": RAMADHANI_2023_DOI_URL,
                "source_type": "open_access_rooftop_uncertainty_method_template",
                "can_support": [
                    "statistical distribution-method template for hosting-capacity style PV studies",
                    "source-backed argument that orientation/tilt uncertainty matters",
                ],
                "cannot_support": [
                    "Dutch installed-PV class weights without a transfer assumption",
                    "first-experiment building-level roof extraction",
                    "D-014 capacity value or PV conversion parameters",
                ],
                "current_packet_role": "method candidate only; transfer assumption would need PI approval",
            },
            {
                "source_id": "pvgis_reference",
                "title": "PVGIS API/reference configurations",
                "url": PVGIS_API_DOCS_URL,
                "source_type": "solar_resource_and_pv_reference_tool",
                "can_support": [
                    "class-wise qualitative sanity checks after class bins are signed",
                    "comparison with normalized PVGIS outputs for selected orientations if approved",
                ],
                "cannot_support": [
                    "statistical class weights",
                    "realized WEATHER-001 path",
                    "installed capacity or node allocation",
                ],
                "current_packet_role": "sanity/provenance only",
            },
            {
                "source_id": "pvlib_conversion_candidate",
                "title": "pvlib modelchain or equivalent transparent PV conversion",
                "url": PVLIB_MODELCHAIN_URL,
                "source_type": "implementation_route_not_data_source",
                "can_support": [
                    "future class-wise plane-of-array conversion if dependency/formula is approved",
                    "transparent separation of weather, geometry, module, and inverter assumptions",
                ],
                "cannot_support": [
                    "orientation/tilt source data or weights",
                    "PV capacity values",
                    "approval of PR=0.86/direct-GHI",
                ],
                "current_packet_role": "conversion implementation candidate only",
            },
            {
                "source_id": "jrc_dbsm_or_3dbag_deferred_building_level_work",
                "title": "JRC/DBSM, 3DBAG, or other building-level PV-map routes",
                "url": JRC_DBSM_NATURE_URL,
                "source_type": "post_first_experiment_roof_or_building_geometry_context",
                "can_support": [
                    "later sensitivity, validation, or source-discovery work after explicit approval",
                ],
                "cannot_support": [
                    "first real experiment orientation/tilt source under PV-ORIENT-001",
                    "near-term per-building allocation or roof extraction",
                ],
                "current_packet_role": "explicitly deferred future improvement",
            },
        ],
        "proposed_class_artifact_requirements": {
            "artifact_id": "d014_pv_orientation_tilt_class_source_choice",
            "executable_allowed_now": False,
            "required_columns_after_pi_signoff": [
                "class_id",
                "orientation_bin_label",
                "azimuth_angle_convention",
                "tilt_bin_label",
                "representative_azimuth_degrees_or_formula",
                "representative_tilt_degrees_or_formula",
                "capacity_weight_fraction",
                "weight_basis",
                "source_id",
                "source_value_trace",
            ],
            "required_invariants_after_pi_signoff": [
                "class weights are finite and nonnegative",
                "class weights sum to one within tolerance signed by PI",
                "azimuth and tilt conventions are explicit",
                "all values trace to a source row/table/figure or to an approved assumption ID",
                "capacity totals still come from D-014/PV-CAP-001 rather than the class source",
                "PV conversion remains blocked until PV-PARAM-001 or an amended decision is signed",
            ],
        },
        "source_backing_summary": {
            "source_backed_now": [
                "candidate literature/source identities and roles",
                "PV-ORIENT-001 scope excluding heavy roof-level work",
                "D-014/PV-CAP-001 separation of capacity from orientation/tilt",
            ],
            "assumption_or_pi_choice_needed": [
                "which candidate source to use as primary",
                "exact class bins and representative angles",
                "exact class weights and weighting basis",
                "whether statistical classes modify conversion through plane-of-array factors or remain metadata until a later PV-PARAM amendment",
                "whether a PI-declared prior is acceptable if empirical weights are not extracted before the first experiment",
            ],
        },
        "pi_approval_keys_before_executable_use": approval_keys,
        "non_claims": [
            "No source candidate is selected as final.",
            "No orientation or tilt class bins, representative angles, or weights are approved.",
            "No raw source, PV-map, roof, building, or location-level geometry data was downloaded.",
            "No 3DBAG per-roof or heavy building-level workflow is implemented before the first real experiment.",
            "No PV capacity, growth factor, capacity convention, per-node allocation, PR=0.86, direct-GHI formula, or plane-of-array conversion is approved.",
            "No net-load, event detection, P(E), threshold run, capacity screen, manuscript result, or final paired HP/PV acceptance is produced.",
        ],
    }


def build_d014_pv_orientation_tilt_value_choice_packet() -> dict[str, Any]:
    """Return proposed unsigned class values for first-experiment PV geometry.

    Public context supports a statistical route and broad tilt/azimuth ranges,
    but the executable class table still needs PI signoff. The concrete fallback
    below is therefore labelled as an assumption-only candidate, not source
    evidence or an approved PV parameter.
    """
    approval_keys = [
        "orientation_tilt_distribution_source_id",
        "source_value_trace_or_approved_assumption_id",
        "azimuth_angle_convention",
        "tilt_angle_convention",
        "orientation_class_bin_definitions",
        "tilt_class_bin_definitions",
        "representative_angle_values",
        "class_weight_values",
        "class_weight_basis_capacity_installation_area_or_assumption",
        "class_weight_sum_tolerance",
        "pv_conversion_treatment_for_classes",
        "pv_param_001_or_amended_conversion_decision",
        "d014_capacity_value_artifact",
        "capacity_unit_and_dc_ac_convention",
        "node_allocation_rule",
    ]
    return {
        "packet_id": D014_ORIENTATION_TILT_VALUE_CHOICE_ID,
        "data_id": D014_DATA_ID,
        "created_utc": _now_utc_iso(),
        "status": "proposed_value_choice_packet_no_raw_download_no_executable_values",
        "download_performed": False,
        "raw_data_committed": False,
        "approved_scope_decision": "PV-ORIENT-001",
        "source_choice_packet_id": D014_ORIENTATION_TILT_SOURCE_CHOICE_ID,
        "capacity_route_boundary": "PV-CAP-001/D-014 capacity remains separate from orientation/tilt values",
        "pv_param_boundary": "PV-PARAM-001 remains proposed/fail-closed; this packet does not approve PR=0.86, direct-GHI, or plane-of-array conversion",
        "first_experiment_scope": {
            "statistical_orientation_tilt_classes_only": True,
            "heavy_building_level_pv_map_deferred": True,
            "roof_or_location_level_extraction_allowed_now": False,
            "specific_3dbag_per_roof_workflow_allowed_now": False,
        },
        "angle_conventions_for_review": {
            "azimuth_basis": "degrees_from_south_positive_west_candidate",
            "azimuth_examples": {"south": 0.0, "east": -90.0, "west": 90.0},
            "tilt_basis": "degrees_from_horizontal_candidate",
            "weight_basis_recommendation": "capacity_weight_fraction_candidate",
            "executable_status": "unsigned_pi_choice_required",
        },
        "source_backing_summary": {
            "source_backed_now": [
                "PV-ORIENT-001 approves statistical orientation/tilt classes only for the first experiment",
                "Killinger et al. 2018 is a primary empirical source candidate and reports PV-system tilt/azimuth metadata distribution analysis",
                "public source snippets support typical tilt ranges and equator-facing azimuth tendency, but do not by themselves approve a Dutch class-weight table",
                "Dutch PV Portal context supports south-facing 37 degree as a Netherlands optimum/reference point, not a fleet distribution",
            ],
            "not_source_backed_yet": [
                "exact Netherlands or Alkmaar class weights",
                "capacity-weighted versus installation-count-weighted convention",
                "class-wise conversion treatment: direct GHI scalar versus transposed plane-of-array/pvlib route",
            ],
            "assumption_only_values_in_this_packet": ["pi_prior_5_class_symmetric_rooftop_candidate_v1"],
        },
        "candidate_class_sets": [
            {
                "class_set_id": "killinger_empirical_extraction_pending_v1",
                "source_id": "killinger_2018_pv_system_characteristics",
                "value_status": "source_candidate_values_not_extracted_not_executable",
                "source_backing_status": "peer_reviewed_distribution_source_candidate",
                "recommendation": "preferred if the Netherlands-relevant distribution parameters can be extracted/cited before PI signoff",
                "class_table": [],
                "blocked_until": [
                    "extract exact class bins/representative values/weights from source table or figure",
                    "record citation/page/table trace",
                    "PI signs weight basis and conversion treatment",
                ],
            },
            {
                "class_set_id": "pi_prior_5_class_symmetric_rooftop_candidate_v1",
                "source_id": "pi_declared_simple_class_prior",
                "value_status": "assumption_only_unsigned_not_executable",
                "source_backing_status": "assumption_only_fallback_informed_by_common_rooftop_geometry_and_source_candidate_ranges",
                "weight_basis": "capacity_weight_fraction_candidate",
                "azimuth_angle_convention": "degrees_from_south_positive_west_candidate",
                "tilt_angle_convention": "degrees_from_horizontal_candidate",
                "class_weight_sum": 1.0,
                "recommendation": "fallback only if the PI prefers a transparent expert prior over additional empirical extraction before the first experiment",
                "class_table": [
                    {"class_id": "south_mid_tilt", "orientation_bin_label": "south-facing", "tilt_bin_label": "mid tilt", "representative_azimuth_degrees_from_south": 0.0, "representative_tilt_degrees": 35.0, "capacity_weight_fraction": 0.40, "source_value_trace": "assumption-only candidate; not extracted from a Dutch class table"},
                    {"class_id": "southeast_low_mid_tilt", "orientation_bin_label": "southeast-facing", "tilt_bin_label": "low-mid tilt", "representative_azimuth_degrees_from_south": -60.0, "representative_tilt_degrees": 25.0, "capacity_weight_fraction": 0.15, "source_value_trace": "assumption-only candidate; not extracted from a Dutch class table"},
                    {"class_id": "southwest_low_mid_tilt", "orientation_bin_label": "southwest-facing", "tilt_bin_label": "low-mid tilt", "representative_azimuth_degrees_from_south": 60.0, "representative_tilt_degrees": 25.0, "capacity_weight_fraction": 0.15, "source_value_trace": "assumption-only candidate; not extracted from a Dutch class table"},
                    {"class_id": "east_west_low_tilt", "orientation_bin_label": "east/west split", "tilt_bin_label": "low tilt", "representative_azimuth_degrees_from_south": [-90.0, 90.0], "representative_tilt_degrees": 15.0, "capacity_weight_fraction": 0.20, "source_value_trace": "assumption-only candidate split equally between east and west if PI signs it"},
                    {"class_id": "flat_low_tilt", "orientation_bin_label": "flat or weakly oriented", "tilt_bin_label": "near-flat", "representative_azimuth_degrees_from_south": 0.0, "representative_tilt_degrees": 10.0, "capacity_weight_fraction": 0.10, "source_value_trace": "assumption-only candidate; azimuth is placeholder because near-flat output is weakly azimuth-sensitive"},
                ],
            },
        ],
        "pi_recommendation_for_review": {
            "preferred_path": "extract and sign Killinger/Netherlands-relevant distribution values if accessible quickly enough for first experiment",
            "fallback_path": "sign pi_prior_5_class_symmetric_rooftop_candidate_v1 explicitly as a first-screen expert prior",
            "do_not_use_as_final_without_signature": True,
        },
        "pi_approval_keys_before_executable_use": approval_keys,
        "non_claims": [
            "No statistical orientation/tilt class set is approved as final.",
            "Numeric class weights and representative angles in this packet are unsigned candidate review values only.",
            "No raw source, PV-map, roof, building, or location-level geometry data was downloaded.",
            "No 3DBAG per-roof or heavy building-level workflow is implemented before the first real experiment.",
            "No PV capacity, growth factor, capacity convention, per-node allocation, PR=0.86, direct-GHI formula, or plane-of-array conversion is approved.",
            "No net-load, event detection, P(E), threshold run, capacity screen, manuscript result, or final paired HP/PV acceptance is produced.",
        ],
    }


def write_d014_pv_capacity_source_value_packet(metadata_dir: str | Path = "data/metadata") -> Path:
    """Write the proposed D-014 source/value packet and return its path."""
    directory = Path(metadata_dir) / "weather_pv"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / D014_PACKET_NAME
    path.write_text(json.dumps(build_d014_pv_capacity_source_value_packet(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_d014_pv_statistical_orientation_tilt_packet(metadata_dir: str | Path = "data/metadata") -> Path:
    """Write the proposed statistical orientation/tilt packet and return its path."""
    directory = Path(metadata_dir) / "weather_pv"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / D014_STATISTICAL_ORIENTATION_TILT_NAME
    path.write_text(
        json.dumps(build_d014_pv_statistical_orientation_tilt_packet(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def write_d014_pv_orientation_tilt_source_choice_packet(metadata_dir: str | Path = "data/metadata") -> Path:
    """Write the proposed orientation/tilt source-choice packet and return its path."""
    directory = Path(metadata_dir) / "weather_pv"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / D014_ORIENTATION_TILT_SOURCE_CHOICE_NAME
    path.write_text(
        json.dumps(build_d014_pv_orientation_tilt_source_choice_packet(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def write_d014_pv_orientation_tilt_value_choice_packet(metadata_dir: str | Path = "data/metadata") -> Path:
    """Write the proposed orientation/tilt value-choice packet and return its path."""
    directory = Path(metadata_dir) / "weather_pv"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / D014_ORIENTATION_TILT_VALUE_CHOICE_NAME
    path.write_text(
        json.dumps(build_d014_pv_orientation_tilt_value_choice_packet(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare D-014 PV capacity source/value metadata.")
    parser.add_argument("--metadata-dir", default="data/metadata")
    parser.add_argument("--write-d014-source-value-packet", action="store_true")
    parser.add_argument("--write-d014-statistical-orientation-tilt", action="store_true")
    parser.add_argument("--write-d014-orientation-tilt-source-choice", action="store_true")
    parser.add_argument("--write-d014-orientation-tilt-value-choice", action="store_true")
    parser.add_argument("--retrieve-d014-cbs-anchor-evidence", action="store_true")
    args = parser.parse_args(argv)

    if args.retrieve_d014_cbs_anchor_evidence:
        path = retrieve_d014_cbs_capacity_anchor_evidence(metadata_dir=args.metadata_dir)
    elif args.write_d014_orientation_tilt_value_choice:
        path = write_d014_pv_orientation_tilt_value_choice_packet(args.metadata_dir)
    elif args.write_d014_orientation_tilt_source_choice:
        path = write_d014_pv_orientation_tilt_source_choice_packet(args.metadata_dir)
    elif args.write_d014_statistical_orientation_tilt:
        path = write_d014_pv_statistical_orientation_tilt_packet(args.metadata_dir)
    else:
        path = write_d014_pv_capacity_source_value_packet(args.metadata_dir)
    print(path)
    return 0


def _now_utc_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
