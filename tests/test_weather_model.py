from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from src.hp_model import (
    When2HeatComponent,
    When2HeatHourlyProfile,
    align_heat_pump_profile,
    downscale_hourly_to_15min,
)
from src.pv_model import PVSystemConfig, generate_pv_profile
from src.weather_model import (
    WeatherMember,
    assert_same_weather_realization,
    canonical_15min_local_axis_for_year,
    canonical_15min_utc_axis_for_local_year,
    validate_canonical_15min_calendar,
)


def _short_weather(
    *,
    member_id: str = "knmi_249_2025",
    shared_weather_driver_id: str = "d004_alkmaar_berkhout_2014_2023_v1:2025",
    ghi: list[float] | None = None,
    provenance: dict[str, object] | None = None,
) -> WeatherMember:
    timestamps_utc = tuple(datetime(2025, 1, 1, tzinfo=UTC) + timedelta(minutes=15 * index) for index in range(4))
    local_zone = canonical_15min_local_axis_for_year(2025)[0].tzinfo
    timestamps_local = tuple(item.astimezone(local_zone) for item in timestamps_utc)
    return WeatherMember(
        member_id=member_id,
        shared_weather_driver_id=shared_weather_driver_id,
        source="knmi_station_249_plus_pvgis_sarah3",
        timestamps_utc=timestamps_utc,
        timestamps_local=timestamps_local,
        temperature_c=[4.0, 4.5, 5.0, 5.5],
        pv_weather_fields={
            "ghi_w_per_m2": ghi or [0.0, 100.0, 200.0, 300.0],
            "poa_global_w_per_m2": [0.0, 120.0, 230.0, 340.0],
        },
        provenance=provenance
        or {
            "knmi_station_id": 249,
            "knmi_sha256": "f83f255b4f1b7a1f48dba935f8396a99989fa600364425e3a45b6b5218dd4f0e",
            "pvgis_sha256": "dca94839809cefd165edd964ddd269fbf6cc9fde7c5875905a84eb0ae830e2dc",
        },
        metadata={"selection_id": "d004_alkmaar_berkhout_2014_2023_v1"},
    )


def test_weather_member_preserves_one_utc_local_calendar_and_pairing() -> None:
    timestamps_utc = canonical_15min_utc_axis_for_local_year(2025)
    timestamps_local = canonical_15min_local_axis_for_year(2025)
    member = WeatherMember(
        member_id="knmi_249_2025",
        shared_weather_driver_id="d004_alkmaar_berkhout_2014_2023_v1:2025",
        source="knmi_station_249_plus_pvgis_sarah3",
        timestamps_utc=timestamps_utc,
        timestamps_local=timestamps_local,
        temperature_c=np.full(len(timestamps_utc), 8.0),
        pv_weather_fields={"ghi_w_per_m2": np.zeros(len(timestamps_utc))},
        provenance={"knmi_station_id": 249},
    )

    validate_canonical_15min_calendar(member, local_year=2025)
    record = member.identity_record()

    assert member.n_timesteps == 35_040
    assert member.cadence_seconds == 900
    assert record["member_id"] == "knmi_249_2025"
    assert record["shared_weather_driver_id"] == "d004_alkmaar_berkhout_2014_2023_v1:2025"
    assert record["temperature_field"] == "temperature_c"
    assert record["pv_weather_field_names"] == ("ghi_w_per_m2",)
    assert len(record["content_sha256"]) == 64
    assert timestamps_local[0].isoformat() == "2025-01-01T00:00:00+01:00"


def test_weather_member_rejects_separate_or_malformed_weather_paths() -> None:
    timestamps_utc = (
        datetime(2025, 1, 1, 0, 15, tzinfo=UTC),
        datetime(2025, 1, 1, 0, 0, tzinfo=UTC),
    )
    timestamps_local = tuple(item.astimezone(canonical_15min_local_axis_for_year(2025)[0].tzinfo) for item in timestamps_utc)

    with pytest.raises(ValueError, match="chronological"):
        WeatherMember(
            member_id="bad",
            shared_weather_driver_id="driver",
            source="knmi",
            timestamps_utc=timestamps_utc,
            timestamps_local=timestamps_local,
            temperature_c=[1.0, 1.0],
            pv_weather_fields={"ghi_w_per_m2": [0.0, 0.0]},
        )

    with pytest.raises(ValueError, match="ghi_w_per_m2"):
        WeatherMember(
            member_id="temperature-only",
            shared_weather_driver_id="driver",
            source="knmi",
            timestamps_utc=tuple(reversed(timestamps_utc)),
            timestamps_local=tuple(reversed(timestamps_local)),
            temperature_c=[1.0, 1.0],
            pv_weather_fields={"temperature_duplicate": [1.0, 1.0]},
        )

    with pytest.raises(ValueError, match="non-negative"):
        _short_weather(ghi=[0.0, -1.0, 0.0, 0.0])


