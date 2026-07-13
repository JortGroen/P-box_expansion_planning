from __future__ import annotations

import argparse
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


def build_probe_request(simulated_year: int = 2033) -> dict[str, Any]:
    """Return the one-profile D-002 API probe request body."""
    return {
        "start_datetime": "2025-01-01T00:00:00+01:00",
        "stop_datetime": "2026-01-01T00:00:00+01:00",
        "step_size_s": 900,
        "timezone": "CET",
        "simulated_year": simulated_year,
        "profile_type": "ev",
        "n_profiles": 1,
        "vehicle_types": "car",
        "location_type": "home",
        "cp_capacity_kw": 11,
        "seed": 133001,
    }


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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Record or probe ElaadNL profile-generator metadata for E2.S1."
    )
    parser.add_argument("--metadata-dir", default="data/metadata/elaad_profiles")
    parser.add_argument("--raw-dir", default="data/raw/elaad_profiles")
    parser.add_argument("--probe-one-profile", action="store_true")
    parser.add_argument("--simulated-year", type=int, default=2033)
    parser.add_argument("--timeout-s", type=int, default=120)
    args = parser.parse_args(argv)

    if args.probe_one_profile:
        path = run_one_profile_probe(
            metadata_dir=Path(args.metadata_dir),
            raw_dir=Path(args.raw_dir),
            simulated_year=args.simulated_year,
            timeout_s=args.timeout_s,
        )
    else:
        path = write_metadata(
            "D-002",
            Path(args.metadata_dir),
            extra={
                "generation_spec": "reports/elaad_profile_generation_spec.md",
                "next_step": "one-profile API probe before bulk generation",
            },
        )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
