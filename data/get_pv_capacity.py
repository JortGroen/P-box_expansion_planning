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
D014_II3050_GROWTH_EVIDENCE_NAME = "d014_ii3050_pv_growth_evidence.json"
D014_II3050_GROWTH_EVIDENCE_ID = "D014-II3050-PV-GROWTH-EVIDENCE"
D014_CAPACITY_VALUE_CHOICE_NAME = "d014_pv_capacity_value_choice_packet.json"
D014_CAPACITY_VALUE_CHOICE_ID = "D014-PV-CAPACITY-VALUE-CHOICE-PACKET"
D014_CAPACITY_APPROVAL_TEMPLATE_NAME = "d014_pv_capacity_approval_template.json"
D014_CAPACITY_APPROVAL_TEMPLATE_ID = "D014-PV-CAPACITY-APPROVAL-TEMPLATE"
D014_PV_EXECUTABLE_READINESS_BLOCKERS_NAME = "d014_pv_executable_readiness_blockers.json"
D014_PV_EXECUTABLE_READINESS_BLOCKERS_ID = "D014-PV-EXECUTABLE-READINESS-BLOCKERS"
D014_PV_EXECUTABLE_PREFLIGHT_GUARD_NAME = "d014_pv_executable_preflight_guard.json"
D014_PV_EXECUTABLE_PREFLIGHT_GUARD_ID = "D014-PV-EXECUTABLE-PREFLIGHT-GUARD"
D014_STATISTICAL_ORIENTATION_TILT_NAME = "d014_pv_statistical_orientation_tilt_packet.json"
D014_STATISTICAL_ORIENTATION_TILT_ID = "D014-PV-STATISTICAL-ORIENTATION-TILT-PACKET"
D014_ORIENTATION_TILT_SOURCE_CHOICE_NAME = "d014_pv_orientation_tilt_source_choice_packet.json"
D014_ORIENTATION_TILT_SOURCE_CHOICE_ID = "D014-PV-ORIENTATION-TILT-SOURCE-CHOICE-PACKET"
D014_ORIENTATION_TILT_VALUE_CHOICE_NAME = "d014_pv_orientation_tilt_value_choice_packet.json"
D014_ORIENTATION_TILT_VALUE_CHOICE_ID = "D014-PV-ORIENTATION-TILT-VALUE-CHOICE-PACKET"
D014_PV_PARAM_CONVERSION_SOURCE_CHOICE_NAME = "d014_pv_param_conversion_source_choice_packet.json"
D014_PV_PARAM_CONVERSION_SOURCE_CHOICE_ID = "D014-PV-PARAM-CONVERSION-SOURCE-CHOICE-PACKET"
D014_PV_FIRST_EXPERIMENT_APPROVAL_NAME = "d014_pv_first_experiment_approval_packet.json"
D014_PV_FIRST_EXPERIMENT_APPROVAL_ID = "D014-PV-FIRST-EXPERIMENT-APPROVAL-PACKET"
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
II3050_APPENDICES_PDF_URL = "https://www.netbeheernederland.nl/sites/default/files/Bijlagen_II3050_eindrapport__285.pdf"
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


def build_d014_ii3050_query_urls() -> dict[str, str]:
    """Return the exact public II3050 URLs used for PV growth evidence."""
    return {
        "appendices_publication_page": II3050_APPENDICES_URL,
        "appendices_pdf": II3050_APPENDICES_PDF_URL,
        "main_report_publication_page": II3050_REPORT_URL,
    }


