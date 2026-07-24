"""Generate the E3.S2b decision-transformer capacity provenance packet."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.evaluator_capacity import CapacityProvenanceConfig, collect_capacity_provenance
from src.grid_loader import load_candidate_grid
from src.manifest import build_manifest, sha256_file

INPUT_PATH = Path("reports/e3_s2b_capacity_provenance_input.json")
COMMAND = ".\\.venv\\Scripts\\python.exe reports\\e3_s2b_generate_capacity_provenance.py"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def json_ready(value: Any) -> Any:
    if isinstance(value, tuple):
        return [json_ready(item) for item in value]
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    return value


def supporting_checksums(paths: tuple[str, ...]) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for path in paths:
        checksums[path] = sha256_file(REPO_ROOT / path)
    return dict(sorted(checksums.items()))


def _rows(records: tuple[Mapping[str, object], ...], columns: tuple[str, ...]) -> str:
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for record in records:
        lines.append("| " + " | ".join(_format(record.get(column, "--")) for column in columns) + " |")
    return "\n".join(lines)


def _blocker_rows(packet: Mapping[str, object]) -> str:
    items = tuple(packet["blocker_manifest"]["items"])
    if not items:
        return "| code | blocker IDs | message |\n| --- | --- | --- |\n| none | -- | -- |"
    lines = ["| code | blocker IDs | message |", "| --- | --- | --- |"]
    for item in items:
        lines.append(
            "| {code} | {ids} | {message} |".format(
                code=item["code"],
                ids=", ".join(item.get("blocker_ids", ())) or "--",
                message=item["message"],
            )
        )
    return "\n".join(lines)


def _format(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, (tuple, list)):
        return ", ".join(_format(item) for item in value)
    return str(value)


def report_text(
    *,
    payload: Mapping[str, object],
    packet: Mapping[str, object],
    manifest_path: Path,
    packet_path: Path,
    support_sha: Mapping[str, str],
    git_commit: str,
) -> str:
    capacity = packet["capacity_provenance"]
    metadata = capacity["metadata"]
    support_rows = "\n".join(f"| {path} | {sha} |" for path, sha in support_sha.items())
    reporting_rows = _rows(tuple(capacity["raw_mva_reporting_fields"]), ("field", "unit", "denominator_field", "meaning"))
    transformer_rows = _rows(tuple(packet["transformer_records"]), ("trafo_index", "name", "hv_bus", "lv_bus", "sn_mva", "sn_kva", "parallel", "tap_pos", "in_service"))
    switch_rows = _rows(tuple(packet["switch_records"]), ("switch_index", "role", "bus", "element", "et", "closed", "type", "name"))
    return f"""# E3.S2b Capacity Provenance

Task: E3.S2b future-layer capacity/domain screen prerequisite.
Status: metadata/provenance packet only. This report records decision-transformer capacity facts for PI review and later E3.S2b pre-run readiness. It does not choose total versus firm capacity.

## Boundary

This packet does not load component trajectories, aggregate real net load, execute IC-2, detect events, compute `P(E)`, use A-013/G2 numerical values, classify capacity/domain cases, choose a denominator, or produce manuscript numbers. The values below are grid input/provenance facts needed before a later capacity/domain screen can report raw MVA under both conventions.

## Evidence

- Versioned input: `{INPUT_PATH.as_posix()}`
- Machine-readable capacity packet: `{packet_path.as_posix()}`
- Claim-source manifest: `{manifest_path.as_posix()}`
- Generated from git commit: `{git_commit}`
- Command: `{payload['command']}`

## Capacity Packet Summary

| Field | Value |
| --- | --- |
| Field-complete for PI review / later E3.S2b use | `{str(packet['ready_for_e3_s2b_capacity_prerun']).lower()}` |
| Status | `{packet['status']}` |
| Grid | `{metadata['grid_code']}` |
| Decision asset | `{metadata['decision_asset_id']}` |
| Transformer indices | `{_format(capacity['transformer_indices'])}` |
| Unit nameplates | `{_format(capacity['unit_nameplate_kva'])}` kVA |
| Total aggregate nameplate | `{_format(capacity['total_nameplate_kva'])}` kVA |
| Firm `(n-1)` aggregate nameplate | `{_format(capacity['firm_n_minus_1_nameplate_kva'])}` kVA |
| Firm outage convention | {capacity['firm_outage_convention']} |
| Capacity convention status | `{capacity['convention_status']}` |
| Busbar/tie status | {metadata['busbar_parallel_status']} |
| Firm primary follow-up | Actual one-transformer-out AC validation required before firm primary use |

## Transformer Records

{transformer_rows}

## Switch Records

{switch_rows}

## Future E3.S2b Raw-MVA Reporting Fields

{reporting_rows}

The future E3.S2b screen must report raw import/export MVA and both loading ratios for every predeclared case. These fields are reporting obligations only; they do not select a denominator or classify a case.

## Blocker Manifest

{_blocker_rows(packet)}

## Supporting Evidence Checksums

| Path | SHA-256 |
| --- | --- |
{support_rows}

## Interpretation

The selected primary-grid decision transformer is a two-unit 40 MVA + 40 MVA bank with the configured busbar/tie and transformer circuit-breaker switches closed. The candidate total-nameplate denominator is 80 MVA. The candidate firm diagnostic denominator records largest-unit-out `(n-1)` nameplate as 40 MVA. G1-A2 keeps both conventions open until the later manifested E3.S2b screen reports raw MVA and both ratios before probabilistic-result inspection.

Firm 40 MVA use here remains a provenance and diagnostic convention. If the PI later selects firm capacity as the primary criterion, E3.S3 must validate the actual one-transformer-out AC topology before paper-use results.
"""


def main() -> None:
    payload = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    git_status_before_generation = git("status", "--short")
    config = CapacityProvenanceConfig.from_mapping(payload)
    outputs = payload["outputs"]
    packet_path = Path(outputs["packet_path"])
    report_path = Path(outputs["report_path"])
    manifest_path = Path(outputs["manifest_path"])

    net = load_candidate_grid(config.grid_key)
    packet = collect_capacity_provenance(net, config).manifest_record()
    support_sha = supporting_checksums(config.supporting_evidence_paths)
    packet["supporting_evidence_sha256_by_path"] = support_sha
    packet["generated_at_utc"] = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    packet_path.write_text(json.dumps(json_ready(packet), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    git_commit = git("rev-parse", "HEAD")
    report_path.write_text(
        report_text(
            payload=payload,
            packet=packet,
            manifest_path=manifest_path,
            packet_path=packet_path,
            support_sha=support_sha,
            git_commit=git_commit,
        ),
        encoding="utf-8",
    )
    manifest = build_manifest(
        config_path=INPUT_PATH,
        seeds={"none": "deterministic"},
        output_paths=(packet_path, report_path),
        extra={
            "artifact_type": "e3_s2b_capacity_provenance",
            "task_id": "E3.S2b",
            "command": COMMAND,
            "git_status_short_before_generation": git_status_before_generation,
            "capacity_packet_path": packet_path.as_posix(),
            "report_path": report_path.as_posix(),
            "ready_for_e3_s2b_capacity_prerun": packet["ready_for_e3_s2b_capacity_prerun"],
            "supporting_evidence_sha256_by_path": support_sha,
        },
    )
    manifest_path.write_text(json.dumps(json_ready(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()