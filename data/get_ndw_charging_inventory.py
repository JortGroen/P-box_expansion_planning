"""Prepare NDW/DOT-NL charging-infrastructure inventory metadata.

The helper is intentionally small and metadata-first. It can summarize a local
NDW OCPI gzip file, but it does not need network access for tests or default
entrypoint execution.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Sequence


ALKMAAR_BBOX = (4.68, 52.59, 4.82, 52.68)
NDW_OCPI_URL = "https://opendata.ndw.nu/charging_point_locations_ocpi.json.gz"
NDW_GEOJSON_BBOX_URL = (
    "https://dotnl.ndw.nu/api/rest/geojson/dynamic-road-status/"
    "charge-point-data/v1/features?bbox=4.68,52.59,4.82,52.68"
)


@dataclass(frozen=True)
class InventorySummary:
    """Count OCPI location, EVSE, and connector units for a selected slice."""

    selector: str
    locations: int
    locations_with_evses: int
    evses: int
    connectors: int
    connectors_missing_power: int
    power_type_counts: dict[str, int]
    connector_standard_counts: dict[str, int]
    max_electric_power_w_counts: dict[str, int]
    bin_around_11kw_10000_12500: int
    bin_around_17kw_16500_17500: int
    bin_around_22kw_21500_22500: int
    dc_connectors_ge_30kw: int


def load_ocpi_locations(path: str | Path) -> list[dict[str, Any]]:
    """Load NDW OCPI locations from a gzip JSON file."""

    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError("Expected NDW OCPI payload to be a JSON list of locations")
    return payload


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 hex digest of a file."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def filter_locations_by_city(
    locations: Iterable[dict[str, Any]],
    city: str,
) -> list[dict[str, Any]]:
    """Select OCPI locations whose free-text city matches exactly, case-insensitively."""

    expected = city.casefold()
    return [
        location
        for location in locations
        if str(location.get("city") or "").strip().casefold() == expected
    ]


def _location_lon_lat(location: dict[str, Any]) -> tuple[float, float] | None:
    coordinates = location.get("coordinates") or {}
    try:
        return float(coordinates["longitude"]), float(coordinates["latitude"])
    except (KeyError, TypeError, ValueError):
        return None


def filter_locations_by_bbox(
    locations: Iterable[dict[str, Any]],
    bbox: Sequence[float],
) -> list[dict[str, Any]]:
    """Select OCPI locations inside ``min_lon, min_lat, max_lon, max_lat``."""

    if len(bbox) != 4:
        raise ValueError("bbox must contain min_lon, min_lat, max_lon, max_lat")
    min_lon, min_lat, max_lon, max_lat = map(float, bbox)
    if min_lon > max_lon or min_lat > max_lat:
        raise ValueError("bbox min values must not exceed max values")
    selected: list[dict[str, Any]] = []
    for location in locations:
        lon_lat = _location_lon_lat(location)
        if lon_lat is None:
            continue
        lon, lat = lon_lat
        if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
            selected.append(location)
    return selected


def summarize_ocpi_locations(
    locations: Iterable[dict[str, Any]],
    *,
    selector: str,
) -> InventorySummary:
    """Summarize location, EVSE, connector, and connector-power units."""

    location_list = list(locations)
    power_counts: Counter[int] = Counter()
    power_type_counts: Counter[str] = Counter()
    standard_counts: Counter[str] = Counter()
    evse_count = 0
    connector_count = 0
    missing_power = 0
    locations_with_evses = 0

    for location in location_list:
        evses = list(location.get("evses") or [])
        if evses:
            locations_with_evses += 1
        evse_count += len(evses)
        for evse in evses:
            for connector in list(evse.get("connectors") or []):
                connector_count += 1
                power_type_counts[str(connector.get("power_type"))] += 1
                standard_counts[str(connector.get("standard"))] += 1
                power = connector.get("max_electric_power")
                if power is None:
                    missing_power += 1
                else:
                    power_counts[int(power)] += 1

    # These bins are diagnostic only: they make the EV-008 22 kW question
    # auditable without collapsing the full connector-power distribution.
    def between(low_w: int, high_w: int) -> int:
        return sum(count for power, count in power_counts.items() if low_w <= power <= high_w)

    return InventorySummary(
        selector=selector,
        locations=len(location_list),
        locations_with_evses=locations_with_evses,
        evses=evse_count,
        connectors=connector_count,
        connectors_missing_power=missing_power,
        power_type_counts=dict(sorted(power_type_counts.items())),
        connector_standard_counts=dict(sorted(standard_counts.items())),
        max_electric_power_w_counts={str(k): v for k, v in sorted(power_counts.items())},
        bin_around_11kw_10000_12500=between(10_000, 12_500),
        bin_around_17kw_16500_17500=between(16_500, 17_500),
        bin_around_22kw_21500_22500=between(21_500, 22_500),
        dc_connectors_ge_30kw=sum(
            count for power, count in power_counts.items() if power >= 30_000
        ),
    )


def build_metadata(
    *,
    input_gzip: str | Path | None = None,
    city: str = "Alkmaar",
    bbox: Sequence[float] = ALKMAAR_BBOX,
    geojson_bbox: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the D-012 metadata payload without requiring network access."""

    payload: dict[str, Any] = {
        "schema_version": 1,
        "data_id": "D-012",
        "task": "E2.S2",
        "created_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "status": "proposed_not_pi_signed",
        "source": {
            "name": "NDW/DOT-NL laadpunten open data",
            "docs_url": "https://docs.ndw.nu/data-uitwisseling/interface-beschrijvingen/dafne-api/dafne_api_consumer_pull/",
            "ocpi_full_dataset_url": NDW_OCPI_URL,
            "geojson_bbox_url": NDW_GEOJSON_BBOX_URL,
            "license_note": "NDW copyright page states CC0 applies to website content unless otherwise stated; this packet commits only metadata and parser code, not the raw live dataset.",
        },
        "selection": {
            "city_exact_match": city,
            "bbox_min_lon_min_lat_max_lon_max_lat": list(map(float, bbox)),
            "municipality_boundary_note": "The NDW OCPI file exposes city strings and coordinates but no CBS municipality code; exact GM0361 counts require an external boundary join.",
        },
        "download_performed_by_script": input_gzip is not None,
        "non_actions": [
            "No ElaadNL public Set B profile was generated.",
            "No EV held-out batch was opened.",
            "No integrated net-load, congestion, event, adequacy, P(E), or manuscript-result analysis was run.",
        ],
    }
    if input_gzip is not None:
        path = Path(input_gzip)
        locations = load_ocpi_locations(path)
        city_locations = filter_locations_by_city(locations, city)
        bbox_locations = filter_locations_by_bbox(locations, bbox)
        city_ids = {str(location.get("id")) for location in city_locations}
        bbox_ids = {str(location.get("id")) for location in bbox_locations}
        payload["ocpi_full_dataset"] = {
            "path_used_locally": str(path),
            "size_bytes": path.stat().st_size,
            "sha256_gzip": sha256_file(path),
            "location_count_netherlands": len(locations),
        }
        payload["summaries"] = {
            "city_exact_match": asdict(
                summarize_ocpi_locations(city_locations, selector=f"city == {city}")
            ),
            "bbox": asdict(
                summarize_ocpi_locations(
                    bbox_locations,
                    selector="bbox == 4.68,52.59,4.82,52.68",
                )
            ),
            "overlap": {
                "city_locations_inside_bbox": len(city_ids & bbox_ids),
                "city_locations_outside_bbox": len(city_ids - bbox_ids),
                "bbox_locations_outside_city_exact_match": len(bbox_ids - city_ids),
            },
        }
    if geojson_bbox:
        payload["geojson_bbox_response"] = dict(geojson_bbox)
    return payload


def write_metadata(
    metadata_dir: str | Path = "data/metadata/ev_adoption",
    *,
    input_gzip: str | Path | None = None,
    geojson_bbox: dict[str, Any] | None = None,
) -> Path:
    """Write the D-012 NDW inventory metadata JSON."""

    directory = Path(metadata_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "ndw_alkmaar_public_charging_inventory_metadata.json"
    payload = build_metadata(input_gzip=input_gzip, geojson_bbox=geojson_bbox)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata-dir", default="data/metadata/ev_adoption")
    parser.add_argument("--input-gzip", default=None)
    args = parser.parse_args()

    print(write_metadata(args.metadata_dir, input_gzip=args.input_gzip))


if __name__ == "__main__":
    main()
