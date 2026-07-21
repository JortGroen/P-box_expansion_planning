from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Sequence
from urllib import request

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.sources import write_metadata

WHEN2HEAT_VERSION = "2023-07-27"
WHEN2HEAT_BASE_URL = f"https://data.open-power-system-data.org/when2heat/{WHEN2HEAT_VERSION}"
WHEN2HEAT_DOI = f"https://doi.org/10.25832/when2heat/{WHEN2HEAT_VERSION}"
WHEN2HEAT_DATASET_PAGE = WHEN2HEAT_BASE_URL
WHEN2HEAT_LICENSE = "Creative Commons Attribution 4.0"
PRIMARY_WHEN2HEAT_FILE_KEY = "csv"
DOWNLOAD_CHUNK_BYTES = 1024 * 1024
CHECKPOINT_EVERY_BYTES = 64 * DOWNLOAD_CHUNK_BYTES


@dataclass(frozen=True)
class When2HeatFileSpec:
    """Concrete OPSD When2Heat file that can be retrieved on request."""

    key: str
    filename: str
    url: str
    description: str
    expected_size_note: str
    listed_size_mb: int | None
    hp_readiness_role: str


WHEN2HEAT_FILES: dict[str, When2HeatFileSpec] = {
    "datapackage": When2HeatFileSpec(
        key="datapackage",
        filename="datapackage.json",
        url=f"{WHEN2HEAT_BASE_URL}/datapackage.json",
        description="OPSD frictionless data package metadata for When2Heat.",
        expected_size_note="small metadata file",
        listed_size_mb=None,
        hp_readiness_role="metadata_for_schema_and_resource_checks",
    ),
    "csv": When2HeatFileSpec(
        key="csv",
        filename="when2heat.csv",
        url=f"{WHEN2HEAT_BASE_URL}/when2heat.csv",
        description="Single-index hourly When2Heat heat-demand and COP time series.",
        expected_size_note="large profile file; OPSD page lists about 313 MB",
        listed_size_mb=313,
        hp_readiness_role="proposed_primary_hp_profile_source",
    ),
    "zip": When2HeatFileSpec(
        key="zip",
        filename=f"opsd-when2heat-{WHEN2HEAT_VERSION}.zip",
        url=f"{WHEN2HEAT_BASE_URL}/opsd-when2heat-{WHEN2HEAT_VERSION}.zip",
        description="Complete OPSD When2Heat data package archive.",
        expected_size_note="large archive; OPSD page lists about 497 MB",
        listed_size_mb=497,
        hp_readiness_role="complete_archive_not_required_for_current_hp_loader",
    ),
}


def write_when2heat_source_metadata(metadata_dir: Path) -> Path:
    """Write metadata-only D-003 provenance without network access."""
    return write_metadata(
        "D-003",
        metadata_dir,
        extra={
            "package_version": WHEN2HEAT_VERSION,
            "doi": WHEN2HEAT_DOI,
            "dataset_page": WHEN2HEAT_DATASET_PAGE,
            "download_performed": False,
            "proposed_primary_file_key": PRIMARY_WHEN2HEAT_FILE_KEY,
            "downloadable_files": {
                key: asdict(spec) for key, spec in sorted(WHEN2HEAT_FILES.items())
            },
            "source_selection_plan": "run with --write-source-selection-plan",
            "e2_s3_boundary": (
                "No concrete When2Heat file is selected by default; run with "
                "--download and record the resulting checksum before using a "
                "downloaded source file in scientific results."
            ),
        },
    )


