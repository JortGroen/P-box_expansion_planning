from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.ev_model import (
    ev_ic1_generic_component_output_loader_manifests,
    materialize_ev_ic1_candidate_component_outputs,
)


DEFAULT_COMPONENT_INPUT_SCAFFOLD = Path(
    "data/metadata/ev_adoption/e2_s2_ev_ic1_component_input_scaffold.json"
)
DEFAULT_CHECKSUM_PREFLIGHT = Path(
    "data/metadata/ev_adoption/e2_s2_ev_candidate_profile_checksum_preflight.json"
)
DEFAULT_SELECTION_MANIFEST_SET = Path(
    "data/metadata/ev_adoption/e2_s2_ev005b_candidate_selection_manifests.json.gz"
)
DEFAULT_COMPONENT_OUTPUT_MANIFEST = Path(
    "data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_component_output_manifest.json"
)
DEFAULT_RECOVERY_CHECKPOINT = Path(
    "data/metadata/ev_adoption/e3_s2a_ev_component_output_recovery_preflight.json"
)
DEFAULT_ACCEPTED_ARTIFACT_INDEX = Path(
    "data/metadata/ev_adoption/e2_s2_ev_ic1_accepted_artifact_index_preflight.json"
)
DEFAULT_GENERIC_LOADER_MANIFEST_DIR = Path(
    "data/metadata/ev_adoption/generic_component_output_manifests"
)
DEFAULT_GENERIC_LOADER_PACKET = Path(
    "data/metadata/ev_adoption/e3_s2a_ev_ic1_generic_component_output_manifest_packet.json"
)
DEFAULT_OUTPUT_DIR = Path("data/processed/elaad_profiles/component_outputs")
RESTORE_INSTRUCTION = (
    "Restore the ignored candidate processed-profile NPZ files listed above "
    "under data/processed/elaad_profiles from the verified local artifact store, "
    "or ask the PI before regenerating ElaadNL source batches. Then rerun "
    ".\\.venv\\Scripts\\python.exe data\\get_ev_component_outputs.py rebuild "
    "--candidate-source-root <verified-local-artifact-root> "
    "--checkpoint-path data\\metadata\\ev_adoption\\e3_s2a_ev_component_output_recovery_preflight.json "
    "and then verify with .\\.venv\\Scripts\\python.exe data\\get_ev_component_outputs.py verify."
)


class EVComponentOutputVerificationError(RuntimeError):
    """Raised when EV component-output handoff verification must fail closed."""


def _load_json(path: Path) -> dict[str, Any]:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise EVComponentOutputVerificationError(f"Expected JSON object in {path}")
    return payload


