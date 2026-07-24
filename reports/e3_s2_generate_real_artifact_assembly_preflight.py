"""Generate the E3.S2 current-main real-artifact assembly preflight packet.

This generator is metadata-only. It instantiates the Agent A-owned
``build_real_artifact_assembly_preflight`` helper from committed metadata packet
references and never opens component trajectory arrays or evaluates events.
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
    build_real_artifact_assembly_preflight,
)

INPUT_PATH = Path("reports/e3_s2_real_artifact_assembly_preflight_input.json")
MANIFEST_PATH = Path("reports/e3_s2_real_artifact_assembly_preflight_manifest.json")
REPORT_PATH = Path("reports/E3_S2_REAL_ARTIFACT_ASSEMBLY_PREFLIGHT.md")
COMMAND = ".\\.venv\\Scripts\\python.exe reports\\e3_s2_generate_real_artifact_assembly_preflight.py"


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


def _packet_status(report: Mapping[str, Any]) -> str:
    artifact = report.get("artifact") or {}
    provenance = artifact.get("provenance") or {}
    return str(
        provenance.get("packet_status")
        or provenance.get("readiness_bucket")
        or report.get("artifact_status")
        or report.get("state")
    )


def _source_record_status(record: Mapping[str, Any]) -> str:
    if not record.get("exists", False):
        return "missing"
    if record.get("checksum_match") is True:
        return "checksum-verified"
    if record.get("checksum_match") is False:
        return "checksum-mismatch"
    return "checksum-unverified"


def _source_groups(dossier: Mapping[str, Any]) -> dict[str, str]:
    groups: dict[str, list[str]] = {
        "checksum_verified": [],
        "checksum_unverified": [],
        "checksum_mismatch": [],
        "missing": [],
    }
    for record in dossier["source_artifact_records"]:
        status = _source_record_status(record)
        path = str(record["path"])
        if status == "checksum-verified":
            groups["checksum_verified"].append(path)
        elif status == "checksum-unverified":
            groups["checksum_unverified"].append(path)
        elif status == "checksum-mismatch":
            groups["checksum_mismatch"].append(path)
        elif status == "missing":
            groups["missing"].append(path)
    return {key: ", ".join(value) or "none" for key, value in groups.items()}


def _component_groups(dossier: Mapping[str, Any]) -> dict[str, str]:
    preflight = dossier["bridge_preflight"]["executable_input_preflight"]
    component_reports = preflight["component_reports"]
    groups: dict[str, list[str]] = {
        "accepted": [],
        "unsigned": [],
        "blocked": [],
        "missing": [],
    }
    for kind in preflight["required_component_kinds"]:
        report = component_reports[kind]
        artifact_status = str(report.get("artifact_status") or "")
        state = str(report["state"])
        if state == "accepted":
            groups["accepted"].append(kind)
        if artifact_status in {"unsigned", "scaffold"}:
            groups["unsigned"].append(kind)
        if state == "blocked":
            groups["blocked"].append(kind)
        if state == "missing":
            groups["missing"].append(kind)
    return {key: ", ".join(value) or "none" for key, value in groups.items()}


def _component_table_rows(dossier: Mapping[str, Any]) -> str:
    preflight = dossier["bridge_preflight"]["executable_input_preflight"]
    component_reports = preflight["component_reports"]
    source_status_by_path = {
        record["path"]: _source_record_status(record)
        for record in dossier["source_artifact_records"]
    }
    rows: list[str] = []
    for kind in preflight["required_component_kinds"]:
        report = component_reports[kind]
        blockers = report.get("blocking_register_ids") or report.get("register_backing_errors") or ()
        signed = report.get("signed_register_ids") or ()
        path = report.get("manifest_path") or "--"
        rows.append(
            "| {kind} | {state} | {packet_status} | {source_status} | {artifact} | {signed} | {blockers} | {path} |".format(
                kind=kind,
                state=report["state"],
                packet_status=_packet_status(report),
                source_status=source_status_by_path.get(path, "not-cited"),
                artifact=report.get("artifact_id") or "--",
                signed=", ".join(signed) if signed else "--",
                blockers=", ".join(blockers) if blockers else "--",
                path=path,
            )
        )
    return "\n".join(rows)


def _source_table_rows(dossier: Mapping[str, Any]) -> str:
    rows: list[str] = []
    for record in dossier["source_artifact_records"]:
        expected = record.get("expected_sha256") or "--"
        observed = record.get("sha256") or "--"
        rows.append(
            "| {kind} | {artifact_id} | {status} | {exists} | {observed} | {expected} | {path} |".format(
                kind=record["kind"],
                artifact_id=record["artifact_id"],
                status=_source_record_status(record),
                exists=str(record["exists"]).lower(),
                observed=observed,
                expected=expected,
                path=record["path"],
            )
        )
    return "\n".join(rows)


def build_dossier_from_payload(
    payload: Mapping[str, Any],
    *,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    config = FutureLayerScreenPreflightConfig(**payload["config"])
    trajectory_config = LoadingTrajectoryPreRunConfig(**payload["trajectory_config"])
    artifacts = tuple(ExecutableInputArtifact(**record) for record in payload["artifacts"])
    return build_real_artifact_assembly_preflight(
        config,
        artifacts,
        trajectory_config,
        capacity_provenance=payload.get("capacity_provenance"),
        artifact_sha256_by_path=payload.get("artifact_sha256_by_path", {}),
        repo_root=repo_root,
        missing_artifact_blockers=payload.get("missing_artifact_blockers", {}),
        downstream_blocker_ids=payload.get("downstream_blocker_ids", ()),
        intended_use=payload["intended_use"],
    )


def _report_text(
    dossier: Mapping[str, Any],
    payload: Mapping[str, Any],
    git_commit: str,
    input_checksum: str,
) -> str:
    component_groups = _component_groups(dossier)
    source_groups = _source_groups(dossier)
    component_rows = _component_table_rows(dossier)
    source_rows = _source_table_rows(dossier)
    ready_flag = str(dossier["ready_for_real_artifact_assembly"]).lower()
    ev_verifier = payload.get("metadata", {}).get("ev_output_verifier_status", "not recorded")
    return f"""# E3.S2 Current-Main Real-Artifact Assembly Preflight

