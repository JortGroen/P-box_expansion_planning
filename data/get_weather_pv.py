from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import io
import json
import math
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence
from urllib import parse, request
import zipfile

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.sources import write_metadata
from src.weather_model import LOCAL_TIMEZONE, WeatherMember

PVGIS_API_BASE = "https://re.jrc.ec.europa.eu/api/v5_3"
KNMI_OPEN_DATA_BASE = "https://api.dataplatform.knmi.nl/open-data/v1"
KNMI_IN_SITU_DATASET_NAME = "10-minute-in-situ-meteorological-observations"
KNMI_IN_SITU_DATASET_VERSION = "1.0"
PVGIS_DOCUMENTATION_URL = (
    "https://joint-research-centre.ec.europa.eu/"
    "photovoltaic-geographical-information-system-pvgis/using-pvgis-5/"
    "api-non-interactive-service_en"
)
PVGIS_USAGE_CONDITIONS_URL = (
    "https://joint-research-centre.ec.europa.eu/"
    "photovoltaic-geographical-information-system-pvgis/general-information/"
    "usage-conditions-data-protection_en"
)
KNMI_OPEN_DATA_API_DOCS_URL = "https://developer.dataplatform.knmi.nl/open-data-api"
KNMI_IN_SITU_DOCS_URL = "https://dataplatform.knmi.nl/dataset/docs/10-minute-in-situ-meteorological-observations-1-0"
D004_SELECTION_ID = "d004_alkmaar_berkhout_2014_2023_v1"
D004_MEMBER_CONSTRUCTION_RULE_ID = "D004-MC-001"
D004_SOURCE = "knmi_station_249_hourly_q_t_plus_pvgis_sarah3_reference"
D004_YEARS = tuple(range(2014, 2024))
D004_STATION_ID = 249
D004_STATION_NAME = "Berkhout"
D004_MEMBER_MANIFEST_NAME = f"{D004_SELECTION_ID}_weather_members_manifest.json"
D004_MEMBER_METADATA_TEMPLATE = f"{D004_SELECTION_ID}_member_{{year}}_metadata.json"
D004_RETRIEVAL_MANIFEST = f"{D004_SELECTION_ID}_retrieval_manifest.json"


@dataclass(frozen=True)
class D004WeatherMemberBuildResult:
    """Constructed D-004 members plus their committed metadata paths."""

    members: tuple[WeatherMember, ...]
    metadata_paths: tuple[Path, ...]
    manifest_path: Path | None




def build_pvgis_seriescalc_url(
    *,
    lat: float,
    lon: float,
    startyear: int,
    endyear: int,
    peakpower_kw: float,
    loss_percent: float,
    angle_degrees: float,
    aspect_degrees: float,
    raddatabase: str | None = None,
    outputformat: str = "json",
) -> str:
    """Build a PVGIS hourly-series URL without making a network request."""
    params = {
        "lat": _finite_number(lat, "lat"),
        "lon": _finite_number(lon, "lon"),
        "startyear": _positive_int(startyear, "startyear"),
        "endyear": _positive_int(endyear, "endyear"),
        "pvcalculation": 1,
        "peakpower": _positive_number(peakpower_kw, "peakpower_kw"),
        "loss": _nonnegative_number(loss_percent, "loss_percent"),
        "angle": _finite_number(angle_degrees, "angle_degrees"),
        "aspect": _finite_number(aspect_degrees, "aspect_degrees"),
        "fixed": 1,
        "outputformat": outputformat,
        "browser": 0,
    }
    if raddatabase is not None:
        params["raddatabase"] = raddatabase
    if int(startyear) > int(endyear):
        raise ValueError("startyear must be less than or equal to endyear")
    return _url_with_query(f"{PVGIS_API_BASE}/seriescalc", params)


def build_pvgis_tmy_url(
    *,
    lat: float,
    lon: float,
    raddatabase: str | None = None,
    outputformat: str = "json",
) -> str:
    """Build a PVGIS typical-year URL for calibration/validation metadata."""
    params = {
        "lat": _finite_number(lat, "lat"),
        "lon": _finite_number(lon, "lon"),
        "outputformat": outputformat,
        "browser": 0,
    }
    if raddatabase is not None:
        params["raddatabase"] = raddatabase
    return _url_with_query(f"{PVGIS_API_BASE}/tmy", params)


def build_knmi_file_list_url(
    *,
    dataset_name: str = KNMI_IN_SITU_DATASET_NAME,
    dataset_version: str = KNMI_IN_SITU_DATASET_VERSION,
    max_keys: int | None = None,
    start_after_filename: str | None = None,
) -> str:
    """Build the KNMI Open Data file-list endpoint without API credentials."""
    url = f"{KNMI_OPEN_DATA_BASE}/datasets/{dataset_name}/versions/{dataset_version}/files"
    params: dict[str, object] = {}
    if max_keys is not None:
        params["maxKeys"] = _positive_int(max_keys, "max_keys")
    if start_after_filename:
        params["startAfterFilename"] = start_after_filename
    return _url_with_query(url, params)


