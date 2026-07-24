"""Generate the E3.S2b integrated pre-run readiness packet.

This generator is metadata-only. It composes the accepted-artifact loader
preflight with E3.S2b launch-shape checks and never opens component trajectory
arrays, runs IC-2, detects events, estimates probabilities, or computes a
capacity/domain screen result.
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
    build_e3_s2b_integrated_prerun_readiness,
)

INPUT_PATH = Path("reports/e3_s2b_integrated_prerun_readiness_input.json")
MANIFEST_PATH = Path("reports/e3_s2b_integrated_prerun_readiness_manifest.json")
REPORT_PATH = Path("reports/E3_S2B_INTEGRATED_PRERUN_READINESS.md")
COMMAND = ".\\.venv\\Scripts\\python.exe reports\\e3_s2b_generate_integrated_prerun_readiness.py"


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


def json_ready(value: Any) -> Any:
    if isinstance(value, tuple):
        return [json_ready(item) for item in value]
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    return value


def build_dossier_from_payload(
    payload: Mapping[str, Any],
    *,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    config = FutureLayerScreenPreflightConfig(**payload["config"])
    trajectory_config = LoadingTrajectoryPreRunConfig(**payload["trajectory_config"])
    artifacts = tuple(ExecutableInputArtifact(**record) for record in payload["artifacts"])
    return build_e3_s2b_integrated_prerun_readiness(
        config,
        artifacts,
        trajectory_config,
        capacity_provenance=payload.get("capacity_provenance"),
        capacity_provenance_packet_path=payload.get("capacity_provenance_packet_path"),
        capacity_provenance_packet_sha256=payload.get("capacity_provenance_packet_sha256"),
        artifact_sha256_by_path=payload.get("artifact_sha256_by_path", {}),
        component_output_manifest_paths_by_kind=payload.get("component_output_manifest_paths_by_kind", {}),
        component_output_manifest_sha256_by_path=payload.get("component_output_manifest_sha256_by_path", {}),
        missing_component_output_manifest_blockers=payload.get("missing_component_output_manifest_blockers", {}),
        scenario_consistency_manifest=payload.get("scenario_consistency_manifest"),
        component_year_coverage_by_kind=payload.get("component_year_coverage_by_kind", {}),
        supporting_metadata_paths=payload.get("supporting_metadata_paths", {}),
        supporting_metadata_sha256_by_path=payload.get("supporting_metadata_sha256_by_path", {}),
        repo_root=repo_root,
        missing_artifact_blockers=payload.get("missing_artifact_blockers", {}),
        downstream_blocker_ids=payload.get("downstream_blocker_ids", ()),
        intended_use=payload["intended_use"],
    )


def _source_status(record: Mapping[str, Any]) -> str:
    if not record.get("exists", False):
        return "missing"
    if record.get("checksum_match") is True:
        return "checksum-verified"
    if record.get("checksum_match") is False:
        return "checksum-mismatch"
    return "checksum-unverified"


def _source_rows(dossier: Mapping[str, Any]) -> str:
    rows: list[str] = []
    source_records = dossier["accepted_artifact_preflight"]["real_artifact_preflight"]["source_artifact_records"]
    for record in source_records:
        rows.append(
            "| {kind} | {artifact_id} | {state} | {path} | {sha} |".format(
                kind=record["kind"],
                artifact_id=record["artifact_id"],
                state=_source_status(record),
                path=record["path"],
                sha=record.get("sha256", "--"),
            )
        )
    return "\n".join(rows)


def _component_manifest_rows(dossier: Mapping[str, Any]) -> str:
    rows: list[str] = []
    for record in dossier["accepted_artifact_preflight"]["component_output_manifest_records"]:
        rows.append(
            "| {kind} | {state} | {path} | {checksum} |".format(
                kind=record["kind"],
                state=record["state"],
                path=record.get("path") or "--",
                checksum=record.get("checksum_match", "--"),
            )
        )
    return "\n".join(rows)


def _capacity_source_row(dossier: Mapping[str, Any]) -> str:
    record = dossier.get("capacity_provenance_source_record")
    if not record:
        return "| -- | missing | -- | -- | -- |"
    return "| {path} | {state} | {checksum} | {sha} | {schema} |".format(
        path=record.get("path") or "--",
        state=record.get("state") or "--",
        checksum=record.get("checksum_match", "--"),
        sha=record.get("sha256", "--"),
        schema=record.get("schema_version", "--"),
    )


def _year_rows(dossier: Mapping[str, Any]) -> str:
    rows: list[str] = []
    for kind, record in dossier["component_year_coverage"].items():
        rows.append(
            "| {kind} | {covered} | {missing} |".format(
                kind=kind,
                covered=", ".join(str(year) for year in record["covered_years"]) or "--",
                missing=", ".join(str(year) for year in record["missing_years"]) or "none",
            )
        )
    return "\n".join(rows)


def _supporting_rows(dossier: Mapping[str, Any]) -> str:
    rows: list[str] = []
    for record in dossier["supporting_metadata_records"]:
        rows.append(
            "| {label} | {path} | {state} | {sha} |".format(
                label=record["label"],
                path=record["path"],
                state=_source_status(record),
                sha=record.get("sha256", "--"),
            )
        )
    return "\n".join(rows) or "| -- | -- | none | -- |"


def _blocker_rows(dossier: Mapping[str, Any]) -> str:
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
    reports = dossier["accepted_artifact_preflight"]["real_artifact_preflight"]["bridge_preflight"]["executable_input_preflight"]["component_reports"]
    return "; ".join(f"{kind}: {record['state']}" for kind, record in sorted(reports.items()))


def _report_text(
    dossier: Mapping[str, Any],
    payload: Mapping[str, Any],
    git_commit: str,
    input_checksum: str,
) -> str:
    planned = dossier["planned_screen"]
    metadata = payload.get("metadata", {})
    return f"""# E3.S2b Integrated Pre-Run Readiness

