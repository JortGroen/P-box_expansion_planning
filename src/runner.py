"""Bootstrap runner used only to verify E0 wiring.

The full IC-5 ExperimentRunner is a later Agent C deliverable. This smoke
runner deliberately produces a non-scientific output and manifest so `make run`
has a harmless target from day one.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from src.manifest import write_manifest


def main(argv: Sequence[str] | None = None) -> int:
    """Run the bootstrap manifest smoke target."""
    parser = argparse.ArgumentParser(description="Run the E0 bootstrap smoke target.")
    parser.add_argument("config_path")
    parser.add_argument("--output-dir", default="experiments/bootstrap")
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    smoke_output = output_dir / "bootstrap_output.txt"
    smoke_output.write_text(
        "bootstrap manifest smoke run; not a scientific experiment\n",
        encoding="utf-8",
    )
    write_manifest(
        output_dir,
        config_path=args.config_path,
        seeds={"root": 0},
        output_paths=[smoke_output],
        extra={"task": "E0.S3", "scientific_result": False},
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

