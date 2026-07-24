"""Generate the E3.S2 accepted-artifact loader blocker preflight packet.

This generator is metadata-only. It instantiates the Agent A-owned
``build_accepted_artifact_loader_blocker_preflight`` helper from committed
metadata packet references and never opens component trajectory arrays or
evaluates IC-2 events.
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
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.contracts.loading_trajectory import LoadingTrajectoryPreRunConfig
from src.contracts.net_load import (
    ExecutableInputArtifact,
    FutureLayerScreenPreflightConfig,
    build_accepted_artifact_loader_blocker_preflight,
)

INPUT_PATH = Path("reports/e3_s2_accepted_artifact_blocker_preflight_input.json")
MANIFEST_PATH = Path("reports/e3_s2_accepted_artifact_blocker_preflight_manifest.json")
REPORT_PATH = Path("reports/E3_S2_ACCEPTED_ARTIFACT_BLOCKER_PREFLIGHT.md")
COMMAND = ".\\.venv\\Scripts\\python.exe reports\\e3_s2_generate_accepted_artifact_blocker_preflight.py"


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


def build_dossier_from_payload(
    payload: Mapping[str, Any],
    *,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    config = FutureLayerScreenPreflightConfig(**payload["config"])
    trajectory_config = LoadingTrajectoryPreRunConfig(**payload["trajectory_config"])
    artifacts = tuple(ExecutableInputArtifact(**record) for record in payload["artifacts"])
    return build_accepted_artifact_loader_blocker_preflight(
        config,
        artifacts,
        trajectory_config,
        capacity_provenance=payload.get("capacity_provenance"),
        artifact_sha256_by_path=payload.get("artifact_sha256_by_path", {}),
        component_output_manifest_paths_by_kind=payload.get("component_output_manifest_paths_by_kind", {}),
        component_output_manifest_sha256_by_path=payload.get("component_output_manifest_sha256_by_path", {}),
        missing_component_output_manifest_blockers=payload.get("missing_component_output_manifest_blockers", {}),
        repo_root=repo_root,
        missing_artifact_blockers=payload.get("missing_artifact_blockers", {}),
        downstream_blocker_ids=payload.get("downstream_blocker_ids", ()),
        intended_use=payload["intended_use"],
    )


def _source_record_status(record: Mapping[str, Any]) -> str:
    if not record.get("exists", False):
        return "missing"
    if record.get("checksum_match") is True:
        return "checksum-verified"
    if record.get("checksum_match") is False:
        return "checksum-mismatch"
    return "checksum-unverified"


def _source_table_rows(dossier: Mapping[str, Any]) -> str:
    base = dossier["real_artifact_preflight"]
    rows: list[str] = []
    for record in base["source_artifact_records"]:
        rows.append(
            "| {kind} | {artifact_id} | {status} | {observed} | {expected} | {path} |".format(
                kind=record["kind"],
                artifact_id=record["artifact_id"],
                status=_source_record_status(record),
                observed=record.get("sha256") or "--",
                expected=record.get("expected_sha256") or "--",
                path=record["path"],
            )
        )
    return "\n".join(rows)


def _component_output_table_rows(dossier: Mapping[str, Any]) -> str:
    rows: list[str] = []
    for record in dossier["component_output_manifest_records"]:
        rows.append(
            "| {kind} | {state} | {checksum} | {path} |".format(
                kind=record["kind"],
                state=record["state"],
                checksum=record.get("checksum_match", "--"),
                path=record.get("path") or "--",
            )
        )
    return "\n".join(rows)


def _blocker_table_rows(dossier: Mapping[str, Any]) -> str:
    rows: list[str] = []
    for item in dossier["blocker_manifest"]["items"]:
        rows.append(
            "| {kind} | {code} | {ids} | {path} | {message} |".format(
                kind=item.get("kind") or "--",
                code=item["code"],
                ids=", ".join(item.get("blocker_ids") or ()) or "--",
                path=item.get("path") or "--",
                message=item["message"],
            )
        )
    return "\n".join(rows) or "| -- | none | -- | -- | -- |"


def _component_state_summary(dossier: Mapping[str, Any]) -> str:
    rows = dossier["real_artifact_preflight"]["bridge_preflight"]["executable_input_preflight"]["component_reports"]
    parts: list[str] = []
    for kind, record in sorted(rows.items()):
        parts.append(f"{kind}: {record['state']}")
    return "; ".join(parts)


def _report_text(
    dossier: Mapping[str, Any],
    payload: Mapping[str, Any],
    git_commit: str,
    input_checksum: str,
) -> str:
    ready = str(dossier["ready_for_artifact_loader_execution"]).lower()
    blocked_kinds = ", ".join(dossier["blocker_manifest"]["blocked_component_kinds"]) or "none"
    blocker_count = dossier["blocker_manifest"]["blocker_count"]
    return f"""# E3.S2 Accepted-Artifact Loader Blocker Preflight

