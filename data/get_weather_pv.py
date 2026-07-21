from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence
from urllib import parse, request

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.sources import write_metadata

PVGIS_API_BASE = "https://re.jrc.ec.europa.eu/api/v5_3"
KNMI_OPEN_DATA_BASE = "https://api.dataplatform.knmi.nl/open-data/v1"
KNMI_IN_SITU_DATASET_NAME = "10-minute-in-situ-meteorological-observations"
KNMI_IN_SITU_DATASET_VERSION = "1.0"


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
    parser.add_argument("--record-local-file")
    parser.add_argument("--source-kind", choices=["knmi", "pvgis"])
    parser.add_argument("--file-role", default="source")
    parser.add_argument("--source-url")
    parser.add_argument("--download-url")
    parser.add_argument("--output-path")
    parser.add_argument("--timeout-s", type=float, default=120.0)
    parser.add_argument("--authorization-env")
    args = parser.parse_args(argv)

    if args.write_retrieval_plan:
        path = write_retrieval_plan(args.metadata_dir)
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


if __name__ == "__main__":
    raise SystemExit(main())
