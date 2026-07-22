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
from src.weather_model import LOCAL_TIMEZONE, WeatherMember, assert_same_weather_realization

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
D004_MEMBER_READINESS_DIAGNOSTICS_NAME = f"{D004_SELECTION_ID}_member_readiness_diagnostics.json"
D004_ACCEPTANCE_PACKET_NAME = f"{D004_SELECTION_ID}_acceptance_packet.json"


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


def build_d004_member_readiness_diagnostics(
    *,
    root_dir: str | Path = ".",
    metadata_dir: str | Path = "data/metadata",
    include_raw_diagnostics: bool = True,
) -> dict[str, Any]:
    """Build D-004 member-readiness diagnostics without signing acceptance."""
    root = Path(root_dir)
    metadata_root = Path(metadata_dir)
    manifest_path = metadata_root / "weather_pv" / D004_MEMBER_MANIFEST_NAME
    retrieval_manifest_path = metadata_root / "weather_pv" / D004_RETRIEVAL_MANIFEST
    manifest = _load_json(manifest_path)
    retrieval_manifest = _load_json(retrieval_manifest_path)
    members = manifest.get("members")
    if not isinstance(members, list):
        raise ValueError("D-004 member manifest lacks members")

    member_checks = [_diagnose_committed_member_metadata(root, metadata_root, item) for item in members]
    expected_years = list(D004_YEARS)
    manifest_checks = {
        "status": manifest.get("status"),
        "members_present": len(members),
        "expected_members": len(expected_years),
        "years": [item["year"] for item in member_checks],
        "years_match_2014_2023": [item["year"] for item in member_checks] == expected_years,
        "unique_member_ids": len({item["member_id"] for item in member_checks}) == len(member_checks),
        "unique_shared_weather_driver_ids": len({item["shared_weather_driver_id"] for item in member_checks})
        == len(member_checks),
        "unique_content_sha256": len({item["content_sha256"] for item in member_checks}) == len(member_checks),
        "all_metadata_files_present": all(item["metadata_file_present"] for item in member_checks),
        "all_calendar_cadence_ok": all(item["calendar_cadence_ok"] for item in member_checks),
        "all_energy_preserved": all(item["energy_preservation_ok"] for item in member_checks),
        "all_temperature_finite": all(item["temperature_finite"] for item in member_checks),
        "all_ghi_nonnegative": all(item["ghi_nonnegative"] for item in member_checks),
        "pvgis_realized_weather_path": manifest.get("source_use_boundary", {}).get("pvgis_realized_weather_path"),
        "no_final_d004_acceptance": manifest.get("no_final_d004_acceptance"),
        "no_integrated_analysis": manifest.get("no_integrated_analysis"),
    }
    raw_source_checks = _diagnose_retrieval_manifest_sources(root, retrieval_manifest)
    raw_available = all(item["local_file_present"] for item in raw_source_checks)
    payload: dict[str, Any] = {
        "data_id": "D-004",
        "selection_id": D004_SELECTION_ID,
        "diagnostics_created_utc": _now_utc_iso(),
        "status": "readiness_diagnostics_pending_pi_review",
        "d004_final_acceptance": False,
        "no_integrated_analysis": True,
        "no_manuscript_results": True,
        "diagnostic_scope": [
            "committed WEATHER-001 member manifest and per-member metadata validation",
            "raw source checksum/provenance verification when ignored local raw files are present",
            "UTC/local calendar and 15-minute cadence consistency checks",
            "KNMI-Q energy-preservation and finite/nonnegative weather-channel checks",
            "PVGIS/KNMI seasonal and peak diagnostics without signed tolerances",
            "HP/PV paired-weather readiness based on shared_weather_driver_id and content identity",
        ],
        "manifest_checks": manifest_checks,
        "member_checks": member_checks,
        "raw_source_checks": raw_source_checks,
        "pvgis_knmi_seasonal_peak_diagnostics": {
            "status": "not_run_raw_files_unavailable" if not raw_available else "pending",
            "tolerance_status": "not_pi_signed_diagnostic_only",
        },
        "hp_pv_paired_weather_readiness": {
            "status": "metadata_ready_pending_integrated_acceptance",
            "weather_contract": "src/weather_model.py::WeatherMember",
            "common_identity_fields": [
                "member_id",
                "shared_weather_driver_id",
                "source",
                "first_timestamp_utc",
                "last_timestamp_utc",
                "n_timesteps",
                "cadence_seconds",
                "content_sha256",
            ],
            "all_members_have_temperature": all(item["temperature_finite"] for item in member_checks),
            "all_members_have_pv_ghi": all(item["ghi_nonnegative"] for item in member_checks),
            "all_members_have_shared_driver": all(item["shared_weather_driver_id_ok"] for item in member_checks),
            "paired_acceptance_not_run": True,
        },
        "remaining_before_final_d004_acceptance": [
            "PI review/sign-off of concrete D-004 source files, checksums, and source-use evidence",
            "PI review/sign-off of seasonal/peak sanity tolerances or acceptance criteria",
            "HP/PV paired-weather acceptance using the same WEATHER-001 member identity",
            "cold-spell acceptance remains separate",
            "net-load, congestion, event, P(E), capacity-screen, and manuscript analyses remain out of scope",
        ],
    }
    if include_raw_diagnostics and raw_available:
        constructed = build_d004_weather_members(root_dir=root, metadata_dir=metadata_root, write_member_metadata=False)
        payload["pvgis_knmi_seasonal_peak_diagnostics"] = _seasonal_peak_diagnostics(
            root,
            retrieval_manifest,
            constructed.members,
        )
        payload["hp_pv_paired_weather_readiness"]["identity_roundtrip_ok"] = all(
            _same_weather_roundtrip_ok(member) for member in constructed.members
        )
        payload["hp_pv_paired_weather_readiness"]["status"] = "ready_for_later_paired_acceptance_design"
    return payload