def build_when2heat_source_selection_plan() -> dict[str, Any]:
    """Return the proposed no-download D-003 file-selection workflow."""
    primary = WHEN2HEAT_FILES[PRIMARY_WHEN2HEAT_FILE_KEY]
    listed_size_mb = primary.listed_size_mb
    minimum_mbps_for_15_min = None
    if listed_size_mb is not None:
        minimum_mbps_for_15_min = round((listed_size_mb * 8) / (15 * 60), 2)
    return {
        "data_id": "D-003",
        "status": (
            "proposed source-selection workflow; no download performed, no "
            "checksum selected, and PI sign-off pending"
        ),
        "created_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "download_performed": False,
        "data_register_status": "proposed",
        "source": "When2Heat, Open Power System Data",
        "package_version": WHEN2HEAT_VERSION,
        "doi": WHEN2HEAT_DOI,
        "dataset_page": WHEN2HEAT_DATASET_PAGE,
        "license": WHEN2HEAT_LICENSE,
        "selected_file_key": PRIMARY_WHEN2HEAT_FILE_KEY,
        "selected_file": asdict(primary),
        "why_selected": [
            "Single-index CSV is directly compatible with the E2.S3 loader.",
            "It contains the hourly heat_profile, heat_demand, and COP columns needed for NL HP profiles.",
            "It is the smallest OPSD-listed complete tabular file for this loader; the zip/archive is not required.",
        ],
        "alternatives_not_selected": {
            key: asdict(spec)
            for key, spec in sorted(WHEN2HEAT_FILES.items())
            if key != PRIMARY_WHEN2HEAT_FILE_KEY
        },
        "runtime_assessment": {
            "listed_size_mb": listed_size_mb,
            "likely_exceeds_15_minutes_by_default": False,
            "minimum_average_network_mbps_for_15_min": minimum_mbps_for_15_min,
            "note": (
                "The primary CSV is listed as 313 MB. Retrieval is not inherently "
                "a >15 minute process on a stable connection above about 3 Mbps, "
                "but Agent C must send a long-run notice before launch if a pilot, "
                "current network conditions, or mirror choice estimate runtime "
                "above 15 minutes. The 497 MB zip is not the proposed primary file."
            ),
        },
        "checksum_workflow": [
            "Request normal network approval before any real download.",
            "Run data/get_when2heat.py --download csv --resume so the file streams into data/raw/when2heat/when2heat.csv.tmp.",
            "Persist download checkpoint metadata under data/metadata/when2heat while streaming.",
            "Compute SHA-256 after completion and atomically replace data/raw/when2heat/when2heat.csv.",
            "Record metadata at data/metadata/when2heat/d003_when2heat_csv_metadata.json.",
            "Update DATA_REGISTER D-003 only after a concrete local file/version/checksum is selected for PI review.",
        ],
        "acceptance_blockers": [
            "Concrete when2heat.csv checksum is not selected.",
            "Shared weather contract path remains unresolved until PI/maintainer action.",
            "Real paired-weather cold-spell sanity evidence is not available.",
        ],
    }