def write_d014_ii3050_appendices_raw_pdf(
    raw_dir: str | Path = "data/raw/pv_capacity",
    *,
    timeout_seconds: int = 30,
) -> Path:
    """Retrieve the ignored II3050 appendix PDF used for D-014 growth evidence."""
    directory = Path(raw_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "d014_ii3050_bijlagen_eindrapport_285.pdf"
    with request.urlopen(II3050_APPENDICES_PDF_URL, timeout=timeout_seconds) as response:
        path.write_bytes(response.read())
    return path


def build_d014_ii3050_growth_evidence_packet(raw_pdf_path: str | Path) -> dict[str, Any]:
    """Build committed metadata from the ignored II3050 appendix PDF.

    The packet records source and row candidates only. It does not select a
    scenario column, denominator, growth factor, or executable PV capacity.
    """
    raw_path = Path(raw_pdf_path)
    raw_bytes = raw_path.read_bytes()
    candidate_columns = [
        {"year": 2019, "scenario": "reference", "column_label": "2019 reference", "zon_pv_gw": 6.2},
        {"year": 2030, "scenario": "KA", "column_label": "2030 KA", "zon_pv_gw": 59.3},
        {"year": 2030, "scenario": "ND", "column_label": "2030 ND", "zon_pv_gw": 76.1},
        {"year": 2030, "scenario": "IA", "column_label": "2030 IA", "zon_pv_gw": 42.1},
        {"year": 2035, "scenario": "KA", "column_label": "2035 KA", "zon_pv_gw": 75.9},
        {"year": 2035, "scenario": "ND", "column_label": "2035 ND", "zon_pv_gw": 98.2},
        {"year": 2035, "scenario": "IA", "column_label": "2035 IA", "zon_pv_gw": 52.6},
        {"year": 2040, "scenario": "DEC", "column_label": "2040 DEC", "zon_pv_gw": 126.1},
        {"year": 2040, "scenario": "NAT", "column_label": "2040 NAT", "zon_pv_gw": 122.7},
        {"year": 2040, "scenario": "EUR", "column_label": "2040 EUR", "zon_pv_gw": 92.6},
        {"year": 2040, "scenario": "INT", "column_label": "2040 INT", "zon_pv_gw": 68.2},
        {"year": 2050, "scenario": "DEC", "column_label": "2050 DEC", "zon_pv_gw": 183.1},
        {"year": 2050, "scenario": "NAT", "column_label": "2050 NAT", "zon_pv_gw": 172.6},
        {"year": 2050, "scenario": "EUR", "column_label": "2050 EUR", "zon_pv_gw": 126.3},
        {"year": 2050, "scenario": "INT", "column_label": "2050 INT", "zon_pv_gw": 100.0},
    ]
    planning_year_candidates = [
        {
            **item,
            "candidate_role": f"planning_year_2035_{item['scenario'].lower()}_candidate",
            "executable_status": "candidate_only_unsigned",
        }
        for item in candidate_columns
        if item["year"] == PLANNING_YEAR
    ]
    return {
        "packet_id": D014_II3050_GROWTH_EVIDENCE_ID,
        "data_id": D014_DATA_ID,
        "status": "retrieved_source_evidence_values_unsigned",
        "created_utc": _now_utc_iso(),
        "download_performed": True,
        "raw_data_committed": False,
        "approved_route_decision": "PV-CAP-001",
        "source_value_packet_id": D014_PACKET_ID,
        "cbs_anchor_evidence_id": D014_CBS_ANCHOR_EVIDENCE_ID,
        "capacity_route_boundary": "II3050/scenario PV growth evidence only; CBS Alkmaar anchor row and all executable values remain separate and unsigned",
        "pv_param_boundary": "PV-PARAM-001 remains proposed/fail-closed; this packet does not approve PR=0.86, direct-GHI, plane-of-array conversion, or PV output",
        "pv_orient_boundary": "PV-ORIENT-001 lightweight statistical orientation/tilt scope preserved; no roof/building/3DBAG/PV-map retrieval",
        "source": {
            "publication": "Bijlagen II3050 eindrapport",
            "owner": "Netbeheer Nederland",
            "publication_date": "2023-10-12",
            "license": "public Netbeheer Nederland web publication/citation route; no redistributable raw data committed",
            "source_pages": build_d014_ii3050_query_urls(),
            "planned_use": "PI-reviewed scenario growth evidence for scaling the CBS Alkmaar PV-capacity anchor to planning year 2035",
        },
        "raw_bundle": {
            "path": raw_path.as_posix(),
            "sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "size_bytes": len(raw_bytes),
            "retrieved_utc": _now_utc_iso(),
            "source_url": II3050_APPENDICES_PDF_URL,
        },
        "table_evidence": {
            "document_section": "A. Cijferbijlage",
            "table_label": "Tabel A.1",
            "table_title": "Overzicht voornaamste kengetallen II3050-editie 2: 2030, 2035, 2040 en 2050",
            "page_candidate": 4,
            "row_label": "Zon PV*",
            "unit": "GW",
            "candidate_columns": candidate_columns,
            "planning_year_2035_candidates": planning_year_candidates,
            "extraction_note": (
                "Values are transcribed as source-evidence candidates from the public Netbeheer Nederland "
                "appendix page/PDF table. They require PI confirmation of scenario column, denominator, "
                "and growth-factor formula before executable use."
            ),
        },
        "growth_factor_choices_for_pi_review": {
            "scenario_column_candidates": planning_year_candidates,
            "denominator_candidates": [
                {
                    "denominator_id": "ii3050_2019_reference_zon_pv_gw",
                    "value_status": "source_evidence_candidate_unsigned",
                    "zon_pv_gw": 6.2,
                    "question": "Use II3050 2019 national PV capacity as the growth denominator?",
                },
                {
                    "denominator_id": "cbs_anchor_year_same_convention",
                    "value_status": "requires signed CBS period/field/convention and a national/local crosswalk",
                    "question": "Use a CBS anchor-year denominator or crosswalk instead of the II3050 2019 reference?",
                },
            ],
            "formula_candidates": [
                {
                    "formula_id": "national_ii3050_ratio_to_reference",
                    "formula": "growth_factor = selected_2035_zon_pv_gw / ii3050_2019_reference_zon_pv_gw",
                    "status": "candidate_only_unsigned",
                },
                {
                    "formula_id": "scenario_crosswalk_to_cbs_anchor_year",
                    "formula": "growth_factor = selected_2035_scenario_value / signed_anchor_year_reference_value",
                    "status": "requires PI-defined source/convention crosswalk",
                },
            ],
        },
        "pi_approval_keys_before_executable_use": [
            "ii3050_raw_pdf_sha256",
            "ii3050_source_table_page_or_sheet",
            "ii3050_row_label",
            "ii3050_unit",
            "ii3050_scenario_column",
            "ii3050_growth_denominator",
            "ii3050_growth_factor_formula",
            "ii3050_growth_factor_value",
            "scenario_source_consistency_with_ev_hp_inputs",
            "cbs_source_period_key",
            "cbs_capacity_field_key",
            "capacity_unit_and_dc_ac_convention",
            "node_allocation_rule",
            "statistical_orientation_tilt_distribution_source",
            "statistical_orientation_tilt_distribution_weights",
            "PV-PARAM-001_or_amended_conversion_decision",
        ],
        "non_claims": [
            "No executable PV installed-capacity value is approved.",
            "No II3050 scenario column is selected as final.",
            "No II3050 growth denominator, formula, or growth-factor value is approved.",
            "No CBS period, sector/category, capacity field, unit convention, or DC/AC convention is selected as final.",
            "No per-node PV allocation is approved.",
            "No statistical orientation/tilt values or PV-PARAM conversion treatment are approved.",
            "No roof, building, 3DBAG, or PV-map geometry source is retrieved or used.",
            "No net-load, event detection, P(E), threshold analysis, capacity screen, manuscript result, or final PV output is produced.",
        ],
    }


def retrieve_d014_ii3050_growth_evidence(
    *,
    metadata_dir: str | Path = "data/metadata",
    raw_dir: str | Path = "data/raw/pv_capacity",
    timeout_seconds: int = 30,
) -> Path:
    """Retrieve II3050 appendix source evidence and write committed metadata."""
    raw_path = write_d014_ii3050_appendices_raw_pdf(raw_dir, timeout_seconds=timeout_seconds)
    directory = Path(metadata_dir) / "weather_pv"
    directory.mkdir(parents=True, exist_ok=True)
    metadata_path = directory / D014_II3050_GROWTH_EVIDENCE_NAME
    metadata_path.write_text(
        json.dumps(build_d014_ii3050_growth_evidence_packet(raw_path), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return metadata_path


def build_d014_pv_capacity_value_choice_packet(
    cbs_evidence_path: str | Path = "data/metadata/weather_pv/d014_cbs_85005ned_alkmaar_gm0361_anchor_evidence.json",
    ii3050_evidence_path: str | Path = "data/metadata/weather_pv/d014_ii3050_pv_growth_evidence.json",
) -> dict[str, Any]:
    """Combine CBS and II3050 evidence into an unsigned PI value-choice packet."""
    cbs_path = Path(cbs_evidence_path)
    ii_path = Path(ii3050_evidence_path)
    cbs = json.loads(cbs_path.read_text(encoding="utf-8"))
    ii3050 = json.loads(ii_path.read_text(encoding="utf-8"))
    rows = cbs["candidate_value_choices_for_pi_review"]["all_retrieved_alkmaar_rows"]
    periods = {item["Key"]: item for item in cbs["schema"]["periods"]}
    sectors = {item["Key"]: item for item in cbs["schema"]["sector_and_capacity_class_codes"]}

    def cbs_operand(period_key: str, sector_key: str, role: str) -> dict[str, Any]:
        row = next(
            item
            for item in rows
            if item["Perioden"] == period_key and item["SectorEnVermogensklasse"] == sector_key
        )
        return {
            "operand_role": role,
            "row_id": row["ID"],
            "period_key": period_key,
            "period_title": str(periods[period_key].get("Title", "")).strip(),
            "period_status": periods[period_key].get("Status"),
            "sector_key": sector_key,
            "sector_title": sectors[sector_key].get("Title"),
            "panel_capacity_kwp_operand": row.get("OpgesteldVermogenVanZonnepanelen_2"),
            "inverter_capacity_kw_operand": row.get("OpgesteldVermogenOmvormers_3"),
            "installations_count_diagnostic": row.get("Installaties_1"),
            "operand_status": "candidate_operand_unsigned_not_executable",
        }

    cbs_operands = [
        cbs_operand("2019JJ00", "E007161", "source_year_matched_ii3050_reference_all_activity_and_homes"),
        cbs_operand("2019JJ00", "E007037", "source_year_matched_ii3050_reference_homes_only_sensitivity"),
        cbs_operand("2023JJ00", "E007161", "latest_definitive_all_activity_and_homes_candidate"),
        cbs_operand("2023JJ00", "E007037", "latest_definitive_homes_only_sensitivity_candidate"),
        cbs_operand("2025JJ00", "E007161", "latest_available_provisional_all_activity_and_homes_diagnostic"),
    ]
    scenario_operands = ii3050["table_evidence"]["planning_year_2035_candidates"]
    denominator_operands = ii3050["growth_factor_choices_for_pi_review"]["denominator_candidates"]
    equations = [
        {
            "equation_id": "dc_kwp_source_year_matched_ii3050_ratio",
            "capacity_convention": "DC panel capacity in kWp",
            "formula": (
                "pv_capacity_2035_kwp_dc = cbs_panel_capacity_kwp(period_key, sector_key) "
                "* ii3050_zon_pv_gw(2035, scenario_column) / ii3050_zon_pv_gw(2019_reference)"
            ),
            "recommended_for_pi_review": True,
            "reason": (
                "Uses the CBS panel-capacity field and II3050 2019 reference denominator in the same source year "
                "when the PI selects the 2019 CBS operand; avoids silently double-counting 2019-2023 growth."
            ),
            "executable_status": "proposed_recommendation_unsigned",
        },
        {
            "equation_id": "dc_kwp_latest_definitive_with_signed_crosswalk",
            "capacity_convention": "DC panel capacity in kWp",
            "formula": (
                "pv_capacity_2035_kwp_dc = cbs_panel_capacity_kwp(2023JJ00, sector_key) "
                "* signed_ii3050_growth_factor_from_2023_to_2035"
            ),
            "recommended_for_pi_review": False,
            "reason": (
                "Uses the latest definitive CBS local anchor, but requires a signed 2023-to-2035 II3050/CBS crosswalk "
                "because Table A.1 evidence currently records 2019 and scenario-year national values, not a 2023 denominator."
            ),
            "executable_status": "blocked_until_growth_crosswalk_signed",
        },
        {
            "equation_id": "ac_kw_inverter_capacity_variant",
            "capacity_convention": "AC inverter/grid-facing capacity in kW",
            "formula": (
                "pv_capacity_2035_kw_ac = cbs_inverter_capacity_kw(period_key, sector_key) "
                "* signed_ii3050_growth_factor_same_convention"
            ),
            "recommended_for_pi_review": False,
            "reason": (
                "Potentially closer to grid-facing capacity, but CBS inverter capacity is not available for all periods "
                "and PV-PARAM-001 must first say whether installed_capacity_kw expects DC peak or AC clipped capacity."
            ),
            "executable_status": "blocked_until_capacity_convention_and_growth_denominator_signed",
        },
    ]
    approval_keys = [
        "D014-PV-CAPACITY-VALUE-CHOICE-PACKET",
        "cbs_anchor_evidence_packet_id_and_sha256",
        "ii3050_growth_evidence_packet_id_and_sha256",
        "alkmaar_geography_key",
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
        "statistical_orientation_tilt_distribution_source",
        "statistical_orientation_tilt_distribution_weights",
        "PV-PARAM-001_or_amended_conversion_decision",
    ]
    return {
        "packet_id": D014_CAPACITY_VALUE_CHOICE_ID,
        "data_id": D014_DATA_ID,
        "created_utc": _now_utc_iso(),
        "status": "proposed_value_choice_packet_no_executable_values",
        "download_performed": False,
        "raw_data_committed": False,
        "governing_decisions": {
            "approved_route": "PV-CAP-001",
            "scenario_consistency": "A-016 requires EV/HP/PV 2035 source-lineage consistency before integrated use",
            "conversion_parameters": "PV-PARAM-001 remains proposed/fail-closed",
            "orientation_scope": "PV-ORIENT-001 statistical orientation/tilt only; no roof/building/3DBAG/PV-map extraction",
        },
        "source_evidence_inputs": {
            "cbs_anchor_packet_id": cbs["packet_id"],
            "cbs_anchor_metadata_path": cbs_path.as_posix(),
            "cbs_raw_sha256": cbs["raw_bundle"]["sha256"],
            "ii3050_growth_packet_id": ii3050["packet_id"],
            "ii3050_growth_metadata_path": ii_path.as_posix(),
            "ii3050_raw_sha256": ii3050["raw_bundle"]["sha256"],
        },
        "candidate_operands_for_pi_review": {
            "cbs_alkmaar_capacity_operands": cbs_operands,
            "ii3050_2035_scenario_operands": scenario_operands,
            "ii3050_denominator_operands": denominator_operands,
        },
        "candidate_equations_for_local_2035_capacity": equations,
        "scenario_consistency_issue": {
            "decision_id": "A-016",
            "issue": (
                "EV local adoption is anchored to ElaadNL Outlook branches, HP scaling uses PBL/CBS/When2Heat evidence, "
                "and PV growth candidates use II3050 scenario columns. Shared labels such as low/middle/high must not be "
                "assumed equivalent to II3050 KA/ND/IA without a signed scenario-consistency mapping."
            ),
            "required_manifest_fields_later": [
                "pv_cbs_source_year",
                "pv_cbs_capacity_field_key",
                "pv_capacity_convention",
                "pv_ii3050_scenario_column",
                "pv_growth_factor_value",
                "scenario_consistency_decision_id",
            ],
            "executable_status": "blocked_until_A016_consistency_mapping_signed",
        },
        "capacity_convention_recommendation": {
            "recommended_for_pi_review": "Use DC panel capacity in kWp as the signed capacity-value artifact convention, label it explicitly as `installed_capacity_kwp_dc`, and let PV-PARAM-001 or an amendment decide how that maps into PVSystemConfig.installed_capacity_kw.",
            "rationale": (
                "CBS panel capacity is available across the complete candidate evidence window and matches PV installed-capacity reporting. "
                "Using inverter AC kW may be useful as a grid-facing sensitivity, but it should not be silently substituted for PV-PARAM's capacity input."
            ),
            "not_approved_by_this_packet": True,
        },
        "pi_recommendation": {
            "recommendation_status": "proposed_unsigned_not_executable",
            "primary_equation_id": "dc_kwp_source_year_matched_ii3050_ratio",
            "primary_cbs_operand_role": "source_year_matched_ii3050_reference_all_activity_and_homes",
            "primary_capacity_convention": "DC kWp labelled as installed_capacity_kwp_dc before PV-PARAM-001",
            "scenario_selection_rule": "PI selects the II3050 2035 scenario column only after A-016 consistency with EV/HP scenario branches is recorded.",
            "sensitivity_candidates": [
                "latest_definitive_2023_all_activity_and_homes_with_signed_2023_to_2035_growth_crosswalk",
                "homes_only_sector_if PV is restricted to residential nodes",
                "inverter_AC_capacity_if PI signs AC/grid-facing capacity convention",
            ],
        },
        "pi_approval_keys_before_executable_use": approval_keys,
        "non_claims": [
            "No final PV capacity value is approved or computed.",
            "No CBS row, period, sector/category, field, unit, or DC/AC convention is selected as final.",
            "No II3050 scenario column, denominator, formula, or growth-factor value is selected as final.",
            "No A-016 EV/HP/PV scenario-consistency mapping is approved.",
            "No per-node PV allocation is approved.",
            "No statistical orientation/tilt values or PV-PARAM conversion treatment are approved.",
            "No roof, building, 3DBAG, or PV-map geometry source is retrieved or used.",
            "No PV generation, net-load, event detection, P(E), threshold analysis, capacity screen, manuscript result, or final PV output is produced.",
        ],
    }


def write_d014_pv_capacity_value_choice_packet(metadata_dir: str | Path = "data/metadata") -> Path:
    """Write the proposed D-014 PV capacity value-choice packet and return its path."""
    directory = Path(metadata_dir) / "weather_pv"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / D014_CAPACITY_VALUE_CHOICE_NAME
    path.write_text(
        json.dumps(build_d014_pv_capacity_value_choice_packet(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def build_d014_pv_capacity_approval_template_packet(
    value_choice_path: str | Path = "data/metadata/weather_pv/d014_pv_capacity_value_choice_packet.json",
) -> dict[str, Any]:
    """Return the unsigned template a later PI-signed PV capacity artifact must satisfy."""
    value_path = Path(value_choice_path)
    value_bytes = value_path.read_bytes()
    value_choice = json.loads(value_bytes.decode("utf-8"))
    if value_choice.get("packet_id") != D014_CAPACITY_VALUE_CHOICE_ID:
        raise ValueError("capacity approval template must be built from the D-014 value-choice packet")

    recommended = value_choice["pi_recommendation"]
    return {
        "packet_id": D014_CAPACITY_APPROVAL_TEMPLATE_ID,
        "data_id": D014_DATA_ID,
        "status": "proposed_signed_capacity_artifact_template_no_values",
        "download_performed": False,
        "raw_data_committed": False,
        "upstream_value_choice_packet": {
            "packet_id": D014_CAPACITY_VALUE_CHOICE_ID,
            "metadata_path": str(value_path).replace("\\", "/"),
            "metadata_sha256": hashlib.sha256(value_bytes).hexdigest(),
            "metadata_size_bytes": len(value_bytes),
            "recommendation_status": recommended["recommendation_status"],
            "recommended_equation_id": recommended["primary_equation_id"],
            "recommended_capacity_convention": recommended["primary_capacity_convention"],
        },
        "approved_route_boundary": {
            "capacity_route_decision": "PV-CAP-001",
            "capacity_route_status": "approved route only; executable values pending",
            "scenario_consistency_decision": "A-016",
            "pv_parameter_decision": "PV-PARAM-001_or_signed_amendment",
            "orientation_scope_decision": "PV-ORIENT-001",
            "orientation_scope_boundary": "statistical orientation/tilt only; no building/roof/3DBAG/PV-map extraction before the first experiment",
        },
        "required_signed_artifact_fields": {
            "artifact_identity": [
                "capacity_artifact_id",
                "signed_decision_id",
                "signed_decision_date",
                "approval_status",
                "created_from_value_choice_packet_id",
            ],
            "capacity_value": [
                "installed_capacity_value",
                "installed_capacity_unit",
                "capacity_convention",
                "capacity_scope",
                "planning_year",
            ],
            "cbs_anchor_operand": [
                "cbs_table_id",
                "alkmaar_geography_key",
                "cbs_source_period_key",
                "cbs_sector_category_key",
                "cbs_capacity_field_key",
                "cbs_anchor_value",
                "cbs_anchor_unit",
                "cbs_evidence_packet_id",
                "cbs_evidence_metadata_sha256",
                "cbs_raw_bundle_sha256",
            ],
            "ii3050_growth_operand": [
                "ii3050_evidence_packet_id",
                "ii3050_evidence_metadata_sha256",
                "ii3050_raw_bundle_sha256",
                "ii3050_scenario_column",
                "ii3050_numerator_year",
                "ii3050_denominator_year_or_crosswalk_id",
                "ii3050_growth_factor_formula",
                "ii3050_growth_factor_value",
            ],
            "a016_scenario_consistency": [
                "scenario_consistency_mapping_id",
                "ev_source_scenario_label",
                "hp_source_scenario_label",
                "pv_ii3050_scenario_label",
                "consistency_check_status",
            ],
            "allocation_and_conversion_dependencies": [
                "node_allocation_rule_id",
                "node_allocation_status",
                "statistical_orientation_tilt_distribution_id",
                "statistical_orientation_tilt_status",
                "pv_param_decision_id",
                "pv_param_status",
            ],
            "audit_outputs": [
                "content_sha256",
                "source_metadata_paths",
                "source_metadata_sha256",
                "non_claims",
                "blocked_until",
            ],
        },
        "executable_gate": {
            "accepted_for_executable_pv_capacity_input": False,
            "signed_capacity_value_approved": False,
            "requires_pi_signed_decision": True,
            "blocking_approval_keys": value_choice["pi_approval_keys_before_executable_use"],
            "guard_message": "Unsigned D-014 capacity templates cannot provide executable PV installed capacity.",
        },
        "recommended_pi_path": {
            "recommended_template_use": "When PI approves the D-014 value choice, instantiate this template as a new signed artifact rather than mutating evidence packets.",
            "recommended_capacity_label_before_pv_param": "installed_capacity_kwp_dc",
            "recommended_equation_id_for_review": recommended["primary_equation_id"],
            "not_approved_by_this_template": True,
        },
        "non_claims": [
            "No final PV installed-capacity value is approved or computed.",
            "No CBS row, II3050 scenario, growth factor, or DC/AC convention is signed.",
            "No node allocation, statistical orientation/tilt value, or PV-PARAM conversion treatment is signed.",
            "No roof, building, 3DBAG, or PV-map geometry source is retrieved or used for the first experiment.",
            "No PV generation, net-load, event detection, P(E), threshold analysis, capacity screen, manuscript result, or final PV output is produced.",
        ],
    }


def write_d014_pv_capacity_approval_template_packet(metadata_dir: str | Path = "data/metadata") -> Path:
    """Write the unsigned D-014 capacity approval-template packet and return its path."""
    directory = Path(metadata_dir) / "weather_pv"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / D014_CAPACITY_APPROVAL_TEMPLATE_NAME
    path.write_text(
        json.dumps(build_d014_pv_capacity_approval_template_packet(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _metadata_input_record(path: str | Path, expected_packet_id: str | None = None) -> dict[str, Any]:
    metadata_path = Path(path)
    raw = metadata_path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if expected_packet_id is not None and payload.get("packet_id") != expected_packet_id:
        raise ValueError(f"expected {expected_packet_id} at {metadata_path}")
    return {
        "path": str(metadata_path).replace("\\", "/"),
        "packet_id": payload.get("packet_id") or payload.get("selection_id"),
        "status": payload.get("status"),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def build_d014_pv_executable_readiness_blockers_packet(
    *,
    weather_input_artifact_path: str | Path = "data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_weather_input_artifact.json",
    capacity_template_path: str | Path = "data/metadata/weather_pv/d014_pv_capacity_approval_template.json",
    orientation_value_choice_path: str | Path = "data/metadata/weather_pv/d014_pv_orientation_tilt_value_choice_packet.json",
    pv_parameter_packet_path: str | Path = "data/metadata/weather_pv/d004_pv_parameter_decision_packet.json",
) -> dict[str, Any]:
    """Return a fail-closed manifest of blockers before executable first-experiment PV input."""
    weather = _metadata_input_record(weather_input_artifact_path, None)
    capacity = _metadata_input_record(capacity_template_path, D014_CAPACITY_APPROVAL_TEMPLATE_ID)
    orientation = _metadata_input_record(orientation_value_choice_path, D014_ORIENTATION_TILT_VALUE_CHOICE_ID)
    pv_param = _metadata_input_record(pv_parameter_packet_path, None)
    return {
        "packet_id": D014_PV_EXECUTABLE_READINESS_BLOCKERS_ID,
        "data_id": D014_DATA_ID,
        "status": "proposed_fail_closed_executable_pv_readiness_blockers",
        "download_performed": False,
        "raw_data_committed": False,
        "input_metadata": {
            "weather_input_artifact": weather,
            "capacity_approval_template": capacity,
            "orientation_tilt_value_choice": orientation,
            "pv_parameter_packet": pv_param,
        },
        "readiness_layers": {
            "weather_source_member": {
                "decision_id": "D004-SOURCE-MEMBER-ACCEPTANCE",
                "component_source_member_ready": True,
                "realized_weather_path": "KNMI station 249 Berkhout WEATHER-001 members",
                "pvgis_role": "qualitative sanity/provenance only",
            },
            "capacity_value": {
                "decision_id": "D014-PV-CAPACITY-APPROVAL-TEMPLATE",
                "ready": False,
                "blocked_by": "PI-signed capacity artifact missing",
            },
            "scenario_consistency": {
                "decision_id": "A-016",
                "ready": False,
                "blocked_by": "EV/HP/PV scenario label mapping not signed",
            },
            "orientation_tilt_distribution": {
                "decision_id": "PV-ORIENT-001",
                "ready": False,
                "blocked_by": "statistical source, bins, weights, and conversion treatment unsigned",
            },
            "pv_conversion_parameters": {
                "decision_id": "PV-PARAM-001_or_signed_amendment",
                "ready": False,
                "blocked_by": "PV-PARAM conversion treatment not signed",
            },
            "node_allocation": {
                "decision_id": "future_node_allocation_rule",
                "ready": False,
                "blocked_by": "per-node PV allocation rule and provenance unsigned",
            },
            "final_paired_hp_pv_and_cold_spell_acceptance": {
                "decision_id": "future_final_paired_acceptance",
                "ready": False,
                "blocked_by": "paired HP/PV validation and HP cold-spell tolerance decisions remain guarded",
            },
        },
        "executable_gate": {
            "executable_pv_generation_authorized": False,
            "component_source_member_artifact_available": True,
            "blocking_register_ids": [
                "D014-PV-CAPACITY-APPROVAL-TEMPLATE",
                "A-016",
                "PV-ORIENT-001",
                "PV-PARAM-001",
                "future_node_allocation_rule",
                "future_final_paired_acceptance",
            ],
            "guard_message": "PV/weather component inputs have accepted weather members, but executable 2035 PV generation remains blocked until capacity, scenario, orientation, allocation, and conversion decisions are signed.",
        },
        "non_claims": [
            "No final PV capacity value, growth factor, orientation/tilt distribution, allocation, or conversion formula is approved.",
            "No PV generation, net-load, event detection, P(E), threshold analysis, capacity screen, manuscript result, or final PV output is produced.",
            "No roof, building, 3DBAG, or PV-map geometry source is retrieved or used for the first experiment.",
        ],
    }


def write_d014_pv_executable_readiness_blockers_packet(metadata_dir: str | Path = "data/metadata") -> Path:
    """Write the fail-closed executable PV readiness-blocker packet and return its path."""
    directory = Path(metadata_dir) / "weather_pv"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / D014_PV_EXECUTABLE_READINESS_BLOCKERS_NAME
    path.write_text(
        json.dumps(build_d014_pv_executable_readiness_blockers_packet(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def build_d014_pv_executable_preflight_guard_packet(
    blockers_path: str | Path = "data/metadata/weather_pv/d014_pv_executable_readiness_blockers.json",
) -> dict[str, Any]:
    """Return the fail-closed preflight packet for executable PV generation attempts."""
    blocker_path = Path(blockers_path)
    blocker_bytes = blocker_path.read_bytes()
    blocker = json.loads(blocker_bytes.decode("utf-8"))
    if blocker.get("packet_id") != D014_PV_EXECUTABLE_READINESS_BLOCKERS_ID:
        raise ValueError("PV executable preflight guard must consume the readiness-blocker packet")
    gate = blocker["executable_gate"]
    if gate.get("executable_pv_generation_authorized") is not False:
        raise ValueError("PV executable preflight guard cannot consume an already-authorizing blocker packet")
    return {
        "packet_id": D014_PV_EXECUTABLE_PREFLIGHT_GUARD_ID,
        "data_id": D014_DATA_ID,
        "status": "proposed_fail_closed_preflight_no_generation",
        "download_performed": False,
        "raw_data_committed": False,
        "input_blocker_manifest": {
            "packet_id": D014_PV_EXECUTABLE_READINESS_BLOCKERS_ID,
            "metadata_path": str(blocker_path).replace("\\", "/"),
            "metadata_sha256": hashlib.sha256(blocker_bytes).hexdigest(),
            "metadata_size_bytes": len(blocker_bytes),
            "status": blocker.get("status"),
        },
        "preflight_checks": {
            "metadata_checksum_recorded": True,
            "component_source_member_artifact_available": gate.get("component_source_member_artifact_available") is True,
            "executable_pv_generation_authorized": False,
            "required_blocking_register_ids": gate.get("blocking_register_ids", []),
            "all_required_blockers_present": all(
                item in gate.get("blocking_register_ids", [])
                for item in [
                    "D014-PV-CAPACITY-APPROVAL-TEMPLATE",
                    "A-016",
                    "PV-ORIENT-001",
                    "PV-PARAM-001",
                    "future_node_allocation_rule",
                    "future_final_paired_acceptance",
                ]
            ),
        },
        "token_policy": {
            "unsafe_tokens_for_executable_outputs": [
                "TODO",
                "TBD",
                "placeholder",
                "synthetic",
                "proposed",
                "unsigned",
                "not-approved",
            ],
            "allowlisted_non_executable_metadata_tokens": [
                "proposed",
                "unsigned",
            ],
            "policy_result": "blocked_metadata_only_no_executable_output",
        },
        "executable_gate": {
            "preflight_ready_for_executable_pv_generation": False,
            "result_if_invoked": "abort_with_blocker_manifest",
            "blocking_register_ids": gate.get("blocking_register_ids", []),
            "guard_message": "Executable PV preflight is blocked by unresolved D-014/PV-PARAM/PV-ORIENT/A-016/allocation/paired-weather gates.",
        },
        "non_claims": [
            "No executable PV preflight passes in this packet.",
            "No final PV capacity value, growth factor, orientation/tilt distribution, allocation, or conversion formula is approved.",
            "No PV generation, net-load, event detection, P(E), threshold analysis, capacity screen, manuscript result, or final PV output is produced.",
            "No roof, building, 3DBAG, or PV-map geometry source is retrieved or used for the first experiment.",
        ],
    }


def write_d014_pv_executable_preflight_guard_packet(metadata_dir: str | Path = "data/metadata") -> Path:
    """Write the fail-closed executable PV preflight guard packet and return its path."""
    directory = Path(metadata_dir) / "weather_pv"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / D014_PV_EXECUTABLE_PREFLIGHT_GUARD_NAME
    path.write_text(
        json.dumps(build_d014_pv_executable_preflight_guard_packet(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


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


def build_d014_pv_param_conversion_source_choice_packet() -> dict[str, Any]:
    """Return proposed PV-PARAM conversion-source choices without approving a formula."""
    approval_keys = [
        "pv_param_decision_id_or_signed_amendment",
        "conversion_formula_id",
        "irradiance_input_basis",
        "orientation_tilt_value_packet_id",
        "transposition_model_or_direct_ghi_simplification",
        "diffuse_fraction_decomposition_rule_if_poa",
        "albedo_assumption_or_source",
        "performance_ratio_or_loss_model_source",
        "temperature_model_and_coefficients",
        "clipping_rule_and_capacity_convention",
        "pvgis_reference_sanity_tolerance",
        "d014_capacity_approval_artifact",
        "node_allocation_rule",
        "a016_scenario_consistency_mapping",
    ]
    return {
        "packet_id": D014_PV_PARAM_CONVERSION_SOURCE_CHOICE_ID,
        "data_id": D014_DATA_ID,
        "created_utc": _now_utc_iso(),
        "status": "proposed_conversion_source_choice_no_raw_download_no_executable_formula",
        "download_performed": False,
        "raw_data_committed": False,
        "governing_decisions": {
            "pv_param_decision_status": "PV-PARAM-001 remains proposed/fail-closed; this packet proposes an amended choice layer only",
            "orientation_scope": "PV-ORIENT-001 statistical orientation/tilt classes only; no building/roof/3DBAG/PV-map extraction before the first experiment",
            "capacity_route": "PV-CAP-001/D-014 capacity remains separate and unsigned until a signed capacity artifact exists",
            "weather_basis": "WEATHER-001 KNMI Q-derived ghi_w_per_m2 remains the realized irradiance path; PVGIS remains qualitative sanity/provenance only",
        },
        "input_dependencies": {
            "weather_member_artifact": "accepted D-004 WEATHER-001 source/member artifact required before component input use",
            "orientation_tilt_values": "D014-PV-ORIENTATION-TILT-VALUE-CHOICE-PACKET or successor must be signed before executable class use",
            "capacity_artifact": "D014-PV-CAPACITY-APPROVAL-TEMPLATE successor must provide signed installed capacity and convention",
            "scenario_consistency": "A-016 mapping must align EV/HP/PV planning-year/scenario labels before executable integrated use",
        },
        "conversion_source_candidates": [
            {
                "candidate_id": "pvlib_statistical_orientation_tilt_poa_candidate",
                "candidate_status": "source_candidate_unsigned_not_executable",
                "description": "Use signed statistical orientation/tilt classes with a pvlib-style plane-of-array workflow applied to the KNMI realized GHI path.",
                "can_prove": [
                    "class-specific geometry can affect production timing once class values are signed",
                    "conversion method can be audited by model/source version and parameter record",
                ],
                "cannot_prove_yet": [
                    "diffuse fraction decomposition rule from GHI alone",
                    "loss/performance ratio and module temperature coefficients",
                    "final class weights or capacity convention",
                ],
                "pi_decision_needed": [
                    "choose transposition/decomposition model",
                    "approve albedo and temperature treatment",
                    "approve source/version traceability for pvlib or equivalent implementation",
                ],
            },
            {
                "candidate_id": "pvgis_reference_calibration_sanity_candidate",
                "candidate_status": "reference_candidate_unsigned_not_realized_weather_not_executable",
                "description": "Use approved PVGIS-SARAH3 normalized requests only as qualitative seasonal/peak sanity or calibration context.",
                "can_prove": [
                    "reference expectation for Alkmaar-like fixed PV output under the normalized setup",
                    "sanity context for seasonal totals and peak timing",
                ],
                "cannot_prove_yet": [
                    "a sampled realized weather path under ALEA-001",
                    "local installed capacity or fleet orientation weights",
                    "a signed conversion formula by itself",
                ],
                "pi_decision_needed": [
                    "approve any numerical PVGIS sanity tolerance before acceptance use",
                    "confirm PVGIS stays provenance/calibration context only",
                ],
            },
            {
                "candidate_id": "direct_ghi_pr_scalar_candidate",
                "candidate_status": "disputed_simple_candidate_unsigned_not_executable",
                "description": "Use KNMI GHI directly with a scalar performance ratio and clipping only as a transparent fallback if the PI explicitly signs that simplification.",
                "can_prove": [
                    "simple monotone nonnegative PV proxy from the realized WEATHER-001 GHI path",
                    "fast first-screen implementation if signed as an explicit simplification",
                ],
                "cannot_prove_yet": [
                    "orientation/tilt timing effects",
                    "plane-of-array irradiance or module-temperature behavior",
                    "the currently disputed PR=0.86 route as an approved method",
                ],
                "pi_decision_needed": [
                    "explicitly approve or reject direct-GHI simplification",
                    "approve performance ratio/loss source and clipping convention",
                ],
            },
        ],
        "recommendation_for_pi_review": {
            "preferred_path": "amend PV-PARAM-001 toward a signed statistical-orientation/tilt plane-of-array conversion route if it can be implemented with public, traceable model assumptions",
            "fallback_path": "use direct_ghi_pr_scalar_candidate only if the PI signs it as an explicit first-screen simplification despite its missing geometry timing effects",
            "keep_pvgis_boundary": "PVGIS may calibrate or sanity-check seasonal/peak behavior, but must not become a realized sampled weather path",
            "do_not_use_as_final_without_signature": True,
        },
        "executable_gate": {
            "executable_allowed_now": False,
            "result_if_invoked": "abort_until_signed_pv_param_conversion_choice",
            "blocking_register_ids": [
                "PV-PARAM-001_or_signed_amendment",
                "PV-ORIENT-001_values",
                "D014-PV-CAPACITY-APPROVAL-TEMPLATE_successor",
                "A-016",
                "future_node_allocation_rule",
            ],
        },
        "pi_approval_keys_before_executable_use": approval_keys,
        "non_claims": [
            "No PV conversion formula is approved by this packet.",
            "No PR=0.86, direct-GHI, pvlib, plane-of-array, decomposition, albedo, temperature, clipping, or capacity-convention treatment is signed.",
            "No PV capacity value, growth factor, orientation/tilt values, allocation, PV generation, net-load, event detection, P(E), threshold run, capacity screen, manuscript result, or final paired HP/PV acceptance is produced.",
            "No roof, building, 3DBAG, or PV-map geometry workflow is implemented before the first experiment.",
        ],
    }



def build_d014_pv_first_experiment_approval_packet(
    *,
    capacity_template_path: str | Path = "data/metadata/weather_pv/d014_pv_capacity_approval_template.json",
    orientation_source_choice_path: str | Path = "data/metadata/weather_pv/d014_pv_orientation_tilt_source_choice_packet.json",
    orientation_value_choice_path: str | Path = "data/metadata/weather_pv/d014_pv_orientation_tilt_value_choice_packet.json",
    conversion_source_choice_path: str | Path = "data/metadata/weather_pv/d014_pv_param_conversion_source_choice_packet.json",
    executable_preflight_guard_path: str | Path = "data/metadata/weather_pv/d014_pv_executable_preflight_guard.json",
) -> dict[str, Any]:
    """Return the fail-closed first-experiment PV approval packet for PI review."""
    capacity = _metadata_input_record(capacity_template_path, D014_CAPACITY_APPROVAL_TEMPLATE_ID)
    orientation_source = _metadata_input_record(orientation_source_choice_path, D014_ORIENTATION_TILT_SOURCE_CHOICE_ID)
    orientation_values = _metadata_input_record(orientation_value_choice_path, D014_ORIENTATION_TILT_VALUE_CHOICE_ID)
    conversion = _metadata_input_record(conversion_source_choice_path, D014_PV_PARAM_CONVERSION_SOURCE_CHOICE_ID)
    preflight = _metadata_input_record(executable_preflight_guard_path, D014_PV_EXECUTABLE_PREFLIGHT_GUARD_ID)
    approval_keys = [
        "signed_d014_capacity_artifact",
        "signed_capacity_unit_and_dc_ac_convention",
        "signed_ii3050_scenario_growth_factor_and_a016_mapping",
        "signed_statistical_orientation_tilt_source",
        "signed_statistical_orientation_tilt_bins_representative_angles_and_weights",
        "signed_orientation_tilt_weighting_convention",
        "signed_pv_param_conversion_formula_or_amendment",
        "signed_irradiance_transposition_or_direct_ghi_treatment",
        "signed_loss_temperature_clipping_and_capacity_convention",
        "signed_node_allocation_rule",
        "signed_final_paired_hp_pv_acceptance_prerequisite",
    ]
    return {
        "packet_id": D014_PV_FIRST_EXPERIMENT_APPROVAL_ID,
        "data_id": D014_DATA_ID,
        "created_utc": _now_utc_iso(),
        "status": "proposed_first_experiment_pv_approval_packet_no_executable_values",
        "download_performed": False,
        "raw_data_committed": False,
        "input_metadata": {
            "capacity_approval_template": capacity,
            "orientation_tilt_source_choice": orientation_source,
            "orientation_tilt_value_choice": orientation_values,
            "pv_param_conversion_source_choice": conversion,
            "executable_preflight_guard": preflight,
        },
        "first_experiment_scope": {
            "orientation_tilt_route": "typical/statistical distribution only",
            "building_roof_location_level_geometry_allowed": False,
            "specific_3dbag_or_pv_map_workflow_allowed": False,
            "deferred_improvement": "post-first-experiment roof/building/PV-map geometry may be revisited only by a later signed scope change",
        },
        "separated_decision_layers": {
            "installed_capacity_route": {
                "governing_decision": "PV-CAP-001/D-014",
                "status": "route approved; executable value unsigned",
                "must_not_decide_here": ["CBS row/value", "II3050 scenario/growth factor", "DC/AC convention"],
            },
            "orientation_tilt_distribution": {
                "governing_decision": "PV-ORIENT-001",
                "status": "scope approved; source, bins, angles, weights, and weighting convention unsigned",
                "must_not_decide_here": ["final class weights", "final representative angles", "roof/building extraction"],
            },
            "irradiance_to_power_conversion": {
                "governing_decision": "PV-PARAM-001_or_signed_amendment",
                "status": "formula unsigned; direct-GHI/PR route disputed until explicitly signed",
                "must_not_decide_here": ["PR=0.86", "pvlib/POA model", "temperature model", "clipping rule"],
            },
            "node_allocation": {
                "governing_decision": "future_node_allocation_rule",
                "status": "unsigned and separate from capacity total and PV-PARAM conversion",
                "must_not_decide_here": ["per-node capacity shares", "allocation denominator", "building/roof allocation"],
            },
        },
        "pi_approval_keys_before_executable_use": approval_keys,
        "executable_gate": {
            "executable_pv_generation_authorized": False,
            "result_if_invoked": "abort_until_first_experiment_pv_approvals_signed",
            "blocking_register_ids": [
                "D014-PV-CAPACITY-APPROVAL-TEMPLATE_successor",
                "PV-ORIENT-001_values",
                "PV-PARAM-001_or_signed_amendment",
                "A-016",
                "future_node_allocation_rule",
                "FINAL-PAIRED-HP-PV-ACCEPTANCE",
            ],
        },
        "non_claims": [
            "No PV capacity value, II3050 growth factor, DC/AC convention, orientation/tilt bins, orientation/tilt weights, PR value, efficiency, conversion formula, or allocation number is approved.",
            "No PV generation, net-load, event detection, P(E), threshold run, capacity screen, manuscript result, or final paired HP/PV acceptance is produced.",
            "No building, roof, location-level, 3DBAG, or PV-map geometry workflow is implemented before the first experiment.",
            "PVGIS remains qualitative sanity/provenance context and is not a realized sampled WEATHER-001 path.",
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


def write_d014_pv_param_conversion_source_choice_packet(metadata_dir: str | Path = "data/metadata") -> Path:
    """Write the proposed PV-PARAM conversion source-choice packet and return its path."""
    directory = Path(metadata_dir) / "weather_pv"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / D014_PV_PARAM_CONVERSION_SOURCE_CHOICE_NAME
    path.write_text(
        json.dumps(build_d014_pv_param_conversion_source_choice_packet(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path



def write_d014_pv_first_experiment_approval_packet(metadata_dir: str | Path = "data/metadata") -> Path:
    """Write the proposed first-experiment PV approval packet and return its path."""
    directory = Path(metadata_dir) / "weather_pv"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / D014_PV_FIRST_EXPERIMENT_APPROVAL_NAME
    path.write_text(
        json.dumps(build_d014_pv_first_experiment_approval_packet(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare D-014 PV capacity source/value metadata.")
    parser.add_argument("--metadata-dir", default="data/metadata")
    parser.add_argument("--write-d014-source-value-packet", action="store_true")
    parser.add_argument("--write-d014-capacity-value-choice", action="store_true")
    parser.add_argument("--write-d014-capacity-approval-template", action="store_true")
    parser.add_argument("--write-d014-pv-executable-readiness-blockers", action="store_true")
    parser.add_argument("--write-d014-pv-executable-preflight-guard", action="store_true")
    parser.add_argument("--write-d014-statistical-orientation-tilt", action="store_true")
    parser.add_argument("--write-d014-orientation-tilt-source-choice", action="store_true")
    parser.add_argument("--write-d014-orientation-tilt-value-choice", action="store_true")
    parser.add_argument("--write-d014-pv-param-conversion-source-choice", action="store_true")
    parser.add_argument("--write-d014-pv-first-experiment-approval", action="store_true")
    parser.add_argument("--retrieve-d014-cbs-anchor-evidence", action="store_true")
    parser.add_argument("--retrieve-d014-ii3050-growth-evidence", action="store_true")
    args = parser.parse_args(argv)

    if args.write_d014_pv_executable_preflight_guard:
        path = write_d014_pv_executable_preflight_guard_packet(args.metadata_dir)
    elif args.write_d014_pv_executable_readiness_blockers:
        path = write_d014_pv_executable_readiness_blockers_packet(args.metadata_dir)
    elif args.write_d014_capacity_approval_template:
        path = write_d014_pv_capacity_approval_template_packet(args.metadata_dir)
    elif args.write_d014_capacity_value_choice:
        path = write_d014_pv_capacity_value_choice_packet(args.metadata_dir)
    elif args.retrieve_d014_ii3050_growth_evidence:
        path = retrieve_d014_ii3050_growth_evidence(metadata_dir=args.metadata_dir)
    elif args.retrieve_d014_cbs_anchor_evidence:
        path = retrieve_d014_cbs_capacity_anchor_evidence(metadata_dir=args.metadata_dir)
    elif args.write_d014_pv_first_experiment_approval:
        path = write_d014_pv_first_experiment_approval_packet(args.metadata_dir)
    elif args.write_d014_pv_param_conversion_source_choice:
        path = write_d014_pv_param_conversion_source_choice_packet(args.metadata_dir)
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
