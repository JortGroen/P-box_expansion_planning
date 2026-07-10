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
        extra={
            "decision": "COST-001",
            "pi_supplied_local_pdf": "data/raw/cicenas_2025_thesis.pdf",
            "pi_supplied_pdf_sha256": "96EF9625BA0AFEE2910189A61967943BA3BCD460AE3AC080B847C4D8DD7D99C0",
            "redistribution": "do not commit or redistribute the PDF",
            "extraction_rule": "record value, unit, context, thesis page, table/appendix/section label, source status, intended project use, and PI sign-off for every number",
        },
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