def _sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_blob_or_file_sha256(base_dir: Path, relative_path: Path) -> str:
    try:
        blob = subprocess.check_output(
            ["git", "-C", str(base_dir), "show", f"HEAD:{relative_path.as_posix()}"],
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return _sha256_file(base_dir / relative_path)
    import hashlib

    return hashlib.sha256(blob).hexdigest()


def _require_output_records(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    materialization = manifest.get("materialization")
    if not isinstance(materialization, dict):
        raise EVComponentOutputVerificationError("Component-output manifest lacks materialization")
    records = materialization.get("output_files")
    if not isinstance(records, list) or not records:
        raise EVComponentOutputVerificationError("Component-output manifest lacks output_files")
    result: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            raise EVComponentOutputVerificationError("Component-output output_files must be objects")
        result.append(record)
    return result



def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_bytes((json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    tmp_path.replace(path)


def _candidate_processed_records(checksum_preflight: Mapping[str, Any]) -> list[dict[str, Any]]:
    verification = checksum_preflight.get("verification")
    if not isinstance(verification, dict):
        raise EVComponentOutputVerificationError("Checksum preflight lacks verification metadata")
    batch_records = verification.get("verified_candidate_batches")
    if not isinstance(batch_records, list) or not batch_records:
        raise EVComponentOutputVerificationError("Checksum preflight lacks verified candidate batches")
    result: list[dict[str, Any]] = []
    for record in batch_records:
        if not isinstance(record, dict):
            raise EVComponentOutputVerificationError("Checksum preflight batch records must be objects")
        processed_path = str(record.get("processed_path", ""))
        expected_sha = str(record.get("expected_sha256", ""))
        if not processed_path or len(expected_sha) != 64:
            raise EVComponentOutputVerificationError(
                "Checksum preflight batch record lacks processed_path or expected_sha256"
            )
        lowered_path = processed_path.lower()
        if "held_out" in lowered_path or "held-out" in lowered_path or "quarantined" in lowered_path:
            raise EVComponentOutputVerificationError(
                "Recovery preflight is candidate-only and rejects held-out/quarantined paths"
            )
        result.append(
            {
                "processed_path": processed_path,
                "expected_sha256": expected_sha,
                "byte_size": record.get("byte_size"),
                "capacity_class": record.get("capacity_class"),
                "component_id": record.get("component_id"),
                "cp_capacity_kw": record.get("cp_capacity_kw"),
                "library_id": record.get("library_id"),
                "n_profiles": record.get("n_profiles"),
                "n_timesteps": record.get("n_timesteps"),
                "seed": record.get("seed"),
            }
        )
    return sorted(result, key=lambda item: str(item["processed_path"]))


def _checkpoint_payload(
    *,
    status: str,
    mode: str,
    timestamp_utc: str,
    candidate_records: Sequence[Mapping[str, Any]],
    missing_candidate_profiles: Sequence[Mapping[str, Any]],
    restored_candidate_profiles: Sequence[Mapping[str, Any]],
    already_present_candidate_profiles: Sequence[Mapping[str, Any]],
    source_mismatches: Sequence[Mapping[str, Any]],
    target_mismatches: Sequence[Mapping[str, Any]],
    component_output_manifest: Mapping[str, Any],
    checkpoint_complete: bool,
    candidate_source_root_supplied: bool,
) -> dict[str, Any]:
    output_records = _require_output_records(component_output_manifest)
    return {
        "artifact_type": "ev_component_output_recovery_preflight",
        "artifact_id": "e3_s2a_ev_component_output_recovery_preflight",
        "schema_version": 1,
        "task_id": "E3.S2a",
        "status": status,
        "mode": mode,
        "timestamp_utc": timestamp_utc,
        "policy": {
            "candidate_only": True,
            "held_out_access": False,
            "quarantined_access": False,
            "elaad_api_calls": False,
            "profile_arrays_loaded_during_candidate_restore": False,
            "m_sufficiency_claim": False,
            "integrated_analysis_performed": False,
        },
        "source_artifacts": {
            "checksum_preflight": DEFAULT_CHECKSUM_PREFLIGHT.as_posix(),
            "component_input_scaffold": DEFAULT_COMPONENT_INPUT_SCAFFOLD.as_posix(),
            "selection_manifest_set": DEFAULT_SELECTION_MANIFEST_SET.as_posix(),
            "component_output_manifest": DEFAULT_COMPONENT_OUTPUT_MANIFEST.as_posix(),
        },
        "candidate_source_root": {
            "argument_supplied": candidate_source_root_supplied,
            "absolute_path_committed": False,
            "description": "User-supplied local ignored artifact root; verify hashes before copying.",
        },
        "required_candidate_processed_profile_count": len(candidate_records),
        "restored_candidate_processed_profile_count": len(restored_candidate_profiles),
        "already_present_candidate_processed_profile_count": len(already_present_candidate_profiles),
        "missing_candidate_processed_profiles": list(missing_candidate_profiles),
        "restored_candidate_processed_profiles": list(restored_candidate_profiles),
        "already_present_candidate_processed_profiles": list(already_present_candidate_profiles),
        "source_checksum_mismatches": list(source_mismatches),
        "target_checksum_mismatches": list(target_mismatches),
        "expected_component_outputs": [
            {
                "scenario": record.get("scenario"),
                "path": record.get("path"),
                "sha256": record.get("sha256"),
                "byte_size": record.get("byte_size"),
                "array_shape": record.get("array_shape"),
            }
            for record in output_records
        ],
        "checkpoint": {
            "complete": checkpoint_complete,
            "resume_command": (
                ".\\.venv\\Scripts\\python.exe data\\get_ev_component_outputs.py rebuild "
                "--candidate-source-root <verified-local-artifact-root> "
                "--checkpoint-path data\\metadata\\ev_adoption\\e3_s2a_ev_component_output_recovery_preflight.json"
            ),
            "safe_resume_behavior": (
                "Existing target candidate NPZs are rehashed and skipped only when their SHA-256 "
                "matches the committed checksum preflight; mismatched targets fail closed."
            ),
        },
    }


def restore_candidate_processed_profiles(
    checksum_preflight: Mapping[str, Any],
    *,
    base_dir: Path,
    candidate_source_root: Path,
    component_output_manifest: Mapping[str, Any],
    checkpoint_path: Path | None,
    timestamp_utc: str,
) -> dict[str, Any]:
    """Restore ignored candidate processed NPZs from a verified local artifact root."""

    candidate_records = _candidate_processed_records(checksum_preflight)
    restored: list[dict[str, Any]] = []
    already_present: list[dict[str, Any]] = []
    missing_source: list[dict[str, Any]] = []
    source_mismatches: list[dict[str, Any]] = []
    target_mismatches: list[dict[str, Any]] = []

    def checkpoint(status: str, *, complete: bool) -> dict[str, Any]:
        payload = _checkpoint_payload(
            status=status,
            mode="restore_candidate_processed_profiles",
            timestamp_utc=timestamp_utc,
            candidate_records=candidate_records,
            missing_candidate_profiles=missing_source,
            restored_candidate_profiles=restored,
            already_present_candidate_profiles=already_present,
            source_mismatches=source_mismatches,
            target_mismatches=target_mismatches,
            component_output_manifest=component_output_manifest,
            checkpoint_complete=complete,
            candidate_source_root_supplied=True,
        )
        if checkpoint_path is not None:
            _write_json(base_dir / checkpoint_path, payload)
        return payload

    checkpoint("candidate_processed_profile_restore_in_progress", complete=False)
    for record in candidate_records:
        rel_path = str(record["processed_path"])
        expected_sha = str(record["expected_sha256"])
        source_path = candidate_source_root / rel_path
        target_path = base_dir / rel_path
        if target_path.is_file():
            observed_sha = _sha256_file(target_path)
            if observed_sha == expected_sha:
                already_present.append({**record, "observed_sha256": observed_sha})
            else:
                target_mismatches.append(
                    {**record, "observed_sha256": observed_sha, "failure": "target_exists_with_wrong_checksum"}
                )
            checkpoint("candidate_processed_profile_restore_in_progress", complete=False)
            continue
        if not source_path.is_file():
            missing_source.append({**record, "failure": "missing_from_candidate_source_root"})
            checkpoint("candidate_processed_profile_restore_in_progress", complete=False)
            continue
        source_sha = _sha256_file(source_path)
        if source_sha != expected_sha:
            source_mismatches.append(
                {**record, "observed_sha256": source_sha, "failure": "source_checksum_mismatch"}
            )
            checkpoint("candidate_processed_profile_restore_in_progress", complete=False)
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target_path.with_name(f"{target_path.name}.part")
        shutil.copy2(source_path, tmp_path)
        copied_sha = _sha256_file(tmp_path)
        if copied_sha != expected_sha:
            tmp_path.unlink(missing_ok=True)
            target_mismatches.append(
                {**record, "observed_sha256": copied_sha, "failure": "copied_file_checksum_mismatch"}
            )
            checkpoint("candidate_processed_profile_restore_in_progress", complete=False)
            continue
        tmp_path.replace(target_path)
        restored.append({**record, "observed_sha256": copied_sha})
        checkpoint("candidate_processed_profile_restore_in_progress", complete=False)

    blocked = bool(missing_source or source_mismatches or target_mismatches)
    status = (
        "blocked_missing_or_mismatched_candidate_processed_profiles"
        if blocked
        else "candidate_processed_profiles_ready_for_component_output_rebuild"
    )
    return checkpoint(status, complete=True)


def missing_candidate_processed_paths(
    checksum_preflight: Mapping[str, Any],
    *,
    base_dir: Path,
) -> tuple[str, ...]:
    """Return missing candidate profile files required before any EV array loading."""

    missing = [
        str(record["processed_path"])
        for record in _candidate_processed_records(checksum_preflight)
        if not (base_dir / str(record["processed_path"])).is_file()
    ]
    return tuple(sorted(missing))


def verify_existing_ev_component_outputs(
    component_output_manifest: Mapping[str, Any],
    *,
    base_dir: Path,
) -> dict[str, object]:
    """Verify ignored EV component-output NPZ files against the committed manifest."""

    missing: list[str] = []
    mismatches: list[dict[str, str]] = []
    verified: list[dict[str, object]] = []
    for record in _require_output_records(component_output_manifest):
        rel_path = str(record.get("path", ""))
        expected_sha = str(record.get("sha256", ""))
        if not rel_path or len(expected_sha) != 64:
            raise EVComponentOutputVerificationError("Output manifest record lacks path or sha256")
        path = base_dir / rel_path
        if not path.is_file():
            missing.append(rel_path)
            continue
        observed_sha = _sha256_file(path)
        if observed_sha != expected_sha:
            mismatches.append(
                {
                    "path": rel_path,
                    "expected_sha256": expected_sha,
                    "observed_sha256": observed_sha,
                }
            )
            continue
        verified.append(
            {
                "path": rel_path,
                "scenario": record.get("scenario"),
                "sha256": observed_sha,
                "byte_size": path.stat().st_size,
            }
        )
    if missing:
        raise EVComponentOutputVerificationError(
            "Missing ignored EV component-output NPZ files:\n"
            + "\n".join(f"- {path}" for path in missing)
            + "\n"
            + RESTORE_INSTRUCTION
        )
    if mismatches:
        lines = [
            f"- {item['path']}: expected {item['expected_sha256']}, observed {item['observed_sha256']}"
            for item in mismatches
        ]
        raise EVComponentOutputVerificationError(
            "EV component-output checksum mismatch:\n" + "\n".join(lines)
        )
    return {
        "status": "verified",
        "mode": "verify",
        "verified_output_count": len(verified),
        "verified_outputs": verified,
    }


def rebuild_and_verify_ev_component_outputs(
    *,
    component_input_scaffold: Mapping[str, Any],
    checksum_preflight: Mapping[str, Any],
    selection_manifest_set: Mapping[str, Any],
    committed_component_output_manifest: Mapping[str, Any],
    base_dir: Path,
    output_dir: Path,
    timestamp_utc: str,
    candidate_source_root: Path | None = None,
    checkpoint_path: Path | None = None,
) -> dict[str, object]:
    """Rebuild ignored EV component outputs and compare them to committed checksums."""

    candidate_recovery: dict[str, Any] | None = None
    missing = missing_candidate_processed_paths(checksum_preflight, base_dir=base_dir)
    if missing and candidate_source_root is None:
        candidate_records = _candidate_processed_records(checksum_preflight)
        if checkpoint_path is not None:
            _write_json(
                base_dir / checkpoint_path,
                _checkpoint_payload(
                    status="blocked_missing_candidate_processed_profiles",
                    mode="rebuild",
                    timestamp_utc=timestamp_utc,
                    candidate_records=candidate_records,
                    missing_candidate_profiles=[
                        record for record in candidate_records if str(record["processed_path"]) in set(missing)
                    ],
                    restored_candidate_profiles=[],
                    already_present_candidate_profiles=[],
                    source_mismatches=[],
                    target_mismatches=[],
                    component_output_manifest=committed_component_output_manifest,
                    checkpoint_complete=True,
                    candidate_source_root_supplied=False,
                ),
            )
        raise EVComponentOutputVerificationError(
            "Missing candidate processed-profile NPZ files required before EV array loading:\n"
            + "\n".join(f"- {path}" for path in missing)
            + "\n"
            + RESTORE_INSTRUCTION
        )
    if missing and candidate_source_root is not None:
        candidate_recovery = restore_candidate_processed_profiles(
            checksum_preflight,
            base_dir=base_dir,
            candidate_source_root=candidate_source_root.resolve(),
            component_output_manifest=committed_component_output_manifest,
            checkpoint_path=checkpoint_path,
            timestamp_utc=timestamp_utc,
        )
        if candidate_recovery["status"] != "candidate_processed_profiles_ready_for_component_output_rebuild":
            failures = [
                *(str(item["processed_path"]) for item in candidate_recovery["missing_candidate_processed_profiles"]),
                *(str(item["processed_path"]) for item in candidate_recovery["source_checksum_mismatches"]),
                *(str(item["processed_path"]) for item in candidate_recovery["target_checksum_mismatches"]),
            ]
            raise EVComponentOutputVerificationError(
                "Candidate processed-profile recovery failed before EV array loading:\n"
                + "\n".join(f"- {path}" for path in failures)
                + "\n"
                + RESTORE_INSTRUCTION
            )
        missing = missing_candidate_processed_paths(checksum_preflight, base_dir=base_dir)
        if missing:
            raise EVComponentOutputVerificationError(
                "Candidate processed-profile recovery checkpoint completed but files are still missing:\n"
                + "\n".join(f"- {path}" for path in missing)
            )
    observed_manifest = materialize_ev_ic1_candidate_component_outputs(
        component_input_scaffold,
        checksum_preflight,
        selection_manifest_set,
        base_dir=base_dir,
        output_dir=output_dir,
        materialized_timestamp_utc=timestamp_utc,
    )
    expected_records = _require_output_records(committed_component_output_manifest)
    observed_records = _require_output_records(observed_manifest)
    expected_names = [str(record.get("scenario")) for record in expected_records]
    observed_names = [str(record.get("scenario")) for record in observed_records]
    duplicate_expected = sorted({name for name in expected_names if expected_names.count(name) > 1})
    duplicate_observed = sorted({name for name in observed_names if observed_names.count(name) > 1})
    if duplicate_expected or duplicate_observed:
        raise EVComponentOutputVerificationError(
            "EV component-output manifest contains duplicate scenario records: "
            f"expected: {', '.join(duplicate_expected) if duplicate_expected else '--'}; "
            f"observed: {', '.join(duplicate_observed) if duplicate_observed else '--'}"
        )
    expected_by_scenario = {name: record for name, record in zip(expected_names, expected_records, strict=True)}
    observed_by_scenario = {name: record for name, record in zip(observed_names, observed_records, strict=True)}
    expected_scenarios = set(expected_by_scenario)
    observed_scenarios = set(observed_by_scenario)
    if observed_scenarios != expected_scenarios:
        missing = sorted(expected_scenarios - observed_scenarios)
        extra = sorted(observed_scenarios - expected_scenarios)
        raise EVComponentOutputVerificationError(
            "Rebuilt EV component-output scenario set mismatch: "
            f"missing: {', '.join(missing) if missing else '--'}; "
            f"extra: {', '.join(extra) if extra else '--'}"
        )
    mismatches: list[dict[str, str]] = []
    for scenario in sorted(observed_by_scenario):
        record = observed_by_scenario[scenario]
        expected = expected_by_scenario[scenario]
        for key in ("path", "sha256"):
            if record.get(key) != expected.get(key):
                mismatches.append(
                    {
                        "scenario": scenario,
                        "field": key,
                        "expected": str(expected.get(key)),
                        "observed": str(record.get(key)),
                    }
                )
    if mismatches:
        lines = [
            f"- {item['scenario']} {item['field']}: expected {item['expected']}, observed {item['observed']}"
            for item in mismatches
        ]
        raise EVComponentOutputVerificationError(
            "Rebuilt EV component outputs do not match the committed manifest:\n"
            + "\n".join(lines)
        )
    result: dict[str, object] = {
        "status": "verified",
        "mode": "rebuild",
        "rebuilt_output_count": len(expected_by_scenario),
        "manifest": observed_manifest,
    }
    if candidate_recovery is not None:
        result["candidate_processed_profile_recovery"] = candidate_recovery
        if checkpoint_path is not None:
            success_checkpoint = dict(candidate_recovery)
            success_checkpoint["status"] = "component_outputs_rebuilt_and_verified"
            success_checkpoint["rebuilt_component_outputs"] = [
                {
                    "scenario": record.get("scenario"),
                    "path": record.get("path"),
                    "sha256": record.get("sha256"),
                    "byte_size": record.get("byte_size"),
                }
                for record in observed_records
            ]
            _write_json(base_dir / checkpoint_path, success_checkpoint)
    return result


def write_generic_loader_manifests(
    *,
    accepted_artifact_index: Mapping[str, Any],
    recovery_preflight: Mapping[str, Any],
    base_dir: Path,
    manifest_directory: Path = DEFAULT_GENERIC_LOADER_MANIFEST_DIR,
    packet_path: Path = DEFAULT_GENERIC_LOADER_PACKET,
    accepted_artifact_index_path: Path = DEFAULT_ACCEPTED_ARTIFACT_INDEX,
    recovery_preflight_path: Path = DEFAULT_RECOVERY_CHECKPOINT,
) -> dict[str, object]:
    """Write generic Agent A-loader EV manifests and their packet."""

    index_sha = _repo_blob_or_file_sha256(base_dir, accepted_artifact_index_path)
    recovery_sha = _repo_blob_or_file_sha256(base_dir, recovery_preflight_path)
    initial = ev_ic1_generic_component_output_loader_manifests(
        accepted_artifact_index,
        recovery_preflight,
        accepted_artifact_index_path=accepted_artifact_index_path.as_posix(),
        accepted_artifact_index_sha256=index_sha,
        recovery_preflight_path=recovery_preflight_path.as_posix(),
        recovery_preflight_sha256=recovery_sha,
        manifest_directory=manifest_directory.as_posix(),
    )
    manifest_sha_by_path: dict[str, str] = {}
    for record in initial["scenario_manifests"]:
        scenario = str(record["scenario"])
        rel_path = Path(str(record["path"]))
        manifest = initial["manifests_by_scenario"][scenario]
        _write_json(base_dir / rel_path, manifest)
        manifest_sha_by_path[rel_path.as_posix()] = _sha256_file(base_dir / rel_path)

    final = ev_ic1_generic_component_output_loader_manifests(
        accepted_artifact_index,
        recovery_preflight,
        accepted_artifact_index_path=accepted_artifact_index_path.as_posix(),
        accepted_artifact_index_sha256=index_sha,
        recovery_preflight_path=recovery_preflight_path.as_posix(),
        recovery_preflight_sha256=recovery_sha,
        manifest_directory=manifest_directory.as_posix(),
        manifest_sha256_by_path=manifest_sha_by_path,
    )
    _write_json(base_dir / packet_path, final)
    return final


def _default_timestamp_utc() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify, rebuild, or write generic-loader manifests for ignored candidate-only "
            "EV component-output NPZs from committed metadata. This command never fetches "
            "or regenerates ElaadNL source data."
        )
    )
    parser.add_argument("mode", choices=("verify", "rebuild", "write-loader-manifests"))
    parser.add_argument("--base-dir", type=Path, default=Path("."))
    parser.add_argument("--component-input-scaffold", type=Path, default=DEFAULT_COMPONENT_INPUT_SCAFFOLD)
    parser.add_argument("--checksum-preflight", type=Path, default=DEFAULT_CHECKSUM_PREFLIGHT)
    parser.add_argument("--selection-manifest-set", type=Path, default=DEFAULT_SELECTION_MANIFEST_SET)
    parser.add_argument("--component-output-manifest", type=Path, default=DEFAULT_COMPONENT_OUTPUT_MANIFEST)
    parser.add_argument("--accepted-artifact-index", type=Path, default=DEFAULT_ACCEPTED_ARTIFACT_INDEX)
    parser.add_argument("--generic-loader-manifest-dir", type=Path, default=DEFAULT_GENERIC_LOADER_MANIFEST_DIR)
    parser.add_argument("--generic-loader-packet", type=Path, default=DEFAULT_GENERIC_LOADER_PACKET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--candidate-source-root", type=Path, default=None)
    parser.add_argument("--checkpoint-path", type=Path, default=DEFAULT_RECOVERY_CHECKPOINT)
    parser.add_argument("--timestamp-utc", default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    base_dir = args.base_dir.resolve()
    try:
        component_output_manifest = _load_json(base_dir / args.component_output_manifest)
        if args.mode == "verify":
            result = verify_existing_ev_component_outputs(
                component_output_manifest,
                base_dir=base_dir,
            )
        elif args.mode == "rebuild":
            result = rebuild_and_verify_ev_component_outputs(
                component_input_scaffold=_load_json(base_dir / args.component_input_scaffold),
                checksum_preflight=_load_json(base_dir / args.checksum_preflight),
                selection_manifest_set=_load_json(base_dir / args.selection_manifest_set),
                committed_component_output_manifest=component_output_manifest,
                base_dir=base_dir,
                output_dir=args.output_dir,
                timestamp_utc=args.timestamp_utc or _default_timestamp_utc(),
                candidate_source_root=args.candidate_source_root,
                checkpoint_path=args.checkpoint_path,
            )
        else:
            result = write_generic_loader_manifests(
                accepted_artifact_index=_load_json(base_dir / args.accepted_artifact_index),
                recovery_preflight=_load_json(base_dir / args.checkpoint_path),
                base_dir=base_dir,
                manifest_directory=args.generic_loader_manifest_dir,
                packet_path=args.generic_loader_packet,
                accepted_artifact_index_path=args.accepted_artifact_index,
                recovery_preflight_path=args.checkpoint_path,
            )
    except EVComponentOutputVerificationError as exc:
        print(str(exc))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
