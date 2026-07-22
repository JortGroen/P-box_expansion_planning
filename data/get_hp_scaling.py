from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
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
DOWNLOAD_TIMEOUT_S = 120.0


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
            sample = archive.read(info)[:65536]
            text = sample.decode("utf-8-sig", errors="replace")
            first_line = text.splitlines()[0] if text.splitlines() else ""
            delimiter = ";" if first_line.count(";") >= first_line.count(",") else ","
            columns = first_line.split(delimiter) if first_line else []
            csv_summaries.append({"filename": info.filename, "delimiter_guess": delimiter, "column_count": len(columns), "columns": columns, "sampled_bytes": len(sample)})
    return {"zip_member_count": len(members), "zip_members": members, "csv_summaries": csv_summaries, "schema_inspection_scope": "ZIP directory and first 64 KiB of each CSV member only"}


def _planned_metadata_path(spec: HpScalingSourceSpec, metadata_dir: Path) -> Path:
    path = Path(spec.planned_metadata_path)
    if path.is_absolute():
        return path
    parts = path.parts
    if len(parts) >= 2 and parts[0] == "data" and parts[1] == "metadata":
        return metadata_dir.joinpath(*parts[2:])
    return metadata_dir / "hp_scaling" / path.name


def _write_source_metadata(*, spec: HpScalingSourceSpec, metadata_dir: Path, raw_path: Path, retrieved_url: str, schema_summary: dict[str, Any]) -> Path:
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
        "download_performed": True,
        "schema_summary": schema_summary,
        "status": "retrieved/checksummed for PI review; HP scaling values remain unsigned",
        "non_claims": [
            "No annual HP TWh values are executable.",
            "No 2035 HP adoption value is signed.",
            "No D-004 acceptance, net-load, event, P(E), threshold, capacity-screen, or manuscript analysis is run.",
        ],
    }
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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write or execute the HP-001 Alkmaar local scaling source route.")
    parser.add_argument("--metadata-dir", default="data/metadata")
    parser.add_argument("--write-plan", action="store_true", help="Write the approved retrieval/checksum/value route without downloading data.")
    parser.add_argument("--download", action="store_true", help="Retrieve/checksum the approved D-013 public sources; no values are produced.")
    parser.add_argument("--resume", action="store_true", help="Skip completed sources whose raw files match checkpoint byte size and SHA-256.")
    parser.add_argument("--raw-dir", default="data/raw/hp_scaling")
    args = parser.parse_args(argv)
    if args.download:
        path = retrieve_hp_scaling_sources(raw_dir=Path(args.raw_dir), metadata_dir=Path(args.metadata_dir), resume=args.resume)
    else:
        path = write_hp_scaling_retrieval_plan(Path(args.metadata_dir))
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