Task: E3.S2b future-layer capacity/domain screen pre-run design scaffold.
Status: metadata/preflight only. This packet composes the current Agent A IC-1 accepted-artifact gate with E3.S2b launch-shape checks on current `origin/main` through PR #268. It consumes the merged EV accepted index, checksum preflight, and #265 generic multi-node component-output manifest packet; consolidated HP readiness guard packets plus the #267 HP profile rebuild runner blocker; PV first-experiment value-decision/approval/preflight blocker packets plus the #263 PV component-output scaffold; the synthetic IC-1 assembly gate; the accepted-artifact blocker refresh; Agent B trust/readiness, rho-sweep guard, hybrid-provenance guard, and #268 alpha event-count scaffold context; and the #264 capacity-provenance packet as metadata only.

## Boundary

This is not a real IC-1 or IC-2 run. It does not load component arrays; aggregate net load; execute IC-2; evaluate thresholds; detect or count events; estimate `P(E)`; choose total versus firm capacity; use A-013/G2 numerical values; classify capacity/domain cases; or produce manuscript numbers.

G0-A3 appears only as governed metadata: strict `L_import > 1.0 p.u.` for four consecutive 15-minute import steps over the full year, with `1.1` and `1.2` retained only as explicit sensitivities. No threshold is evaluated here.

The version-controlled input is `{INPUT_PATH.as_posix()}`. The claim-source manifest for this pre-run readiness packet is `{MANIFEST_PATH.as_posix()}`.

## Planned E3.S2b Screen Shape

| Field | Value |
| --- | --- |
| Scenarios | {', '.join(planned['scenario_ids'])} |
| Planning years | {', '.join(str(year) for year in planned['planning_years'])} |
| Rho endpoints | {', '.join(str(rho) for rho in planned['rho_values'])} |
| Planned metadata cases | {planned['planned_case_count']} |
| Timestep cadence | {planned['timestep_seconds']} seconds |
| Capacity convention status | {planned['capacity_convention_status']} |

## Readiness Result