Task: E3.S2 IC-1 NetLoadProvider readiness.
Status: metadata/preflight only. This packet instantiates `build_real_artifact_assembly_preflight(...)` from the current committed metadata surface on `origin/main` after PR #221, #222, and #223. It reports which component packet references are accepted, unsigned, blocked, missing, or checksum-unverified before any component arrays are opened.

## Boundary

This is not a real IC-1 integration run. It does not load EV, HP, PV, baseline, adoption, or flexibility trajectories; does not aggregate net load; does not execute IC-2; does not detect or count events; does not compute `P(E)`; does not produce a capacity/domain conclusion; and does not add manuscript numbers.

The dry run used the version-controlled input `{INPUT_PATH.as_posix()}` at commit `{git_commit[:12]}`. The standard claim-source manifest for this preflight packet is `{MANIFEST_PATH.as_posix()}`.

## Result

Overall ready for real-artifact assembly: `{ready_flag}`.

Accepted component families: {component_groups['accepted']}.
Unsigned/scaffold component families: {component_groups['unsigned']}.
Gate-blocked component families: {component_groups['blocked']}.
Missing component families: {component_groups['missing']}.
Checksum-verified source packet paths: {source_groups['checksum_verified']}.
Checksum-unverified source packet paths: {source_groups['checksum_unverified']}.
Checksum-mismatched source packet paths: {source_groups['checksum_mismatch']}.
Missing source packet paths: {source_groups['missing']}.

| Component | Gate result | Packet status | Source packet status | Artifact | Signed IDs | Blocking IDs | Artifact path |
| --- | --- | --- | --- | --- | --- | --- | --- |
{component_rows}

| Component | Artifact | Source packet status | Exists | Observed SHA-256 | Expected SHA-256 | Path |
| --- | --- | --- | --- | --- | --- | --- |
{source_rows}

## Interpretation

EV and flexibility are the only gate-accepted component families in this metadata preflight. EV remains metadata-only: candidate checksum provenance is recorded, PR #224 EV component-output verifier availability is `{ev_verifier}`, no held-out EV data are opened, and no candidate profile arrays are loaded. FLEX-001 is approved only as a scaffold protocol; real flexibility values/results remain outside this packet.

Baseline, HP, PV/weather, and adoption remain blocked before executable IC-1 aggregation. Baseline lacks an accepted executable adapter artifact. HP still needs the signed HP annual value binding choices, D-004 paired-weather acceptance, and cold-spell tolerances. PV/weather includes the newly merged D-014 CBS Alkmaar PV-capacity anchor evidence from PR #222 and the existing final-acceptance gate packet, but PV-PARAM-001, D-014 value/source choices, final paired HP/PV acceptance, cold-spell acceptance, scenario growth, capacity convention, per-node allocation, and statistical orientation/tilt values remain unsigned. Adoption still lacks an accepted executable per-node artifact.

The bridge preserves G0-A3 as governed metadata only: strict `L_import > 1.0 p.u.` for four consecutive 15-minute import steps over the full year, with `1.1` and `1.2` only as explicit sensitivities. A-013, G2, G1-A2 capacity/domain provenance, A-016 scenario consistency, and the missing capacity-convention/domain choices remain downstream blockers; no threshold is evaluated here.

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
        "schema_version": "e3_s2_real_artifact_assembly_preflight_manifest_v1",
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
        "source_artifact_summary": _source_groups(dossier),
        "outputs": {
            "report_path": REPORT_PATH.as_posix(),
            "report_sha256": sha256(REPORT_PATH),
        },
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