def build_knmi_temporary_url_endpoint(
    filename: str,
    *,
    dataset_name: str = KNMI_IN_SITU_DATASET_NAME,
    dataset_version: str = KNMI_IN_SITU_DATASET_VERSION,
) -> str:
    """Build the KNMI endpoint that returns a temporary download URL."""
    if not filename:
        raise ValueError("filename must be non-empty")
    safe_filename = parse.quote(filename, safe="")
    return (
        f"{KNMI_OPEN_DATA_BASE}/datasets/{dataset_name}/versions/"
        f"{dataset_version}/files/{safe_filename}/url"
    )


def sha256_file(path: Path) -> str:
    """Return the SHA-256 checksum for a local file."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_d004_weather_members(
    *,
    root_dir: str | Path = ".",
    metadata_dir: str | Path = "data/metadata",
    years: Sequence[int] = D004_YEARS,
    write_member_metadata: bool = False,
    builder_command: str = "data/get_weather_pv.py --build-d004-weather-members",
) -> D004WeatherMemberBuildResult:
    """Build approved D-004 WEATHER-001 members from local recorded raw files.

    This implements D004-MC-001 only. PVGIS files are copied into provenance as
    calibration/validation references and are not sampled as realized weather.
    """
    root = Path(root_dir)
    metadata_root = Path(metadata_dir)
    retrieval_manifest_path = metadata_root / "weather_pv" / D004_RETRIEVAL_MANIFEST
    retrieval_manifest = _load_json(retrieval_manifest_path)
    source_files = _verify_d004_source_files(root, retrieval_manifest)
    records = _load_knmi_station_records(source_files["knmi"])
    pvgis_provenance = _pvgis_reference_provenance(source_files["pvgis"])

    members: list[WeatherMember] = []
    metadata_payloads: list[dict[str, Any]] = []
    for year in tuple(int(item) for item in years):
        hourly = _select_complete_knmi_year(records, year)
        timestamps_utc, timestamps_local, temperature_c, ghi_w_per_m2 = _expand_knmi_hourly_to_15min(hourly)
        member = WeatherMember(
            member_id=f"d004_alkmaar_berkhout_{year}_v1",
            shared_weather_driver_id=f"{D004_SELECTION_ID}:{year}",
            source=D004_SOURCE,
            timestamps_utc=timestamps_utc,
            timestamps_local=timestamps_local,
            temperature_c=temperature_c,
            pv_weather_fields={"ghi_w_per_m2": ghi_w_per_m2},
            provenance={
                "data_id": "D-004",
                "selection_id": D004_SELECTION_ID,
                "member_construction_rule_id": D004_MEMBER_CONSTRUCTION_RULE_ID,
                "knmi": _knmi_provenance(source_files["knmi"], year),
                "pvgis": pvgis_provenance,
                "construction": {
                    "builder_command": builder_command,
                    "calendar_year_basis": "UTC calendar year",
                    "hourly_to_15min_temperature_rule": "repeat KNMI hourly T/10 over four quarter-hour timestamps",
                    "hourly_to_15min_ghi_rule": "repeat KNMI hourly-average Q-derived GHI over four quarter-hour sub-intervals",
                    "local_timezone": LOCAL_TIMEZONE,
                    "weather_model_contract_path": "src/weather_model.py",
                },
            },
            metadata={
                "year": year,
                "station_id": D004_STATION_ID,
                "station_name": D004_STATION_NAME,
                "status": "constructed_from_approved_rule_pending_final_d004_source_acceptance",
                "raw_data_committed": False,
                "pvgis_realized_weather_path": False,
            },
        )
        members.append(member)
        metadata_payloads.append(_member_metadata_payload(member, hourly, source_files))

    metadata_paths: tuple[Path, ...] = ()
    manifest_path: Path | None = None
    if write_member_metadata:
        output_dir = metadata_root / "weather_pv"
        output_dir.mkdir(parents=True, exist_ok=True)
        metadata_paths = tuple(
            _write_json(output_dir / D004_MEMBER_METADATA_TEMPLATE.format(year=payload["year"]), payload)
            for payload in metadata_payloads
        )
        manifest_path = _write_json(
            output_dir / D004_MEMBER_MANIFEST_NAME,
            _member_library_manifest_payload(metadata_payloads, retrieval_manifest),
        )
    return D004WeatherMemberBuildResult(
        members=tuple(members),
        metadata_paths=metadata_paths,
        manifest_path=manifest_path,
    )


def write_retrieval_plan(metadata_dir: str | Path = "data/metadata") -> Path:
    """Write the D-004 weather/PV retrieval protocol without downloading data."""
    directory = Path(metadata_dir) / "weather_pv"
    directory.mkdir(parents=True, exist_ok=True)
    write_metadata(
        "D-004",
        metadata_dir,
        extra={
            "e2_s4_support": "retrieval URL builders, checksum recording, and PV/weather-member validation",
            "download_performed": False,
        },
    )
    payload: dict[str, Any] = {
        "data_id": "D-004",
        "created_utc": _now_utc_iso(),
        "download_performed": False,
        "raw_data_committed": False,
        "status": "proposed; no concrete KNMI or PVGIS file selected in this manifest",
        "pvgis": {
            "api_base": PVGIS_API_BASE,
            "tools": ["seriescalc", "tmy"],
            "typical_year_use": "calibration_or_validation_only",
            "realized_weather_path_use": False,
        },
        "knmi": {
            "api_base": KNMI_OPEN_DATA_BASE,
            "dataset_name": KNMI_IN_SITU_DATASET_NAME,
            "selected_dataset_version": None,
            "dataset_version_example": KNMI_IN_SITU_DATASET_VERSION,
            "authorization_header_stored": False,
            "file_list_endpoint_example": build_knmi_file_list_url(),
        },
        "alea_001": {
            "common_calendar_required": True,
            "complete_chronological_paths_required": True,
            "hp_and_pv_same_weather_member_required": True,
            "member_identity_fields": [
                "member_id",
                "source",
                "timestamps_utc",
                "timestamps_local",
                "temperature_c",
                "ghi_w_per_m2",
            ],
        },
        "checksum_policy": {
            "algorithm": "sha256",
            "record_function": "record_local_file",
            "no_checksum_recorded_without_concrete_local_file": True,
        },
    }
    path = directory / "d004_weather_pv_retrieval_plan.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def build_d004_execution_plan() -> dict[str, Any]:
    """Return the no-download D-004 raw retrieval execution plan.

    Concrete station/site/year values remain PI-selected data choices. Keeping
    placeholders explicit prevents a metadata plan from silently becoming a
    source selection.
    """
    pvgis_series_placeholder = build_pvgis_seriescalc_url(
        lat=0.0,
        lon=0.0,
        startyear=2005,
        endyear=2023,
        peakpower_kw=1.0,
        loss_percent=14.0,
        angle_degrees=35.0,
        aspect_degrees=0.0,
        raddatabase="PVGIS-SARAH3",
    )
    pvgis_tmy_placeholder = build_pvgis_tmy_url(
        lat=0.0,
        lon=0.0,
        raddatabase="PVGIS-SARAH3",
    )
    return {
        "data_id": "D-004",
        "status": (
            "execution plan only; no raw PVGIS/KNMI download performed, no "
            "concrete station/site/year bundle selected, and PI sign-off pending"
        ),
        "created_utc": _now_utc_iso(),
        "download_performed": False,
        "raw_data_committed": False,
        "data_register_status": "proposed",
        "shared_weather_contract": {
            "decision_id": "WEATHER-001",
            "question_id": "Q-8",
            "neutral_paths_owned": True,
            "implemented_paths": ["src/weather_model.py", "tests/test_weather_model.py"],
            "effect": "D-004 member builders must emit the neutral WeatherMember contract so HP and PV consume one shared weather realization",
        },
        "official_source_verification": {
            "verified_on": "2026-07-21",
            "pvgis": {
                "api_docs": PVGIS_DOCUMENTATION_URL,
                "usage_conditions": PVGIS_USAGE_CONDITIONS_URL,
                "api_base": PVGIS_API_BASE,
                "version": "PVGIS 5.3",
                "license_or_terms": "PVGIS information is free with no restrictions on use per official usage-conditions page",
                "api_facts": [
                    "GET is the supported computation method; HEAD confirms function existence only.",
                    "PVGIS 5.3 entry point is https://re.jrc.ec.europa.eu/api/v5_3/{tool_name}.",
                    "Relevant tools are seriescalc for hourly time series and tmy for typical-year reference output.",
                    "PVGIS 5.3 SARAH-3/ERA5 coverage is documented through 2023.",
                ],
                "expected_size_bytes": None,
                "expected_size_note": "PVGIS API pages do not publish response byte sizes; record response Content-Length when available and final SHA-256/size after retrieval.",
            },
            "knmi": {
                "api_docs": KNMI_OPEN_DATA_API_DOCS_URL,
                "dataset_docs": KNMI_IN_SITU_DOCS_URL,
                "api_base": KNMI_OPEN_DATA_BASE,
                "dataset_name": KNMI_IN_SITU_DATASET_NAME,
                "dataset_version": KNMI_IN_SITU_DATASET_VERSION,
                "license_or_terms": "D-004 register records KNMI 10-minute in-situ dataset as CC-BY-4.0; reconfirm on concrete dataset metadata before retrieval.",
                "api_facts": [
                    "Open Data API endpoints require an Authorization header.",
                    "List files endpoint: /datasets/{datasetName}/versions/{versionId}/files.",
                    "Temporary download URL endpoint: /datasets/{datasetName}/versions/{versionId}/files/{filename}/url.",
                    "The dataset is NetCDF, UTC timestamped, available from 2012-01-01, and may be incomplete/unvalidated because it is a near-real-time product archive.",
                    "Avoid excessive polling; use narrow file listing or notification/bulk-key route if a large multi-year bundle is approved.",
                ],
                "expected_size_bytes": None,
                "expected_size_note": "Public dataset documentation does not list per-file byte sizes; capture file-list metadata and temporary URL Content-Length before download when available.",
            },
        },
        "pi_selection_required_before_raw_download": [
            "D004_SELECTION_ID",
            "PVGIS latitude/longitude and whether those coordinates are the grid area, representative CBS cluster, or another signed site proxy",
            "PVGIS radiation database, years, PV system capacity, losses, tilt, azimuth, and whether seriescalc is a reference only or feeds an approved irradiance bridge",
            "KNMI station or station-selection rule, calendar years, file names or listing filters, and required variables",
            "Whether KNMI 10-minute in-situ incompleteness is acceptable or whether a validated hourly/daily KNMI source should replace it",
            "Whether expected runtime and file volume require the long-run notice below before execution",
        ],
        "target_paths": {
            "raw_root": "data/raw/weather_pv",
            "pvgis_raw_dir": "data/raw/weather_pv/pvgis/<D004_SELECTION_ID>",
            "knmi_raw_dir": "data/raw/weather_pv/knmi/<D004_SELECTION_ID>",
            "pvgis_series_raw": "data/raw/weather_pv/pvgis/<D004_SELECTION_ID>/pvgis_seriescalc_<D004_SELECTION_ID>.json",
            "pvgis_tmy_raw": "data/raw/weather_pv/pvgis/<D004_SELECTION_ID>/pvgis_tmy_<D004_SELECTION_ID>.json",
            "knmi_file_list_metadata": "data/metadata/weather_pv/d004_knmi_file_list_<D004_SELECTION_ID>.json",
            "download_checkpoint": "data/metadata/weather_pv/d004_download_checkpoint_<D004_SELECTION_ID>.json",
            "source_metadata_dir": "data/metadata/weather_pv",
        },
        "exact_commands_after_pi_selection": {
            "metadata_only_refresh": ".\\.venv\\Scripts\\python.exe data/get_weather_pv.py --write-execution-plan",
            "pvgis_series_url_template": pvgis_series_placeholder.replace("lat=0.0", "lat=<PI_SIGNED_LAT>").replace("lon=0.0", "lon=<PI_SIGNED_LON>"),
            "pvgis_tmy_url_template": pvgis_tmy_placeholder.replace("lat=0.0", "lat=<PI_SIGNED_LAT>").replace("lon=0.0", "lon=<PI_SIGNED_LON>"),
            "pvgis_series_download": ".\\.venv\\Scripts\\python.exe data/get_weather_pv.py --download-url \"<PI_SIGNED_PVGIS_SERIESCALC_URL>\" --output-path \"data/raw/weather_pv/pvgis/<D004_SELECTION_ID>/pvgis_seriescalc_<D004_SELECTION_ID>.json\" --timeout-s 300",
            "pvgis_series_checksum": ".\\.venv\\Scripts\\python.exe data/get_weather_pv.py --record-local-file \"data/raw/weather_pv/pvgis/<D004_SELECTION_ID>/pvgis_seriescalc_<D004_SELECTION_ID>.json\" --source-kind pvgis --file-role calibration_or_validation_reference --source-url \"<PI_SIGNED_PVGIS_SERIESCALC_URL>\"",
            "pvgis_tmy_download": ".\\.venv\\Scripts\\python.exe data/get_weather_pv.py --download-url \"<PI_SIGNED_PVGIS_TMY_URL>\" --output-path \"data/raw/weather_pv/pvgis/<D004_SELECTION_ID>/pvgis_tmy_<D004_SELECTION_ID>.json\" --timeout-s 300",
            "pvgis_tmy_checksum": ".\\.venv\\Scripts\\python.exe data/get_weather_pv.py --record-local-file \"data/raw/weather_pv/pvgis/<D004_SELECTION_ID>/pvgis_tmy_<D004_SELECTION_ID>.json\" --source-kind pvgis --file-role typical_year_calibration_or_validation_only --source-url \"<PI_SIGNED_PVGIS_TMY_URL>\"",
            "knmi_list_files": "$Files = Invoke-RestMethod -Headers @{Authorization=$env:KNMI_API_KEY} -Uri \"https://api.dataplatform.knmi.nl/open-data/v1/datasets/10-minute-in-situ-meteorological-observations/versions/1.0/files?maxKeys=<PI_SIGNED_MAX_KEYS>&startAfterFilename=<PI_SIGNED_START_AFTER>\"; $Files | ConvertTo-Json -Depth 20 | Set-Content -Encoding UTF8 \"data/metadata/weather_pv/d004_knmi_file_list_<D004_SELECTION_ID>.json\"",
            "knmi_get_temporary_url": "$DownloadUrl = (Invoke-RestMethod -Headers @{Authorization=$env:KNMI_API_KEY} -Uri \"https://api.dataplatform.knmi.nl/open-data/v1/datasets/10-minute-in-situ-meteorological-observations/versions/1.0/files/<PI_SIGNED_KNMI_FILENAME>/url\").temporaryDownloadUrl",
            "knmi_download": ".\\.venv\\Scripts\\python.exe data/get_weather_pv.py --download-url $DownloadUrl --output-path \"data/raw/weather_pv/knmi/<D004_SELECTION_ID>/<PI_SIGNED_KNMI_FILENAME>\" --timeout-s 300",
            "knmi_checksum": ".\\.venv\\Scripts\\python.exe data/get_weather_pv.py --record-local-file \"data/raw/weather_pv/knmi/<D004_SELECTION_ID>/<PI_SIGNED_KNMI_FILENAME>\" --source-kind knmi --file-role historical_weather_path --source-url \"https://api.dataplatform.knmi.nl/open-data/v1/datasets/10-minute-in-situ-meteorological-observations/versions/1.0/files/<PI_SIGNED_KNMI_FILENAME>/url\"",
        },
        "checkpoint_resume_plan": {
            "required_before_bulk_or_slow_download": True,
            "current_download_helper_resume_capable": False,
            "policy": [
                "Do not start raw D-004 retrieval until the PI has approved the source selection and the long-run notice.",
                "For small PVGIS JSON responses, a failed retrieval may be restarted from byte 0 because no partial file is accepted without final checksum metadata.",
                "For KNMI multi-file or any run expected to exceed 15 minutes, extend the executor before launch to stream each file to a .tmp path, checkpoint after each file and at least every 64 MiB, and atomically promote only after final SHA-256 verification.",
                "A resume run must validate source URL, target path, bytes already present, partial SHA-256 at the checkpoint boundary, and next pending filename before skipping work.",
            ],
            "checkpoint_fields": [
                "selection_id",
                "code_git_commit",
                "source_urls",
                "target_paths",
                "completed_files",
                "bytes_downloaded",
                "partial_sha256",
                "final_sha256",
                "next_file",
                "resume_command",
            ],
        },
        "long_run_notice_text": (
            "LONG-RUN NOTICE\n"
            "Task: E2.S4 / D-004 concrete PVGIS/KNMI weather-PV retrieval and checksum recording\n"
            "Process: PI-approved PVGIS JSON retrieval plus KNMI Open Data API file-list, temporary-URL, and NetCDF downloads for <D004_SELECTION_ID>\n"
            "Estimated wall time: unknown until the PI-selected station/year/file list is enumerated; PVGIS JSON is expected to be small, but KNMI multi-year 10-minute NetCDF retrieval may exceed 15 minutes depending on file count and network. Stop for PI approval if the enumerated plan estimates more than 15 minutes.\n"
            "Resource impact: network transfer of PVGIS JSON plus selected KNMI NetCDF files; light CPU for SHA-256 hashing; raw files under data/raw/weather_pv remain ignored; metadata/checkpoints under data/metadata/weather_pv remain committed only after review.\n"
            "Checkpoint plan: before raw download, write data/metadata/weather_pv/d004_download_checkpoint_<D004_SELECTION_ID>.json with source URLs, target paths, expected files, completed files, bytes downloaded, partial/final SHA-256 values, and next file. For bulk/slow KNMI retrieval, checkpoint after each file and at least every 64 MiB within a large file, writing to .tmp and atomically promoting only after final checksum.\n"
            "Resume procedure: rerun the PI-approved retrieval command for <D004_SELECTION_ID>; validate the checkpoint source URLs, target paths, partial SHA-256, and completed-file list; skip files with matching final checksum metadata; resume or restart the next .tmp file; after completion update D-004 only as proposed and do not mark D-004 PI-signed."
        ),
        "acceptance_boundary": [
            "This plan does not approve site, station, year, PV system, or radiation-database choices.",
            "This plan does not make PVGIS TMY a realized weather member.",
            "WEATHER-001 resolves Q-8 at the contract level; this plan does not create accepted D-004 weather members.",
            "DATA_REGISTER D-004 must be updated only after concrete file/version/checksum selections are made for PI review.",
        ],
    }


def write_execution_plan(metadata_dir: str | Path = "data/metadata") -> Path:
    """Write the metadata-only D-004 retrieval execution plan."""
    write_retrieval_plan(metadata_dir)
    directory = Path(metadata_dir) / "weather_pv"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "d004_weather_pv_execution_plan.json"
    payload = build_d004_execution_plan()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def record_local_file(
    *,
    file_path: str | Path,
    source_kind: str,
    file_role: str,
    metadata_dir: str | Path = "data/metadata",
    source_url: str | None = None,
    extra: Mapping[str, object] | None = None,
) -> Path:
    """Record checksum metadata for a concrete local D-004 source file."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    source_kind_normalized = source_kind.lower()
    if source_kind_normalized not in {"knmi", "pvgis"}:
        raise ValueError("source_kind must be 'knmi' or 'pvgis'")
    if not file_role:
        raise ValueError("file_role must be non-empty")

    directory = Path(metadata_dir) / "weather_pv"
    directory.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "data_id": "D-004",
        "created_utc": _now_utc_iso(),
        "source_kind": source_kind_normalized,
        "file_role": file_role,
        "path": path.as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256_file": sha256_file(path),
        "source_url": source_url,
        "raw_data_committed": False,
        "status": "local file checksum recorded; DATA_REGISTER must be updated only after PI accepts the concrete selection",
    }
    if extra:
        payload["extra"] = dict(sorted(extra.items()))
    stem = _safe_stem(path.stem)
    manifest_path = directory / f"d004_{source_kind_normalized}_{stem}_metadata.json"
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path


