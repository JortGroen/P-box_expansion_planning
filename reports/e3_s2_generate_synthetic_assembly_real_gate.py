"""Generate the E3.S2 synthetic IC-1 assembly and real-input gate packet.

This generator creates tiny synthetic fixture arrays, proves the IC-1 assembly
contract on those fixtures, and runs the fail-closed real-project input gate
against committed metadata packets. It never opens real component arrays and
never invokes IC-2/event/probability/capacity-screen logic.
"""

from __future__ import annotations

import hashlib
import importlib.metadata as importlib_metadata
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.contracts.loading_trajectory import LoadingTrajectoryPreRunConfig
from src.contracts.net_load import (
    ExecutableInputArtifact,
    FutureLayerScreenPreflightConfig,
    NetLoadAssemblyPlan,
    build_realization_context,
    build_synthetic_ic1_assembly_and_real_input_gate,
)

INPUT_PATH = Path("reports/e3_s2_synthetic_assembly_real_gate_input.json")
BASE_INPUT_PATH = Path("reports/e3_s2_accepted_artifact_blocker_preflight_input.json")
MANIFEST_PATH = Path("reports/e3_s2_synthetic_assembly_real_gate_manifest.json")
REPORT_PATH = Path("reports/E3_S2_SYNTHETIC_ASSEMBLY_REAL_GATE.md")
FIXTURE_DIR = Path("reports/e3_s2_synthetic_assembly_real_gate_fixtures")
COMMAND = ".\\.venv\\Scripts\\python.exe reports\\e3_s2_generate_synthetic_assembly_real_gate.py"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def package_version(name: str) -> str:
    try:
        return importlib_metadata.version(name)
    except importlib_metadata.PackageNotFoundError:
        return "not-installed"


def _repo_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        raise ValueError("packet paths must be repository-relative")
    resolved = (REPO_ROOT / candidate).resolve()
    try:
        resolved.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise ValueError("packet paths must stay inside the repository") from exc
    return resolved


def _compute_existing_checksums(paths: Sequence[str]) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for path in paths:
        resolved = _repo_path(path)
        if resolved.is_file():
            checksums[path] = sha256(resolved)
    return checksums


