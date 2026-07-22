from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.sources import write_metadata

DATA_ID = "D-013"
BUNDLE_ID = "hp001_alkmaar_gm0361_source_route_v1"
MUNICIPALITY_CODE = "GM0361"
MUNICIPALITY_NAME = "Alkmaar"


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
        planned_metadata_path=(
            "data/metadata/hp_scaling/cbs_85035ned_alkmaar_dwelling_stock_metadata.json"
        ),
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
        boundary=(
            "Provides stock/type evidence only; it does not provide heat demand, "
            "DHW demand, or 2035 HP adoption."
        ),
    ),
    HpScalingSourceSpec(
        key="pbl_startanalyse_2025_alkmaar",
        title="PBL Startanalyse aardgasvrije buurten 2025 Alkmaar municipality ZIP",
        source="PBL Planbureau voor de Leefomgeving",
        url=(
            "https://dataportaal.pbl.nl/Startanalyse_aardgasvrije_buurten/2025/"
            "Gemeentes"
        ),
        license_or_terms="CC BY 4.0 NL according to the PBL data portal",
        planned_raw_path="data/raw/hp_scaling/pbl_startanalyse_2025_alkmaar.zip",
        planned_metadata_path=(
            "data/metadata/hp_scaling/pbl_startanalyse_2025_alkmaar_metadata.json"
        ),
        expected_size_note="PBL municipality listing reports Alkmaar.zip as 215.1 kB",
        expected_runtime_note="expected seconds; no >15 minute run expected",
        role=(
            "local heat-demand, neighbourhood, and pathway/suitability context for Alkmaar"
        ),
        proposed_fields_or_filters=(
            "download link with visible filename Alkmaar.zip from the 2025 Gemeentes page",
            "buurt/wijk identifiers and municipality coverage",
            "residential heat-demand fields if present and documented",
            "space/DHW split only if explicit in the public file schema or documentation",
            "Startanalyse strategy/pathway and national-cost indicators as suitability context",
        ),
        boundary=(
            "Startanalyse pathway outputs are suitability/pathway evidence unless the PI "
            "separately signs a source-use rule for heat-demand scaling."
        ),
    ),
    HpScalingSourceSpec(
        key="cbs_85523ned_heat_pump_context",
        title="CBS StatLine 85523NED heat pumps by sector, capacity, and energy flows",
        source="CBS StatLine",
        url="https://opendata.cbs.nl/ODataApi/OData/85523NED",
        license_or_terms="CBS open data terms; cite CBS table page and retrieval timestamp",
        planned_raw_path="data/raw/hp_scaling/cbs_85523ned_heat_pump_context.json",
        planned_metadata_path=(
            "data/metadata/hp_scaling/cbs_85523ned_heat_pump_context_metadata.json"
        ),
        expected_size_note="small national/context table request after field filtering",
        expected_runtime_note="expected seconds to a few minutes; no >15 minute run expected",
        role="national/current heat-pump context and uncertainty framing",
        proposed_fields_or_filters=(
            "sector == Woningen where available",
            "air-source and ground/water-source categories",
            "in-use counts, thermal capacity, heat production, and energy-flow fields",
            "periods available through the latest public table version",
        ),
        boundary=(
            "Context only for this route; it is not a local Alkmaar 2035 adoption "
            "source and cannot make values executable."
        ),
    ),
)


