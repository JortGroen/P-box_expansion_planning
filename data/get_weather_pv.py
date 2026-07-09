from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from data.sources import write_metadata


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record KNMI/PVGIS source metadata for E2.S1.")
    parser.add_argument("--metadata-dir", default="data/metadata")
    args = parser.parse_args(argv)

    path = write_metadata(
        "D-004",
        Path(args.metadata_dir),
        extra={"g0_weather_scope": "KNMI historical winters including at least one design-cold winter"},
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
