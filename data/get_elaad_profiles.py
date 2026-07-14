from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import gzip
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Sequence
from urllib import request

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.sources import write_metadata

API_URL = "https://api.charging.data.elaad.nl/profile/simulate"
DOCS_URL = "https://api.charging.data.elaad.nl/docs#"
DASHBOARD_URL = "https://charging.elaad.nl/"
DOC_VERSION = "Documentatie Laadprofielengenerator, ElaadNL, 10 November 2025"
OUTLOOK_BASIS = "Outlook Personenauto's 2024; Outlook Logistiek 2025"
CALENDAR_START = "2025-01-01T00:00:00+01:00"
CALENDAR_STOP = "2026-01-01T00:00:00+01:00"
STEP_SIZE_S = 900
TIMEZONE = "CET"
DEFAULT_BATCH_SIZE = 100


@dataclass(frozen=True)
class ProfileBatch:
    """One planned ElaadNL API request batch for the frozen profile library."""

    set_id: str
    purpose: str
    simulated_year: int
    profile_type: str
    n_profiles: int
    vehicle_types: str | list[str]
    location_type: str
    cp_capacity_kw: int
    seed: int
    storage_stem: str


def build_probe_request(simulated_year: int = 2033) -> dict[str, Any]:
    """Return the one-profile D-002 API probe request body."""
    return {
        "start_datetime": CALENDAR_START,
        "stop_datetime": CALENDAR_STOP,
        "step_size_s": STEP_SIZE_S,
        "timezone": TIMEZONE,
        "simulated_year": simulated_year,
        "profile_type": "ev",
        "n_profiles": 1,
        "vehicle_types": "car",
        "location_type": "home",
        "cp_capacity_kw": 11,
        "seed": 133001,
    }


def build_batch_request(batch: ProfileBatch) -> dict[str, Any]:
    """Return the exact API request body for one planned profile-library batch."""
    return {
        "start_datetime": CALENDAR_START,
        "stop_datetime": CALENDAR_STOP,
        "step_size_s": STEP_SIZE_S,
        "timezone": TIMEZONE,
        "simulated_year": batch.simulated_year,
        "profile_type": batch.profile_type,
        "n_profiles": batch.n_profiles,
        "vehicle_types": batch.vehicle_types,
        "location_type": batch.location_type,
        "cp_capacity_kw": batch.cp_capacity_kw,
        "seed": batch.seed,
    }