Ready for E3.S2b pre-run launch: `{str(dossier['ready_for_e3_s2b_prerun_launch']).lower()}`.
Ready for accepted-artifact loader execution: `{str(dossier['ready_for_artifact_loader_execution']).lower()}`.
Blocker count: `{dossier['blocker_manifest']['blocker_count']}`.
Blocked component families: {', '.join(dossier['blocker_manifest']['blocked_component_kinds']) or 'none'}.
Executable input gate states: {_component_state_summary(dossier)}.

## Capacity Provenance Packet

| Packet path | State | Checksum match | Observed SHA-256 | Schema |
| --- | --- | --- | --- | --- |
{_capacity_source_row(dossier)}

Capacity convention status: {dossier['capacity_prerun_provenance']['status']}. Total and firm nameplate fields are provenance inputs only; no denominator is selected here.

## Source Metadata Packets

| Component | Artifact | State | Path | Observed SHA-256 |
| --- | --- | --- | --- | --- |
{_source_rows(dossier)}

## Component-Output Manifest Boundary

| Component | Manifest state | Manifest path | Checksum match |
| --- | --- | --- | --- |
{_component_manifest_rows(dossier)}

## Planned-Year Coverage

| Component | Covered years in current metadata | Missing planned years |
| --- | --- | --- |
{_year_rows(dossier)}

## Supporting Metadata Consumed

| Label | Path | State | Observed SHA-256 |
| --- | --- | --- | --- |
{_supporting_rows(dossier)}

## Blocker Manifest

| Component | Code | Blocker IDs | Path | Message |
| --- | --- | --- | --- | --- |
{_blocker_rows(dossier)}

## Interpretation

The useful current-main state is metadata-rich but still fail-closed. EV has an accepted Agent A-facing index, checksum preflight, and #265 generic low/middle/high component-output manifest packet, but those manifests describe 115-node scenario NPZ files while the current A-owned generic NPZ loader accepts only single-node, one-dimensional component-output manifests. That metadata wrapper is therefore reported as a loadability blocker until A adds an explicit multi-node loader or C emits per-node loadable manifests. Adoption metadata is accepted for declared branches, and FLEX-001 is approved as a scaffold protocol. PV now has the first-experiment value-decision packet, approval checklist packets, executable preflight guard, and #263 component-output artifact scaffold, but PV capacity values, orientation/tilt values, conversion treatment, allocation, A-016 consistency, and final paired HP/PV acceptance remain unsigned. HP now has the consolidated #250 component-output readiness blocker, profile-artifact template, cold-spell acceptance packet, refreshed value-binding packet, and #267 profile rebuild runner blocker, but still lacks signed annual value binding, final A-016 scenario consistency, paired-weather acceptance, cold-spell tolerances, and an accepted component-output manifest. Baseline, HP, PV, adoption, and flexibility still lack accepted generic component-output manifests for the IC-1 loader boundary.

The E3.S2b design also records that the future screen must be a predeclared 2030/2033/2035 by low/middle/high by rho-endpoint plan, but current component metadata does not yet cover all planned years. The #264 capacity provenance packet is now checksum-verified and supplies total 80 MVA plus firm (n-1) 40 MVA raw-reporting fields, but the denominator convention remains pending and no screen can launch until all component-output, A-016, A-013, G2, and convention prerequisites are satisfied. A-013 and G2 remain downstream blockers for later model-error and Tier-1 validation; this report does not use their numerical values.

## Reproduction

Command: `{COMMAND}`
Input SHA-256: `{input_checksum}`
Generated from git commit: `{git_commit}`
Refresh basis: {metadata.get('refresh_basis', 'current main')}
"""


def main() -> None:
    payload = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    dossier = build_dossier_from_payload(payload, repo_root=REPO_ROOT)
    git_commit = git("rev-parse", "HEAD")
    git_status = git("status", "--short")
    input_checksum = sha256(INPUT_PATH)
    REPORT_PATH.write_text(_report_text(dossier, payload, git_commit, input_checksum), encoding="utf-8")

    manifest = {
        "schema_version": "e3_s2b_integrated_prerun_readiness_manifest_v1",
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
        "preflight": json_ready(dossier),
        "outputs": {
            "report_path": REPORT_PATH.as_posix(),
            "report_sha256": sha256(REPORT_PATH),
        },
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
