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
    quarantined_seeds = (141001, 141101)
    held_out_seeds = (141201, 141301)
    for partition, seeds in (
        ("candidate", candidate_seeds),
        ("quarantined_precriterion_diagnostic", quarantined_seeds),
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


def _validate_response_config_matches_request(config: dict[str, Any], request_body: dict[str, Any]) -> None:
    """Reject saved responses whose echoed request identity does not match."""
    expected = {
        "start_datetime": request_body["start_datetime"],
        "stop_datetime": request_body["stop_datetime"],
        "step_size_s": "PT15M",
        "timezone": request_body["timezone"],
        "simulated_year": request_body["simulated_year"],
        "profile_type": request_body["profile_type"],
        "n_profiles": request_body["n_profiles"],
        "vehicle_types": request_body["vehicle_types"],
        "location_type": request_body["location_type"],
        "cp_capacity_kw": float(request_body["cp_capacity_kw"]),
        "seed": request_body["seed"],
    }
    for key, value in expected.items():
        actual = config.get(key)
        if key == "cp_capacity_kw" and actual is not None:
            actual = float(actual)
        if actual != value:
            raise ValueError(
                f"ElaadNL response config mismatch for {key}: expected {value!r}, got {actual!r}"
            )


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
        batch=batch,
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
    batch: ProfileBatch | None = None,
    response_payload: bytes,
    metadata_dir: Path,
    raw_dir: Path | None = None,
    raw_path: Path | None = None,
    write_raw_response: bool = True,
    processed_dir: Path,
    reports_dir: Path,
    api_runtime_s: float | None,
    retrieval_ts: str,
    status_code: int,
    response_headers: dict[str, str],
    reconstructed_from_saved_raw: bool,
    raw_response_provenance: dict[str, Any] | None = None,
) -> Path:
    """Write commit-safe artifacts for one authorized EV-004 Set A batch."""
    if batch is None:
        batch = build_library_plan()[0]
    stem = batch.storage_stem
    body = build_batch_request(batch)
    if raw_path is None:
        if raw_dir is None:
            raise ValueError("raw_dir is required when raw_path is not provided")
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path = raw_dir / f"{stem}.json.gz"
    if write_raw_response:
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(raw_path, "wb") as handle:
            handle.write(response_payload)
    elif not raw_path.is_file():
        raise FileNotFoundError(f"Saved raw gzip does not exist: {raw_path}")

    parsed_batch = parse_elaad_profile_response(
        response_payload,
        batch_seed=batch.seed,
        expected_n_profiles=batch.n_profiles,
    )
    _validate_response_config_matches_request(parsed_batch.response_config, body)
    distinct_members = distinct_member_count(parsed_batch)

    processed_dir.mkdir(parents=True, exist_ok=True)
    processed_path = processed_dir / f"{stem}.npz"
    save_processed_batch_npz(parsed_batch, processed_path)

    summary = batch_summary(parsed_batch)
    if batch.partition == "held_out":
        # Fresh held-out batches stay source-integrity-only until E3.S2a freezes
        # its adequacy criterion; behavior summaries would leak evidence early.
        summary.pop("annual_energy_kwh", None)
        summary.pop("peak_kw", None)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = metadata_dir / f"{stem}_manifest.json"
    metadata = {
        "data_id": "D-002",
        "task_id": "E2.S2",
        "manifest_type": "elaad_profile_batch",
        "status": (
            "single-ev004-probe-batch-generated"
            if batch.seed == 140001 and batch.partition == "candidate"
            else f"ev004-set-a-{batch.partition}-batch-generated"
        ),
        "library_partition": batch.partition,
        "storage_stem": stem,
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
            "independent_seed_claim": f"Not claimed; batch seed {batch.seed} identifies the response and member indices distinguish returned profiles.",
            "distinct_returned_members": distinct_members,
            "returned_indices_available_for_planned_pairing": distinct_members == batch.n_profiles,
        },
        "raw_response": {
            "path": raw_path.as_posix(),
            "size_bytes": raw_path.stat().st_size,
            "sha256_uncompressed_json": _sha256_bytes(response_payload),
            "sha256_gzip_file": _sha256_bytes(raw_path.read_bytes()),
            **({"provenance": raw_response_provenance} if raw_response_provenance is not None else {}),
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
        "bulk_generation_performed": not (batch.seed == 140001 and batch.partition == "candidate"),
        "authorized_generation_scope": "EV-004 Set A home charge-point batch; no public or smart-control profiles.",
        "only_authorized_batch_generated": batch.seed == 140001 and batch.partition == "candidate",
        "held_out_policy": {
            "partition": batch.partition,
            "adequacy_use_allowed": False if batch.partition in {"held_out", "quarantined_precriterion_diagnostic"} else True,
            "note": (
                "Held-out batches are archived and source-validated only; they remain unopened for adequacy analysis until E3.S2a freezes the downstream criterion."
                if batch.partition == "held_out"
                else (
                    "Quarantined precriterion diagnostic batch retained transparently but excluded from candidate membership and held-out adequacy certification."
                    if batch.partition == "quarantined_precriterion_diagnostic"
                    else "Candidate batch available for downstream candidate-library construction; adequacy is not inferred here."
                )
            ),
        },
        "reconstructed_from_saved_raw_response": reconstructed_from_saved_raw,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"elaad_e2_s2_ev004_home_cp_batchseed{batch.seed}_shape_report.md"
    report_path.write_text(_shape_report(metadata, metadata_path), encoding="utf-8")

    if distinct_members < batch.n_profiles:
        raise ValueError(
            f"Expected {batch.n_profiles} distinct returned members, got {distinct_members}; "
            f"metadata saved at {metadata_path}"
        )
    return metadata_path


def write_authorized_set_a_artifacts_from_raw(
    *,
    batch: ProfileBatch | None = None,
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
    response_payload = read_gzip_json(raw_path)
    metadata_path = write_authorized_set_a_artifacts_from_response(
        batch=batch,
        response_payload=response_payload,
        metadata_dir=metadata_dir,
        raw_path=raw_path,
        write_raw_response=False,
        processed_dir=processed_dir,
        reports_dir=reports_dir,
        api_runtime_s=None,
        retrieval_ts=datetime.fromtimestamp(raw_path.stat().st_mtime, UTC).isoformat().replace("+00:00", "Z"),
        status_code=200,
        response_headers={},
        reconstructed_from_saved_raw=True,
    )
    if command_wall_time_s is not None:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["observed_failed_command_wall_time_s"] = command_wall_time_s
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        reports_dir.mkdir(parents=True, exist_ok=True)
        active_batch = batch or build_library_plan()[0]
        report_path = reports_dir / f"elaad_e2_s2_ev004_home_cp_batchseed{active_batch.seed}_shape_report.md"
        report_path.write_text(_shape_report(metadata, metadata_path), encoding="utf-8")
    return metadata_path


def _batch_paths(
    batch: ProfileBatch,
    *,
    metadata_dir: Path,
    raw_dir: Path,
    processed_dir: Path,
) -> dict[str, Path]:
    return {
        "manifest": metadata_dir / f"{batch.storage_stem}_manifest.json",
        "raw": raw_dir / f"{batch.storage_stem}.json.gz",
        "processed": processed_dir / f"{batch.storage_stem}.npz",
    }


def _load_verified_checkpoint(
    batch: ProfileBatch,
    *,
    metadata_dir: Path,
    raw_dir: Path,
    processed_dir: Path,
    reports_dir: Path,
) -> dict[str, Any] | None:
    paths = _batch_paths(batch, metadata_dir=metadata_dir, raw_dir=raw_dir, processed_dir=processed_dir)
    manifest_path = paths["manifest"]
    if not manifest_path.is_file():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("request_json") != build_batch_request(batch):
        raise ValueError(f"Checkpoint request mismatch for seed {batch.seed}: {manifest_path}")
    if not paths["raw"].is_file() or not paths["processed"].is_file():
        raise FileNotFoundError(f"Checkpoint files missing for seed {batch.seed}: {manifest_path}")
    if manifest["raw_response"]["sha256_gzip_file"] != _sha256_bytes(paths["raw"].read_bytes()):
        raise ValueError(f"Raw checksum mismatch for seed {batch.seed}: {paths['raw']}")
    if manifest["processed_profiles"]["sha256_file"] != _sha256_bytes(paths["processed"].read_bytes()):
        raise ValueError(f"Processed checksum mismatch for seed {batch.seed}: {paths['processed']}")
    if manifest.get("library_partition") != batch.partition:
        _reclassify_checkpoint_manifest(
            manifest_path=manifest_path,
            manifest=manifest,
            batch=batch,
            reports_dir=reports_dir,
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return manifest


def _reclassify_checkpoint_manifest(
    *,
    manifest_path: Path,
    manifest: dict[str, Any],
    batch: ProfileBatch,
    reports_dir: Path,
) -> None:
    manifest["library_partition"] = batch.partition
    manifest["status"] = f"ev004-set-a-{batch.partition}-batch-retained"
    manifest["bulk_generation_performed"] = not (batch.seed == 140001 and batch.partition == "candidate")
    if batch.partition == "candidate":
        policy_note = "Candidate batch available for downstream candidate-library construction; adequacy is not inferred here."
        adequacy_use_allowed = True
    elif batch.partition == "held_out":
        policy_note = "Held-out batch archived and source-validated only; adequacy use blocked until E3.S2a criterion authorization exists."
        adequacy_use_allowed = False
    else:
        policy_note = "Quarantined precriterion diagnostic batch retained transparently but excluded from candidate membership and held-out adequacy certification."
        adequacy_use_allowed = False
    manifest["held_out_policy"] = {
        "partition": batch.partition,
        "adequacy_use_allowed": adequacy_use_allowed,
        "note": policy_note,
    }
    if batch.partition == "quarantined_precriterion_diagnostic":
        manifest["quarantine"] = {
            "decision": "EV-005 follow-up",
            "reason": "PI-approved low-cost conservative replacement after source-level summaries were viewed before E3.S2a criterion freeze.",
            "not_general_redo_rule": True,
            "replacement_required_consultation_note": "Materially expensive repetition or evidence invalidation still requires PI consultation before repeating work.",
        }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"elaad_e2_s2_ev004_home_cp_batchseed{batch.seed}_shape_report.md"
    report_path.write_text(_shape_report(manifest, manifest_path), encoding="utf-8")


def run_set_a_library_batch(
    batch: ProfileBatch,
    *,
    metadata_dir: Path,
    raw_dir: Path,
    processed_dir: Path,
    reports_dir: Path,
    timeout_s: int,
) -> Path:
    """Generate one Set A batch or reuse a verified checkpoint.

    A retry may skip a batch only when the manifest request and both file
    checksums agree; otherwise the same seed could silently represent two
    different local member archives.
    """
    checkpoint = _load_verified_checkpoint(
        batch,
        metadata_dir=metadata_dir,
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        reports_dir=reports_dir,
    )
    if checkpoint is not None:
        return metadata_dir / f"{batch.storage_stem}_manifest.json"

    paths = _batch_paths(batch, metadata_dir=metadata_dir, raw_dir=raw_dir, processed_dir=processed_dir)
    if paths["raw"].is_file():
        return write_authorized_set_a_artifacts_from_raw(
            batch=batch,
            raw_path=paths["raw"],
            metadata_dir=metadata_dir,
            processed_dir=processed_dir,
            reports_dir=reports_dir,
        )

    body = build_batch_request(batch)
    request_payload = json.dumps(body, indent=2, sort_keys=True).encode("utf-8")
    retrieval_ts = datetime.now(UTC).isoformat().replace("+00:00", "Z")
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
        batch=batch,
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


def run_set_a_home_profile_library(
    *,
    metadata_dir: Path,
    raw_dir: Path,
    processed_dir: Path,
    reports_dir: Path,
    timeout_s: int,
) -> Path:
    """Generate remaining authorized Set A batches and write the library manifest."""
    started = perf_counter()
    generated_or_verified: list[Path] = []
    for batch in build_library_plan():
        # Seed 140001 was authorized and generated by the merged probe PR; this
        # command verifies it as a checkpoint but never issues a second request.
        generated_or_verified.append(
            run_set_a_library_batch(
                batch,
                metadata_dir=metadata_dir,
                raw_dir=raw_dir,
                processed_dir=processed_dir,
                reports_dir=reports_dir,
                timeout_s=timeout_s,
            )
        )
    return write_set_a_library_manifest(
        metadata_dir=metadata_dir,
        reports_dir=reports_dir,
        command_wall_time_s=perf_counter() - started,
        batch_manifest_paths=generated_or_verified,
    )


def write_set_a_library_manifest(
    *,
    metadata_dir: Path,
    reports_dir: Path,
    command_wall_time_s: float,
    batch_manifest_paths: Sequence[Path],
) -> Path:
    """Write a commit-safe manifest summarizing the frozen local Set A archive."""
    manifests = [json.loads(path.read_text(encoding="utf-8")) for path in batch_manifest_paths]
    partitions_by_seed = {batch.seed: batch.partition for batch in build_library_plan()}
    for item in manifests:
        item.setdefault("library_partition", partitions_by_seed[item["request_json"]["seed"]])
    candidate = [item for item in manifests if item["library_partition"] == "candidate"]
    quarantined = [
        item for item in manifests if item["library_partition"] == "quarantined_precriterion_diagnostic"
    ]
    held_out = [item for item in manifests if item["library_partition"] == "held_out"]
    payload = {
        "data_id": "D-002",
        "task_id": "E2.S2",
        "manifest_type": "elaad_set_a_home_cp_library",
        "status": "candidate-quarantined-and-fresh-held-out-batches-archived-locally",
        "created_timestamp_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "command_wall_time_s": command_wall_time_s,
        "summed_recorded_api_runtime_s": sum(
            item.get("api_runtime_s") or 0.0 for item in manifests
        ),
        "api_runtime_note": "Sum excludes any batch whose HTTPS runtime was not recorded, including recovered seed 140001.",
        "candidate_seed_range": "140001-140901 step 100",
        "quarantined_diagnostic_seeds": [141001, 141101],
        "held_out_seeds": [141201, 141301],
        "candidate_member_count": sum(item["response_shape_summary"]["n_profiles"] for item in candidate),
        "quarantined_diagnostic_member_count": sum(
            item["response_shape_summary"]["n_profiles"] for item in quarantined
        ),
        "held_out_member_count": sum(item["response_shape_summary"]["n_profiles"] for item in held_out),
        "library_adequacy_proven": False,
        "held_out_unopened_for_adequacy": True,
        "policy": {
            "decisions": ["EV-003", "EV-004", "EV-005", "EV-006"],
            "commit_generated_profiles": False,
            "redistribute_generated_profiles": False,
            "public_profiles_generated": False,
            "smart_profiles_generated": False,
        },
        "checkpoint_recovery": {
            "unit": "one 100-profile API batch",
            "resume_procedure": "Re-run data/get_elaad_profiles.py --run-set-a-home-profile-library; verified checkpoints are skipped, saved raw gzip files are recovered without rewriting, and mismatched checksums stop the run.",
            "retry_idempotence": "Retries reuse the identical request_json for a batch seed and cannot register a duplicate batch.",
        },
        "batches": [
            {
                "seed": item["request_json"]["seed"],
                "partition": item["library_partition"],
                "manifest_path": path.as_posix(),
                "raw_path": item["raw_response"]["path"],
                "raw_sha256_gzip_file": item["raw_response"]["sha256_gzip_file"],
                "raw_sha256_uncompressed_json": item["raw_response"]["sha256_uncompressed_json"],
                "processed_path": item["processed_profiles"]["path"],
                "processed_sha256_file": item["processed_profiles"]["sha256_file"],
                "n_timesteps": item["response_shape_summary"]["n_timesteps"],
                "n_profiles": item["response_shape_summary"]["n_profiles"],
                "distinct_member_count": item["response_shape_summary"]["distinct_member_count"],
                "smart_pair_order_verified": item["seed_semantics_observed"]["smart_pair_order_verified"],
            }
            for path, item in zip(batch_manifest_paths, manifests, strict=True)
        ],
    }
    metadata_dir.mkdir(parents=True, exist_ok=True)
    path = metadata_dir / "A_home_vancar_cp_y2030_set_a_library_manifest.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "elaad_e2_s2_home_cp_library_report.md"
    report_path.write_text(_library_report(payload, path), encoding="utf-8")
    return path


def _shape_report(metadata: dict[str, Any], metadata_path: Path) -> str:
    summary = metadata["response_shape_summary"]
    request_body = metadata["request_json"]
    request_json = json.dumps(metadata["request_json"], indent=2, sort_keys=True)
    partition = metadata.get("library_partition", "candidate")
    behavior_summary = ""
    if "annual_energy_kwh" in summary and "peak_kw" in summary:
        energy = summary["annual_energy_kwh"]
        peak = summary["peak_kw"]
        behavior_summary = (
            "## Summary statistics\n\n"
            f"- Annual energy kWh: min {energy['min']:.3f}, median {energy['median']:.3f}, "
            f"mean {energy['mean']:.3f}, p95 {energy['p95']:.3f}, max {energy['max']:.3f}\n"
            f"- Peak kW: min {peak['min']:.3f}, median {peak['median']:.3f}, "
            f"mean {peak['mean']:.3f}, p95 {peak['p95']:.3f}, max {peak['max']:.3f}\n\n"
        )
    else:
        behavior_summary = (
            "## Summary statistics\n\n"
            "Behavioral annual-energy, peak, and percentile summaries are intentionally omitted for fresh held-out batches until E3.S2a freezes the adequacy criterion.\n\n"
        )
    return (
        "# E2.S2 ElaadNL Set A shape report\n\n"
        "## Scope\n\n"
        f"EV-004 Set A `{partition}` batch: home charge-point profiles "
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
        f"{behavior_summary}"
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
        f"{_raw_response_provenance_lines(metadata)}"
        f"- Processed local checksum: `{metadata['processed_profiles']['sha256_file']}` "
        f"({metadata['processed_profiles']['size_bytes']} bytes npz)\n"
    )


def _raw_response_provenance_lines(metadata: dict[str, Any]) -> str:
    provenance = metadata.get("raw_response", {}).get("provenance")
    if not provenance:
        return ""
    lines = ["- Raw response provenance:"]
    for key in (
        "initial_saved_wrapper_sha256_gzip_file",
        "recovery_rewritten_wrapper_sha256_gzip_file",
        "sha256_uncompressed_json",
        "note",
    ):
        value = provenance.get(key)
        if value is not None:
            lines.append(f"  - {key}: `{value}`")
    return "\n".join(lines) + "\n"


def _library_report(payload: dict[str, Any], manifest_path: Path) -> str:
    batches = payload["batches"]
    candidate = [item for item in batches if item["partition"] == "candidate"]
    quarantined = [
        item for item in batches if item["partition"] == "quarantined_precriterion_diagnostic"
    ]
    held_out = [item for item in batches if item["partition"] == "held_out"]
    return (
        "# E2.S2 ElaadNL Set A home charge-point library report\n\n"
        "## Scope\n\n"
        "Frozen EV-004 uncontrolled home charge-point library for the native "
        "van/car mix, 11 kW charge points, simulated_year 2030. Raw API "
        "responses and processed annual members stay in ignored data paths and "
        "are not redistributed. This report records source integrity only; it "
        "does not declare M=1000 sufficient.\n\n"
        "## Generated batches\n\n"
        f"- Candidate seeds: {payload['candidate_seed_range']} "
        f"({len(candidate)} batches, {payload['candidate_member_count']} members)\n"
        f"- Quarantined diagnostic seeds: {', '.join(str(seed) for seed in payload['quarantined_diagnostic_seeds'])} "
        f"({len(quarantined)} batches, {payload['quarantined_diagnostic_member_count']} members)\n"
        f"- Held-out seeds: {', '.join(str(seed) for seed in payload['held_out_seeds'])} "
        f"({len(held_out)} batches, {payload['held_out_member_count']} members)\n"
        "- Public Set B generated: False\n"
        "- Smart Set D generated: False\n\n"
        "## Checkpoint and recovery\n\n"
        f"{payload['checkpoint_recovery']['resume_procedure']} "
        f"{payload['checkpoint_recovery']['retry_idempotence']}\n\n"
        "## Verification\n\n"
        f"- Command wall time seconds: {_format_optional_seconds(payload['command_wall_time_s'])}\n"
        f"- Summed recorded API runtime seconds: {_format_optional_seconds(payload['summed_recorded_api_runtime_s'])}\n"
        f"- API runtime note: {payload['api_runtime_note']}\n"
        f"- Every listed batch has 35,040 timesteps: {all(item['n_timesteps'] == 35040 for item in batches)}\n"
        f"- Every listed batch has 100 profiles: {all(item['n_profiles'] == 100 for item in batches)}\n"
        f"- Every listed batch has 100 distinct members: {all(item['distinct_member_count'] == 100 for item in batches)}\n"
        f"- Smart pair order verified: {all(item['smart_pair_order_verified'] for item in batches)}\n"
        "- Missing/nonfinite and negative-value checks are recorded in the per-batch manifests.\n\n"
        "## Held-out isolation\n\n"
        "Seeds 141001 and 141101 are retained as quarantined precriterion "
        "diagnostics and may not certify held-out adequacy. Fresh held-out "
        "batches 141201 and 141301 were generated, source-validated, "
        "checksummed, and archived only. They were not opened for adequacy "
        "analysis, and E3.S2a must freeze the criterion before any held-out "
        "use. The low-cost replacement does not create a blanket requirement "
        "to redo materially expensive work without PI consultation.\n\n"
        "## Evidence\n\n"
        f"- Library manifest: `{manifest_path.as_posix()}`\n"
        "- Per-batch raw and processed checksums are listed in the manifest.\n"
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
    parser.add_argument("--run-set-a-home-profile-library", action="store_true")
    parser.add_argument("--processed-dir", default="data/processed/elaad_profiles")
    parser.add_argument("--reports-dir", default="reports")
    parser.add_argument("--simulated-year", type=int, default=2033)
    parser.add_argument("--timeout-s", type=int, default=120)
    args = parser.parse_args(argv)

    actions = [
        args.probe_one_profile,
        args.write_library_plan,
        args.run_ev004_home_cp_probe,
        args.run_set_a_home_profile_library,
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
    elif args.run_set_a_home_profile_library:
        path = run_set_a_home_profile_library(
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
