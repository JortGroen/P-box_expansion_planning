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


def _table_rows(preflight: dict[str, object]) -> str:
    component_reports = preflight["component_reports"]
    rows: list[str] = []
    for kind in preflight["required_component_kinds"]:
        report = component_reports[kind]
        blockers = report.get("blocking_register_ids") or report.get("register_backing_errors") or ()
        signed = report.get("signed_register_ids") or ()
        rows.append(
            "| {kind} | {state} | {artifact} | {signed} | {blockers} | {path} |".format(
                kind=kind,
                state=report["state"],
                artifact=report.get("artifact_id") or "--",
                signed=", ".join(signed) if signed else "--",
                blockers=", ".join(blockers) if blockers else "--",
                path=report.get("manifest_path") or "--",
            )
        )
    return "\n".join(rows)


def _report_text(preflight: dict[str, object], git_commit: str, input_checksum: str) -> str:
    ready = ", ".join(preflight["accepted_component_kinds"]) or "none"
    blocked = ", ".join(preflight["blocked_component_kinds"]) or "none"
    missing = ", ".join(preflight["missing_component_kinds"]) or "none"
    rows = _table_rows(preflight)
    ready_flag = str(preflight["ready_for_input_assembly"]).lower()
    return f"""# E3.S2 Executable Readiness Preflight

Task: E3.S2 IC-1 NetLoadProvider readiness.  
Status: metadata/preflight only. This packet discovers the component-readiness artifacts currently merged on `origin/main`, routes them through the register-backed executable-input dry run, and reports whether each IC-1 input family is ready, missing, or blocked.

## Boundary

This is not a real IC-1 integration run. It does not load EV, HP, PV, baseline, adoption, or flexibility trajectories; does not aggregate net load; does not call IC-2; does not detect threshold events; does not compute `P(E)`; does not produce a capacity-screen result; and does not add manuscript numbers.

The dry run used the version-controlled input `{INPUT_PATH.as_posix()}` at commit `{git_commit[:12]}`. The standard claim-source manifest for this preflight packet is `{MANIFEST_PATH.as_posix()}`.

## Result

Overall ready for executable input assembly: `{ready_flag}`.

Ready component families: {ready}.  
Blocked component families: {blocked}.  
Missing component families: {missing}.

| Component | State | Artifact | Signed IDs | Blocking IDs | Artifact path |
| --- | --- | --- | --- | --- | --- |
{rows}

## Interpretation

The EV candidate adapter metadata and FLEX-001 scaffold protocol are register-backed enough for this metadata gate. That does not open held-out EV data, certify EV library adequacy, approve real flexibility values, or run any event-based analysis.

Baseline, HP, PV/weather, and adoption are not ready for executable IC-1 aggregation. Baseline still lacks an accepted executable adapter artifact. HP has source and scaling guard material, but D-013 executable values/adoption remain unsigned. D-004 WEATHER-001 source/member material is accepted for internal first-screen source/member use, but PV executable conversion is still blocked by PV-PARAM-001 and paired/cold-spell signoffs. Adoption has approved local counts/allocation governance but the discovered preview is not an accepted executable per-node adoption artifact.

## Reproduction

Command: `{COMMAND}`  
Input SHA-256: `{input_checksum}`  
Generated from git commit: `{git_commit}`

Verification for the PR should still use `./scripts/task.ps1 ownership`, `./scripts/task.ps1 test`, and `git diff --check`.
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