def download_url_to_file(
    *,
    url: str,
    output_path: str | Path,
    timeout_s: float,
    authorization_header: str | None = None,
) -> Path:
    """Download a single URL to a local path and return the written file path."""
    if not url:
        raise ValueError("url must be non-empty")
    if timeout_s <= 0:
        raise ValueError("timeout_s must be positive")
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    headers = {"Authorization": authorization_header} if authorization_header else {}
    req = request.Request(url, headers=headers)
    with request.urlopen(req, timeout=timeout_s) as response:
        destination.write_bytes(response.read())
    return destination


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record KNMI/PVGIS source metadata for D-004.")
    parser.add_argument("--metadata-dir", default="data/metadata")
    parser.add_argument("--write-retrieval-plan", action="store_true")
    parser.add_argument("--write-execution-plan", action="store_true")
    parser.add_argument("--record-local-file")
    parser.add_argument("--source-kind", choices=["knmi", "pvgis"])
    parser.add_argument("--file-role", default="source")
    parser.add_argument("--source-url")
    parser.add_argument("--download-url")
    parser.add_argument("--output-path")
    parser.add_argument("--timeout-s", type=float, default=120.0)
    parser.add_argument("--authorization-env")
    parser.add_argument("--build-d004-weather-members", action="store_true")
    parser.add_argument("--root-dir", default=".")
    args = parser.parse_args(argv)

    if args.write_retrieval_plan:
        path = write_retrieval_plan(args.metadata_dir)
        print(path)
        return 0
    if args.write_execution_plan:
        path = write_execution_plan(args.metadata_dir)
        print(path)
        return 0
    if args.record_local_file:
        if args.source_kind is None:
            parser.error("--source-kind is required with --record-local-file")
        path = record_local_file(
            file_path=args.record_local_file,
            source_kind=args.source_kind,
            file_role=args.file_role,
            metadata_dir=args.metadata_dir,
            source_url=args.source_url,
        )
        print(path)
        return 0
    if args.download_url or args.output_path:
        if not args.download_url or not args.output_path:
            parser.error("--download-url and --output-path must be provided together")
        authorization = None
        if args.authorization_env:
            import os

            authorization = os.environ.get(args.authorization_env)
            if not authorization:
                parser.error(f"Environment variable {args.authorization_env!r} is not set")
        path = download_url_to_file(
            url=args.download_url,
            output_path=args.output_path,
            timeout_s=args.timeout_s,
            authorization_header=authorization,
        )
        print(path)
        return 0

    if args.build_d004_weather_members:
        result = build_d004_weather_members(
            root_dir=args.root_dir,
            metadata_dir=args.metadata_dir,
            write_member_metadata=True,
        )
        if result.manifest_path is not None:
            print(result.manifest_path)
        for path in result.metadata_paths:
            print(path)
        return 0

    path = write_metadata(
        "D-004",
        Path(args.metadata_dir),
        extra={
            "g0_weather_scope": "KNMI historical winters including at least one design-cold winter",
            "e2_s4_support": "run with --write-retrieval-plan for PVGIS/KNMI endpoint and checksum protocol metadata",
        },
    )
    print(path)
    return 0