def build_library_plan() -> tuple[ProfileBatch, ...]:
    """Return the EV-002-compatible ElaadNL profile-library batch schedule.

    The plan is metadata only: it defines request bodies and distinct batch
    seeds. Running the API and storing generated profiles is an explicit later
    step, and generated files remain ignored/non-redistributed.
    """
    batches: list[ProfileBatch] = []

    home_year_seed_starts = {
        2030: 130001,
        2033: 133001,
        2035: 135001,
    }
    for year, first_seed in home_year_seed_starts.items():
        for offset in range(0, 1000, DEFAULT_BATCH_SIZE):
            seed = first_seed + offset
            batches.append(
                ProfileBatch(
                    set_id="A",
                    purpose="primary_home_car_ev_library",
                    simulated_year=year,
                    profile_type="ev",
                    n_profiles=DEFAULT_BATCH_SIZE,
                    vehicle_types="car",
                    location_type="home",
                    cp_capacity_kw=11,
                    seed=seed,
                    storage_stem=f"A_home_car_ev_y{year}_seed{seed}-{seed + DEFAULT_BATCH_SIZE - 1}",
                )
            )

    public_year_seed_starts = {
        2030: 230001,
        2035: 235001,
    }
    for year, first_seed in public_year_seed_starts.items():
        for offset in range(0, 200, DEFAULT_BATCH_SIZE):
            seed = first_seed + offset
            batches.append(
                ProfileBatch(
                    set_id="B",
                    purpose="public_van_car_cp_library",
                    simulated_year=year,
                    profile_type="cp",
                    n_profiles=DEFAULT_BATCH_SIZE,
                    vehicle_types=["van", "car"],
                    location_type="public",
                    cp_capacity_kw=22,
                    seed=seed,
                    storage_stem=f"B_public_vancar_cp_y{year}_seed{seed}-{seed + DEFAULT_BATCH_SIZE - 1}",
                )
            )

    return tuple(batches)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _parse_json(payload: bytes) -> dict[str, Any]:
    parsed = json.loads(payload.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("Expected API response JSON object")
    return parsed


def _profile_shape(parsed: dict[str, Any]) -> dict[str, Any]:
    profile = parsed.get("profile") if isinstance(parsed.get("profile"), dict) else {}
    cp_ids = profile.get("cp_ids") or []
    datetimes = profile.get("datetimes") or []
    demands_kw = profile.get("demands_kw") or []
    first_series_len = len(demands_kw[0]) if demands_kw and isinstance(demands_kw[0], list) else None
    orientation = (
        "time-major: len(demands_kw) equals len(datetimes), each row contains profile values"
        if demands_kw and len(demands_kw) == len(datetimes)
        else "profile-major or unknown: len(demands_kw) does not equal len(datetimes)"
    )
    return {
        "n_cp_ids": len(cp_ids),
        "n_datetimes": len(datetimes),
        "n_demand_series": len(demands_kw),
        "first_demand_series_len": first_series_len,
        "demands_kw_orientation_observed": orientation,
        "first_datetime": datetimes[0] if datetimes else None,
        "last_datetime": datetimes[-1] if datetimes else None,
        "timezone_behavior_observed": _timezone_note(datetimes),
    }


def _timezone_note(datetimes: list[Any]) -> str:
    if not datetimes:
        return "No datetimes returned."
    first = str(datetimes[0])
    last = str(datetimes[-1])
    if first.endswith("Z") or first.endswith("+00:00"):
        return f"API returned UTC timestamps; first={first}; last={last}. Convert to Europe/Amsterdam downstream."
    return f"API timestamp timezone not recognized as UTC from first value; first={first}; last={last}."


def run_one_profile_probe(
    *,
    metadata_dir: Path,
    raw_dir: Path,
    simulated_year: int,
    timeout_s: int,
) -> Path:
    """Run exactly one profile-generator probe and write raw + metadata files."""
    body = build_probe_request(simulated_year)
    request_payload = json.dumps(body, indent=2, sort_keys=True).encode("utf-8")
    retrieval_ts = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    stem = f"d002_elaad_profile_probe_y{simulated_year}_seed{body['seed']}_n{body['n_profiles']}"

    req = request.Request(
        API_URL,
        data=request_payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout_s) as response:
        response_payload = response.read()
        status_code = response.status
        response_headers = dict(response.headers.items())

    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{stem}.json.gz"
    with gzip.open(raw_path, "wb") as handle:
        handle.write(response_payload)

    parsed = _parse_json(response_payload)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = metadata_dir / f"{stem}_metadata.json"
    metadata = {
        "data_id": "D-002",
        "retrieval_timestamp_utc": retrieval_ts,
        "api_url": API_URL,
        "api_docs_url": DOCS_URL,
        "dashboard_url": DASHBOARD_URL,
        "api_docs_version_info": {
            "local_documentation_version": DOC_VERSION,
            "outlook_basis": OUTLOOK_BASIS,
            "live_api_version_header": response_headers.get("x-api-version") or response_headers.get("X-API-Version"),
            "server_header": response_headers.get("server") or response_headers.get("Server"),
        },
        "request_json": body,
        "response_status_code": status_code,
        "response_config_block": parsed.get("config"),
        "response_statistics_block": parsed.get("statistics"),
        "output_shape": _profile_shape(parsed),
        "raw_response": {
            "path": raw_path.as_posix(),
            "sha256_uncompressed_json": _sha256_bytes(response_payload),
            "sha256_gzip_file": _sha256_bytes(raw_path.read_bytes()),
        },
        "accepted_simulated_year_values_observed": {
            str(simulated_year): status_code == 200,
            "note": "Only one one-profile probe was executed; other years were not called in this session.",
        },
        "seed_semantics_observed": {
            "request_seed": body["seed"],
            "n_profiles": body["n_profiles"],
            "response_config_seed": (parsed.get("config") or {}).get("seed") if isinstance(parsed.get("config"), dict) else None,
            "note": "A single-profile call cannot verify same-seed reproducibility or batch seed expansion without additional calls.",
        },
        "terms_of_use_license_evidence": {
            "status": "uncertain",
            "note": "EV-001 approves the route, but generated-profile redistribution/publication terms remain to be verified before bulk generation or data-availability claims.",
        },
        "bulk_generation_performed": False,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return metadata_path


def write_library_plan(metadata_dir: Path) -> Path:
    """Write the planned ElaadNL profile-library request schedule metadata."""
    batches = build_library_plan()
    seeds = [batch.seed for batch in batches]
    if len(seeds) != len(set(seeds)):
        raise ValueError("ElaadNL batch seeds must be distinct across the library plan")

    metadata_dir.mkdir(parents=True, exist_ok=True)
    path = metadata_dir / "d002_elaad_profile_library_plan.json"
    payload = {
        "data_id": "D-002",
        "status": "planned-request-metadata-only",
        "bulk_generation_performed": False,
        "api_url": API_URL,
        "api_docs_url": DOCS_URL,
        "dashboard_url": DASHBOARD_URL,
        "local_documentation_version": DOC_VERSION,
        "outlook_basis": OUTLOOK_BASIS,
        "calendar": {
            "start_datetime": CALENDAR_START,
            "stop_datetime": CALENDAR_STOP,
            "step_size_s": STEP_SIZE_S,
            "timezone": TIMEZONE,
        },
        "policy": {
            "decision": "EV-002",
            "internal_project_computation": True,
            "commit_generated_profiles": False,
            "redistribute_generated_profiles": False,
            "data_availability": "Readers regenerate through the public API subject to terms applicable at retrieval time.",
            "stop_condition": "If explicit terms later prohibit this research use, stop and escalate.",
        },
        "seed_semantics": {
            "batch_seeds_are_distinct": True,
            "note": "The one-profile probe cannot prove n_profiles batch expansion semantics; keep member identity as (batch seed, returned profile index) until batch probes confirm otherwise.",
        },
        "batches": [
            {
                **asdict(batch),
                "request_json": build_batch_request(batch),
                "raw_response_path": f"data/raw/elaad_profiles/{batch.storage_stem}.json.gz",
                "processed_path": f"data/processed/elaad_profiles/{batch.storage_stem}.parquet",
            }
            for batch in batches
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Record or probe ElaadNL profile-generator metadata for E2.S1."
    )
    parser.add_argument("--metadata-dir", default="data/metadata/elaad_profiles")
    parser.add_argument("--raw-dir", default="data/raw/elaad_profiles")
    parser.add_argument("--probe-one-profile", action="store_true")
    parser.add_argument("--write-library-plan", action="store_true")
    parser.add_argument("--simulated-year", type=int, default=2033)
    parser.add_argument("--timeout-s", type=int, default=120)
    args = parser.parse_args(argv)

    if args.probe_one_profile and args.write_library_plan:
        parser.error("--probe-one-profile and --write-library-plan are mutually exclusive")

    if args.probe_one_profile:
        path = run_one_profile_probe(
            metadata_dir=Path(args.metadata_dir),
            raw_dir=Path(args.raw_dir),
            simulated_year=args.simulated_year,
            timeout_s=args.timeout_s,
        )
    elif args.write_library_plan:
        path = write_library_plan(Path(args.metadata_dir))
    else:
        path = write_metadata(
            "D-002",
            Path(args.metadata_dir),
            extra={
                "generation_spec": "reports/elaad_profile_generation_spec.md",
                "next_step": "write library plan, then generate ignored raw/profile files under EV-002 boundary",
            },
        )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
