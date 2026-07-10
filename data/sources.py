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
        source="SimBench package and official repository",
        doi_url="https://github.com/e2nIEE/simbench; package pin simbench==1.6.2",
        license="Database: ODbL 1.0 with DbCL 1.0 contents; code: BSD-3-Clause",
        retrieval_script="data/get_simbench.py",
        raw_subdir="simbench",
        notes="No raw download: use the pinned package source; raw redistribution is not committed.",
    ),
    SourceSpec(
        data_id="D-002",
        item="EV charging behavior profiles",
        source="ElaadNL Laadprofielengenerator generated profiles",
        doi_url="Dashboard https://charging.elaad.nl/; API docs https://api.charging.data.elaad.nl/docs#; generation spec reports/elaad_profile_generation_spec.md",
        license="Terms of use for generated profiles still to verify before redistribution or manuscript data-availability claims",
        retrieval_script="data/get_elaad_profiles.py",
        raw_subdir="elaad_profiles",
        notes="EV-001 approved profile-generator route; one-profile probe completed for simulated_year=2033; bulk generation still blocked pending terms/source sign-off.",
    ),
    SourceSpec(
        data_id="D-003",
        item="Heat-pump profiles",
        source="When2Heat, Open Power System Data",
        doi_url="https://doi.org/10.25832/when2heat/2023-07-27; https://data.open-power-system-data.org/when2heat/",
        license="Creative Commons Attribution 4.0",
        retrieval_script="data/get_when2heat.py",
        raw_subdir="when2heat",
        notes="No raw download in T2-T3; checksum must be recorded after selecting and downloading a concrete file.",
    ),
    SourceSpec(
        data_id="D-004",
        item="PV and weather inputs",
        source="PVGIS plus KNMI historical weather",
        doi_url="PVGIS: https://re.jrc.ec.europa.eu/pvg_tools/en/; KNMI API: https://developer.dataplatform.knmi.nl/open-data-api",
        license="PVGIS: free/no restrictions; KNMI 10-minute in-situ dataset: CC-BY-4.0",
        retrieval_script="data/get_weather_pv.py",
        raw_subdir="weather_pv",
        notes="No raw download in T2-T3; checksum must be recorded after selecting and downloading concrete PVGIS/KNMI files.",
    ),
    SourceSpec(
        data_id="D-008",
        item="Indicative Dutch unit costs",
        source="Cicenas 2025 TU Delft MSc thesis with Stedin/Eneco context",
        doi_url="Source URL/file required from PI; verified literature-review anchor exists",
        license="Unclear until thesis source URL/file and reuse terms are confirmed",
        retrieval_script="data/get_unit_costs.py",
        raw_subdir="unit_costs",
        notes="No extraction until PI supplies or approves the source URL/file and license terms.",
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
    payload["status"] = "metadata-only; pending license/API verification and PI sign-off before data use"
    if extra:
        payload["extra"] = dict(sorted(extra.items()))

    path = directory / f"{data_id.lower()}_{spec.raw_subdir}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