def _write_synthetic_fixture_artifacts(
    payload: Mapping[str, Any],
    *,
    context_weather_id: str,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    fixture_dir = REPO_ROOT / FIXTURE_DIR
    fixture_dir.mkdir(parents=True, exist_ok=True)
    timestamps = np.array(payload["synthetic_fixture"]["timestamps"], dtype="datetime64[s]")
    manifest_records: list[dict[str, object]] = []
    output_records: list[dict[str, object]] = []
    for component in payload["synthetic_fixture"]["components"]:
        kind = str(component["kind"])
        component_id = str(component["component_id"])
        node_id = str(component["node_id"])
        member_id = str(component["member_id"])
        source_id = str(component["source_id"])
        shared_weather_driver_id = context_weather_id if kind in {"hp", "pv"} else None
        array_path = fixture_dir / f"{kind}.npz"
        arrays: dict[str, object] = {
            "p_kw": np.array(component["p_kw"], dtype=float),
            "q_kvar": np.array(component["q_kvar"], dtype=float),
            "timestamps": timestamps,
            "artifact_id": f"{component_id}-synthetic-array",
            "component_id": component_id,
            "kind": kind,
            "node_id": node_id,
            "member_id": member_id,
            "source_id": source_id,
            "calendar_id": payload["synthetic_fixture"]["calendar_id"],
            "timestep_seconds": "900",
        }
        if shared_weather_driver_id is not None:
            arrays["shared_weather_driver_id"] = shared_weather_driver_id
        np.savez(array_path, **arrays)
        array_relative = array_path.relative_to(REPO_ROOT).as_posix()
        array_sha = sha256(array_path)
        manifest = {
            "artifact_id": f"{component_id}-synthetic-array",
            "kind": kind,
            "artifact_status": "synthetic_fixture",
            "component_id": component_id,
            "node_id": node_id,
            "member_id": member_id,
            "source_id": source_id,
            "calendar_id": payload["synthetic_fixture"]["calendar_id"],
            "timestep_seconds": 900,
            "timestep_count": int(timestamps.size),
            "array_path": array_relative,
            "array_sha256": array_sha,
            "provenance": {
                "fixture_id": payload["synthetic_fixture"]["fixture_id"],
                "synthetic_fixture_only": True,
                "not_a_scientific_result": True,
            },
        }
        if shared_weather_driver_id is not None:
            manifest["shared_weather_driver_id"] = shared_weather_driver_id
        manifest_path = fixture_dir / f"{kind}_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        manifest_records.append(manifest)
        output_records.append(
            {
                "kind": kind,
                "component_id": component_id,
                "node_id": node_id,
                "array_path": array_relative,
                "array_sha256": array_sha,
                "manifest_path": manifest_path.relative_to(REPO_ROOT).as_posix(),
                "manifest_sha256": sha256(manifest_path),
            }
        )
    return manifest_records, output_records


def _component_rows(blocker_manifest: Mapping[str, Any]) -> str:
    rows: list[str] = []
    for item in blocker_manifest["items"]:
        rows.append(
            "| {kind} | {code} | {blockers} | {path} |".format(
                kind=item.get("kind", "cross-cutting"),
                code=item["code"],
                blockers=", ".join(item.get("blocker_ids", ())) or "--",
                path=item.get("path", "--"),
            )
        )
    return "\n".join(rows) or "| none | none | -- | -- |"


def _fixture_rows(records: Sequence[Mapping[str, object]]) -> str:
    return "\n".join(
        "| {kind} | {component_id} | {node_id} | synthetic_fixture | {array_path} | {array_sha256} |".format(
            **record
        )
        for record in records
    )


def _artifact_paths(base_payload: Mapping[str, Any]) -> tuple[str, ...]:
    paths: list[str] = []
    for artifact in base_payload["artifacts"]:
        if artifact.get("manifest_path"):
            paths.append(str(artifact["manifest_path"]))
    return tuple(paths)


def _build_dossier(payload: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, object]]]:
    base_payload = json.loads(BASE_INPUT_PATH.read_text(encoding="utf-8"))
    context = build_realization_context(**payload["synthetic_context"])
    fixture_manifests, fixture_records = _write_synthetic_fixture_artifacts(
        payload,
        context_weather_id=context.shared_weather_driver_id,
    )
    real_config = FutureLayerScreenPreflightConfig(**base_payload["config"])
    trajectory_config = LoadingTrajectoryPreRunConfig(**base_payload["trajectory_config"])
    real_artifacts = tuple(ExecutableInputArtifact(**record) for record in base_payload["artifacts"])
    source_checksums = _compute_existing_checksums(_artifact_paths(base_payload))
    component_manifest_paths = dict(base_payload.get("component_output_manifest_paths_by_kind", {}))
    component_manifest_checksums = _compute_existing_checksums(tuple(component_manifest_paths.values()))
    dossier = build_synthetic_ic1_assembly_and_real_input_gate(
        assembly_id=payload["assembly_id"],
        plan=NetLoadAssemblyPlan(**payload["synthetic_plan"]),
        context=context,
        synthetic_component_manifests=fixture_manifests,
        real_config=real_config,
        real_artifacts=real_artifacts,
        trajectory_config=trajectory_config,
        repo_root=REPO_ROOT,
        expected_calendar_id=payload["synthetic_fixture"]["calendar_id"],
        capacity_provenance=base_payload.get("capacity_provenance"),
        artifact_sha256_by_path=source_checksums,
        component_output_manifest_paths_by_kind=component_manifest_paths,
        component_output_manifest_sha256_by_path=component_manifest_checksums,
        missing_component_output_manifest_blockers=base_payload.get(
            "missing_component_output_manifest_blockers",
            {},
        ),
        downstream_blocker_ids=base_payload.get("downstream_blocker_ids", ()),
        intended_use=payload["intended_use"],
    )
    dossier["current_main_metadata_refs"] = payload["current_main_metadata_refs"]
    dossier["real_input_source"] = BASE_INPUT_PATH.as_posix()
    dossier["source_checksum_policy"] = "computed_from_current_repository_files_before_no_array_preflight"
    return dossier, fixture_records