def build_hp_scaling_retrieval_plan() -> dict[str, Any]:
    """Return the no-download HP-001 Alkmaar source-binding plan."""
    created_utc = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "data_id": DATA_ID,
        "bundle_id": BUNDLE_ID,
        "created_utc": created_utc,
        "status": "proposed retrieval/checksum/value-proposal route; no values executable",
        "download_performed": False,
        "geography": {
            "municipality_name": MUNICIPALITY_NAME,
            "municipality_code": MUNICIPALITY_CODE,
            "service_area_status": "proposed proxy for PI review",
        },
        "public_source_policy": {
            "public_sources_only": True,
            "private_thesis_policy": (
                "The PI-supplied private student thesis may be used only as "
                "confidential source-discovery guidance; it is not cited, quoted, "
                "committed, or used as value provenance."
            ),
        },
        "sources": [asdict(source) for source in HP_SCALING_SOURCES],
        "hp001_component_traceability": [
            {
                "component_id": "sfh_space",
                "building_class": "SFH",
                "end_use": "space",
                "when2heat_shape_column": "NL_heat_profile_space_SFH",
                "when2heat_cop_column": "NL_COP_ASHP_radiator",
                "annual_twh_source_status": "unsigned_local_value_pending",
            },
            {
                "component_id": "mfh_space",
                "building_class": "MFH",
                "end_use": "space",
                "when2heat_shape_column": "NL_heat_profile_space_MFH",
                "when2heat_cop_column": "NL_COP_ASHP_radiator",
                "annual_twh_source_status": "unsigned_local_value_pending",
            },
            {
                "component_id": "sfh_dhw",
                "building_class": "SFH",
                "end_use": "water",
                "when2heat_shape_column": "NL_heat_profile_water_SFH",
                "when2heat_cop_column": "NL_COP_ASHP_water",
                "annual_twh_source_status": "unsigned_local_value_pending",
            },
            {
                "component_id": "mfh_dhw",
                "building_class": "MFH",
                "end_use": "water",
                "when2heat_shape_column": "NL_heat_profile_water_MFH",
                "when2heat_cop_column": "NL_COP_ASHP_water",
                "annual_twh_source_status": "unsigned_local_value_pending",
            },
        ],
        "value_route": {
            "local_heat_demand": (
                "Future value proposal should extract or document public local heat-demand "
                "evidence first, then preserve space and DHW separately if the schema "
                "supports that interpretation."
            ),
            "suitability_pathway": (
                "PBL Startanalyse pathway/cost outputs are kept separate from demand and "
                "adoption; they can justify scenario plausibility only after PI source-use "
                "approval."
            ),
            "unsigned_2035_adoption": (
                "2035 HP adoption/electrification fractions or counts require a separate "
                "PI-signed scenario source before annual TWh values enter executable config."
            ),
        },
        "checksum_workflow": {
            "future_command": r".\.venv\Scripts\python.exe data\get_hp_scaling.py --download --resume",
            "checkpoint_path": (
                "data/metadata/hp_scaling/"
                "hp001_alkmaar_gm0361_retrieval_checkpoint.json"
            ),
            "checkpoint_behavior": (
                "After each source is retrieved, record URL, byte size, SHA-256, "
                "retrieval timestamp, and next pending source. Resume skips any source "
                "whose raw file still matches the checkpoint checksum."
            ),
            "atomic_write_behavior": (
                "Future downloads should write .tmp files under data/raw/hp_scaling, "
                "checksum them, then atomically replace the final raw path."
            ),
        },
        "long_run_notice": {
            "required_before_launch_if_expected_runtime_exceeds_15_minutes": True,
            "current_assessment": (
                "Planned public-source retrievals are small filtered CBS OData requests "
                "and one 215.1 kB PBL ZIP, so the route does not currently require a "
                "long-run notice before retrieval."
            ),
        },
        "blocked_or_out_of_scope": [
            "No executable annual TWh values are created.",
            "No D-004 acceptance or paired-weather cold-spell check is run.",
            "No net-load, event, P(E), threshold, capacity-screen, or manuscript-result analysis is run.",
            "No commercial heat is included in the primary route.",
        ],
    }


def write_hp_scaling_retrieval_plan(metadata_dir: Path) -> Path:
    """Write D-013 metadata and the no-download route plan for PI review."""
    write_metadata(DATA_ID, metadata_dir)
    target_dir = metadata_dir / "hp_scaling"
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{BUNDLE_ID}_plan.json"
    payload = build_hp_scaling_retrieval_plan()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Write the proposed no-download HP-001 Alkmaar local scaling source route."
        )
    )
    parser.add_argument("--metadata-dir", default="data/metadata")
    parser.add_argument(
        "--write-plan",
        action="store_true",
        help="Write the proposed retrieval/checksum/value route without downloading data.",
    )
    args = parser.parse_args(argv)

    path = write_hp_scaling_retrieval_plan(Path(args.metadata_dir))
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