Task: E3.S2 IC-1 NetLoadProvider readiness.
Status: metadata/preflight only. This packet instantiates `build_accepted_artifact_loader_blocker_preflight(...)` from the current committed metadata surface on `origin/main` through PR #248 (with PR #249 methods cleanup on main). The merged EV accepted-artifact index, EV held-out blocker, PV executable guard, and adoption artifact are consumed as metadata only; remaining gaps are reported as blockers.

## Boundary

This is not a real IC-1 integration run. It does not load EV, HP, PV, baseline, adoption, or flexibility trajectories; does not aggregate net load; does not execute IC-2; does not detect or count events; does not compute `P(E)`; does not produce a capacity/domain conclusion; and does not add manuscript numbers.

The dry run used the version-controlled input `{INPUT_PATH.as_posix()}` at commit `{git_commit[:12]}`. The claim-source manifest for this preflight packet is `{MANIFEST_PATH.as_posix()}`.

## Result

Ready for accepted-artifact loader execution: `{ready}`.
Ready for integrated trajectory acceptance: `{str(dossier['ready_for_integrated_trajectory_acceptance']).lower()}`.
Blocker count: `{blocker_count}`.
Blocked component families: {blocked_kinds}.
Executable input gate states: {_component_state_summary(dossier)}.

Source metadata packet checksums are verified before component-output manifests are considered. Component-output manifests must then be repository-contained, checksum-pinned, accepted, schema-compatible with the loader, and consistent with the executable artifact metadata before any array path can be trusted. This packet opens JSON metadata only; it does not open the component arrays named by any manifest.

| Component | Artifact | Source packet status | Observed SHA-256 | Expected SHA-256 | Source path |
| --- | --- | --- | --- | --- | --- |
{_source_table_rows(dossier)}

| Component | Component-output manifest state | Checksum match | Manifest path |
| --- | --- | --- | --- |
{_component_output_table_rows(dossier)}

## Blocker Manifest

| Component | Code | Blocker IDs | Path | Message |
| --- | --- | --- | --- | --- |
{_blocker_table_rows(dossier)}

## Interpretation

The current metadata surface is intentionally not accepted for loader execution. EV now has the merged PR #243 accepted-artifact index, the PR #248 held-out adequacy blocker packet, and a checksum-pinned candidate component-output manifest path, but that manifest is not yet the accepted generic loader schema and held-out data remain closed. Adoption now has the merged PR #235 accepted per-node allocation artifact, but no component-output loader manifest is present for the IC-1 assembly boundary. PV/weather now has the merged PR #241 executable-readiness blocker packet and PR #246 executable preflight guard, which confirm weather source/member readiness while keeping PV generation blocked. Flexibility has the approved FLEX-001 scaffold protocol, but no real flexibility values or results are signed. Baseline, HP, PV/weather, adoption, and flexibility still lack accepted component-output manifests for the loader boundary.

The preflight also preserves downstream blockers for A-013, G2, G1-A2 capacity/domain provenance, A-016 scenario consistency, and the capacity convention. G0-A3 is recorded only as governed metadata: strict `L_import > 1.0 p.u.` for four consecutive 15-minute import steps over the full year, with `1.1` and `1.2` only as explicit sensitivities. No threshold is evaluated here.

## Reproduction

Command: `{COMMAND}`
Input SHA-256: `{input_checksum}`
Generated from git commit: `{git_commit}`

Verification for this PR should use focused `tests/test_evaluator_net_load.py`, `./scripts/task.ps1 ownership`, `./scripts/task.ps1 test-fast`, and `git diff --check`.
"""


def main() -> None:
    payload = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    dossier = build_dossier_from_payload(payload, repo_root=REPO_ROOT)

    git_commit = git("rev-parse", "HEAD")
    git_status = git("status", "--short")
    input_checksum = sha256(INPUT_PATH)
    REPORT_PATH.write_text(_report_text(dossier, payload, git_commit, input_checksum), encoding="utf-8")

    manifest = {
        "schema_version": "e3_s2_accepted_artifact_blocker_preflight_manifest_v1",
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
        "outputs": {
            "report_path": REPORT_PATH.as_posix(),
            "report_sha256": sha256(REPORT_PATH),
        },
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
