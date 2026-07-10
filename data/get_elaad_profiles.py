from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.sources import write_metadata


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Record ElaadNL profile-generator metadata for E2.S1."
    )
    parser.add_argument("--metadata-dir", default="data/metadata/elaad_profiles")
    args = parser.parse_args(argv)

    path = write_metadata(
        "D-002",
        Path(args.metadata_dir),
        extra={
            "generation_spec": "reports/elaad_profile_generation_spec.md",
            "next_step": "one-profile API probe before bulk generation",
        },
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