def test_content_identity_changes_with_weather_or_provenance() -> None:
    baseline = _short_weather()
    changed_irradiance = _short_weather(ghi=[0.0, 100.0, 200.0, 301.0])
    changed_provenance = _short_weather(provenance={"knmi_station_id": 249, "revision": "new"})

    assert baseline.content_sha256 != changed_irradiance.content_sha256
    assert baseline.content_sha256 != changed_provenance.content_sha256
    assert_same_weather_realization(baseline, baseline.identity_record())
    with pytest.raises(ValueError, match="content_sha256"):
        assert_same_weather_realization(baseline.identity_record(), changed_irradiance.identity_record())


def test_weather_member_audit_mappings_are_immutable_after_construction() -> None:
    member = _short_weather()

    with pytest.raises(TypeError):
        member.pv_weather_fields["dni_w_per_m2"] = np.zeros(member.n_timesteps)  # type: ignore[index]
    with pytest.raises(TypeError):
        member.provenance["revision"] = "changed"  # type: ignore[index]
    with pytest.raises(TypeError):
        member.metadata["selection_id"] = "changed"  # type: ignore[index]

    assert member.pv_weather_fields["ghi_w_per_m2"].flags.writeable is False
    assert member.provenance["knmi_station_id"] == 249
    assert member.metadata["selection_id"] == "d004_alkmaar_berkhout_2014_2023_v1"


def test_identity_record_mutation_does_not_change_member_or_content_hash() -> None:
    member = _short_weather()
    original_hash = member.content_sha256
    record = member.identity_record()

    record["content_sha256"] = "0" * 64
    record["provenance"]["knmi_station_id"] = 999  # type: ignore[index]
    record["metadata"]["selection_id"] = "mutated"  # type: ignore[index]

    assert member.content_sha256 == original_hash
    assert member.provenance["knmi_station_id"] == 249
    assert member.metadata["selection_id"] == "d004_alkmaar_berkhout_2014_2023_v1"
    assert member.identity_record()["content_sha256"] == original_hash


def test_same_neutral_weather_member_feeds_hp_and_pv_common_driver() -> None:
    weather = _short_weather()
    hourly = When2HeatHourlyProfile(
        timestamps_utc=(datetime(2025, 1, 1, tzinfo=UTC),),
        thermal_demand_kw=np.array([3000.0]),
        electric_kw=np.array([1000.0]),
        cop=np.array([3.0]),
        components=(When2HeatComponent("heat", "cop", 1.0),),
    )
    hp_profile = align_heat_pump_profile(downscale_hourly_to_15min(hourly), weather)
    pv_profile = generate_pv_profile(
        weather,
        PVSystemConfig(
            installed_capacity_kw=10.0,
            performance_ratio=0.9,
            reference_irradiance_w_per_m2=1000.0,
            temperature_coefficient_per_c=-0.004,
            reference_temperature_c=25.0,
            clip_to_capacity=True,
            config_id="q8-neutral-weather-test",
        ),
    )

    hp_identity = hp_profile.weather_identity_record()
    pv_identity = {
        **weather.identity_record(),
        "shared_weather_driver_id": pv_profile.shared_weather_driver_id,
        "member_id": pv_profile.weather_member_id,
        "source": pv_profile.weather_source,
    }

    assert hp_profile.shared_weather_driver_id == weather.shared_weather_driver_id
    assert pv_profile.shared_weather_driver_id == weather.shared_weather_driver_id
    assert hp_profile.timestamps_utc == weather.timestamps_utc
    assert pv_profile.timestamps_utc == weather.timestamps_utc
    assert hp_profile.pv_weather_field_names == ("ghi_w_per_m2", "poa_global_w_per_m2")
    assert_same_weather_realization(weather.identity_record(), pv_identity)
    assert hp_identity["shared_weather_driver_id"] == weather.shared_weather_driver_id
    assert hp_identity["member_id"] == weather.member_id
