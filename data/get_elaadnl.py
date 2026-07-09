from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from data.sources import write_metadata


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record ElaadNL source metadata for E2.S1.")
    parser.add_argument("--metadata-dir", default="data/metadata")
    args = parser.parse_args(argv)

    path = write_metadata(
        "D-002",
        Path(args.metadata_dir),
        extra={"download_blocked_until": "license and source URL verification"},
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
