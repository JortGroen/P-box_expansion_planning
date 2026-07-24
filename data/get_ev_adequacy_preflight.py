from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.ev_model import e3_s2a_ev_heldout_adequacy_preflight_blockers

DEFAULT_ACCEPTED_INDEX = Path(
    "data/metadata/ev_adoption/e2_s2_ev_ic1_accepted_artifact_index_preflight.json"
)
DEFAULT_CRITERION_PACKET = Path(
    "data/metadata/ev_adoption/e3_s2a_ev_adequacy_criterion_packet.json"
)
DEFAULT_OUTPUT = Path(
    "data/metadata/ev_adoption/e3_s2a_ev_heldout_adequacy_preflight_blockers.json"
)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def git_blob_or_file_sha256(path: Path) -> str:
    """Return a stable committed-blob hash, falling back to file bytes for new files."""

    repo_path = path.as_posix()
    try:
        blob = subprocess.check_output(
            ["git", "show", f"HEAD:{repo_path}"],
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        blob = path.read_bytes()
    return hashlib.sha256(blob).hexdigest()


def build_preflight_from_paths(
    *,
    accepted_index_path: Path = DEFAULT_ACCEPTED_INDEX,
    criterion_packet_path: Path = DEFAULT_CRITERION_PACKET,
    local_candidate_output_checksums_verified: bool = False,
) -> dict[str, object]:
    """Build the E3.S2a EV adequacy blocker manifest from committed metadata."""

    accepted_index = _load_json(accepted_index_path)
    criterion_packet = _load_json(criterion_packet_path)
    return e3_s2a_ev_heldout_adequacy_preflight_blockers(
        accepted_index,
        criterion_packet,
        accepted_artifact_index_path=accepted_index_path.as_posix(),
        accepted_artifact_index_sha256=git_blob_or_file_sha256(accepted_index_path),
        criterion_packet_path=criterion_packet_path.as_posix(),
        criterion_packet_sha256=git_blob_or_file_sha256(criterion_packet_path),
        local_candidate_output_checksums_verified=local_candidate_output_checksums_verified,
    )


def write_preflight_manifest(
    output_path: Path = DEFAULT_OUTPUT,
    *,
    accepted_index_path: Path = DEFAULT_ACCEPTED_INDEX,
    criterion_packet_path: Path = DEFAULT_CRITERION_PACKET,
    local_candidate_output_checksums_verified: bool = False,
) -> dict[str, object]:
    """Write the deterministic EV held-out adequacy preflight blocker manifest."""

    manifest = build_preflight_from_paths(
        accepted_index_path=accepted_index_path,
        criterion_packet_path=criterion_packet_path,
        local_candidate_output_checksums_verified=local_candidate_output_checksums_verified,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the fail-closed E3.S2a EV held-out adequacy preflight blocker "
            "manifest without opening held-out/quarantined data."
        )
    )
    parser.add_argument("--accepted-index", type=Path, default=DEFAULT_ACCEPTED_INDEX)
    parser.add_argument("--criterion-packet", type=Path, default=DEFAULT_CRITERION_PACKET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--local-candidate-output-checksums-verified",
        action="store_true",
        help=(
            "Record that candidate component-output NPZ checksums were verified in this worktree. "
            "This still does not authorize held-out access or integrated adequacy."
        ),
    )
    args = parser.parse_args(argv)
    manifest = write_preflight_manifest(
        args.output,
        accepted_index_path=args.accepted_index,
        criterion_packet_path=args.criterion_packet,
        local_candidate_output_checksums_verified=args.local_candidate_output_checksums_verified,
    )
    print(json.dumps({"output": args.output.as_posix(), "blocked": manifest["blocked"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
