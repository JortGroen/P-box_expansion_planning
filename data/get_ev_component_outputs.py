from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.ev_model import materialize_ev_ic1_candidate_component_outputs


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
DEFAULT_OUTPUT_DIR = Path("data/processed/elaad_profiles/component_outputs")
RESTORE_INSTRUCTION = (
    "Restore the ignored candidate processed-profile NPZ files listed above "
    "under data/processed/elaad_profiles from the verified local artifact store, "
    "or ask the PI before regenerating ElaadNL source batches. Then rerun "
    ".\\.venv\\Scripts\\python.exe data\\get_ev_component_outputs.py rebuild."
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


def missing_candidate_processed_paths(
    checksum_preflight: Mapping[str, Any],
    *,
    base_dir: Path,
) -> tuple[str, ...]:
    """Return missing candidate profile files required before any EV array loading."""

    verification = checksum_preflight.get("verification")
    if not isinstance(verification, dict):
        raise EVComponentOutputVerificationError("Checksum preflight lacks verification metadata")
    batch_records = verification.get("verified_candidate_batches")
    if not isinstance(batch_records, list) or not batch_records:
        raise EVComponentOutputVerificationError("Checksum preflight lacks verified candidate batches")
    missing: list[str] = []
    for record in batch_records:
        if not isinstance(record, dict):
            raise EVComponentOutputVerificationError("Checksum preflight batch records must be objects")
        processed_path = str(record.get("processed_path", ""))
        if not processed_path:
            raise EVComponentOutputVerificationError("Checksum preflight batch record lacks processed_path")
        if not (base_dir / processed_path).is_file():
            missing.append(processed_path)
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
) -> dict[str, object]:
    """Rebuild ignored EV component outputs and compare them to committed checksums."""

    missing = missing_candidate_processed_paths(checksum_preflight, base_dir=base_dir)
    if missing:
        raise EVComponentOutputVerificationError(
            "Missing candidate processed-profile NPZ files required before EV array loading:\n"
            + "\n".join(f"- {path}" for path in missing)
            + "\n"
            + RESTORE_INSTRUCTION
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
    return {
        "status": "verified",
        "mode": "rebuild",
        "rebuilt_output_count": len(expected_by_scenario),
        "manifest": observed_manifest,
    }


def _default_timestamp_utc() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify or rebuild ignored candidate-only EV component-output NPZs "
            "from committed metadata. This command never fetches or regenerates "
            "ElaadNL source data."
        )
    )
    parser.add_argument("mode", choices=("verify", "rebuild"))
    parser.add_argument("--base-dir", type=Path, default=Path("."))
    parser.add_argument("--component-input-scaffold", type=Path, default=DEFAULT_COMPONENT_INPUT_SCAFFOLD)
    parser.add_argument("--checksum-preflight", type=Path, default=DEFAULT_CHECKSUM_PREFLIGHT)
    parser.add_argument("--selection-manifest-set", type=Path, default=DEFAULT_SELECTION_MANIFEST_SET)
    parser.add_argument("--component-output-manifest", type=Path, default=DEFAULT_COMPONENT_OUTPUT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
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
        else:
            result = rebuild_and_verify_ev_component_outputs(
                component_input_scaffold=_load_json(base_dir / args.component_input_scaffold),
                checksum_preflight=_load_json(base_dir / args.checksum_preflight),
                selection_manifest_set=_load_json(base_dir / args.selection_manifest_set),
                committed_component_output_manifest=component_output_manifest,
                base_dir=base_dir,
                output_dir=args.output_dir,
                timestamp_utc=args.timestamp_utc or _default_timestamp_utc(),
            )
    except EVComponentOutputVerificationError as exc:
        print(str(exc))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
