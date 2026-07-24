from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib import parse

D014_PACKET_NAME = "d014_pv_capacity_source_value_packet.json"
D014_PACKET_ID = "D014-PV-CAPACITY-SOURCE-VALUE-PACKET"
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


def write_d014_pv_capacity_source_value_packet(metadata_dir: str | Path = "data/metadata") -> Path:
    """Write the proposed D-014 source/value packet and return its path."""
    directory = Path(metadata_dir) / "weather_pv"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / D014_PACKET_NAME
    path.write_text(json.dumps(build_d014_pv_capacity_source_value_packet(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare D-014 PV capacity source/value metadata.")
    parser.add_argument("--metadata-dir", default="data/metadata")
    parser.add_argument("--write-d014-source-value-packet", action="store_true")
    args = parser.parse_args(argv)

    path = write_d014_pv_capacity_source_value_packet(args.metadata_dir)
    print(path)
    return 0


def _now_utc_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())