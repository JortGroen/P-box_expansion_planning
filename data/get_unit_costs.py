from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.sources import write_metadata


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record unit-cost source metadata for E2.S1.")
    parser.add_argument("--metadata-dir", default="data/metadata")
    args = parser.parse_args(argv)

    path = write_metadata(
        "D-008",
        Path(args.metadata_dir),
        extra={"extraction_blocked_until": "source URL and license verification"},
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
