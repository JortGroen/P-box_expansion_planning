from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import gzip
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter
from typing import Any, Sequence
from urllib import request

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.sources import write_metadata
from src.ev_model import (
    batch_summary,
    distinct_member_count,
    parse_elaad_profile_response,
    read_gzip_json,
    save_processed_batch_npz,
)

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
    partition: str
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
    """Return the EV-002/EV-004/EV-005 profile-library batch schedule.

    The plan is metadata only: it defines request bodies and distinct
    uncontrolled batch seeds. EV-006 may reuse one of these seeds only for its
    labelled smart-control counterpart. Running the API and storing generated
    profiles is an explicit later step, and generated files remain
    ignored/non-redistributed.
    """
    batches: list[ProfileBatch] = []

    # Start at 140001 because 130001 already identifies the archived legacy EV
    # probe; reusing it for an unrelated draw would make provenance and
    # same-seed checks ambiguous. EV-006 treatment/control pairing is the only
    # deliberate reuse and keeps the control mode in the member identity.
    candidate_seeds = range(140001, 141001, DEFAULT_BATCH_SIZE)
    held_out_seeds = (141001, 141101)
    for partition, seeds in (
        ("candidate", candidate_seeds),
        ("held_out", held_out_seeds),
    ):
        for seed in seeds:
            batches.append(
                ProfileBatch(
                    set_id="A",
                    purpose="primary_home_van_car_cp_library",
                    partition=partition,
                    simulated_year=2030,
                    profile_type="cp",
                    n_profiles=DEFAULT_BATCH_SIZE,
                    vehicle_types=["van", "car"],
                    location_type="home",
                    cp_capacity_kw=11,
                    seed=seed,
                    storage_stem=f"A_home_vancar_cp_y2030_batchseed{seed}_n{DEFAULT_BATCH_SIZE}",
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
    start = perf_counter()
    with request.urlopen(req, timeout=timeout_s) as response:
        response_payload = response.read()
        status_code = response.status
        response_headers = dict(response.headers.items())
    api_runtime_s = perf_counter() - start

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


def run_authorized_set_a_batch(
    *,
    metadata_dir: Path,
    raw_dir: Path,
    processed_dir: Path,
    reports_dir: Path,
    timeout_s: int,
) -> Path:
    """Run the first EV-004 home charge-point candidate probe batch."""
    batch = build_library_plan()[0]
    expected = {
        "set_id": "A",
        "partition": "candidate",
        "simulated_year": 2030,
        "profile_type": "cp",
        "location_type": "home",
        "vehicle_types": ["van", "car"],
        "cp_capacity_kw": 11,
        "seed": 140001,
        "n_profiles": 100,
    }
    for key, value in expected.items():
        if getattr(batch, key) != value:
            raise ValueError(f"Authorized batch mismatch for {key}: {getattr(batch, key)!r}")

    body = build_batch_request(batch)
    request_payload = json.dumps(body, indent=2, sort_keys=True).encode("utf-8")
    retrieval_ts = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    stem = batch.storage_stem

    req = request.Request(
        API_URL,
        data=request_payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    start = perf_counter()
    with request.urlopen(req, timeout=timeout_s) as response:
        response_payload = response.read()
        status_code = response.status
        response_headers = dict(response.headers.items())
    api_runtime_s = perf_counter() - start

    return write_authorized_set_a_artifacts_from_response(
        response_payload=response_payload,
        metadata_dir=metadata_dir,
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        reports_dir=reports_dir,
        api_runtime_s=api_runtime_s,
        retrieval_ts=retrieval_ts,
        status_code=status_code,
        response_headers=response_headers,
        reconstructed_from_saved_raw=False,
    )


def write_authorized_set_a_artifacts_from_response(
    *,
    response_payload: bytes,
    metadata_dir: Path,
    raw_dir: Path,
    processed_dir: Path,
    reports_dir: Path,
    api_runtime_s: float | None,
    retrieval_ts: str,
    status_code: int,
    response_headers: dict[str, str],
    reconstructed_from_saved_raw: bool,
) -> Path:
    """Write commit-safe artifacts for the one authorized EV-004 Set A probe."""
    batch = build_library_plan()[0]
    stem = batch.storage_stem
    body = build_batch_request(batch)
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{stem}.json.gz"
    with gzip.open(raw_path, "wb") as handle:
        handle.write(response_payload)

    parsed_batch = parse_elaad_profile_response(
        response_payload,
        batch_seed=batch.seed,
        expected_n_profiles=batch.n_profiles,
    )
    distinct_members = distinct_member_count(parsed_batch)

    processed_dir.mkdir(parents=True, exist_ok=True)
    processed_path = processed_dir / f"{stem}.npz"
    save_processed_batch_npz(parsed_batch, processed_path)

    summary = batch_summary(parsed_batch)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = metadata_dir / f"{stem}_manifest.json"
    metadata = {
        "data_id": "D-002",
        "task_id": "E2.S2",
        "manifest_type": "elaad_profile_batch",
        "status": "single-ev004-probe-batch-generated",
        "retrieval_timestamp_utc": retrieval_ts,
        "api_url": API_URL,
        "api_docs_url": DOCS_URL,
        "dashboard_url": DASHBOARD_URL,
        "api_docs_version_info": {
            "local_documentation_version": DOC_VERSION,
            "outlook_basis": OUTLOOK_BASIS,
            "server_header": response_headers.get("server") or response_headers.get("Server"),
            "live_api_version_header": response_headers.get("x-api-version") or response_headers.get("X-API-Version"),
        },
        "policy": {
            "decision": "EV-002",
            "scientific_decisions": ["EV-004", "EV-005"],
            "internal_project_computation": True,
            "commit_generated_profiles": False,
            "redistribute_generated_profiles": False,
            "data_availability": "Readers regenerate through the public API subject to terms applicable at retrieval time.",
            "stop_condition": "If explicit terms later prohibit this research use, stop and escalate.",
        },
        "request_json": body,
        "api_runtime_s": api_runtime_s,
        "api_runtime_note": (
            "Measured around the HTTPS POST only."
            if api_runtime_s is not None
            else "Exact HTTPS runtime was not captured because the first authorized call hit a post-response manifest bug; no second API call was made."
        ),
        "response_status_code": status_code,
        "response_status_code_source": (
            "HTTP response object"
            if not reconstructed_from_saved_raw
            else "Inferred from successful urlopen before the post-response manifest bug."
        ),
        "response_config_block": parsed_batch.response_config,
        "response_shape_summary": summary,
        "seed_semantics_observed": {
            "batch_seed": batch.seed,
            "n_profiles": batch.n_profiles,
            "control_mode": "uncontrolled",
            "member_identity": "Members are identified as (batch seed, returned profile index).",
            "future_smart_pair_identity": "A future EV-006 smart counterpart would add control_mode and reuse this batch seed plus returned profile index.",
            "smart_pair_order_verified": False,
            "smart_pair_order_note": "This uncontrolled-only probe cannot verify that a future smart batch preserves member ordering; actual smart-pair order remains pending per reports/elaad_profile_generation_spec.md section 7.",
            "independent_seed_claim": "Not claimed; batch seed 140001 identifies the response and member indices distinguish returned profiles.",
            "distinct_returned_members": distinct_members,
            "returned_indices_available_for_planned_pairing": distinct_members == batch.n_profiles,
        },
        "raw_response": {
            "path": raw_path.as_posix(),
            "size_bytes": raw_path.stat().st_size,
            "sha256_uncompressed_json": _sha256_bytes(response_payload),
            "sha256_gzip_file": _sha256_bytes(raw_path.read_bytes()),
        },
        "processed_profiles": {
            "path": processed_path.as_posix(),
            "format": "npz",
            "size_bytes": processed_path.stat().st_size,
            "sha256_file": _sha256_bytes(processed_path.read_bytes()),
            "commit_status": "ignored; not committed or redistributed",
        },
        "source_level_probe_verdict": {
            "supports_remaining_candidate_and_held_out_generation": distinct_members == batch.n_profiles,
            "library_adequacy_proven": False,
            "note": "This source-level probe checks API shape and member distinctness only; EV-005 adequacy is downstream and must not be inferred from component diagnostics.",
        },
        "bulk_generation_performed": False,
        "only_authorized_batch_generated": True,
        "reconstructed_from_saved_raw_response": reconstructed_from_saved_raw,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "elaad_e2_s2_ev004_home_cp_batchseed140001_shape_report.md"
    report_path.write_text(_shape_report(metadata, metadata_path), encoding="utf-8")

    if distinct_members < batch.n_profiles:
        raise ValueError(
            f"Expected {batch.n_profiles} distinct returned members, got {distinct_members}; "
            f"metadata saved at {metadata_path}"
        )
    return metadata_path


def write_authorized_set_a_artifacts_from_raw(
    *,
    raw_path: Path,
    metadata_dir: Path,
    processed_dir: Path,
    reports_dir: Path,
    command_wall_time_s: float | None = None,
) -> Path:
    """Recover manifest/report artifacts from an ignored raw response.

    This is intentionally local-only: it exists so a post-response failure can
    be repaired without making a second ElaadNL API call and violating the
    one-batch authorization.
    """
    retrieval_ts = datetime.fromtimestamp(raw_path.stat().st_mtime, UTC).isoformat().replace("+00:00", "Z")
    response_payload = read_gzip_json(raw_path)
    metadata_path = write_authorized_set_a_artifacts_from_response(
        response_payload=response_payload,
        metadata_dir=metadata_dir,
        raw_dir=raw_path.parent,
        processed_dir=processed_dir,
        reports_dir=reports_dir,
        api_runtime_s=None,
        retrieval_ts=retrieval_ts,
        status_code=200,
        response_headers={},
        reconstructed_from_saved_raw=True,
    )
    if command_wall_time_s is not None:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["observed_failed_command_wall_time_s"] = command_wall_time_s
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / "elaad_e2_s2_ev004_home_cp_batchseed140001_shape_report.md"
        report_path.write_text(_shape_report(metadata, metadata_path), encoding="utf-8")
    return metadata_path


def _shape_report(metadata: dict[str, Any], metadata_path: Path) -> str:
    summary = metadata["response_shape_summary"]
    energy = summary["annual_energy_kwh"]
    peak = summary["peak_kw"]
    request_body = metadata["request_json"]
    request_json = json.dumps(metadata["request_json"], indent=2, sort_keys=True)
    return (
        "# E2.S2 ElaadNL Set A shape report\n\n"
        "## Scope\n\n"
        "Single EV-004 Set A candidate probe only: home charge-point profiles "
        f"with the native car/van mix, simulated_year {request_body['simulated_year']}, "
        f"batch seed {request_body['seed']}, n_profiles {request_body['n_profiles']}. Raw and processed "
        "generated profiles are ignored and not redistributed under EV-002.\n\n"
        "## Request JSON\n\n"
        f"```json\n{request_json}\n```\n\n"
        "## Shape and timezone\n\n"
        f"- Timesteps: {summary['n_timesteps']}\n"
        f"- Profiles: {summary['n_profiles']}\n"
        f"- Distinct returned members: {summary['distinct_member_count']}\n"
        f"- Returned indices available for planned pairing: {metadata['seed_semantics_observed']['returned_indices_available_for_planned_pairing']}\n"
        f"- Smart pair order verified: {metadata['seed_semantics_observed']['smart_pair_order_verified']}\n"
        f"- First UTC timestamp: `{summary['first_timestamp_utc']}`\n"
        f"- First local timestamp: `{summary['first_timestamp_local']}`\n"
        f"- Last local timestamp: `{summary['last_timestamp_local']}`\n"
        f"- Missing/nonfinite values: {summary['missing_or_nonfinite_values']}\n"
        f"- Negative values: {summary['negative_values']}\n\n"
        "## Summary statistics\n\n"
        f"- Annual energy kWh: min {energy['min']:.3f}, median {energy['median']:.3f}, "
        f"mean {energy['mean']:.3f}, p95 {energy['p95']:.3f}, max {energy['max']:.3f}\n"
        f"- Peak kW: min {peak['min']:.3f}, median {peak['median']:.3f}, "
        f"mean {peak['mean']:.3f}, p95 {peak['p95']:.3f}, max {peak['max']:.3f}\n\n"
        "## Seed semantics\n\n"
        "Members are identified as `(batch seed, returned profile index)`. This "
        "report does not interpret a batch seed as a range of per-member seeds. "
        "Seed 140001 is reserved by EV-006 for a future same-seed smart-control "
        "counterpart, but no smart-control API call was made in this session. "
        "This uncontrolled-only probe leaves smart-batch member ordering "
        "unverified; actual pairing remains pending per section 7 of the "
        "Elaad profile generation spec.\n\n"
        "## Source-level verdict\n\n"
        f"- API runtime seconds: {_format_optional_seconds(metadata['api_runtime_s'])}\n"
        f"- API runtime note: {metadata['api_runtime_note']}\n"
        f"- Observed failed command wall time seconds: "
        f"{_format_optional_seconds(metadata.get('observed_failed_command_wall_time_s'))}\n"
        f"- Supports proceeding to remaining candidate and held-out generation: "
        f"{metadata['source_level_probe_verdict']['supports_remaining_candidate_and_held_out_generation']}\n"
        "- Library adequacy proven: False. Adequacy is an EV-005 downstream "
        "net-load/evaluator question, not a component-profile statistic.\n\n"
        "## Evidence\n\n"
        f"- Manifest: `{metadata_path.as_posix()}`\n"
        f"- Raw response checksum: `{metadata['raw_response']['sha256_gzip_file']}` "
        f"({metadata['raw_response']['size_bytes']} bytes gzip)\n"
        f"- Processed local checksum: `{metadata['processed_profiles']['sha256_file']}` "
        f"({metadata['processed_profiles']['size_bytes']} bytes npz)\n"
    )


def _format_optional_seconds(value: Any) -> str:
    if value is None:
        return "not recorded"
    return f"{float(value):.3f}"


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
            "scientific_decisions": ["EV-004", "EV-005"],
            "internal_project_computation": True,
            "commit_generated_profiles": False,
            "redistribute_generated_profiles": False,
            "data_availability": "Readers regenerate through the public API subject to terms applicable at retrieval time.",
            "stop_condition": "If explicit terms later prohibit this research use, stop and escalate.",
        },
        "seed_semantics": {
            "batch_seeds_are_distinct": True,
            "candidate_and_held_out_batches_are_disjoint": True,
            "smart_counterfactual_pairing": {
                "decision": "EV-006",
                "reuse_uncontrolled_batch_seed_and_member_index": True,
                "may_be_aggregated_as_independent_members": False,
                "smart_control_role_and_parameters_approved": False,
            },
            "note": "Keep uncontrolled member identity as (batch seed, returned profile index). A smart counterpart adds control_mode, reuses the same seed/index, and is never treated as an independent charger.",
        },
        "batches": [
            {
                **asdict(batch),
                "request_json": build_batch_request(batch),
                "raw_response_path": f"data/raw/elaad_profiles/{batch.storage_stem}.json.gz",
                "processed_path": f"data/processed/elaad_profiles/{batch.storage_stem}.npz",
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
    parser.add_argument("--run-ev004-home-cp-probe", action="store_true")
    parser.add_argument("--processed-dir", default="data/processed/elaad_profiles")
    parser.add_argument("--reports-dir", default="reports")
    parser.add_argument("--simulated-year", type=int, default=2033)
    parser.add_argument("--timeout-s", type=int, default=120)
    args = parser.parse_args(argv)

    actions = [
        args.probe_one_profile,
        args.write_library_plan,
        args.run_ev004_home_cp_probe,
    ]
    if sum(bool(item) for item in actions) > 1:
        parser.error("ElaadNL actions are mutually exclusive")

    if args.probe_one_profile:
        path = run_one_profile_probe(
            metadata_dir=Path(args.metadata_dir),
            raw_dir=Path(args.raw_dir),
            simulated_year=args.simulated_year,
            timeout_s=args.timeout_s,
        )
    elif args.write_library_plan:
        path = write_library_plan(Path(args.metadata_dir))
    elif args.run_ev004_home_cp_probe:
        path = run_authorized_set_a_batch(
            metadata_dir=Path(args.metadata_dir),
            raw_dir=Path(args.raw_dir),
            processed_dir=Path(args.processed_dir),
            reports_dir=Path(args.reports_dir),
            timeout_s=args.timeout_s,
        )
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