def _report_text(
    dossier: Mapping[str, Any],
    payload: Mapping[str, Any],
    fixture_records: Sequence[Mapping[str, object]],
    git_commit: str,
    input_checksum: str,
    base_input_checksum: str,
) -> str:
    blocker_manifest = dossier["blocker_manifest"]
    return f"""# E3.S2 Synthetic IC-1 Assembly and Real-Input Gate

Task: E3.S2 IC-1 NetLoadProvider readiness.
Status: metadata/preflight only. This packet proves the IC-1 assembly surface on tiny synthetic fixtures and runs the real-project accepted-artifact gate from current committed metadata through PR #248. It does not open real component arrays.

## Boundary

The synthetic fixture is marked `synthetic_fixture_only`, uses `time_domain=window_set`, and is not in the primary full-year probability domain. It proves common calendar handling, node-axis summation, component provenance, HP/PV weather identity preservation, and import/export-ready P-net sign metadata only.

The real-project gate remains fail-closed. It checks committed metadata packet paths/checksums, register-backed artifact statuses, component-output manifest readiness, common calendar/cadence metadata, HP/PV weather identity metadata, A-016 scenario-consistency blockers, capacity-provenance blockers, and downstream G1/G2/A-013 blockers before any arrays could be accepted.

This packet performs no real net-load aggregation, no IC-2 execution, no threshold evaluation, no event detection/counting, no `P(E)`, no capacity/domain conclusion, and no manuscript-number analysis.

## Synthetic Fixture Result

Synthetic fixture assembly ready: `{str(dossier['ready_for_synthetic_fixture_assembly']).lower()}`.
Synthetic primary probability domain: `{str(dossier['synthetic_fixture_manifest']['loading_input']['primary_probability_domain']).lower()}`.
Synthetic node axis: `{', '.join(dossier['synthetic_fixture_manifest']['node_axis'])}`.
Synthetic timestep count: `{dossier['synthetic_fixture_manifest']['timestep_count']}`.
Synthetic net-load shape: `{dossier['synthetic_fixture_manifest']['net_load_shape']}`.
Shared weather IDs: `{', '.join(dossier['synthetic_fixture_manifest']['shared_weather_driver_ids'])}`.

| Component | Component ID | Node | Status | Array path | Array SHA-256 |
| --- | --- | --- | --- | --- | --- |
{_fixture_rows(fixture_records)}

## Real-Project Gate

Ready for real input execution: `{str(dossier['ready_for_real_input_execution']).lower()}`.
Real blocker count: `{blocker_manifest['blocker_count']}`.
Blocked component families: `{', '.join(blocker_manifest['blocked_component_kinds']) or 'none'}`.
Real metadata source: `{dossier['real_input_source']}`.
Source checksum policy: `{dossier['source_checksum_policy']}`.

| Component | Blocker code | Blocker IDs | Path |
| --- | --- | --- | --- |
{_component_rows(blocker_manifest)}

## Current Main Inputs

The generator consumes the merged Agent A accepted-artifact blocker preflight, the EV accepted-artifact index, the EV held-out adequacy blocker packet from PR #248, the PV executable preflight guard, and the PV executable readiness blocker packet as metadata references only. HP remains blocked unless a later accepted HP component-output artifact appears on main; missing HP accepted component-output artifacts are reported as blockers, not fabricated.

G0-A3 appears only as governed metadata: strict `L_import > 1.0 p.u.` for four consecutive 15-minute import steps over the full year, with 1.1 and 1.2 as sensitivities. No event logic is run here.

## Reproduction

Command: `{COMMAND}`
Input: `{INPUT_PATH.as_posix()}`
Input SHA-256: `{input_checksum}`
Base real-gate input: `{BASE_INPUT_PATH.as_posix()}`
Base real-gate input SHA-256: `{base_input_checksum}`
Generated from git commit: `{git_commit}`
Standard claim-source manifest: `{MANIFEST_PATH.as_posix()}`
"""


def main() -> None:
    payload = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    dossier, fixture_records = _build_dossier(payload)

    git_commit = git("rev-parse", "HEAD")
    git_status = git("status", "--short")
    input_checksum = sha256(INPUT_PATH)
    base_input_checksum = sha256(BASE_INPUT_PATH)
    REPORT_PATH.write_text(
        _report_text(dossier, payload, fixture_records, git_commit, input_checksum, base_input_checksum),
        encoding="utf-8",
    )

    outputs = {
        "report_path": REPORT_PATH.as_posix(),
        "report_sha256": sha256(REPORT_PATH),
        "fixture_records": fixture_records,
    }
    manifest = {
        "schema_version": "e3_s2_synthetic_assembly_real_gate_manifest_v1",
        "task_id": payload["task_id"],
        "scope": payload["scope"],
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "git_commit": git_commit,
        "git_status_short_before_generation": git_status,
        "command": COMMAND,
        "input": {
            "path": INPUT_PATH.as_posix(),
            "sha256": input_checksum,
            "schema_version": payload["schema_version"],
        },
        "base_real_gate_input": {
            "path": BASE_INPUT_PATH.as_posix(),
            "sha256": base_input_checksum,
        },
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": {
                "numpy": package_version("numpy"),
                "pandapower": package_version("pandapower"),
                "simbench": package_version("simbench"),
                "lightsim2grid": package_version("lightsim2grid"),
            },
        },
        "preflight": dossier,
        "outputs": outputs,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
