from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Sequence
from urllib import request

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.sources import write_metadata

WHEN2HEAT_VERSION = "2023-07-27"
WHEN2HEAT_BASE_URL = f"https://data.open-power-system-data.org/when2heat/{WHEN2HEAT_VERSION}"


@dataclass(frozen=True)
class When2HeatFileSpec:
    """Concrete OPSD When2Heat file that can be retrieved on request."""

    key: str
    filename: str
    url: str
    description: str
    expected_size_note: str


WHEN2HEAT_FILES: dict[str, When2HeatFileSpec] = {
    "datapackage": When2HeatFileSpec(
        key="datapackage",
        filename="datapackage.json",
        url=f"{WHEN2HEAT_BASE_URL}/datapackage.json",
        description="OPSD frictionless data package metadata for When2Heat.",
        expected_size_note="small metadata file",
    ),
    "csv": When2HeatFileSpec(
        key="csv",
        filename="when2heat.csv",
        url=f"{WHEN2HEAT_BASE_URL}/when2heat.csv",
        description="Single-index hourly When2Heat heat-demand and COP time series.",
        expected_size_note="large profile file; OPSD page lists about 313 MB",
    ),
    "zip": When2HeatFileSpec(
        key="zip",
        filename=f"opsd-when2heat-{WHEN2HEAT_VERSION}.zip",
        url=f"{WHEN2HEAT_BASE_URL}/opsd-when2heat-{WHEN2HEAT_VERSION}.zip",
        description="Complete OPSD When2Heat data package archive.",
        expected_size_note="large archive; OPSD page lists about 497 MB",
    ),
}


def write_when2heat_source_metadata(metadata_dir: Path) -> Path:
    """Write metadata-only D-003 provenance without network access."""
    return write_metadata(
        "D-003",
        metadata_dir,
        extra={
            "package_version": WHEN2HEAT_VERSION,
            "download_performed": False,
            "downloadable_files": {
                key: asdict(spec) for key, spec in sorted(WHEN2HEAT_FILES.items())
            },
            "e2_s3_boundary": (
                "No concrete When2Heat file is selected by default; run with "
                "--download and record the resulting checksum before using a "
                "downloaded source file in scientific results."
            ),
        },
    )


def retrieve_when2heat_file(
    key: str,
    *,
    raw_dir: Path,
    metadata_dir: Path,
    url_override: str | None = None,
    timeout_s: float = 120.0,
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

    digest = hashlib.sha256()
    size_bytes = 0
    with request.urlopen(url, timeout=timeout_s) as response, temp_path.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size_bytes += len(chunk)
            handle.write(chunk)
    temp_path.replace(raw_path)

    payload = {
        "data_id": "D-003",
        "source": "When2Heat, Open Power System Data",
        "package_version": WHEN2HEAT_VERSION,
        "selected_file": asdict(spec),
        "retrieved_url": url,
        "retrieved_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "download_performed": True,
        "raw_path": raw_path.as_posix(),
        "sha256_file": digest.hexdigest(),
        "size_bytes": size_bytes,
        "license": "Creative Commons Attribution 4.0",
        "data_register_update_required": True,
        "status": "concrete file retrieved; D-003 remains proposed until PI sign-off",
    }
    metadata_path = metadata_subdir / f"d003_when2heat_{key}_metadata.json"
    metadata_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return metadata_path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record or retrieve When2Heat source metadata for D-003.")
    parser.add_argument("--metadata-dir", default="data/metadata")
    parser.add_argument("--raw-dir", default="data/raw/when2heat")
    parser.add_argument(
        "--download",
        choices=sorted(WHEN2HEAT_FILES),
        help="Opt-in retrieval of one concrete OPSD file. Large files require normal network approval.",
    )
    parser.add_argument("--url", default=None, help="Override URL for controlled tests or mirrors.")
    parser.add_argument("--timeout-s", type=float, default=120.0)
    args = parser.parse_args(argv)

    if args.download:
        path = retrieve_when2heat_file(
            args.download,
            raw_dir=Path(args.raw_dir),
            metadata_dir=Path(args.metadata_dir),
            url_override=args.url,
            timeout_s=args.timeout_s,
        )
    else:
        path = write_when2heat_source_metadata(Path(args.metadata_dir))
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
