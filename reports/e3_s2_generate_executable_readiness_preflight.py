"""Generate the E3.S2 executable-readiness preflight packet.

This report generator is intentionally metadata-only. It calls the
register-backed dry-run gate and never loads component arrays or evaluates
events, probabilities, or capacity screens.
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
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.contracts.net_load import (
    ExecutableInputArtifact,
    FutureLayerScreenPreflightConfig,
    dry_run_integrated_input_preflight,
)

INPUT_PATH = Path("reports/e3_s2_executable_readiness_preflight_input.json")
MANIFEST_PATH = Path("reports/e3_s2_executable_readiness_preflight_manifest.json")
REPORT_PATH = Path("reports/E3_S2_EXECUTABLE_READINESS_PREFLIGHT.md")
COMMAND = ".\\.venv\\Scripts\\python.exe reports\\e3_s2_generate_executable_readiness_preflight.py"


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


def _packet_status(report: dict[str, Any]) -> str:
    artifact = report.get("artifact") or {}
    provenance = artifact.get("provenance") or {}
    return str(
        provenance.get("packet_status")
        or provenance.get("readiness_bucket")
        or report.get("artifact_status")
        or report.get("state")
    )


def _component_groups(preflight: dict[str, object]) -> dict[str, str]:
    component_reports = preflight["component_reports"]
    groups = {
        "accepted": [],
        "proposed_or_unsigned": [],
        "blocked": [],
        "missing": [],
    }
    for kind in preflight["required_component_kinds"]:
        report = component_reports[kind]
        packet_status = _packet_status(report).lower()
        artifact_status = str(report.get("artifact_status") or "")
        state = str(report["state"])
        if state == "missing":
            groups["missing"].append(kind)
        if state == "blocked":
            groups["blocked"].append(kind)
        if state == "accepted":
            groups["accepted"].append(kind)
        if artifact_status in {"unsigned", "scaffold"} or "proposed" in packet_status:
            groups["proposed_or_unsigned"].append(kind)
    return {key: ", ".join(value) or "none" for key, value in groups.items()}


def _table_rows(preflight: dict[str, object]) -> str:
    component_reports = preflight["component_reports"]
    rows: list[str] = []
    for kind in preflight["required_component_kinds"]:
        report = component_reports[kind]
        blockers = report.get("blocking_register_ids") or report.get("register_backing_errors") or ()
        signed = report.get("signed_register_ids") or ()
        rows.append(
            "| {kind} | {state} | {packet_status} | {artifact} | {signed} | {blockers} | {path} |".format(
                kind=kind,
                state=report["state"],
                packet_status=_packet_status(report),
                artifact=report.get("artifact_id") or "--",
                signed=", ".join(signed) if signed else "--",
                blockers=", ".join(blockers) if blockers else "--",
                path=report.get("manifest_path") or "--",
            )
        )
    return "\n".join(rows)


def _report_text(preflight: dict[str, object], git_commit: str, input_checksum: str) -> str:
    groups = _component_groups(preflight)
    rows = _table_rows(preflight)
    ready_flag = str(preflight["ready_for_input_assembly"]).lower()
    return f"""# E3.S2 Executable Readiness Preflight

Task: E3.S2 IC-1 NetLoadProvider readiness.
Status: metadata/preflight only. PR #215 discovers the component-readiness artifacts currently merged on `origin/main`, including the accepted metadata-only EV IC-1 component input scaffold, the EV candidate checksum preflight, the newest HP executable value-binding decision packet, the PV final-acceptance gate, the approved PV-CAP-001 installed-capacity source route, the PV-ORIENT-001 first-experiment scope decision, the proposed D014-PV-ORIENTATION-TILT-SOURCE-CHOICE-PACKET, and the IC-1/IC-2 executable bridge preflight. It routes those artifacts through the register-backed executable-input dry run and reports which IC-1 input families are accepted, proposed or unsigned, blocked, or missing.

## Boundary