def write_when2heat_source_selection_plan(metadata_dir: Path) -> Path:
    """Write the proposed D-003 source-selection plan without downloading data."""
    write_when2heat_source_metadata(metadata_dir)
    metadata_subdir = metadata_dir / "when2heat"
    metadata_subdir.mkdir(parents=True, exist_ok=True)
    path = metadata_subdir / "d003_when2heat_source_selection_plan.json"
    payload = build_when2heat_source_selection_plan()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(DOWNLOAD_CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _write_download_checkpoint(
    checkpoint_path: Path,
    *,
    spec: When2HeatFileSpec,
    url: str,
    raw_path: Path,
    temp_path: Path,
    status: str,
    bytes_downloaded: int,
    partial_sha256: str | None,
    resume_from_bytes: int,
) -> None:
    payload = {
        "data_id": "D-003",
        "status": status,
        "package_version": WHEN2HEAT_VERSION,
        "selected_file": asdict(spec),
        "retrieved_url": url,
        "raw_path": raw_path.as_posix(),
        "temp_path": temp_path.as_posix(),
        "bytes_downloaded": bytes_downloaded,
        "partial_sha256": partial_sha256,
        "resume_from_bytes": resume_from_bytes,
        "updated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "resume_command": f"data/get_when2heat.py --download {spec.key} --resume",
    }
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def retrieve_when2heat_file(
    key: str,
    *,
    raw_dir: Path,
    metadata_dir: Path,
    url_override: str | None = None,
    timeout_s: float = 120.0,
    resume: bool = False,
    checkpoint_path: Path | None = None,
) -> Path:
    """Download one selected When2Heat file and write checksum metadata.

    The script is intentionally opt-in because the profile files are large and
    D-003 remains proposed until the PI signs a concrete file/version/checksum.
    """
    try:
        spec = WHEN2HEAT_FILES[key]
    except KeyError as exc:
        valid = ", ".join(sorted(WHEN2HEAT_FILES))
        raise ValueError(f"Unknown When2Heat file key {key!r}; valid keys: {valid}") from exc

    url = url_override or spec.url
    raw_dir.mkdir(parents=True, exist_ok=True)
    metadata_subdir = metadata_dir / "when2heat"
    metadata_subdir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / spec.filename
    temp_path = raw_path.with_suffix(raw_path.suffix + ".tmp")
    checkpoint = checkpoint_path or metadata_subdir / f"d003_when2heat_{key}_download_checkpoint.json"

    resume_from_bytes = temp_path.stat().st_size if resume and temp_path.exists() else 0
    headers = {"Range": f"bytes={resume_from_bytes}-"} if resume_from_bytes else {}
    req = request.Request(url, headers=headers)
    size_bytes = 0
    with request.urlopen(req, timeout=timeout_s) as response:
        status = response.getcode()
        append_existing = resume_from_bytes > 0 and status == 206
        if resume_from_bytes > 0 and not append_existing:
            resume_from_bytes = 0
        mode = "ab" if append_existing else "wb"
        size_bytes = resume_from_bytes
        next_checkpoint_at = size_bytes + CHECKPOINT_EVERY_BYTES
        _write_download_checkpoint(
            checkpoint,
            spec=spec,
            url=url,
            raw_path=raw_path,
            temp_path=temp_path,
            status="in_progress",
            bytes_downloaded=size_bytes,
            partial_sha256=_sha256_path(temp_path) if append_existing else None,
            resume_from_bytes=resume_from_bytes,
        )
        with temp_path.open(mode) as handle:
            while True:
                chunk = response.read(DOWNLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                size_bytes += len(chunk)
                handle.write(chunk)
                if size_bytes >= next_checkpoint_at:
                    handle.flush()
                    _write_download_checkpoint(
                        checkpoint,
                        spec=spec,
                        url=url,
                        raw_path=raw_path,
                        temp_path=temp_path,
                        status="in_progress",
                        bytes_downloaded=size_bytes,
                        partial_sha256=_sha256_path(temp_path),
                        resume_from_bytes=resume_from_bytes,
                    )
                    next_checkpoint_at = size_bytes + CHECKPOINT_EVERY_BYTES
    partial_sha256 = _sha256_path(temp_path)
    _write_download_checkpoint(
        checkpoint,
        spec=spec,
        url=url,
        raw_path=raw_path,
        temp_path=temp_path,
        status="download_complete_pending_atomic_replace",
        bytes_downloaded=size_bytes,
        partial_sha256=partial_sha256,
        resume_from_bytes=resume_from_bytes,
    )
    temp_path.replace(raw_path)
    final_sha256 = _sha256_path(raw_path)

    payload = {
        "data_id": "D-003",
        "source": "When2Heat, Open Power System Data",
        "package_version": WHEN2HEAT_VERSION,
        "doi": WHEN2HEAT_DOI,
        "dataset_page": WHEN2HEAT_DATASET_PAGE,
        "selected_file": asdict(spec),
        "retrieved_url": url,
        "retrieved_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "download_performed": True,
        "raw_path": raw_path.as_posix(),
        "sha256_file": final_sha256,
        "size_bytes": size_bytes,
        "license": WHEN2HEAT_LICENSE,
        "data_register_update_required": True,
        "status": "concrete file retrieved; D-003 remains proposed until PI sign-off",
        "checkpoint_path": checkpoint.as_posix(),
        "resume": {
            "enabled": resume,
            "resumed_from_bytes": resume_from_bytes,
            "server_range_status": "partial_content_206" if resume_from_bytes else "not_resumed_or_restarted",
        },
    }
    metadata_path = metadata_subdir / f"d003_when2heat_{key}_metadata.json"
    metadata_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_download_checkpoint(
        checkpoint,
        spec=spec,
        url=url,
        raw_path=raw_path,
        temp_path=temp_path,
        status="complete",
        bytes_downloaded=size_bytes,
        partial_sha256=final_sha256,
        resume_from_bytes=resume_from_bytes,
    )
    return metadata_path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record or retrieve When2Heat source metadata for D-003.")
    parser.add_argument("--metadata-dir", default="data/metadata")
    parser.add_argument("--raw-dir", default="data/raw/when2heat")
    parser.add_argument(
        "--write-source-selection-plan",
        action="store_true",
        help="Write the proposed primary file/checksum workflow without downloading data.",
    )
    parser.add_argument(
        "--download",
        choices=sorted(WHEN2HEAT_FILES),
        help="Opt-in retrieval of one concrete OPSD file. Large files require normal network approval.",
    )
    parser.add_argument("--url", default=None, help="Override URL for controlled tests or mirrors.")
    parser.add_argument("--timeout-s", type=float, default=120.0)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from an existing .tmp file when the server supports HTTP Range requests.",
    )
    parser.add_argument(
        "--checkpoint-path",
        default=None,
        help="Optional explicit path for durable download checkpoint metadata.",
    )
    args = parser.parse_args(argv)

    if args.write_source_selection_plan:
        path = write_when2heat_source_selection_plan(Path(args.metadata_dir))
    elif args.download:
        path = retrieve_when2heat_file(
            args.download,
            raw_dir=Path(args.raw_dir),
            metadata_dir=Path(args.metadata_dir),
            url_override=args.url,
            timeout_s=args.timeout_s,
            resume=args.resume,
            checkpoint_path=Path(args.checkpoint_path) if args.checkpoint_path else None,
        )
    else:
        path = write_when2heat_source_metadata(Path(args.metadata_dir))
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
