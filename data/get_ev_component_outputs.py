from __future__ import annotations

import argparse
import gzip
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from typing import Any, Mapping, Sequence

import numpy as np

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
DEFAULT_PER_NODE_OUTPUT_DIR = Path("data/processed/elaad_profiles/component_outputs/per_node")
DEFAULT_PER_NODE_MANIFEST_DIR = Path("data/metadata/ev_adoption/per_node_component_output_manifests")
DEFAULT_PER_NODE_EXPORT_PREFLIGHT = Path("data/metadata/ev_adoption/e3_s2a_ev_per_node_export_preflight.json")
DEFAULT_PER_NODE_INDEX_PATH = Path("data/metadata/ev_adoption/e3_s2a_ev_per_node_manifest_index_preflight.json")
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


_FORBIDDEN_APPROVAL_TOKENS = ("future", "pending", "todo", "tbd", "placeholder", "proposed", "unsigned", "not-approved", "<", ">")


def _repo_relative_path(path: Path, *, field_name: str) -> Path:
    if path.is_absolute() or ".." in path.parts:
        raise EVComponentOutputVerificationError(f"{field_name} must be a repository-relative path")
    return path


def _validate_per_node_export_packet(generic_packet: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if generic_packet.get("artifact_type") != "ev_ic1_generic_component_output_manifest_packet":
        raise EVComponentOutputVerificationError("Per-node export requires the EV generic-loader packet")
    if generic_packet.get("status") != "blocked_ev_generic_loader_manifests_multi_node_contract":
        raise EVComponentOutputVerificationError("Per-node export expects the multi-node contract blocker packet")
    policy = generic_packet.get("policy")
    if not isinstance(policy, Mapping):
        raise EVComponentOutputVerificationError("EV generic-loader packet lacks policy flags")
    for key in ("held_out_access", "quarantined_access", "integrated_analysis_performed", "event_or_p_e_analysis_performed", "m_sufficiency_claimed"):
        if policy.get(key) is not False:
            raise EVComponentOutputVerificationError(f"Per-node export requires {key}=False")
    for key in ("decision_ids", "source_ids"):
        values = generic_packet.get(key)
        if not isinstance(values, list) or not values:
            raise EVComponentOutputVerificationError(f"EV generic-loader packet lacks {key}")
        for value in values:
            lowered = str(value).lower()
            if any(token in lowered for token in _FORBIDDEN_APPROVAL_TOKENS):
                raise EVComponentOutputVerificationError(f"Unsafe approval/source token in {key}: {value}")
    scenario_records = generic_packet.get("scenario_manifests")
    manifests_by_scenario = generic_packet.get("manifests_by_scenario")
    if not isinstance(scenario_records, list) or not isinstance(manifests_by_scenario, Mapping):
        raise EVComponentOutputVerificationError("EV generic-loader packet lacks scenario manifests")
    scenario_names = [str(row.get("scenario")) for row in scenario_records if isinstance(row, Mapping)]
    duplicates = sorted({name for name in scenario_names if scenario_names.count(name) > 1})
    if duplicates:
        raise EVComponentOutputVerificationError(f"Per-node export rejects duplicate scenario records: {', '.join(duplicates)}")
    if set(scenario_names) != {"low", "middle", "high"}:
        raise EVComponentOutputVerificationError("Per-node export requires low/middle/high scenario coverage")
    return [dict(row) for row in scenario_records if isinstance(row, Mapping)], dict(manifests_by_scenario)


def _expected_node_ids_for_scenario(manifest: Mapping[str, Any]) -> tuple[str, ...]:
    provenance = manifest.get("provenance")
    if not isinstance(provenance, Mapping):
        raise EVComponentOutputVerificationError("EV scenario manifest lacks provenance")
    node_axis = provenance.get("node_axis")
    if not isinstance(node_axis, Mapping):
        raise EVComponentOutputVerificationError("EV scenario manifest lacks node axis provenance")
    node_ids = node_axis.get("node_ids")
    if not isinstance(node_ids, list) or not node_ids:
        raise EVComponentOutputVerificationError("EV per-node export requires node IDs")
    result = tuple(str(node_id) for node_id in node_ids)
    duplicates = sorted({node_id for node_id in result if result.count(node_id) > 1})
    if duplicates:
        raise EVComponentOutputVerificationError(f"EV per-node export rejects duplicate node IDs: {', '.join(duplicates)}")
    if node_axis.get("node_count") is not None and int(node_axis["node_count"]) != len(result):
        raise EVComponentOutputVerificationError("EV node axis node_count does not match node_ids")
    return result


def _datetime64_seconds(values: np.ndarray) -> np.ndarray:
    flattened = np.asarray(values).reshape(-1)
    converted: list[np.datetime64] = []
    for value in flattened:
        text = str(value)
        if text.endswith("+00:00"):
            text = text[:-6]
        elif text.endswith("Z"):
            text = text[:-1]
        converted.append(np.datetime64(text, "s"))
    return np.asarray(converted, dtype="datetime64[s]")


def _load_verified_multi_node_ev_npz(path: Path, *, expected_node_ids: tuple[str, ...]) -> tuple[np.ndarray, np.ndarray, np.ndarray, tuple[str, ...]]:
    with np.load(path, allow_pickle=False) as data:
        for name in ("p_kw_by_node", "q_kvar_by_node", "timestamps_utc", "node_ids"):
            if name not in data.files:
                raise EVComponentOutputVerificationError(f"EV source component-output NPZ missing {name}")
        p_kw = np.asarray(data["p_kw_by_node"], dtype=float)
        q_kvar = np.asarray(data["q_kvar_by_node"], dtype=float)
        timestamps = _datetime64_seconds(np.asarray(data["timestamps_utc"]))
        node_ids = tuple(str(item) for item in np.asarray(data["node_ids"]).reshape(-1))
    if p_kw.ndim != 2 or q_kvar.ndim != 2:
        raise EVComponentOutputVerificationError("EV source component-output arrays must be two-dimensional")
    if p_kw.shape != q_kvar.shape:
        raise EVComponentOutputVerificationError("EV source p/q arrays must have identical shape")
    if p_kw.shape[1] != timestamps.size:
        raise EVComponentOutputVerificationError("EV source timestamps must match the time dimension")
    if p_kw.shape[0] != len(node_ids):
        raise EVComponentOutputVerificationError("EV source node_ids must match the node dimension")
    if not np.isfinite(p_kw).all() or not np.isfinite(q_kvar).all():
        raise EVComponentOutputVerificationError("EV source arrays must contain finite values")
    duplicates = sorted({node_id for node_id in node_ids if node_ids.count(node_id) > 1})
    if duplicates:
        raise EVComponentOutputVerificationError(f"EV source NPZ has duplicate node IDs: {', '.join(duplicates)}")
    if node_ids != expected_node_ids:
        missing = sorted(set(expected_node_ids) - set(node_ids))
        extra = sorted(set(node_ids) - set(expected_node_ids))
        raise EVComponentOutputVerificationError(
            "EV source node axis does not match the generic packet: "
            f"missing: {', '.join(missing) if missing else '--'}; extra: {', '.join(extra) if extra else '--'}"
        )
    return p_kw, q_kvar, timestamps, node_ids


def _write_deterministic_npz(path: Path, arrays: Mapping[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    with zipfile.ZipFile(tmp_path, "w") as archive:
        for name in sorted(arrays):
            buffer = io.BytesIO()
            np.save(buffer, arrays[name], allow_pickle=False)
            info = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, buffer.getvalue())
    tmp_path.replace(path)


def _per_node_checkpoint(
    *,
    status: str,
    timestamp_utc: str,
    generic_packet_path: Path,
    output_dir: Path,
    manifest_dir: Path,
    source_records: Sequence[Mapping[str, Any]],
    missing_sources: Sequence[Mapping[str, Any]],
    checksum_mismatches: Sequence[Mapping[str, Any]],
    completed_exports: Sequence[Mapping[str, Any]],
    artifact_status: str,
) -> dict[str, object]:
    return {
        "artifact_type": "ev_per_node_component_output_export_preflight",
        "artifact_id": "e3_s2a_ev_per_node_export_preflight",
        "schema_version": 1,
        "task_id": "E3.S2a",
        "status": status,
        "timestamp_utc": timestamp_utc,
        "source_generic_loader_packet": generic_packet_path.as_posix(),
        "policy": {
            "candidate_libraries_only": True,
            "held_out_access": False,
            "quarantined_access": False,
            "elaad_api_calls": False,
            "integrated_analysis_performed": False,
            "event_or_p_e_analysis_performed": False,
            "capacity_screen_performed": False,
            "final_low_middle_high_branch_selected": False,
            "m_sufficiency_claimed": False,
            "manuscript_numbers_produced": False,
            "source_multi_node_npz_sha256_verified_before_loading": True,
            "per_node_outputs_are_one_dimensional": True,
        },
        "artifact_status_for_written_manifests": artifact_status,
        "required_source_component_outputs": list(source_records),
        "missing_source_component_outputs": list(missing_sources),
        "source_checksum_mismatches": list(checksum_mismatches),
        "completed_per_node_exports": list(completed_exports),
        "completed_per_node_export_count": len(completed_exports),
        "output_directory": output_dir.as_posix(),
        "manifest_directory": manifest_dir.as_posix(),
        "checkpoint": {
            "complete": status in {"blocked_missing_source_component_outputs", "blocked_source_component_output_checksum_mismatch", "per_node_exports_written_scaffold"},
            "work_unit": "one scenario/node per exported NPZ and manifest",
            "resume_command": (
                ".\\.venv\\Scripts\\python.exe data\\get_ev_component_outputs.py export-per-node "
                "--generic-loader-packet data\\metadata\\ev_adoption\\e3_s2a_ev_ic1_generic_component_output_manifest_packet.json "
                "--checkpoint-path data\\metadata\\ev_adoption\\e3_s2a_ev_per_node_export_preflight.json"
            ),
            "safe_resume_behavior": "Existing per-node outputs are skipped only when their manifest and file checksum agree with the current source checksum.",
        },
        "remaining_blockers": [
            "E3.S2a-EV-HELD-OUT-ADEQUACY-NOT-RUN",
            "EV-005-M-SUFFICIENCY-NOT-CERTIFIED",
            "G5-FINAL-LOW-MIDDLE-HIGH-BRANCH-NOT-SELECTED",
            "IC-1-INTEGRATED-NET-LOAD-ASSEMBLY-NOT-RUN",
            "A-016-CROSS-COMPONENT-SCENARIO-CONSISTENCY-NOT-YET-CHECKED",
        ],
    }


def export_ev_per_node_component_outputs(
    *,
    generic_packet: Mapping[str, Any],
    base_dir: Path,
    generic_packet_path: Path = DEFAULT_GENERIC_LOADER_PACKET,
    output_dir: Path = DEFAULT_PER_NODE_OUTPUT_DIR,
    manifest_dir: Path = DEFAULT_PER_NODE_MANIFEST_DIR,
    checkpoint_path: Path | None = DEFAULT_PER_NODE_EXPORT_PREFLIGHT,
    timestamp_utc: str,
    artifact_status: str = "scaffold",
    allow_accepted_status: bool = False,
    scenario_filter: Sequence[str] | None = None,
    node_filter: Sequence[str] | None = None,
) -> dict[str, object]:
    """Split verified multi-node EV component-output NPZs into one-node artifacts."""

    if artifact_status == "accepted" and not allow_accepted_status:
        raise EVComponentOutputVerificationError("accepted EV per-node artifacts require a future signed executable approval")
    if artifact_status not in {"scaffold", "synthetic_fixture", "accepted"}:
        raise EVComponentOutputVerificationError("EV per-node artifact_status must be scaffold, synthetic_fixture, or accepted")
    if any(token in artifact_status.lower() for token in _FORBIDDEN_APPROVAL_TOKENS):
        raise EVComponentOutputVerificationError("EV per-node artifact_status contains an unsafe approval token")

    scenario_records, manifests_by_scenario = _validate_per_node_export_packet(generic_packet)
    wanted_scenarios = set(scenario_filter or [str(row["scenario"]) for row in scenario_records])
    wanted_nodes = set(node_filter or [])
    base_dir = Path(base_dir).resolve()
    output_dir = _repo_relative_path(Path(output_dir), field_name="output_dir")
    manifest_dir = _repo_relative_path(Path(manifest_dir), field_name="manifest_dir")
    generic_packet_path = _repo_relative_path(Path(generic_packet_path), field_name="generic_packet_path")
    if checkpoint_path is not None:
        checkpoint_path = _repo_relative_path(Path(checkpoint_path), field_name="checkpoint_path")

    source_records: list[dict[str, Any]] = []
    missing_sources: list[dict[str, Any]] = []
    checksum_mismatches: list[dict[str, Any]] = []
    completed: list[dict[str, Any]] = []

    for record in sorted(scenario_records, key=lambda item: str(item["scenario"])):
        scenario = str(record["scenario"])
        if scenario not in wanted_scenarios:
            continue
        expected_sha = str(record.get("array_sha256", ""))
        source_rel = _repo_relative_path(Path(str(record.get("array_path", ""))), field_name="array_path")
        source_info = {"scenario": scenario, "path": source_rel.as_posix(), "sha256": expected_sha}
        source_records.append(source_info)
        source_path = base_dir / source_rel
        if not source_path.is_file():
            missing_sources.append({**source_info, "failure": "missing_ignored_source_npz"})
            continue
        observed_sha = _sha256_file(source_path)
        if observed_sha != expected_sha:
            checksum_mismatches.append({**source_info, "observed_sha256": observed_sha, "failure": "source_checksum_mismatch"})
            continue

    if missing_sources or checksum_mismatches:
        status = "blocked_missing_source_component_outputs" if missing_sources else "blocked_source_component_output_checksum_mismatch"
        payload = _per_node_checkpoint(
            status=status,
            timestamp_utc=timestamp_utc,
            generic_packet_path=generic_packet_path,
            output_dir=output_dir,
            manifest_dir=manifest_dir,
            source_records=source_records,
            missing_sources=missing_sources,
            checksum_mismatches=checksum_mismatches,
            completed_exports=completed,
            artifact_status=artifact_status,
        )
        if checkpoint_path is not None:
            _write_json(base_dir / checkpoint_path, payload)
        return payload

    for record in sorted(scenario_records, key=lambda item: str(item["scenario"])):
        scenario = str(record["scenario"])
        if scenario not in wanted_scenarios:
            continue
        scenario_manifest = manifests_by_scenario.get(scenario)
        if not isinstance(scenario_manifest, Mapping):
            raise EVComponentOutputVerificationError(f"Missing scenario manifest for {scenario}")
        expected_node_ids = _expected_node_ids_for_scenario(scenario_manifest)
        source_rel = Path(str(record["array_path"]))
        source_sha = str(record["array_sha256"])
        p_kw, q_kvar, timestamps, node_ids = _load_verified_multi_node_ev_npz(base_dir / source_rel, expected_node_ids=expected_node_ids)
        for row_index, node_id in enumerate(node_ids):
            if wanted_nodes and node_id not in wanted_nodes:
                continue
            output_rel = output_dir / f"ev_ic1_candidate_component_output_{scenario}_{node_id}.npz"
            manifest_rel = manifest_dir / f"ev_2035_{scenario}_{node_id}.json"
            if (base_dir / output_rel).is_file() and (base_dir / manifest_rel).is_file():
                existing_manifest = _load_json(base_dir / manifest_rel)
                existing_sha = _sha256_file(base_dir / output_rel)
                if existing_manifest.get("array_sha256") == existing_sha and existing_manifest.get("provenance", {}).get("source_multi_node_sha256") == source_sha:
                    completed.append({"scenario": scenario, "node_id": node_id, "path": output_rel.as_posix(), "sha256": existing_sha, "skipped_existing_verified": True})
                    continue
                raise EVComponentOutputVerificationError(f"Existing per-node EV output is not a verified checkpoint: {output_rel.as_posix()}")
            artifact_id = f"e3_s2a_ev_ic1_per_node_component_output_2035_{scenario}_{node_id}"
            component_id = f"ev_component_output_2035_{scenario}_{node_id}"
            member_id = f"ev005b_root20260722_sample0_{scenario}_{node_id}"
            source_id = str(scenario_manifest.get("source_id", "D-002_D-010_D-012"))
            calendar_id = str(scenario_manifest.get("calendar_id", "planning-2035-europe-amsterdam-15min"))
            arrays = {
                "artifact_id": np.asarray(artifact_id),
                "component_id": np.asarray(component_id),
                "kind": np.asarray("ev"),
                "node_id": np.asarray(node_id),
                "member_id": np.asarray(member_id),
                "source_id": np.asarray(source_id),
                "calendar_id": np.asarray(calendar_id),
                "timestep_seconds": np.asarray("900"),
                "p_kw": np.asarray(p_kw[row_index], dtype=np.float64),
                "q_kvar": np.asarray(q_kvar[row_index], dtype=np.float64),
                "timestamps": timestamps,
            }
            _write_deterministic_npz(base_dir / output_rel, arrays)
            output_sha = _sha256_file(base_dir / output_rel)
            manifest = {
                "artifact_id": artifact_id,
                "artifact_status": artifact_status,
                "kind": "ev",
                "component_id": component_id,
                "node_id": node_id,
                "member_id": member_id,
                "source_id": source_id,
                "calendar_id": calendar_id,
                "timestep_seconds": 900,
                "timestep_count": int(timestamps.size),
                "array_path": output_rel.as_posix(),
                "array_sha256": output_sha,
                "loader_contract": "single_node_1d_component_output_v1",
                "node_axis_contract": "single_manifest_single_node",
                "array_shape_contract": "p_kw_q_kvar_timestamps_1d_same_length",
                "provenance": {
                    "artifact_type": "ev_per_node_component_output_manifest",
                    "scenario": scenario,
                    "node_id": node_id,
                    "candidate_only": True,
                    "held_out_access": False,
                    "quarantined_access": False,
                    "source_multi_node_path": source_rel.as_posix(),
                    "source_multi_node_sha256": source_sha,
                    "source_row_index": row_index,
                    "calendar_mapping": scenario_manifest.get("provenance", {}).get("calendar_mapping"),
                    "a014_allocation_provenance": scenario_manifest.get("provenance", {}).get("a014_allocation_provenance"),
                    "selection_manifest_provenance": scenario_manifest.get("provenance", {}).get("selection_manifest_provenance"),
                    "remaining_blockers": scenario_manifest.get("provenance", {}).get("remaining_blockers"),
                    "not_a_net_load_result": True,
                    "event_or_p_e_analysis_performed": False,
                    "m_sufficiency_claimed": False,
                },
            }
            _write_json(base_dir / manifest_rel, manifest)
            manifest_sha = _sha256_file(base_dir / manifest_rel)
            completed.append({"scenario": scenario, "node_id": node_id, "path": output_rel.as_posix(), "sha256": output_sha, "manifest_path": manifest_rel.as_posix(), "manifest_sha256": manifest_sha})
            if checkpoint_path is not None:
                _write_json(
                    base_dir / checkpoint_path,
                    _per_node_checkpoint(
                        status="per_node_export_in_progress",
                        timestamp_utc=timestamp_utc,
                        generic_packet_path=generic_packet_path,
                        output_dir=output_dir,
                        manifest_dir=manifest_dir,
                        source_records=source_records,
                        missing_sources=missing_sources,
                        checksum_mismatches=checksum_mismatches,
                        completed_exports=completed,
                        artifact_status=artifact_status,
                    ),
                )

    status = "per_node_exports_written_scaffold"
    payload = _per_node_checkpoint(
        status=status,
        timestamp_utc=timestamp_utc,
        generic_packet_path=generic_packet_path,
        output_dir=output_dir,
        manifest_dir=manifest_dir,
        source_records=source_records,
        missing_sources=missing_sources,
        checksum_mismatches=checksum_mismatches,
        completed_exports=completed,
        artifact_status=artifact_status,
    )
    if checkpoint_path is not None:
        _write_json(base_dir / checkpoint_path, payload)
    return payload


_REQUIRED_PER_NODE_MANIFEST_KEYS = (
    "artifact_id",
    "artifact_status",
    "kind",
    "component_id",
    "node_id",
    "member_id",
    "source_id",
    "calendar_id",
    "timestep_seconds",
    "array_path",
    "array_sha256",
    "loader_contract",
    "node_axis_contract",
    "array_shape_contract",
    "provenance",
)
_EXPECTED_PER_NODE_LOADER_CONTRACT = {
    "loader_contract": "single_node_1d_component_output_v1",
    "node_axis_contract": "single_manifest_single_node",
    "array_shape_contract": "p_kw_q_kvar_timestamps_1d_same_length",
}
_PER_NODE_INDEX_BLOCKERS = [
    "E3.S2a-EV-HELD-OUT-ADEQUACY-NOT-RUN",
    "EV-005-M-SUFFICIENCY-NOT-CERTIFIED",
    "G5-FINAL-LOW-MIDDLE-HIGH-BRANCH-NOT-SELECTED",
    "IC-1-INTEGRATED-NET-LOAD-ASSEMBLY-NOT-RUN",
    "A-016-CROSS-COMPONENT-SCENARIO-CONSISTENCY-NOT-YET-CHECKED",
]


def _contains_blocked_path_token(path: str) -> bool:
    lowered = path.lower().replace("\\", "/")
    return any(token in lowered for token in ("held_out", "held-out", "quarantined", "data/raw/", "generic_component_output_manifests"))


def _unsafe_manifest_token_fields(manifest: Mapping[str, Any]) -> tuple[str, ...]:
    unsafe: list[str] = []
    for field in ("artifact_status", "artifact_id", "component_id", "member_id", "source_id", "calendar_id", "array_path"):
        value = manifest.get(field)
        if value is None:
            continue
        lowered = str(value).lower()
        if any(token in lowered for token in _FORBIDDEN_APPROVAL_TOKENS):
            unsafe.append(field)
    return tuple(sorted(set(unsafe)))


def _expected_per_node_units(
    generic_packet: Mapping[str, Any],
    *,
    output_dir: Path,
    manifest_dir: Path,
    scenario_filter: Sequence[str] | None,
    node_filter: Sequence[str] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    scenario_records, manifests_by_scenario = _validate_per_node_export_packet(generic_packet)
    policy = generic_packet.get("policy")
    if not isinstance(policy, Mapping):
        raise EVComponentOutputVerificationError("EV generic-loader packet lacks policy flags")
    for key in (
        "held_out_access",
        "quarantined_access",
        "integrated_analysis_performed",
        "event_or_p_e_analysis_performed",
        "capacity_screen_performed",
        "final_low_middle_high_branch_selected",
        "m_sufficiency_claimed",
        "manuscript_numbers_produced",
    ):
        if policy.get(key) is not False:
            raise EVComponentOutputVerificationError(f"Per-node manifest index requires {key}=False")
    if policy.get("elaad_api_calls", False) is not False:
        raise EVComponentOutputVerificationError("Per-node manifest index requires elaad_api_calls=False")
    output_dir = _repo_relative_path(Path(output_dir), field_name="output_dir")
    manifest_dir = _repo_relative_path(Path(manifest_dir), field_name="manifest_dir")
    wanted_scenarios = set(scenario_filter or [str(row["scenario"]) for row in scenario_records])
    wanted_nodes = set(node_filter or [])
    if not wanted_scenarios:
        raise EVComponentOutputVerificationError("Per-node manifest index requires at least one scenario")
    units: list[dict[str, Any]] = []
    for record in sorted(scenario_records, key=lambda item: str(item["scenario"])):
        scenario = str(record["scenario"])
        if scenario not in wanted_scenarios:
            continue
        scenario_manifest = manifests_by_scenario.get(scenario)
        if not isinstance(scenario_manifest, Mapping):
            raise EVComponentOutputVerificationError(f"Missing scenario manifest for {scenario}")
        source_rel = _repo_relative_path(Path(str(record.get("array_path", ""))), field_name="array_path")
        if _contains_blocked_path_token(source_rel.as_posix()):
            raise EVComponentOutputVerificationError("Per-node manifest index rejects held-out/quarantined/raw/generic source paths")
        for node_id in _expected_node_ids_for_scenario(scenario_manifest):
            if wanted_nodes and node_id not in wanted_nodes:
                continue
            units.append(
                {
                    "scenario": scenario,
                    "node_id": node_id,
                    "manifest_path": (manifest_dir / f"ev_2035_{scenario}_{node_id}.json").as_posix(),
                    "array_path": (output_dir / f"ev_ic1_candidate_component_output_{scenario}_{node_id}.npz").as_posix(),
                    "source_multi_node_path": source_rel.as_posix(),
                    "source_multi_node_sha256": str(record.get("array_sha256", "")),
                }
            )
    if not units:
        raise EVComponentOutputVerificationError("Per-node manifest index selected no scenario/node units")
    pairs = [(str(unit["scenario"]), str(unit["node_id"])) for unit in units]
    duplicates = sorted({pair for pair in pairs if pairs.count(pair) > 1})
    if duplicates:
        labels = ", ".join(f"{scenario}/{node_id}" for scenario, node_id in duplicates)
        raise EVComponentOutputVerificationError(f"Per-node manifest index rejects duplicate scenario/node units: {labels}")
    scenario_order = tuple(dict.fromkeys(str(unit["scenario"]) for unit in units))
    node_order = tuple(dict.fromkeys(str(unit["node_id"]) for unit in units))
    return units, {"scenario_order": scenario_order, "node_order": node_order}


def _validate_per_node_manifest_for_index(
    manifest: Mapping[str, Any],
    *,
    expected: Mapping[str, Any],
    artifact_status: str,
    allow_synthetic_fixture: bool,
) -> list[str]:
    blockers: list[str] = []
    missing_keys = [key for key in _REQUIRED_PER_NODE_MANIFEST_KEYS if key not in manifest]
    if missing_keys:
        blockers.append("manifest_required_keys_missing")
    if manifest.get("kind") != "ev":
        blockers.append("manifest_kind_not_ev")
    if manifest.get("node_id") != expected["node_id"]:
        blockers.append("manifest_node_id_mismatch")
    if manifest.get("array_path") != expected["array_path"]:
        blockers.append("manifest_array_path_mismatch")
    if manifest.get("artifact_status") != artifact_status:
        blockers.append("manifest_artifact_status_not_allowed")
    if artifact_status == "synthetic_fixture" and not allow_synthetic_fixture:
        blockers.append("synthetic_fixture_not_allowed")
    if artifact_status == "accepted" and allow_synthetic_fixture:
        blockers.append("accepted_status_not_expected_for_synthetic_fixture")
    if artifact_status not in {"accepted", "synthetic_fixture"}:
        blockers.append("manifest_artifact_status_not_accepted")
    for key, value in _EXPECTED_PER_NODE_LOADER_CONTRACT.items():
        if manifest.get(key) != value:
            blockers.append(f"{key}_mismatch")
    unsafe_fields = _unsafe_manifest_token_fields(manifest)
    if unsafe_fields:
        blockers.append("manifest_unsafe_token")
    array_path = str(manifest.get("array_path", ""))
    try:
        _repo_relative_path(Path(array_path), field_name="array_path")
    except EVComponentOutputVerificationError:
        blockers.append("manifest_array_path_not_repository_relative")
    if _contains_blocked_path_token(array_path):
        blockers.append("manifest_array_path_forbidden")
    provenance = manifest.get("provenance")
    if not isinstance(provenance, Mapping):
        blockers.append("manifest_provenance_missing")
        return blockers
    for key in ("held_out_access", "quarantined_access", "event_or_p_e_analysis_performed", "m_sufficiency_claimed"):
        if provenance.get(key) is not False:
            blockers.append(f"manifest_{key}_not_false")
    if provenance.get("candidate_only") is not True:
        blockers.append("manifest_candidate_only_not_true")
    if provenance.get("source_multi_node_path") != expected["source_multi_node_path"]:
        blockers.append("manifest_source_multi_node_path_mismatch")
    if provenance.get("source_multi_node_sha256") != expected["source_multi_node_sha256"]:
        blockers.append("manifest_source_multi_node_sha256_mismatch")
    return blockers


def build_ev_per_node_manifest_index(
    *,
    generic_packet: Mapping[str, Any],
    base_dir: Path,
    generic_packet_path: Path = DEFAULT_GENERIC_LOADER_PACKET,
    output_dir: Path = DEFAULT_PER_NODE_OUTPUT_DIR,
    manifest_dir: Path = DEFAULT_PER_NODE_MANIFEST_DIR,
    index_path: Path | None = DEFAULT_PER_NODE_INDEX_PATH,
    timestamp_utc: str,
    scenario_filter: Sequence[str] | None = None,
    node_filter: Sequence[str] | None = None,
    require_accepted_status: bool = True,
    allow_synthetic_fixture: bool = False,
) -> dict[str, object]:
    """Build a fail-closed index over loadable one-node EV component artifacts."""

    base_dir = Path(base_dir).resolve()
    generic_packet_path = _repo_relative_path(Path(generic_packet_path), field_name="generic_packet_path")
    output_dir = _repo_relative_path(Path(output_dir), field_name="output_dir")
    manifest_dir = _repo_relative_path(Path(manifest_dir), field_name="manifest_dir")
    if index_path is not None:
        index_path = _repo_relative_path(Path(index_path), field_name="index_path")
    filtered_scope = scenario_filter is not None or node_filter is not None
    expected_units, ordering = _expected_per_node_units(
        generic_packet,
        output_dir=output_dir,
        manifest_dir=manifest_dir,
        scenario_filter=scenario_filter,
        node_filter=node_filter,
    )
    accepted_status = "synthetic_fixture" if allow_synthetic_fixture and not require_accepted_status else "accepted"
    verified: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    checksum_mismatches: list[dict[str, Any]] = []
    for unit in expected_units:
        manifest_path = base_dir / str(unit["manifest_path"])
        array_path = base_dir / str(unit["array_path"])
        if not manifest_path.is_file() or not array_path.is_file():
            missing.append(
                {
                    "scenario": unit["scenario"],
                    "node_id": unit["node_id"],
                    "manifest_path": unit["manifest_path"],
                    "array_path": unit["array_path"],
                    "missing_manifest": not manifest_path.is_file(),
                    "missing_array": not array_path.is_file(),
                }
            )
            continue
        manifest = _load_json(manifest_path)
        blockers = _validate_per_node_manifest_for_index(
            manifest,
            expected=unit,
            artifact_status=accepted_status,
            allow_synthetic_fixture=allow_synthetic_fixture,
        )
        observed_array_sha = _sha256_file(array_path)
        manifest_array_sha = str(manifest.get("array_sha256", ""))
        if manifest_array_sha != observed_array_sha:
            checksum_mismatches.append(
                {
                    "scenario": unit["scenario"],
                    "node_id": unit["node_id"],
                    "path": unit["array_path"],
                    "expected_sha256": manifest_array_sha,
                    "observed_sha256": observed_array_sha,
                }
            )
            blockers.append("array_checksum_mismatch")
        manifest_sha = _sha256_file(manifest_path)
        record = {
            "scenario": unit["scenario"],
            "node_id": unit["node_id"],
            "manifest_path": unit["manifest_path"],
            "manifest_sha256": manifest_sha,
            "array_path": unit["array_path"],
            "array_sha256": observed_array_sha,
            "artifact_status": manifest.get("artifact_status"),
            "loader_contract": manifest.get("loader_contract"),
            "node_axis_contract": manifest.get("node_axis_contract"),
            "array_shape_contract": manifest.get("array_shape_contract"),
        }
        if blockers:
            stale.append({**record, "blockers": sorted(set(blockers))})
        else:
            verified.append(record)
    structurally_ready = not missing and not stale and not checksum_mismatches
    real_loader_ready = bool(structurally_ready and not allow_synthetic_fixture and not filtered_scope)
    synthetic_fixture_ready = bool(structurally_ready and allow_synthetic_fixture)
    status = (
        "synthetic_per_node_manifest_index_ready_for_agent_a_loader_fixture"
        if synthetic_fixture_ready
        else "accepted_per_node_manifest_index_ready_for_agent_a_loader"
        if real_loader_ready
        else "blocked_filtered_per_node_manifest_index_not_real_loader_ready"
        if structurally_ready and filtered_scope
        else "blocked_per_node_manifest_index_not_ready_for_agent_a_loader"
    )
    by_scenario: dict[str, dict[str, Any]] = {}
    for record in verified:
        scenario = str(record["scenario"])
        by_scenario.setdefault(
            scenario,
            {
                "scenario": scenario,
                "node_ids": [],
                "component_output_manifest_paths": [],
                "component_output_manifest_sha256_by_path": {},
            },
        )
        by_scenario[scenario]["node_ids"].append(record["node_id"])
        by_scenario[scenario]["component_output_manifest_paths"].append(record["manifest_path"])
        by_scenario[scenario]["component_output_manifest_sha256_by_path"][record["manifest_path"]] = record["manifest_sha256"]
    payload: dict[str, object] = {
        "artifact_type": "ev_per_node_component_output_manifest_index_preflight",
        "artifact_id": "e3_s2a_ev_per_node_manifest_index_preflight",
        "schema_version": 1,
        "task_id": "E3.S2a",
        "status": status,
        "timestamp_utc": timestamp_utc,
        "ready_for_agent_a_loader_execution": real_loader_ready,
        "ready_for_synthetic_agent_a_loader_fixture": synthetic_fixture_ready,
        "index_scope": {
            "full_declared_scope": not filtered_scope,
            "filtered_scope": filtered_scope,
            "scenario_filter": list(scenario_filter) if scenario_filter is not None else None,
            "node_filter": list(node_filter) if node_filter is not None else None,
            "real_loader_ready_requires_full_declared_scope": True,
        },
        "source_generic_loader_packet": generic_packet_path.as_posix(),
        "source_generic_loader_packet_sha256": _repo_blob_or_file_sha256(base_dir, generic_packet_path),
        "policy": {
            "candidate_libraries_only": True,
            "held_out_access": False,
            "quarantined_access": False,
            "elaad_api_calls": False,
            "integrated_analysis_performed": False,
            "event_or_p_e_analysis_performed": False,
            "capacity_screen_performed": False,
            "final_low_middle_high_branch_selected": False,
            "m_sufficiency_claimed": False,
            "manuscript_numbers_produced": False,
            "requires_accepted_per_node_artifacts_for_real_loader_execution": True,
        },
        "expected_per_node_unit_count": len(expected_units),
        "verified_per_node_unit_count": len(verified),
        "missing_per_node_unit_count": len(missing),
        "stale_per_node_unit_count": len(stale),
        "checksum_mismatch_count": len(checksum_mismatches),
        "scenario_order": list(ordering["scenario_order"]),
        "node_order": list(ordering["node_order"]),
        "expected_per_node_units": expected_units,
        "verified_per_node_units": verified,
        "missing_per_node_units": missing,
        "stale_per_node_units": stale,
        "checksum_mismatches": checksum_mismatches,
        "agent_a_loader_index_by_scenario": [by_scenario[key] for key in sorted(by_scenario)],
        "checkpoint": {
            "complete": True,
            "resume_command": (
                ".\\.venv\\Scripts\\python.exe data\\get_ev_component_outputs.py write-per-node-index "
                "--generic-loader-packet data\\metadata\\ev_adoption\\e3_s2a_ev_ic1_generic_component_output_manifest_packet.json "
                "--per-node-index-path data\\metadata\\ev_adoption\\e3_s2a_ev_per_node_manifest_index_preflight.json"
            ),
            "safe_resume_behavior": "Rerun rehashes every present per-node manifest and NPZ; missing/stale units remain blockers.",
        },
        "remaining_blockers": (
            []
            if real_loader_ready or synthetic_fixture_ready
            else ["E3.S2a-FILTERED-INDEX-NOT-REAL-LOADER-READY", *_PER_NODE_INDEX_BLOCKERS]
            if structurally_ready and filtered_scope
            else list(_PER_NODE_INDEX_BLOCKERS)
        ),
    }
    if index_path is not None:
        _write_json(base_dir / index_path, payload)
    return payload


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
    parser.add_argument("mode", choices=("verify", "rebuild", "write-loader-manifests", "export-per-node", "write-per-node-index"))
    parser.add_argument("--base-dir", type=Path, default=Path("."))
    parser.add_argument("--component-input-scaffold", type=Path, default=DEFAULT_COMPONENT_INPUT_SCAFFOLD)
    parser.add_argument("--checksum-preflight", type=Path, default=DEFAULT_CHECKSUM_PREFLIGHT)
    parser.add_argument("--selection-manifest-set", type=Path, default=DEFAULT_SELECTION_MANIFEST_SET)
    parser.add_argument("--component-output-manifest", type=Path, default=DEFAULT_COMPONENT_OUTPUT_MANIFEST)
    parser.add_argument("--accepted-artifact-index", type=Path, default=DEFAULT_ACCEPTED_ARTIFACT_INDEX)
    parser.add_argument("--generic-loader-manifest-dir", type=Path, default=DEFAULT_GENERIC_LOADER_MANIFEST_DIR)
    parser.add_argument("--generic-loader-packet", type=Path, default=DEFAULT_GENERIC_LOADER_PACKET)
    parser.add_argument("--per-node-output-dir", type=Path, default=DEFAULT_PER_NODE_OUTPUT_DIR)
    parser.add_argument("--per-node-manifest-dir", type=Path, default=DEFAULT_PER_NODE_MANIFEST_DIR)
    parser.add_argument("--per-node-artifact-status", default="scaffold")
    parser.add_argument("--allow-accepted-per-node-status", action="store_true")
    parser.add_argument("--per-node-index-path", type=Path, default=DEFAULT_PER_NODE_INDEX_PATH)
    parser.add_argument("--allow-synthetic-per-node-index", action="store_true")
    parser.add_argument("--allow-nonaccepted-per-node-index", action="store_true")
    parser.add_argument("--scenario", action="append", dest="scenarios", default=None)
    parser.add_argument("--node-id", action="append", dest="node_ids", default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--candidate-source-root", type=Path, default=None)
    parser.add_argument("--checkpoint-path", type=Path, default=DEFAULT_RECOVERY_CHECKPOINT)
    parser.add_argument("--timestamp-utc", default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    base_dir = args.base_dir.resolve()
    checkpoint_path = args.checkpoint_path
    if args.mode == "export-per-node" and checkpoint_path == DEFAULT_RECOVERY_CHECKPOINT:
        checkpoint_path = DEFAULT_PER_NODE_EXPORT_PREFLIGHT
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
                checkpoint_path=checkpoint_path,
            )
        elif args.mode == "write-loader-manifests":
            result = write_generic_loader_manifests(
                accepted_artifact_index=_load_json(base_dir / args.accepted_artifact_index),
                recovery_preflight=_load_json(base_dir / checkpoint_path),
                base_dir=base_dir,
                manifest_directory=args.generic_loader_manifest_dir,
                packet_path=args.generic_loader_packet,
                accepted_artifact_index_path=args.accepted_artifact_index,
                recovery_preflight_path=checkpoint_path,
            )
        elif args.mode == "export-per-node":
            result = export_ev_per_node_component_outputs(
                generic_packet=_load_json(base_dir / args.generic_loader_packet),
                base_dir=base_dir,
                generic_packet_path=args.generic_loader_packet,
                output_dir=args.per_node_output_dir,
                manifest_dir=args.per_node_manifest_dir,
                checkpoint_path=checkpoint_path,
                timestamp_utc=args.timestamp_utc or _default_timestamp_utc(),
                artifact_status=args.per_node_artifact_status,
                allow_accepted_status=args.allow_accepted_per_node_status,
                scenario_filter=args.scenarios,
                node_filter=args.node_ids,
            )
        else:
            result = build_ev_per_node_manifest_index(
                generic_packet=_load_json(base_dir / args.generic_loader_packet),
                base_dir=base_dir,
                generic_packet_path=args.generic_loader_packet,
                output_dir=args.per_node_output_dir,
                manifest_dir=args.per_node_manifest_dir,
                index_path=args.per_node_index_path,
                timestamp_utc=args.timestamp_utc or _default_timestamp_utc(),
                scenario_filter=args.scenarios,
                node_filter=args.node_ids,
                require_accepted_status=not args.allow_nonaccepted_per_node_index,
                allow_synthetic_fixture=args.allow_synthetic_per_node_index,
            )
    except EVComponentOutputVerificationError as exc:
        print(str(exc))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
