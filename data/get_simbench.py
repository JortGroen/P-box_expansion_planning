from __future__ import annotations

import argparse
from importlib import metadata
from pathlib import Path
from typing import Sequence

from data.sources import write_metadata


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record SimBench source metadata for E2.S1.")
    parser.add_argument("--metadata-dir", default="data/metadata")
    args = parser.parse_args(argv)

    try:
        version = metadata.version("simbench")
    except metadata.PackageNotFoundError:
        version = "not-installed"

    path = write_metadata(
        "D-001",
        Path(args.metadata_dir),
        extra={"simbench_package_version": version},
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
