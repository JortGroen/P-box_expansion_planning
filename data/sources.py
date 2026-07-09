"""Data acquisition source registry for E2.S1.

The registry is deliberately metadata-first. It records source provenance and
script ownership without downloading raw data before license and URL checks are
complete and signed by the PI.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class SourceSpec:
    """External source metadata tracked by E2.S1."""

    data_id: str
    item: str
    source: str
    doi_url: str
    license: str
    retrieval_script: str
    raw_subdir: str
    notes: str


_SOURCE_SPECS: tuple[SourceSpec, ...] = (
    SourceSpec(
        data_id="D-001",
        item="SimBench benchmark grids and time series",
        source="SimBench dataset paper and package",
        doi_url="DOI/URL to verify in E2.S1",
        license="to check",
        retrieval_script="data/get_simbench.py",
        raw_subdir="simbench",
        notes="Package-backed source; no raw data redistribution without license confirmation.",
    ),
    SourceSpec(
        data_id="D-002",
        item="EV charging behavior",
        source="ElaadNL open datasets",
        doi_url="URL to verify in E2.S1",
        license="to check",
        retrieval_script="data/get_elaadnl.py",
        raw_subdir="elaadnl",
        notes="Metadata-only until URL, license, and checksum workflow are confirmed.",
    ),
    SourceSpec(
        data_id="D-003",
        item="Heat-pump profiles",
        source="When2Heat, Open Power System Data",
        doi_url="DOI 10.25832/when2heat",
        license="to check",
        retrieval_script="data/get_when2heat.py",
        raw_subdir="when2heat",
        notes="Metadata-only until retrieval URL and license are confirmed.",
    ),
    SourceSpec(
        data_id="D-004",
        item="PV and weather inputs",
        source="PVGIS plus KNMI or DWD/ERA5 weather",
        doi_url="URLs to verify in E2.S1",
        license="to check",
        retrieval_script="data/get_weather_pv.py",
        raw_subdir="weather_pv",
        notes="G0 selects KNMI historical winters; PVGIS/KNMI URLs still need verification.",
    ),
    SourceSpec(
        data_id="D-008",
        item="Indicative Dutch unit costs",
        source="Cicenas 2025 TU Delft MSc thesis with Stedin/Eneco context",
        doi_url="URL to verify in E2.S1",
        license="to check",
        retrieval_script="data/get_unit_costs.py",
        raw_subdir="unit_costs",
        notes="Metadata-only until source URL, license, and extraction target are confirmed.",
    ),
)


def source_specs() -> tuple[SourceSpec, ...]:
    """Return E2.S1 source specs in DATA_REGISTER order."""
    return _SOURCE_SPECS


def get_spec(data_id: str) -> SourceSpec:
    """Return one source spec by DATA_REGISTER id."""
    for spec in _SOURCE_SPECS:
        if spec.data_id == data_id:
            return spec
    raise KeyError(f"Unknown data source id: {data_id}")


def write_metadata(
    data_id: str,
    metadata_dir: str | Path = "data/metadata",
    *,
    extra: Mapping[str, object] | None = None,
) -> Path:
    """Write stable source metadata JSON and return the created path.

    Parameters
    ----------
    data_id:
        DATA_REGISTER id such as ``D-001``.
    metadata_dir:
        Directory for generated metadata files.
    extra:
        Optional non-scientific runtime metadata, for example installed package
        version or a note that no download was performed.
    """
    spec = get_spec(data_id)
    directory = Path(metadata_dir)
    directory.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = asdict(spec)
    payload["download_performed"] = False
    payload["status"] = "metadata-only; pending license and URL verification"
    if extra:
        payload["extra"] = dict(sorted(extra.items()))

    path = directory / f"{data_id.lower()}_{spec.raw_subdir}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