def _url_with_query(base_url: str, params: Mapping[str, object]) -> str:
    if not params:
        return base_url
    return f"{base_url}?{parse.urlencode(params)}"


def _finite_number(value: float, name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _positive_number(value: float, name: str) -> float:
    number = _finite_number(value, name)
    if number <= 0:
        raise ValueError(f"{name} must be positive")
    return number


def _nonnegative_number(value: float, name: str) -> float:
    number = _finite_number(value, name)
    if number < 0:
        raise ValueError(f"{name} must be non-negative")
    return number


def _positive_int(value: int, name: str) -> int:
    number = int(value)
    if number <= 0:
        raise ValueError(f"{name} must be positive")
    return number


def _safe_stem(value: str) -> str:
    safe = "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in value)
    return safe or "source"


def _now_utc_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _verify_d004_source_files(root: Path, retrieval_manifest: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    files = retrieval_manifest.get("source_files")
    if not isinstance(files, list):
        raise ValueError("D-004 retrieval manifest lacks source_files")
    grouped: dict[str, list[dict[str, Any]]] = {"knmi": [], "pvgis": []}
    for raw_item in files:
        if not isinstance(raw_item, Mapping):
            raise ValueError("D-004 source_files entries must be objects")
        item = dict(raw_item)
        kind = str(item.get("source_kind", "")).lower()
        if kind not in grouped:
            raise ValueError(f"unsupported D-004 source kind: {kind}")
        path = root / str(item["path"])
        if not path.is_file():
            raise FileNotFoundError(path)
        size = path.stat().st_size
        digest = sha256_file(path)
        if size != int(item["size_bytes"]):
            raise ValueError(f"{path} size {size} does not match retrieval manifest")
        if digest != item["sha256_file"]:
            raise ValueError(f"{path} sha256 does not match retrieval manifest")
        item["verified_path"] = path.as_posix()
        item["verified_size_bytes"] = size
        item["verified_sha256_file"] = digest
        grouped[kind].append(item)
    if len(grouped["knmi"]) != 2 or len(grouped["pvgis"]) != 2:
        raise ValueError("D-004 builder expects exactly two KNMI and two PVGIS source files")
    return grouped


def _load_knmi_station_records(source_files: Sequence[Mapping[str, Any]]) -> dict[datetime, dict[str, Any]]:
    records: dict[datetime, dict[str, Any]] = {}
    for source_file in source_files:
        path = Path(str(source_file["verified_path"]))
        with zipfile.ZipFile(path) as archive:
            text_names = [name for name in archive.namelist() if name.lower().endswith(".txt")]
            if len(text_names) != 1:
                raise ValueError(f"{path} must contain exactly one KNMI text file")
            content = archive.read(text_names[0]).decode("latin-1")
        header: list[str] | None = None
        rows: list[str] = []
        for line in content.splitlines():
            if line.startswith("# STN,"):
                header = [_clean_knmi_column_name(item) for item in line.lstrip("# ").split(",")]
                continue
            if header is not None and line.strip() and not line.startswith("#"):
                rows.append(line)
        if header is None:
            raise ValueError(f"{path} lacks KNMI column header")
        for row in csv.DictReader(io.StringIO("\n".join(rows)), fieldnames=header, skipinitialspace=True):
            if int(_required_knmi_value(row, "STN")) != D004_STATION_ID:
                continue
            end_timestamp = _knmi_hour_ending_utc(
                yyyymmdd=_required_knmi_value(row, "YYYYMMDD"),
                hh=_required_knmi_value(row, "HH"),
            )
            if end_timestamp in records:
                raise ValueError(f"duplicate KNMI hour-ending timestamp: {end_timestamp.isoformat()}")
            records[end_timestamp] = {
                "end_timestamp_utc": end_timestamp,
                "temperature_c": int(_required_knmi_value(row, "T")) / 10.0,
                "q_j_per_cm2": int(_required_knmi_value(row, "Q")),
                "source_zip_path": path.as_posix(),
            }
    return records


def _select_complete_knmi_year(records: Mapping[datetime, Mapping[str, Any]], year: int) -> tuple[Mapping[str, Any], ...]:
    expected_end_times = tuple(_utc_hour_endings_for_year(year))
    selected: list[Mapping[str, Any]] = []
    missing: list[str] = []
    for timestamp in expected_end_times:
        record = records.get(timestamp)
        if record is None:
            missing.append(timestamp.isoformat())
        else:
            selected.append(record)
    if missing:
        raise ValueError(f"KNMI station {D004_STATION_ID} year {year} is incomplete; first missing {missing[0]}")
    return tuple(selected)


def _expand_knmi_hourly_to_15min(
    hourly: Sequence[Mapping[str, Any]],
) -> tuple[tuple[datetime, ...], tuple[datetime, ...], tuple[float, ...], tuple[float, ...]]:
    from zoneinfo import ZoneInfo

    local_zone = ZoneInfo(LOCAL_TIMEZONE)
    timestamps_utc: list[datetime] = []
    timestamps_local: list[datetime] = []
    temperature_c: list[float] = []
    ghi_w_per_m2: list[float] = []
    for record in hourly:
        end_timestamp = record["end_timestamp_utc"]
        if not isinstance(end_timestamp, datetime):
            raise ValueError("KNMI record timestamp is malformed")
        start_timestamp = end_timestamp - timedelta(hours=1)
        ghi = float(record["q_j_per_cm2"]) * 10000.0 / 3600.0
        if ghi < 0 or not math.isfinite(ghi):
            raise ValueError("KNMI Q-derived GHI must be finite and non-negative")
        temperature = float(record["temperature_c"])
        if not math.isfinite(temperature):
            raise ValueError("KNMI T-derived temperature must be finite")
        for offset_minutes in (0, 15, 30, 45):
            timestamp = start_timestamp + timedelta(minutes=offset_minutes)
            timestamps_utc.append(timestamp)
            timestamps_local.append(timestamp.astimezone(local_zone))
            temperature_c.append(temperature)
            ghi_w_per_m2.append(ghi)
    return tuple(timestamps_utc), tuple(timestamps_local), tuple(temperature_c), tuple(ghi_w_per_m2)


def _member_metadata_payload(
    member: WeatherMember,
    hourly: Sequence[Mapping[str, Any]],
    source_files: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    year = int(member.metadata["year"])
    q_total_j_per_cm2 = sum(int(record["q_j_per_cm2"]) for record in hourly)
    ghi = member.ghi_w_per_m2
    temperature = member.temperature_c
    expanded_energy = float(ghi.sum() * 900.0 / 10000.0)
    return {
        "data_id": "D-004",
        "selection_id": D004_SELECTION_ID,
        "member_construction_rule_id": D004_MEMBER_CONSTRUCTION_RULE_ID,
        "status": "constructed_from_approved_rule_pending_final_d004_source_acceptance",
        "year": year,
        "member_id": member.member_id,
        "shared_weather_driver_id": member.shared_weather_driver_id,
        "source": member.source,
        "content_sha256": member.content_sha256,
        "identity_record": member.identity_record(),
        "calendar": {
            "calendar_year_basis": "UTC calendar year",
            "timezone": LOCAL_TIMEZONE,
            "first_timestamp_utc": member.timestamps_utc[0].isoformat(),
            "last_timestamp_utc": member.timestamps_utc[-1].isoformat(),
            "first_timestamp_local": member.timestamps_local[0].isoformat(),
            "last_timestamp_local": member.timestamps_local[-1].isoformat(),
            "n_timesteps": member.n_timesteps,
            "cadence_seconds": member.cadence_seconds,
        },
        "knmi_hourly_source": {
            "station_id": D004_STATION_ID,
            "station_name": D004_STATION_NAME,
            "source_hourly_rows": len(hourly),
            "hour_semantics": "HH is UT hour-ending; HH=24 maps to 00:00 UTC on the following date",
            "temperature_conversion": "temperature_c = T / 10",
            "ghi_conversion": "ghi_w_per_m2 = Q_j_per_cm2 * 10000 / 3600",
            "hourly_to_15min_rule": "repeat T/10 and Q-derived hourly-average GHI over four quarter-hours",
            "q_total_j_per_cm2": q_total_j_per_cm2,
            "expanded_ghi_energy_j_per_cm2": expanded_energy,
            "energy_preservation_abs_error_j_per_cm2": abs(expanded_energy - q_total_j_per_cm2),
            "temperature_min_c": float(temperature.min()),
            "temperature_max_c": float(temperature.max()),
            "ghi_min_w_per_m2": float(ghi.min()),
            "ghi_max_w_per_m2": float(ghi.max()),
        },
        "source_files": {
            "knmi": [_source_file_record(item) for item in source_files["knmi"]],
            "pvgis": [_source_file_record(item) for item in source_files["pvgis"]],
        },
        "boundaries": [
            "D-004 remains proposed pending final PI source acceptance",
            "PVGIS-SARAH3 is provenance/calibration reference only, not a realized sampled weather path",
            "No HP/PV paired acceptance, cold-spell acceptance, net-load/event/P(E), capacity screen, or manuscript result is produced",
        ],
    }


def _member_library_manifest_payload(
    member_payloads: Sequence[Mapping[str, Any]],
    retrieval_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "data_id": "D-004",
        "selection_id": D004_SELECTION_ID,
        "member_construction_rule_id": D004_MEMBER_CONSTRUCTION_RULE_ID,
        "status": "constructed_from_approved_rule_pending_final_d004_source_acceptance",
        "retrieval_manifest_selection_id": retrieval_manifest.get("selection_id"),
        "retrieval_manifest_d004_status": retrieval_manifest.get("d004_status"),
        "members": [
            {
                "year": payload["year"],
                "member_id": payload["member_id"],
                "shared_weather_driver_id": payload["shared_weather_driver_id"],
                "content_sha256": payload["content_sha256"],
                "metadata_path": f"data/metadata/weather_pv/{D004_MEMBER_METADATA_TEMPLATE.format(year=payload['year'])}",
                "n_timesteps": payload["calendar"]["n_timesteps"],
                "first_timestamp_utc": payload["calendar"]["first_timestamp_utc"],
                "last_timestamp_utc": payload["calendar"]["last_timestamp_utc"],
            }
            for payload in member_payloads
        ],
        "source_use_boundary": {
            "knmi": "realized temperature and GHI weather path",
            "pvgis": "calibration_or_validation_provenance_only",
            "pvgis_realized_weather_path": False,
        },
        "no_final_d004_acceptance": True,
        "no_integrated_analysis": True,
    }


def _knmi_provenance(source_files: Sequence[Mapping[str, Any]], year: int) -> dict[str, Any]:
    return {
        "station_id": D004_STATION_ID,
        "station_name": D004_STATION_NAME,
        "year": year,
        "source_files": [_source_file_record(item) for item in source_files],
        "source_columns": ["STN", "YYYYMMDD", "HH", "T", "Q"],
        "hour_semantics": "HH is UT hour-ending; HH=24 maps to 00:00 UTC on the following date",
        "unit_conversions": {
            "temperature_c": "T / 10",
            "ghi_w_per_m2": "Q_j_per_cm2 * 10000 / 3600",
        },
    }


def _pvgis_reference_provenance(source_files: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "use_boundary": "calibration_or_validation_provenance_only",
        "not_realized_weather_member_source": True,
        "radiation_database": "PVGIS-SARAH3",
        "site_latitude": 52.63167,
        "site_longitude": 4.74861,
        "system_configuration": {
            "peakpower_kw": 1.0,
            "loss_percent": 14.0,
            "angle_degrees": 35.0,
            "aspect_degrees": 0.0,
            "fixed": True,
        },
        "source_files": [_source_file_record(item) for item in source_files],
    }


def _source_file_record(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "file_role": item.get("file_role"),
        "path": item.get("path"),
        "source_kind": item.get("source_kind"),
        "source_url": item.get("source_url"),
        "size_bytes": item.get("size_bytes"),
        "sha256_file": item.get("sha256_file"),
    }


def _clean_knmi_column_name(value: str) -> str:
    return value.strip()


def _required_knmi_value(row: Mapping[str, str | None], key: str) -> str:
    value = row.get(key)
    if value is None or not value.strip():
        raise ValueError(f"KNMI row missing required {key}")
    return value.strip()


def _knmi_hour_ending_utc(*, yyyymmdd: str, hh: str) -> datetime:
    date = datetime.strptime(yyyymmdd, "%Y%m%d").replace(tzinfo=UTC)
    hour = int(hh)
    if hour < 1 or hour > 24:
        raise ValueError(f"KNMI HH must be in 1..24, got {hour}")
    return date + timedelta(hours=hour)


def _utc_hour_endings_for_year(year: int) -> tuple[datetime, ...]:
    start = datetime(int(year), 1, 1, 1, tzinfo=UTC)
    end = datetime(int(year) + 1, 1, 1, tzinfo=UTC)
    values: list[datetime] = []
    current = start
    while current <= end:
        values.append(current)
        current += timedelta(hours=1)
    return tuple(values)


if __name__ == "__main__":
    raise SystemExit(main())