def write_d004_member_readiness_diagnostics(
    *,
    root_dir: str | Path = ".",
    metadata_dir: str | Path = "data/metadata",
) -> Path:
    """Write D-004 member-readiness diagnostics metadata."""
    directory = Path(metadata_dir) / "weather_pv"
    directory.mkdir(parents=True, exist_ok=True)
    payload = build_d004_member_readiness_diagnostics(
        root_dir=root_dir,
        metadata_dir=metadata_dir,
        include_raw_diagnostics=True,
    )
    return _write_json(directory / D004_MEMBER_READINESS_DIAGNOSTICS_NAME, payload)

def build_d004_acceptance_packet(*, metadata_dir: str | Path = "data/metadata") -> dict[str, Any]:
    """Prepare the PI-facing D-004 acceptance packet without signing D-004."""
    metadata_root = Path(metadata_dir)
    weather_dir = metadata_root / "weather_pv"
    retrieval_manifest = _load_json(weather_dir / D004_RETRIEVAL_MANIFEST)
    source_evidence = _load_json(weather_dir / f"{D004_SELECTION_ID}_source_acceptance_evidence.json")
    member_manifest = _load_json(weather_dir / D004_MEMBER_MANIFEST_NAME)
    readiness = _load_json(weather_dir / D004_MEMBER_READINESS_DIAGNOSTICS_NAME)
    source_files = retrieval_manifest.get("source_files", [])
    member_checks = readiness.get("member_checks", [])
    seasonal = readiness.get("pvgis_knmi_seasonal_peak_diagnostics", {})
    return {
        "data_id": "D-004",
        "selection_id": D004_SELECTION_ID,
        "packet_created_utc": _now_utc_iso(),
        "status": "pi_acceptance_packet_proposed_not_signed",
        "recommended_action": "PI review: accept source/member readiness evidence or request amendments; do not treat this packet as final D-004 signoff by itself",
        "scope_boundaries": [
            "D-004 remains proposed until PI signs source/member acceptance",
            "PVGIS-SARAH3 remains calibration/validation provenance only, not a realized weather path",
            "seasonal/peak tolerances are proposed questions only and are not approved by this artifact",
            "no HP/PV paired acceptance, cold-spell acceptance, net-load, event, P(E), capacity-screen, or manuscript-result analysis is run",
        ],
        "evidence_artifacts": {
            "retrieval_manifest": f"data/metadata/weather_pv/{D004_RETRIEVAL_MANIFEST}",
            "source_acceptance_evidence": f"data/metadata/weather_pv/{D004_SELECTION_ID}_source_acceptance_evidence.json",
            "weather_member_manifest": f"data/metadata/weather_pv/{D004_MEMBER_MANIFEST_NAME}",
            "member_readiness_diagnostics": f"data/metadata/weather_pv/{D004_MEMBER_READINESS_DIAGNOSTICS_NAME}",
            "acceptance_memo": "reports/e2_s4_d004_acceptance_packet.md",
        },
        "source_files_for_review": [
            {
                "source_kind": item.get("source_kind"),
                "file_role": item.get("file_role"),
                "path": item.get("path"),
                "source_url": item.get("source_url"),
                "size_bytes": item.get("size_bytes"),
                "sha256_file": item.get("sha256_file"),
            }
            for item in source_files
            if isinstance(item, Mapping)
        ],
        "source_completeness_summary": {
            "retrieval_status": retrieval_manifest.get("d004_status"),
            "download_performed": retrieval_manifest.get("download_performed"),
            "raw_data_committed": retrieval_manifest.get("raw_data_committed"),
            "source_checksums_match": all(item.get("sha256_matches_manifest") for item in readiness.get("raw_source_checks", [])),
            "source_sizes_match": all(item.get("size_matches_manifest") for item in readiness.get("raw_source_checks", [])),
            "knmi_years_complete_2014_2023": all(
                source_evidence.get("knmi_station_249_hourly_coverage", {}).get("years", {}).get(str(year), {}).get("complete")
                for year in D004_YEARS
            ),
            "pvgis_hourly_rows_by_year": source_evidence.get("pvgis_sarah3_hourly_series_coverage", {}).get("rows_by_year"),
        },
        "member_readiness_summary": {
            "member_manifest_status": member_manifest.get("status"),
            "member_years": readiness.get("manifest_checks", {}).get("years"),
            "members_present": readiness.get("manifest_checks", {}).get("members_present"),
            "calendar_cadence_ok": readiness.get("manifest_checks", {}).get("all_calendar_cadence_ok"),
            "energy_preserved": readiness.get("manifest_checks", {}).get("all_energy_preserved"),
            "temperature_finite": readiness.get("manifest_checks", {}).get("all_temperature_finite"),
            "ghi_nonnegative": readiness.get("manifest_checks", {}).get("all_ghi_nonnegative"),
            "pvgis_realized_weather_path": readiness.get("manifest_checks", {}).get("pvgis_realized_weather_path"),
            "hp_pv_identity_roundtrip_ok": readiness.get("hp_pv_paired_weather_readiness", {}).get("identity_roundtrip_ok"),
            "content_sha256_by_year": {
                str(item.get("year")): item.get("content_sha256")
                for item in member_checks
                if isinstance(item, Mapping)
            },
        },
        "seasonal_peak_sanity_summary": _acceptance_packet_seasonal_peak_summary(seasonal),
        "pi_decision_questions": [
            {
                "id": "D004-ACCEPT-Q1",
                "question": "Does the PI accept the four concrete D-004 source files, URLs, sizes, and SHA-256 checksums as the source bundle for 2014-2023 WEATHER-001 members?",
                "agent_recommendation": "Accept, subject to PI license/source-use review; the local files match the committed retrieval manifest and remain ignored/uncommitted.",
                "decision_needed_for": "D-004 source acceptance",
            },
            {
                "id": "D004-ACCEPT-Q2",
                "question": "Does the PI accept the constructed 2014-2023 UTC-year WEATHER-001 member library as complete and calendar-consistent under D004-MC-001?",
                "agent_recommendation": "Accept member construction readiness; all members have expected 15-minute counts, UTC/local timestamp alignment, finite T/10 temperature, nonnegative Q-derived GHI, and shared weather-driver IDs.",
                "decision_needed_for": "D-004 member acceptance",
            },
            {
                "id": "D004-ACCEPT-Q3",
                "question": "What seasonal/peak sanity criterion should be signed before final D-004 acceptance?",
                "options": [
                    "A) Qualitative first-pass: annual GHI-to-PVGIS fixed-plane G(i) ratio remains within the observed diagnostic range, seasonal maximum occurs in MAM/JJA, and peak GHI month is May-July; no numeric percent tolerance is claimed.",
                    "B) Numeric tolerance: PI supplies explicit annual/seasonal relative-error bounds and allowed peak-month set, acknowledging KNMI GHI and PVGIS fixed-plane G(i)/P are not the same irradiance quantity.",
                    "C) Request a different PVGIS comparison quantity or transform before signing seasonal/peak checks.",
                ],
                "agent_recommendation": "A for source/member acceptance, with B or C reserved for later PV calibration acceptance; it avoids inventing a numeric tolerance between GHI and fixed-plane PVGIS reference fields.",
                "decision_needed_for": "PVGIS seasonal/peak sanity acceptance",
            },
            {
                "id": "D004-ACCEPT-Q4",
                "question": "Should final D-004 acceptance wait for the E2-S3-COLD-SPELL-ACCEPTANCE-DESIGN paired HP/PV run, or may source/member acceptance be signed separately first?",
                "agent_recommendation": "Sign source/member acceptance separately if Q1-Q3 pass; keep paired HP/PV and cold-spell acceptance as later gates with their own unsigned tolerances.",
                "decision_needed_for": "sequencing of D-004 source/member acceptance versus paired HP/PV acceptance",
            },
        ],
    }


