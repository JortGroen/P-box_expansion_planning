from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.ev_model import e3_s2a_ev_heldout_adequacy_preflight_blockers

DEFAULT_ACCEPTED_INDEX = Path(
    "data/metadata/ev_adoption/e2_s2_ev_ic1_accepted_artifact_index_preflight.json"
)
DEFAULT_CRITERION_PACKET = Path(
    "data/metadata/ev_adoption/e3_s2a_ev_adequacy_criterion_packet.json"
)
DEFAULT_OUTPUT = Path(
    "data/metadata/ev_adoption/e3_s2a_ev_heldout_adequacy_preflight_blockers.json"
)
DEFAULT_CHECKSUM_OUTPUT = Path(
    "data/metadata/ev_adoption/e3_s2a_ev_candidate_component_output_checksum_preflight.json"
)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def git_blob_or_file_sha256(path: Path) -> str:
    """Return a stable committed-blob hash, falling back to file bytes for new files."""

    repo_path = path.as_posix()
    try:
        blob = subprocess.check_output(
            ["git", "show", f"HEAD:{repo_path}"],
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        blob = path.read_bytes()
    return hashlib.sha256(blob).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def verify_candidate_component_output_checksums(
    accepted_index: dict[str, Any],
    *,
    base_dir: Path = Path("."),
    checkpoint_path: Path = DEFAULT_CHECKSUM_OUTPUT,
) -> dict[str, object]:
    """Checkpoint candidate EV component-output checksum verification.

    This hashes NPZ bytes only. Missing ignored files are recorded as blockers;
    no profile arrays, held-out batches, or quarantined paths are opened.
    """

    scenario_index = accepted_index.get("scenario_index")
    if not isinstance(scenario_index, list):
        raise ValueError("Accepted EV index must include scenario_index")
    scenario_names = [
        str(row.get("scenario", ""))
        for row in scenario_index
        if isinstance(row, dict)
    ]
    if len(scenario_names) != len(scenario_index):
        raise ValueError("Accepted EV scenario records must be objects")
    duplicates = sorted({name for name in scenario_names if scenario_names.count(name) > 1})
    if duplicates:
        raise ValueError(f"Accepted EV index contains duplicate scenarios: {duplicates}")
    if set(scenario_names) != {"low", "middle", "high"}:
        raise ValueError("Accepted EV index must cover exactly low/middle/high scenarios")
    records: list[dict[str, object]] = []
    missing: list[dict[str, object]] = []
    mismatches: list[dict[str, object]] = []
    for row in sorted(scenario_index, key=lambda item: str(item.get("scenario", "")) if isinstance(item, dict) else ""):
        if not isinstance(row, dict):
            raise ValueError("Accepted EV scenario records must be objects")
        scenario = str(row.get("scenario", ""))
        rel_path = str(row.get("output_npz_path", ""))
        expected_sha = str(row.get("output_sha256", ""))
        if not scenario or not rel_path or len(expected_sha) != 64:
            raise ValueError("Accepted EV scenario record lacks scenario/path/sha256")
        normalized = rel_path.replace("\\", "/")
        if "held_out" in normalized or "quarantined" in normalized:
            raise ValueError("Candidate output checksum preflight must not reference held-out/quarantined paths")
        path = base_dir / rel_path
        record: dict[str, object] = {
            "scenario": scenario,
            "output_npz_path": normalized,
            "expected_sha256": expected_sha,
            "status": "missing",
            "observed_sha256": None,
            "byte_size": None,
        }
        if not path.is_file():
            missing.append({"scenario": scenario, "output_npz_path": normalized})
        else:
            observed = _sha256_file(path)
            record["observed_sha256"] = observed
            record["byte_size"] = path.stat().st_size
            if observed == expected_sha:
                record["status"] = "verified"
            else:
                record["status"] = "checksum_mismatch"
                mismatches.append(
                    {
                        "scenario": scenario,
                        "output_npz_path": normalized,
                        "expected_sha256": expected_sha,
                        "observed_sha256": observed,
                    }
                )
        records.append(record)
        checkpoint = _candidate_output_checksum_payload(
            records=records,
            missing_outputs=missing,
            checksum_mismatches=mismatches,
            complete=False,
        )
        _atomic_write_json(checkpoint_path, checkpoint)

    payload = _candidate_output_checksum_payload(
        records=records,
        missing_outputs=missing,
        checksum_mismatches=mismatches,
        complete=True,
    )
    _atomic_write_json(checkpoint_path, payload)
    return payload


def _candidate_output_checksum_payload(
    *,
    records: list[dict[str, object]],
    missing_outputs: list[dict[str, object]],
    checksum_mismatches: list[dict[str, object]],
    complete: bool,
) -> dict[str, object]:
    all_verified = complete and not missing_outputs and not checksum_mismatches and all(
        record.get("status") == "verified" for record in records
    )
    if all_verified:
        status = "verified_candidate_component_outputs"
    elif checksum_mismatches:
        status = "blocked_checksum_mismatch"
    elif missing_outputs:
        status = "blocked_missing_ignored_component_outputs"
    else:
        status = "checkpoint_incomplete"
    return {
        "schema_version": 1,
        "artifact_type": "ev_candidate_component_output_checksum_verification",
        "artifact_id": "e3_s2a_ev_candidate_component_output_checksum_preflight",
        "status": status,
        "all_expected_outputs_verified": all_verified,
        "verification_records": records,
        "missing_outputs": missing_outputs,
        "checksum_mismatches": checksum_mismatches,
        "checkpoint": {
            "complete": complete,
            "verified_or_checked_count": len(records),
            "resume_command": "./.venv/Scripts/python.exe data/get_ev_adequacy_preflight.py --verify-candidate-output-checksums",
        },
        "policy": {
            "candidate_outputs_only": True,
            "hash_file_bytes_only": True,
            "held_out_access": False,
            "quarantined_access": False,
            "profile_arrays_loaded": False,
            "integrated_analysis_performed": False,
            "event_or_p_e_analysis_performed": False,
            "capacity_screen_performed": False,
            "m_sufficiency_claimed": False,
            "manuscript_numbers_produced": False,
        },
    }


def build_preflight_from_paths(
    *,
    accepted_index_path: Path = DEFAULT_ACCEPTED_INDEX,
    criterion_packet_path: Path = DEFAULT_CRITERION_PACKET,
    candidate_output_checksum_verification_path: Path | None = None,
    local_candidate_output_checksums_verified: bool = False,
) -> dict[str, object]:
    """Build the E3.S2a EV adequacy blocker manifest from committed metadata."""

    accepted_index = _load_json(accepted_index_path)
    criterion_packet = _load_json(criterion_packet_path)
    checksum_verification = None
    checksum_path_text = None
    checksum_sha = None
    if candidate_output_checksum_verification_path is not None:
        checksum_verification = _load_json(candidate_output_checksum_verification_path)
        checksum_path_text = candidate_output_checksum_verification_path.as_posix()
        checksum_sha = git_blob_or_file_sha256(candidate_output_checksum_verification_path)
    return e3_s2a_ev_heldout_adequacy_preflight_blockers(
        accepted_index,
        criterion_packet,
        accepted_artifact_index_path=accepted_index_path.as_posix(),
        accepted_artifact_index_sha256=git_blob_or_file_sha256(accepted_index_path),
        criterion_packet_path=criterion_packet_path.as_posix(),
        criterion_packet_sha256=git_blob_or_file_sha256(criterion_packet_path),
        candidate_output_checksum_verification=checksum_verification,
        candidate_output_checksum_verification_path=checksum_path_text,
        candidate_output_checksum_verification_sha256=checksum_sha,
        local_candidate_output_checksums_verified=local_candidate_output_checksums_verified,
    )


def write_preflight_manifest(
    output_path: Path = DEFAULT_OUTPUT,
    *,
    accepted_index_path: Path = DEFAULT_ACCEPTED_INDEX,
    criterion_packet_path: Path = DEFAULT_CRITERION_PACKET,
    candidate_output_checksum_verification_path: Path | None = None,
    local_candidate_output_checksums_verified: bool = False,
) -> dict[str, object]:
    """Write the deterministic EV held-out adequacy preflight blocker manifest."""

    manifest = build_preflight_from_paths(
        accepted_index_path=accepted_index_path,
        criterion_packet_path=criterion_packet_path,
        candidate_output_checksum_verification_path=candidate_output_checksum_verification_path,
        local_candidate_output_checksums_verified=local_candidate_output_checksums_verified,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the fail-closed E3.S2a EV held-out adequacy preflight blocker "
            "manifest without opening held-out/quarantined data."
        )
    )
    parser.add_argument("--accepted-index", type=Path, default=DEFAULT_ACCEPTED_INDEX)
    parser.add_argument("--criterion-packet", type=Path, default=DEFAULT_CRITERION_PACKET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--checksum-output", type=Path, default=DEFAULT_CHECKSUM_OUTPUT)
    parser.add_argument("--base-dir", type=Path, default=Path("."))
    parser.add_argument(
        "--verify-candidate-output-checksums",
        action="store_true",
        help=(
            "Hash ignored candidate EV component-output NPZ files listed in the accepted index. "
            "Missing files are checkpointed as blockers; no arrays are loaded."
        ),
    )
    parser.add_argument(
        "--local-candidate-output-checksums-verified",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)
    checksum_path = None
    local_verified = args.local_candidate_output_checksums_verified
    if args.verify_candidate_output_checksums:
        accepted_index = _load_json(args.accepted_index)
        checksum_manifest = verify_candidate_component_output_checksums(
            accepted_index,
            base_dir=args.base_dir,
            checkpoint_path=args.checksum_output,
        )
        checksum_path = args.checksum_output
        local_verified = checksum_manifest["all_expected_outputs_verified"] is True
    manifest = write_preflight_manifest(
        args.output,
        accepted_index_path=args.accepted_index,
        criterion_packet_path=args.criterion_packet,
        candidate_output_checksum_verification_path=checksum_path,
        local_candidate_output_checksums_verified=local_verified,
    )
    print(json.dumps({"output": args.output.as_posix(), "blocked": manifest["blocked"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