This is not a real IC-1 integration run. It does not load EV, HP, PV, baseline, adoption, or flexibility trajectories; does not aggregate net load; does not call IC-2; does not detect threshold events; does not compute `P(E)`; does not produce a capacity-screen result; and does not add manuscript numbers.

The dry run used the version-controlled input `{INPUT_PATH.as_posix()}` at commit `{git_commit[:12]}`. The standard claim-source manifest for this preflight packet is `{MANIFEST_PATH.as_posix()}`.

## Result

Overall ready for executable input assembly: `{ready_flag}`.

Gate-accepted component families: {groups['accepted']}.
Proposed or unsigned packet families: {groups['proposed_or_unsigned']}.
Gate-blocked component families: {groups['blocked']}.
Missing component families: {groups['missing']}.

| Component | Gate result | Packet status | Artifact | Signed IDs | Blocking IDs | Artifact path |
| --- | --- | --- | --- | --- | --- | --- |
{rows}

## Interpretation

The accepted metadata-only EV IC-1 component input scaffold and FLEX-001 scaffold protocol are register-backed enough for this metadata gate. The EV row now carries the merged candidate checksum preflight provenance, which verified candidate processed files by SHA-256 without loading arrays. That does not open held-out EV data, certify EV library adequacy, approve real flexibility values, or run any event-based analysis.

Baseline, HP, PV/weather, and adoption are not ready for executable IC-1 aggregation. Baseline still lacks an accepted executable adapter artifact. HP now has the proposed `E2-S3-HP001-EXECUTABLE-VALUE-BINDING-PACKET` as the newest packet; it is an approval template only, so the current blockers are `E2-S3-HP001-EXECUTABLE-VALUE-BINDING-PACKET`, `value_column`, `denominator`, `unit_conversion`, `sfh_mfh_split`, `adoption_electrification`, `d004_paired_weather_acceptance`, and `cold_spell_tolerances`. PV/weather now records that `PV-CAP-001` approves the installed-capacity source route and `PV-ORIENT-001` approves statistical orientation/tilt scope only; concrete D-014 retrieval, numeric capacity values, scenario growth, capacity convention, per-node allocation, statistical orientation/tilt source/weights, `PV-PARAM-001`, final paired HP/PV acceptance, and cold-spell acceptance remain unresolved before executable PV/weather input. Adoption has approved local counts/allocation governance but the discovered preview is not an accepted executable per-node adoption artifact.

The merged IC-1/IC-2 bridge preflight confirms that G0-A3 metadata can be carried forward as strict `L_import > 1.0 p.u.` for four consecutive 15-minute import steps, with `1.1` and `1.2` only as explicit sensitivities. PR #215 does not build loading trajectories or evaluate that threshold.

## Reproduction

Command: `{COMMAND}`
Input SHA-256: `{input_checksum}`
Generated from git commit: `{git_commit}`

Verification for PR #215 should still use `./scripts/task.ps1 ownership`, `./scripts/task.ps1 test-fast`, and `git diff --check`.
"""


def main() -> None:
    payload = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    config = FutureLayerScreenPreflightConfig(**payload["config"])
    artifacts = tuple(ExecutableInputArtifact(**record) for record in payload["artifacts"])
    preflight = dry_run_integrated_input_preflight(
        config,
        artifacts,
        missing_artifact_blockers=payload.get("missing_artifact_blockers", {}),
        intended_use=payload["intended_use"],
    )

    git_commit = git("rev-parse", "HEAD")
    git_status = git("status", "--short")
    input_checksum = sha256(INPUT_PATH)
    REPORT_PATH.write_text(_report_text(preflight, git_commit, input_checksum), encoding="utf-8")

    manifest = {
        "schema_version": "e3_s2_executable_readiness_preflight_manifest_v1",
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
        "preflight": preflight,
        "outputs": {
            "report_path": REPORT_PATH.as_posix(),
            "report_sha256": sha256(REPORT_PATH),
        },
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