def write_d004_acceptance_packet(*, metadata_dir: str | Path = "data/metadata") -> Path:
    """Write the proposed D-004 PI acceptance packet metadata."""
    directory = Path(metadata_dir) / "weather_pv"
    directory.mkdir(parents=True, exist_ok=True)
    return _write_json(directory / D004_ACCEPTANCE_PACKET_NAME, build_d004_acceptance_packet(metadata_dir=metadata_dir))

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
    parser.add_argument("--write-d004-member-readiness-diagnostics", action="store_true")
    parser.add_argument("--write-d004-acceptance-packet", action="store_true")
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

    if args.write_d004_acceptance_packet:
        path = write_d004_acceptance_packet(metadata_dir=args.metadata_dir)
        print(path)
        return 0

    if args.write_d004_member_readiness_diagnostics:
        path = write_d004_member_readiness_diagnostics(
            root_dir=args.root_dir,
            metadata_dir=args.metadata_dir,
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


def _acceptance_packet_seasonal_peak_summary(seasonal: Mapping[str, Any]) -> dict[str, Any]:
    years = seasonal.get("years", {}) if isinstance(seasonal, Mapping) else {}
    ratios = [
        float(item["annual_ghi_to_pvgis_gi_ratio"])
        for item in years.values()
        if isinstance(item, Mapping) and item.get("annual_ghi_to_pvgis_gi_ratio") is not None
    ]
    peak_months = [
        int(item["knmi_peak_ghi_month_utc"])
        for item in years.values()
        if isinstance(item, Mapping) and item.get("knmi_peak_ghi_month_utc") is not None
    ]
    return {
        "status": seasonal.get("status") if isinstance(seasonal, Mapping) else None,
        "tolerance_status": seasonal.get("tolerance_status") if isinstance(seasonal, Mapping) else None,
        "comparison_boundary": seasonal.get("comparison_boundary") if isinstance(seasonal, Mapping) else None,
        "n_years": len(years) if isinstance(years, Mapping) else 0,
        "annual_ghi_to_pvgis_gi_ratio_min": _round_float(min(ratios)) if ratios else None,
        "annual_ghi_to_pvgis_gi_ratio_max": _round_float(max(ratios)) if ratios else None,
        "knmi_peak_ghi_months_utc": sorted(set(peak_months)),
        "all_knmi_peak_months_may_to_july": bool(peak_months) and all(month in {5, 6, 7} for month in peak_months),
        "diagnostic_only_not_final_acceptance": True,
    }

def _diagnose_committed_member_metadata(
    root: Path,
    metadata_root: Path,
    manifest_member: Mapping[str, Any],
) -> dict[str, Any]:
    year = int(manifest_member["year"])
    manifest_metadata_path = str(manifest_member["metadata_path"])
    metadata_path = root / manifest_metadata_path
    if not metadata_path.is_file():
        metadata_path = metadata_root / "weather_pv" / Path(manifest_metadata_path).name
    expected_steps = 35_136 if _is_leap_year(year) else 35_040
    expected_first_utc = datetime(year, 1, 1, tzinfo=UTC).isoformat()
    expected_last_utc = datetime(year, 12, 31, 23, 45, tzinfo=UTC).isoformat()
    if not metadata_path.is_file():
        return {
            "year": year,
            "member_id": manifest_member.get("member_id"),
            "shared_weather_driver_id": manifest_member.get("shared_weather_driver_id"),
            "content_sha256": manifest_member.get("content_sha256"),
            "metadata_path": manifest_member.get("metadata_path"),
            "metadata_file_present": False,
            "calendar_cadence_ok": False,
            "energy_preservation_ok": False,
            "temperature_finite": False,
            "ghi_nonnegative": False,
            "shared_weather_driver_id_ok": False,
        }
    metadata = _load_json(metadata_path)
    calendar = metadata.get("calendar", {})
    knmi = metadata.get("knmi_hourly_source", {})
    identity = metadata.get("identity_record", {})
    source_files = metadata.get("source_files", {})
    return {
        "year": year,
        "member_id": str(manifest_member.get("member_id")),
        "shared_weather_driver_id": str(manifest_member.get("shared_weather_driver_id")),
        "content_sha256": str(manifest_member.get("content_sha256")),
        "metadata_path": str(manifest_member.get("metadata_path")),
        "metadata_file_present": True,
        "metadata_content_sha256_matches_manifest": metadata.get("content_sha256") == manifest_member.get("content_sha256"),
        "metadata_member_id_matches_manifest": metadata.get("member_id") == manifest_member.get("member_id"),
        "metadata_shared_driver_matches_manifest": metadata.get("shared_weather_driver_id")
        == manifest_member.get("shared_weather_driver_id"),
        "shared_weather_driver_id_ok": metadata.get("shared_weather_driver_id") == f"{D004_SELECTION_ID}:{year}",
        "calendar_year_basis": calendar.get("calendar_year_basis"),
        "n_timesteps": calendar.get("n_timesteps"),
        "expected_n_timesteps": expected_steps,
        "cadence_seconds": calendar.get("cadence_seconds"),
        "first_timestamp_utc": calendar.get("first_timestamp_utc"),
        "last_timestamp_utc": calendar.get("last_timestamp_utc"),
        "first_timestamp_local": calendar.get("first_timestamp_local"),
        "last_timestamp_local": calendar.get("last_timestamp_local"),
        "calendar_cadence_ok": calendar.get("calendar_year_basis") == "UTC calendar year"
        and calendar.get("n_timesteps") == expected_steps
        and calendar.get("cadence_seconds") == 900
        and calendar.get("first_timestamp_utc") == expected_first_utc
        and calendar.get("last_timestamp_utc") == expected_last_utc,
        "source_hourly_rows": knmi.get("source_hourly_rows"),
        "expected_source_hourly_rows": 8784 if _is_leap_year(year) else 8760,
        "energy_preservation_abs_error_j_per_cm2": knmi.get("energy_preservation_abs_error_j_per_cm2"),
        "energy_preservation_ok": float(knmi.get("energy_preservation_abs_error_j_per_cm2", float("inf"))) <= 1e-9,
        "temperature_min_c": knmi.get("temperature_min_c"),
        "temperature_max_c": knmi.get("temperature_max_c"),
        "temperature_finite": math.isfinite(float(knmi.get("temperature_min_c", float("nan"))))
        and math.isfinite(float(knmi.get("temperature_max_c", float("nan")))),
        "ghi_min_w_per_m2": knmi.get("ghi_min_w_per_m2"),
        "ghi_max_w_per_m2": knmi.get("ghi_max_w_per_m2"),
        "ghi_nonnegative": float(knmi.get("ghi_min_w_per_m2", -1.0)) >= 0.0
        and math.isfinite(float(knmi.get("ghi_max_w_per_m2", float("nan")))),
        "identity_record_content_matches_metadata": identity.get("content_sha256") == metadata.get("content_sha256"),
        "identity_record_shared_driver_matches_metadata": identity.get("shared_weather_driver_id")
        == metadata.get("shared_weather_driver_id"),
        "pvgis_provenance_only": any(
            str(item.get("file_role", "")).endswith("reference")
            or str(item.get("file_role", "")).endswith("only")
            for item in source_files.get("pvgis", [])
            if isinstance(item, Mapping)
        ),
    }


def _diagnose_retrieval_manifest_sources(root: Path, retrieval_manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    files = retrieval_manifest.get("source_files")
    if not isinstance(files, list):
        raise ValueError("D-004 retrieval manifest lacks source_files")
    checks: list[dict[str, Any]] = []
    for item in files:
        if not isinstance(item, Mapping):
            raise ValueError("D-004 source_files entries must be objects")
        path = root / str(item["path"])
        local_file_present = path.is_file()
        size_bytes = path.stat().st_size if local_file_present else None
        sha256 = sha256_file(path) if local_file_present else None
        checks.append(
            {
                "source_kind": item.get("source_kind"),
                "file_role": item.get("file_role"),
                "path": item.get("path"),
                "source_url": item.get("source_url"),
                "local_file_present": local_file_present,
                "size_bytes": size_bytes,
                "expected_size_bytes": item.get("size_bytes"),
                "size_matches_manifest": local_file_present and size_bytes == int(item["size_bytes"]),
                "sha256_file": sha256,
                "expected_sha256_file": item.get("sha256_file"),
                "sha256_matches_manifest": local_file_present and sha256 == item.get("sha256_file"),
            }
        )
    return checks


def _seasonal_peak_diagnostics(
    root: Path,
    retrieval_manifest: Mapping[str, Any],
    members: Sequence[WeatherMember],
) -> dict[str, Any]:
    pvgis_path = _pvgis_seriescalc_path(root, retrieval_manifest)
    pvgis_by_year = _pvgis_hourly_year_diagnostics(pvgis_path)
    knmi_by_year = {str(int(member.metadata["year"])): _member_ghi_year_diagnostics(member) for member in members}
    comparisons: dict[str, Any] = {}
    for year, knmi in sorted(knmi_by_year.items()):
        pvgis = pvgis_by_year.get(year, {})
        comparisons[year] = {
            "knmi_ghi_annual_kwh_per_m2": knmi["annual_ghi_kwh_per_m2"],
            "pvgis_gi_annual_kwh_per_m2": pvgis.get("annual_gi_kwh_per_m2"),
            "annual_ghi_to_pvgis_gi_ratio": _safe_ratio(
                knmi["annual_ghi_kwh_per_m2"],
                pvgis.get("annual_gi_kwh_per_m2"),
            ),
            "knmi_peak_ghi_month_utc": knmi["peak_ghi_month_utc"],
            "pvgis_peak_gi_month": pvgis.get("peak_gi_month"),
            "pvgis_peak_p_month": pvgis.get("peak_p_month"),
            "knmi_seasonal_ghi_kwh_per_m2": knmi["seasonal_ghi_kwh_per_m2"],
            "pvgis_seasonal_gi_kwh_per_m2": pvgis.get("seasonal_gi_kwh_per_m2"),
        }
    return {
        "status": "diagnostic_only_not_final_acceptance",
        "tolerance_status": "not_pi_signed_diagnostic_only",
        "season_basis": "UTC month grouping; DJF is Jan/Feb/Dec within each UTC year",
        "comparison_boundary": "KNMI Q-derived GHI is the realized WeatherMember irradiance field; PVGIS G(i)/P are Alkmaar fixed-plane calibration or validation references only",
        "pvgis_series_file": pvgis_path.relative_to(root).as_posix(),
        "years": comparisons,
    }


def _pvgis_seriescalc_path(root: Path, retrieval_manifest: Mapping[str, Any]) -> Path:
    for item in retrieval_manifest.get("source_files", []):
        if isinstance(item, Mapping) and item.get("source_kind") == "pvgis" and "hourly_series" in str(item.get("file_role")):
            path = root / str(item["path"])
            if not path.is_file():
                raise FileNotFoundError(path)
            return path
    raise ValueError("D-004 retrieval manifest lacks a PVGIS hourly-series source file")


def _pvgis_hourly_year_diagnostics(path: Path) -> dict[str, dict[str, Any]]:
    payload = _load_json(path)
    hourly = payload.get("outputs", {}).get("hourly")
    if not isinstance(hourly, list):
        raise ValueError("PVGIS seriescalc payload lacks outputs.hourly")
    by_year: dict[str, dict[str, Any]] = {}
    monthly_gi: dict[tuple[int, int], float] = {}
    monthly_p: dict[tuple[int, int], float] = {}
    peak_gi: dict[int, tuple[float, int]] = {}
    peak_p: dict[int, tuple[float, int]] = {}
    for row in hourly:
        if not isinstance(row, Mapping):
            raise ValueError("PVGIS hourly entries must be objects")
        timestamp = datetime.strptime(str(row["time"]), "%Y%m%d:%H%M")
        year = timestamp.year
        month = timestamp.month
        gi = float(row.get("G(i)", 0.0))
        pv_power = float(row.get("P", 0.0))
        monthly_gi[(year, month)] = monthly_gi.get((year, month), 0.0) + gi / 1000.0
        monthly_p[(year, month)] = monthly_p.get((year, month), 0.0) + pv_power / 1000.0
        if year not in peak_gi or gi > peak_gi[year][0]:
            peak_gi[year] = (gi, month)
        if year not in peak_p or pv_power > peak_p[year][0]:
            peak_p[year] = (pv_power, month)
    for year in D004_YEARS:
        gi_by_month = {month: monthly_gi.get((year, month), 0.0) for month in range(1, 13)}
        p_by_month = {month: monthly_p.get((year, month), 0.0) for month in range(1, 13)}
        by_year[str(year)] = {
            "annual_gi_kwh_per_m2": _round_float(sum(gi_by_month.values())),
            "annual_pvgis_p_kwh_per_kwp": _round_float(sum(p_by_month.values())),
            "seasonal_gi_kwh_per_m2": _seasonal_from_months(gi_by_month),
            "seasonal_pvgis_p_kwh_per_kwp": _seasonal_from_months(p_by_month),
            "peak_gi_month": peak_gi.get(year, (None, None))[1],
            "peak_p_month": peak_p.get(year, (None, None))[1],
        }
    return by_year


def _member_ghi_year_diagnostics(member: WeatherMember) -> dict[str, Any]:
    monthly: dict[int, float] = {month: 0.0 for month in range(1, 13)}
    peak_value = -1.0
    peak_month = 0
    for timestamp, ghi in zip(member.timestamps_utc, member.ghi_w_per_m2, strict=True):
        value = float(ghi)
        monthly[timestamp.month] += value * 0.25 / 1000.0
        if value > peak_value:
            peak_value = value
            peak_month = timestamp.month
    return {
        "annual_ghi_kwh_per_m2": _round_float(sum(monthly.values())),
        "seasonal_ghi_kwh_per_m2": _seasonal_from_months(monthly),
        "peak_ghi_month_utc": peak_month,
    }


def _seasonal_from_months(monthly: Mapping[int, float]) -> dict[str, float]:
    return {
        "DJF": _round_float(monthly[12] + monthly[1] + monthly[2]),
        "MAM": _round_float(monthly[3] + monthly[4] + monthly[5]),
        "JJA": _round_float(monthly[6] + monthly[7] + monthly[8]),
        "SON": _round_float(monthly[9] + monthly[10] + monthly[11]),
    }


def _same_weather_roundtrip_ok(member: WeatherMember) -> bool:
    try:
        assert_same_weather_realization(member, member.identity_record())
    except ValueError:
        return False
    return True


def _safe_ratio(numerator: float, denominator: object) -> float | None:
    if denominator is None:
        return None
    value = float(denominator)
    if value == 0.0:
        return None
    return _round_float(float(numerator) / value)


def _round_float(value: float) -> float:
    return round(float(value), 6)


def _is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

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




