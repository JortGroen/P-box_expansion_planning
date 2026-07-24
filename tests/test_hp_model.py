from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
import threading
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

import data.get_hp_scaling as hp_scaling
from data.get_when2heat import (
    PRIMARY_WHEN2HEAT_FILE_KEY,
    WHEN2HEAT_FILES,
    retrieve_when2heat_file,
    write_when2heat_source_selection_plan,
    write_when2heat_source_metadata,
)
from src.hp_model import (
    HP001_FINAL_READINESS_REQUIRED_APPROVAL_KEYS,
    HP001LocalScalingConfig,
    HeatPumpProfile,
    HeatPumpComponentSeries,
    When2HeatComponent,
    When2HeatHourlyProfile,
    align_heat_pump_profile,
    build_executable_hp001_profile_from_when2heat_csv,
    build_heat_pump_profile_from_when2heat_csv,
    cold_week_sanity_check,
    default_when2heat_components,
    downscale_hourly_to_15min,
    hp001_components_from_local_scaling_config,
    hp001_final_readiness_missing_approval_keys,
    hp001_local_scaling_config_from_value_binding_record,
    hp001_residential_when2heat_components,
    require_hp001_final_readiness_approvals,
    require_signed_hp001_local_scaling_config,
    load_when2heat_hourly_csv,
    require_signed_annual_scaling,
)
from src.weather_model import WeatherMember


@dataclass(frozen=True)
class PairedWeatherMemberStub:
    """PV/weather-shaped member used to verify HP consumes the shared contract."""

    member_id: str
    source: str
    timestamps_utc: tuple[datetime, ...]
    timestamps_local: tuple[datetime, ...]
    temperature_c: np.ndarray
    ghi_w_per_m2: np.ndarray
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def shared_weather_driver_id(self) -> str:
        return f"{self.source}:{self.member_id}"


def _shared_weather(
    *,
    member_id: str = "knmi_2025_rotterdam_001",
    source: str = "knmi_historical_plus_paired_irradiance",
    timestamps_utc: tuple[datetime, ...],
    temperature_c: list[float] | np.ndarray,
    metadata: dict[str, object] | None = None,
) -> PairedWeatherMemberStub:
    local_zone = ZoneInfo("Europe/Amsterdam")
    local = tuple(item.astimezone(local_zone) for item in timestamps_utc)
    temperature = np.asarray(temperature_c, dtype=np.float64)
    return PairedWeatherMemberStub(
        member_id=member_id,
        source=source,
        timestamps_utc=timestamps_utc,
        timestamps_local=local,
        temperature_c=temperature,
        ghi_w_per_m2=np.zeros_like(temperature),
        metadata=metadata or {},
    )


def _hourly_timestamps(count: int) -> tuple[datetime, ...]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return tuple(start + timedelta(hours=index) for index in range(count))


def _quarter_timestamps(count: int) -> tuple[datetime, ...]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return tuple(start + timedelta(minutes=15 * index) for index in range(count))


def test_when2heat_metadata_default_is_no_download(tmp_path: Path) -> None:
    path = write_when2heat_source_metadata(tmp_path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["data_id"] == "D-003"
    assert payload["download_performed"] is False
    assert payload["extra"]["package_version"] == "2023-07-27"
    assert payload["extra"]["proposed_primary_file_key"] == "csv"
    assert payload["extra"]["downloadable_files"]["csv"]["filename"] == "when2heat.csv"
    assert payload["extra"]["downloadable_files"]["csv"]["listed_size_mb"] == 313


def test_when2heat_source_selection_plan_identifies_primary_csv(tmp_path: Path) -> None:
    path = write_when2heat_source_selection_plan(tmp_path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    base_metadata = tmp_path / "d-003_when2heat.json"

    assert path == tmp_path / "when2heat" / "d003_when2heat_source_selection_plan.json"
    assert base_metadata.is_file()
    assert payload["data_id"] == "D-003"
    assert payload["download_performed"] is False
    assert payload["data_register_status"] == "proposed"
    assert payload["package_version"] == "2023-07-27"
    assert payload["selected_file_key"] == PRIMARY_WHEN2HEAT_FILE_KEY
    assert payload["selected_file"]["filename"] == "when2heat.csv"
    assert payload["selected_file"]["url"].endswith("/2023-07-27/when2heat.csv")
    assert payload["selected_file"]["listed_size_mb"] == 313
    assert payload["runtime_assessment"]["likely_exceeds_15_minutes_by_default"] is False
    assert payload["runtime_assessment"]["minimum_average_network_mbps_for_15_min"] == 2.78
    assert payload["alternatives_not_selected"]["zip"]["listed_size_mb"] == 497
    assert "Concrete when2heat.csv checksum is not selected." in payload["acceptance_blockers"]
    assert any("--download csv" in step for step in payload["checksum_workflow"])


def test_when2heat_retrieval_records_checksum_with_local_url(tmp_path: Path) -> None:
    source = tmp_path / "source_datapackage.json"
    source.write_bytes(b'{"name":"when2heat-test"}\n')

    metadata_path = retrieve_when2heat_file(
        "datapackage",
        raw_dir=tmp_path / "raw",
        metadata_dir=tmp_path / "metadata",
        url_override=source.as_uri(),
    )

    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    raw_path = tmp_path / "raw" / WHEN2HEAT_FILES["datapackage"].filename
    assert raw_path.read_bytes() == source.read_bytes()
    assert payload["download_performed"] is True
    assert payload["sha256_file"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert payload["data_register_update_required"] is True
    assert payload["license"] == "Creative Commons Attribution 4.0"


def test_when2heat_retrieval_resumes_with_checkpoint(tmp_path: Path) -> None:
    content = b"when2heat-resume-test-content"

    class RangeHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            start = 0
            range_header = self.headers.get("Range")
            if range_header:
                start = int(range_header.removeprefix("bytes=").split("-", maxsplit=1)[0])
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{len(content) - 1}/{len(content)}")
            else:
                self.send_response(200)
            body = content[start:]
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), RangeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    temp_path = raw_dir / f"{WHEN2HEAT_FILES['datapackage'].filename}.tmp"
    temp_path.write_bytes(content[:10])

    try:
        metadata_path = retrieve_when2heat_file(
            "datapackage",
            raw_dir=raw_dir,
            metadata_dir=tmp_path / "metadata",
            url_override=f"http://127.0.0.1:{server.server_port}/datapackage.json",
            resume=True,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    checkpoint = json.loads(Path(payload["checkpoint_path"]).read_text(encoding="utf-8"))
    raw_path = raw_dir / WHEN2HEAT_FILES["datapackage"].filename

    assert raw_path.read_bytes() == content
    assert payload["sha256_file"] == hashlib.sha256(content).hexdigest()
    assert payload["resume"]["enabled"] is True
    assert payload["resume"]["resumed_from_bytes"] == 10
    assert payload["resume"]["server_range_status"] == "partial_content_206"
    assert checkpoint["status"] == "complete"
    assert checkpoint["bytes_downloaded"] == len(content)
    assert checkpoint["partial_sha256"] == payload["sha256_file"]


def test_load_when2heat_csv_uses_component_cop_columns(tmp_path: Path) -> None:
    path = tmp_path / "when2heat.csv"
    pd.DataFrame(
        {
            "utc_timestamp": [item.isoformat().replace("+00:00", "Z") for item in _hourly_timestamps(2)],
            "cet_cest_timestamp": ["2025-01-01T01:00:00+0100", "2025-01-01T02:00:00+0100"],
            "NL_heat_profile_space_SFH": [2.0, 4.0],
            "NL_COP_ASHP_radiator": [2.0, 4.0],
            "NL_heat_profile_water_SFH": [1.0, 1.0],
            "NL_COP_ASHP_water": [2.0, 2.0],
        }
    ).to_csv(path, index=False, sep=";", decimal=",")
    components = (
        When2HeatComponent("NL_heat_profile_space_SFH", "NL_COP_ASHP_radiator", 0.5),
        When2HeatComponent("NL_heat_profile_water_SFH", "NL_COP_ASHP_water", 1.0),
    )

    profile = load_when2heat_hourly_csv(path, components=components)

    assert np.allclose(profile.thermal_demand_kw, [2000.0, 3000.0])
    assert np.allclose(profile.electric_kw, [1000.0, 1000.0])
    assert np.allclose(profile.cop, [2.0, 3.0])
    assert profile.source_path == path.as_posix()
    assert profile.source_metadata is not None
    assert profile.source_metadata.csv_separator == ";"
    assert profile.source_metadata.decimal == ","
    assert profile.source_metadata.heat_profile_unit == "MW_per_annual_TWh"
    assert profile.source_metadata.cop_unit == "dimensionless"
    assert profile.source_metadata.selected_heat_columns == (
        "NL_heat_profile_space_SFH",
        "NL_heat_profile_water_SFH",
    )
    assert profile.source_metadata.selected_cop_columns == (
        "NL_COP_ASHP_radiator",
        "NL_COP_ASHP_water",
    )
    assert profile.source_metadata.first_timestamp_local == "2025-01-01T01:00:00+0100"
    assert profile.source_metadata.last_timestamp_local == "2025-01-01T02:00:00+0100"
    assert profile.source_metadata.n_rows_loaded == 2


def test_load_when2heat_csv_can_sample_retrieved_real_file_if_available() -> None:
    path = Path("data/raw/when2heat/when2heat.csv")
    if not path.exists():
        pytest.skip("ignored D-003 raw When2Heat CSV is not present in this checkout")
    components = (
        When2HeatComponent("NL_heat_profile_space_SFH", "NL_COP_ASHP_radiator", 1.0),
        When2HeatComponent("NL_heat_profile_water_SFH", "NL_COP_ASHP_water", 1.0),
    )

    profile = load_when2heat_hourly_csv(path, components=components, nrows=3)

    assert len(profile.timestamps_utc) == 3
    assert profile.timestamps_utc[0] == datetime(2007, 12, 31, 22, tzinfo=UTC)
    assert np.all(profile.thermal_demand_kw >= 0)
    assert np.all(profile.electric_kw >= 0)
    assert profile.source_metadata is not None
    assert profile.source_metadata.n_rows_loaded == 3
    assert profile.source_metadata.first_timestamp_local == "2007-12-31T23:00:00+0100"


def test_default_components_make_space_and_water_cop_mapping_explicit() -> None:
    components = default_when2heat_components(
        space_heat_twh_by_class={"SFH": 0.25},
        water_heat_twh_by_class={"SFH": 0.1},
    )

    assert components == (
        When2HeatComponent(
            "NL_heat_profile_space_SFH",
            "NL_COP_ASHP_radiator",
            0.25,
            end_use="space",
            building_class="SFH",
        ),
        When2HeatComponent(
            "NL_heat_profile_water_SFH",
            "NL_COP_ASHP_water",
            0.1,
            end_use="water",
            building_class="SFH",
        ),
    )


def test_hp001_components_encode_residential_space_and_dhw_boundary() -> None:
    components = hp001_residential_when2heat_components(
        space_heat_twh_by_class={"SFH": 0.25, "MFH": 0.15},
        water_heat_twh_by_class={"SFH": 0.05, "MFH": 0.03},
        provenance={"scaling_source": "unit-test explicit values"},
    )

    assert [component.as_record() for component in components] == [
        {
            "heat_column": "NL_heat_profile_space_SFH",
            "cop_column": "NL_COP_ASHP_radiator",
            "annual_heat_demand_twh": 0.25,
            "end_use": "space",
            "building_class": "SFH",
            "provenance": {
                "annual_scaling_status": "caller_supplied_not_approved_by_hp001",
                "boundary": "residential_space_plus_domestic_hot_water",
                "component_boundary": "SFH_space_heat",
                "data_id": "D-003",
                "decision_id": "HP-001",
                "scaling_source": "unit-test explicit values",
                "source": "OPSD When2Heat 2023-07-27 when2heat.csv",
            },
        },
        {
            "heat_column": "NL_heat_profile_space_MFH",
            "cop_column": "NL_COP_ASHP_radiator",
            "annual_heat_demand_twh": 0.15,
            "end_use": "space",
            "building_class": "MFH",
            "provenance": {
                "annual_scaling_status": "caller_supplied_not_approved_by_hp001",
                "boundary": "residential_space_plus_domestic_hot_water",
                "component_boundary": "MFH_space_heat",
                "data_id": "D-003",
                "decision_id": "HP-001",
                "scaling_source": "unit-test explicit values",
                "source": "OPSD When2Heat 2023-07-27 when2heat.csv",
            },
        },
        {
            "heat_column": "NL_heat_profile_water_SFH",
            "cop_column": "NL_COP_ASHP_water",
            "annual_heat_demand_twh": 0.05,
            "end_use": "water",
            "building_class": "SFH",
            "provenance": {
                "annual_scaling_status": "caller_supplied_not_approved_by_hp001",
                "boundary": "residential_space_plus_domestic_hot_water",
                "component_boundary": "SFH_domestic_hot_water",
                "data_id": "D-003",
                "decision_id": "HP-001",
                "scaling_source": "unit-test explicit values",
                "source": "OPSD When2Heat 2023-07-27 when2heat.csv",
            },
        },
        {
            "heat_column": "NL_heat_profile_water_MFH",
            "cop_column": "NL_COP_ASHP_water",
            "annual_heat_demand_twh": 0.03,
            "end_use": "water",
            "building_class": "MFH",
            "provenance": {
                "annual_scaling_status": "caller_supplied_not_approved_by_hp001",
                "boundary": "residential_space_plus_domestic_hot_water",
                "component_boundary": "MFH_domestic_hot_water",
                "data_id": "D-003",
                "decision_id": "HP-001",
                "scaling_source": "unit-test explicit values",
                "source": "OPSD When2Heat 2023-07-27 when2heat.csv",
            },
        },
    ]


def test_hp001_components_reject_missing_or_com_classes() -> None:
    with pytest.raises(ValueError, match="missing=\\('MFH',\\)"):
        hp001_residential_when2heat_components(
            space_heat_twh_by_class={"SFH": 0.25},
            water_heat_twh_by_class={"SFH": 0.05, "MFH": 0.03},
        )

    with pytest.raises(ValueError, match="extra=\\('COM',\\)"):
        hp001_residential_when2heat_components(
            space_heat_twh_by_class={"SFH": 0.25, "MFH": 0.15, "COM": 0.40},
            water_heat_twh_by_class={"SFH": 0.05, "MFH": 0.03},
        )


def test_hp001_csv_load_keeps_space_and_dhw_components_traceable(tmp_path: Path) -> None:
    path = tmp_path / "when2heat.csv"
    pd.DataFrame(
        {
            "utc_timestamp": [item.isoformat().replace("+00:00", "Z") for item in _hourly_timestamps(1)],
            "cet_cest_timestamp": ["2025-01-01T01:00:00+0100"],
            "NL_heat_profile_space_SFH": [2.0],
            "NL_heat_profile_space_MFH": [3.0],
            "NL_heat_profile_water_SFH": [4.0],
            "NL_heat_profile_water_MFH": [5.0],
            "NL_COP_ASHP_radiator": [2.0],
            "NL_COP_ASHP_water": [4.0],
        }
    ).to_csv(path, index=False, sep=";", decimal=",")
    components = hp001_residential_when2heat_components(
        space_heat_twh_by_class={"SFH": 0.5, "MFH": 1.0},
        water_heat_twh_by_class={"SFH": 0.25, "MFH": 0.2},
    )

    profile = load_when2heat_hourly_csv(path, components=components)

    # Space thermal: (2*0.5 + 3*1.0) MW = 4000 kW, divided by radiator COP 2.
    # DHW thermal: (4*0.25 + 5*0.2) MW = 2000 kW, divided by water COP 4.
    assert np.allclose(profile.thermal_demand_kw, [6000.0])
    assert np.allclose(profile.electric_kw, [2500.0])
    assert profile.components == components
    assert profile.source_metadata is not None
    assert profile.source_metadata.selected_heat_columns == (
        "NL_heat_profile_space_SFH",
        "NL_heat_profile_space_MFH",
        "NL_heat_profile_water_SFH",
        "NL_heat_profile_water_MFH",
    )
    assert profile.source_metadata.selected_cop_columns == (
        "NL_COP_ASHP_radiator",
        "NL_COP_ASHP_radiator",
        "NL_COP_ASHP_water",
        "NL_COP_ASHP_water",
    )
    assert tuple(
        (record["end_use"], record["building_class"], record["cop_column"])
        for record in profile.source_metadata.selected_components
    ) == (
        ("space", "SFH", "NL_COP_ASHP_radiator"),
        ("space", "MFH", "NL_COP_ASHP_radiator"),
        ("water", "SFH", "NL_COP_ASHP_water"),
        ("water", "MFH", "NL_COP_ASHP_water"),
    )


def test_hp001_component_series_remain_traceable_through_downscale_and_alignment(tmp_path: Path) -> None:
    path = tmp_path / "when2heat.csv"
    pd.DataFrame(
        {
            "utc_timestamp": [item.isoformat().replace("+00:00", "Z") for item in _hourly_timestamps(1)],
            "cet_cest_timestamp": ["2025-01-01T01:00:00+0100"],
            "NL_heat_profile_space_SFH": [2.0],
            "NL_heat_profile_space_MFH": [3.0],
            "NL_heat_profile_water_SFH": [4.0],
            "NL_heat_profile_water_MFH": [5.0],
            "NL_COP_ASHP_radiator": [2.0],
            "NL_COP_ASHP_water": [4.0],
        }
    ).to_csv(path, index=False, sep=";", decimal=",")
    components = hp001_residential_when2heat_components(
        space_heat_twh_by_class={"SFH": 0.5, "MFH": 1.0},
        water_heat_twh_by_class={"SFH": 0.25, "MFH": 0.2},
    )
    hourly = load_when2heat_hourly_csv(path, components=components)
    quarter = downscale_hourly_to_15min(hourly)
    weather = _shared_weather(
        member_id="d004-test-member",
        timestamps_utc=quarter.timestamps_utc,
        temperature_c=[1.0, 1.0, 1.0, 1.0],
    )

    profile = align_heat_pump_profile(quarter, weather)

    assert len(profile.component_series) == 4
    assert np.allclose(
        sum(component.electric_kw for component in profile.component_series),
        profile.electric_kw,
    )
    assert profile.component_traceability_record() == (
        {
            "component_id": "sfh_space",
            "heat_column": "NL_heat_profile_space_SFH",
            "cop_column": "NL_COP_ASHP_radiator",
            "annual_heat_demand_twh": 0.5,
            "end_use": "space",
            "building_class": "SFH",
            "n_timesteps": 4,
            "interval_hours": 0.25,
            "thermal_energy_kwh": 1000.0,
            "electric_energy_kwh": 500.0,
            "provenance": components[0].provenance,
        },
        {
            "component_id": "mfh_space",
            "heat_column": "NL_heat_profile_space_MFH",
            "cop_column": "NL_COP_ASHP_radiator",
            "annual_heat_demand_twh": 1.0,
            "end_use": "space",
            "building_class": "MFH",
            "n_timesteps": 4,
            "interval_hours": 0.25,
            "thermal_energy_kwh": 3000.0,
            "electric_energy_kwh": 1500.0,
            "provenance": components[1].provenance,
        },
        {
            "component_id": "sfh_water",
            "heat_column": "NL_heat_profile_water_SFH",
            "cop_column": "NL_COP_ASHP_water",
            "annual_heat_demand_twh": 0.25,
            "end_use": "water",
            "building_class": "SFH",
            "n_timesteps": 4,
            "interval_hours": 0.25,
            "thermal_energy_kwh": 1000.0,
            "electric_energy_kwh": 250.0,
            "provenance": components[2].provenance,
        },
        {
            "component_id": "mfh_water",
            "heat_column": "NL_heat_profile_water_MFH",
            "cop_column": "NL_COP_ASHP_water",
            "annual_heat_demand_twh": 0.2,
            "end_use": "water",
            "building_class": "MFH",
            "n_timesteps": 4,
            "interval_hours": 0.25,
            "thermal_energy_kwh": 1000.0,
            "electric_energy_kwh": 250.0,
            "provenance": components[3].provenance,
        },
    )


def test_alignment_preserves_weather_content_identity_from_shared_contract() -> None:
    hourly = When2HeatHourlyProfile(
        timestamps_utc=_hourly_timestamps(1),
        thermal_demand_kw=np.array([3000.0]),
        electric_kw=np.array([1000.0]),
        cop=np.array([3.0]),
        components=(When2HeatComponent("heat", "cop", 1.0),),
    )
    quarter = downscale_hourly_to_15min(hourly)
    local_zone = ZoneInfo("Europe/Amsterdam")
    weather = WeatherMember(
        member_id="d004_alkmaar_berkhout_2025_v1",
        shared_weather_driver_id="d004_alkmaar_berkhout_2014_2023_v1:2025",
        source="D-004 WEATHER-001 fixture",
        timestamps_utc=quarter.timestamps_utc,
        timestamps_local=tuple(item.astimezone(local_zone) for item in quarter.timestamps_utc),
        temperature_c=[2.0, 2.0, 2.0, 2.0],
        pv_weather_fields={"ghi_w_per_m2": [0.0, 0.0, 0.0, 0.0]},
        provenance={"retrieval_manifest": "data/metadata/weather_pv/test.json"},
    )

    profile = align_heat_pump_profile(quarter, weather)

    assert profile.weather_content_sha256 == weather.content_sha256
    assert profile.weather_identity_record()["content_sha256"] == weather.content_sha256


def test_executable_hp001_profile_requires_signed_annual_scaling(tmp_path: Path) -> None:
    path = tmp_path / "when2heat.csv"
    pd.DataFrame(
        {
            "utc_timestamp": [datetime(2025, 1, 1, tzinfo=UTC).isoformat().replace("+00:00", "Z")],
            "cet_cest_timestamp": ["2025-01-01T01:00:00+0100"],
            "NL_heat_profile_space_SFH": [3.0],
            "NL_COP_ASHP_radiator": [3.0],
        }
    ).to_csv(path, index=False, sep=";", decimal=",")
    weather = _shared_weather(
        member_id="weather-member-1",
        timestamps_utc=_quarter_timestamps(4),
        temperature_c=[0.0, 0.0, 0.0, 0.0],
    )
    unsigned = (When2HeatComponent("NL_heat_profile_space_SFH", "NL_COP_ASHP_radiator", 1.0),)

    with pytest.raises(ValueError, match="signed annual scaling provenance"):
        require_signed_annual_scaling(unsigned)
    with pytest.raises(ValueError, match="signed annual scaling provenance"):
        build_executable_hp001_profile_from_when2heat_csv(path, weather=weather, components=unsigned)

    signed = (
        When2HeatComponent(
            "NL_heat_profile_space_SFH",
            "NL_COP_ASHP_radiator",
            1.0,
            provenance={"annual_scaling_status": "signed", "annual_scaling_approval_id": "HP-SCALING-TEST"},
        ),
    )
    profile = build_executable_hp001_profile_from_when2heat_csv(path, weather=weather, components=signed)

    assert np.allclose(profile.electric_kw, [1000.0] * 4)


def test_hp001_local_scaling_config_fails_closed_until_all_remaining_choices_signed() -> None:
    config = HP001LocalScalingConfig(
        value_column="Referentie_2030",
        denominator_column="I11_woningequivalenten [Woning]",
        gj_to_twh_divisor=3_600_000.0,
        sfh_mfh_split_rule="cbs_85035ned_count_share",
        adoption_electrification_scenario="unsigned_2035_full_service_fraction",
        space_heat_twh_by_class={"SFH": 0.2, "MFH": 0.1},
        water_heat_twh_by_class={"SFH": 0.04, "MFH": 0.02},
        approval_ids={"value_column": "D013-PBL-MAPPING"},
    )

    assert config.missing_approval_keys() == (
        "denominator",
        "unit_conversion",
        "sfh_mfh_split",
        "adoption_electrification",
    )
    with pytest.raises(ValueError, match="remaining choices"):
        require_signed_hp001_local_scaling_config(config)
    with pytest.raises(ValueError, match="remaining choices"):
        hp001_components_from_local_scaling_config(config)


def test_hp001_local_scaling_config_records_signed_formula_provenance() -> None:
    config = HP001LocalScalingConfig(
        value_column="Referentie_2030",
        denominator_column="I11_woningequivalenten [Woning]",
        gj_to_twh_divisor=3_600_000.0,
        sfh_mfh_split_rule="cbs_85035ned_count_share",
        adoption_electrification_scenario="signed_2035_full_service_fraction",
        space_heat_twh_by_class={"SFH": 0.2, "MFH": 0.1},
        water_heat_twh_by_class={"SFH": 0.04, "MFH": 0.02},
        approval_ids={
            "value_column": "HP-SCALING-VALUE-COLUMN",
            "denominator": "HP-SCALING-DENOMINATOR",
            "unit_conversion": "HP-SCALING-CONVERSION",
            "sfh_mfh_split": "HP-SCALING-SPLIT",
            "adoption_electrification": "HP-SCALING-ADOPTION",
        },
        provenance={"source_use": "unit-test signed fixture"},
    )

    components = hp001_components_from_local_scaling_config(config)

    assert config.missing_approval_keys() == ()
    assert len(components) == 4
    assert {component.provenance["annual_scaling_status"] for component in components} == {"signed"}
    assert all(component.provenance["local_scaling_data_id"] == "D-013" for component in components)
    assert all(component.provenance["indicator_mapping_approval_id"] == "A-015" for component in components)
    assert components[0].provenance["value_column"] == "Referentie_2030"
    assert components[0].provenance["denominator_column"] == "I11_woningequivalenten [Woning]"
    assert components[0].provenance["local_scaling_config"]["missing_approval_keys"] == ()


def test_hp001_value_binding_readiness_packet_is_not_config_approved() -> None:
    packet = hp_scaling.build_hp001_value_binding_readiness_packet()

    with pytest.raises(ValueError, match="not approved for executable use"):
        hp001_local_scaling_config_from_value_binding_record(packet)


def test_hp001_value_binding_record_adapter_requires_all_approval_ids() -> None:
    packet = hp_scaling.build_hp001_value_binding_readiness_packet()
    packet = {
        **packet,
        "status": "approved_for_executable_value_binding",
        "approval_state": {
            **packet["approval_state"],
            "approval_ids": {"value_column": "HP-SCALING-VALUE-COLUMN"},
            "missing_approval_keys": [],
            "executable_binding_allowed": True,
        },
        "component_value_drafts_unsigned_before_2035_adoption": [
            {
                **component,
                "annual_twh_status": "approved_for_executable_value_binding",
            }
            for component in packet["component_value_drafts_unsigned_before_2035_adoption"]
        ],
    }

    with pytest.raises(ValueError, match="remaining choices"):
        hp001_local_scaling_config_from_value_binding_record(packet)


def test_hp001_value_binding_record_adapter_builds_signed_config_only() -> None:
    packet = hp_scaling.build_hp001_value_binding_readiness_packet()
    packet = {
        **packet,
        "status": "approved_for_executable_value_binding",
        "approval_state": {
            **packet["approval_state"],
            "missing_approval_keys": [],
            "executable_binding_allowed": True,
            "approval_ids": {
                "value_column": "HP-SCALING-VALUE-COLUMN",
                "denominator": "HP-SCALING-DENOMINATOR",
                "unit_conversion": "HP-SCALING-CONVERSION",
                "sfh_mfh_split": "HP-SCALING-SPLIT",
                "adoption_electrification": "HP-SCALING-ADOPTION",
            },
        },
        "component_value_drafts_unsigned_before_2035_adoption": [
            {
                **component,
                "annual_twh_status": "approved_for_executable_value_binding",
            }
            for component in packet["component_value_drafts_unsigned_before_2035_adoption"]
        ],
    }

    config = hp001_local_scaling_config_from_value_binding_record(packet)

    assert config.value_column == "Referentie_2030"
    assert config.denominator_column == "I11_woningequivalenten [Woning]"
    assert config.missing_approval_keys() == ()
    assert config.space_heat_twh_by_class == {"MFH": 0.140904121, "SFH": 0.221155323}
    assert config.water_heat_twh_by_class == {"MFH": 0.038099269, "SFH": 0.059798509}
    assert config.provenance["value_binding_packet_id"] == "E2-S3-HP001-VALUE-BINDING-READINESS"


def test_hp001_value_binding_record_requires_executable_flag_even_with_approvals() -> None:
    packet = hp_scaling.build_hp001_value_binding_readiness_packet()
    packet = {
        **packet,
        "status": "approved_for_executable_value_binding",
        "approval_state": {
            **packet["approval_state"],
            "approval_ids": {
                "value_column": "HP-SCALING-VALUE-COLUMN",
                "denominator": "HP-SCALING-DENOMINATOR",
                "unit_conversion": "HP-SCALING-CONVERSION",
                "sfh_mfh_split": "HP-SCALING-SPLIT",
                "adoption_electrification": "HP-SCALING-ADOPTION",
            },
            "missing_approval_keys": [],
            "executable_binding_allowed": False,
        },
        "component_value_drafts_unsigned_before_2035_adoption": [
            {
                **component,
                "annual_twh_status": "approved_for_executable_value_binding",
            }
            for component in packet["component_value_drafts_unsigned_before_2035_adoption"]
        ],
    }

    with pytest.raises(ValueError, match="executable_binding_allowed"):
        hp001_local_scaling_config_from_value_binding_record(packet)


def test_hp001_value_binding_record_requires_component_approval_status() -> None:
    packet = hp_scaling.build_hp001_value_binding_readiness_packet()
    packet = {
        **packet,
        "status": "approved_for_executable_value_binding",
        "approval_state": {
            **packet["approval_state"],
            "approval_ids": {
                "value_column": "HP-SCALING-VALUE-COLUMN",
                "denominator": "HP-SCALING-DENOMINATOR",
                "unit_conversion": "HP-SCALING-CONVERSION",
                "sfh_mfh_split": "HP-SCALING-SPLIT",
                "adoption_electrification": "HP-SCALING-ADOPTION",
            },
            "missing_approval_keys": [],
            "executable_binding_allowed": True,
        },
    }

    with pytest.raises(ValueError, match="annual_twh_status"):
        hp001_local_scaling_config_from_value_binding_record(packet)

def test_default_components_require_explicit_scales() -> None:
    with pytest.raises(ValueError, match="explicit annual heat TWh scale"):
        default_when2heat_components()


def test_hourly_to_15min_downscale_preserves_energy_and_calendar() -> None:
    hourly = When2HeatHourlyProfile(
        timestamps_utc=_hourly_timestamps(2),
        thermal_demand_kw=np.array([4000.0, 8000.0]),
        electric_kw=np.array([1000.0, 2000.0]),
        cop=np.array([4.0, 4.0]),
        components=(When2HeatComponent("heat", "cop", 1.0),),
    )

    quarter = downscale_hourly_to_15min(hourly)

    assert len(quarter.timestamps_utc) == 8
    assert quarter.timestamps_utc[1] == datetime(2025, 1, 1, 0, 15, tzinfo=UTC)
    assert np.allclose(quarter.electric_kw, [1000.0] * 4 + [2000.0] * 4)
    hourly_energy_kwh = hourly.electric_kw.sum() * 1.0
    quarter_energy_kwh = quarter.electric_kw.sum() * 0.25
    assert quarter_energy_kwh == hourly_energy_kwh
    assert quarter.downscaling_method == "hourly_zero_order_hold_to_15min_energy_preserving"


def test_profile_alignment_records_weather_member_and_rejects_mismatch() -> None:
    hourly = When2HeatHourlyProfile(
        timestamps_utc=_hourly_timestamps(1),
        thermal_demand_kw=np.array([6000.0]),
        electric_kw=np.array([2000.0]),
        cop=np.array([3.0]),
        components=(When2HeatComponent("heat", "cop", 1.0),),
    )
    quarter = downscale_hourly_to_15min(hourly)
    weather = _shared_weather(
        member_id="knmi-2012",
        timestamps_utc=quarter.timestamps_utc,
        temperature_c=[3.0, 2.5, 2.0, 1.5],
        metadata={"station_id": "260", "source_file_sha256": "abc123"},
    )

    profile = align_heat_pump_profile(quarter, weather)

    assert profile.weather_member_id == "knmi-2012"
    assert profile.weather_source == "knmi_historical_plus_paired_irradiance"
    assert profile.shared_weather_driver_id == weather.shared_weather_driver_id
    assert profile.timestamps_utc == weather.timestamps_utc
    assert profile.timestamps_local == weather.timestamps_local
    assert np.array_equal(profile.temperature_c, weather.temperature_c)
    assert profile.pv_weather_field_names == ("ghi_w_per_m2",)
    assert profile.source_columns == ("heat", "cop")
    assert profile.weather_provenance == {"source_file_sha256": "abc123", "station_id": "260"}
    assert profile.weather_identity_record() == {
        "shared_weather_driver_id": weather.shared_weather_driver_id,
        "member_id": "knmi-2012",
        "source": "knmi_historical_plus_paired_irradiance",
        "first_timestamp_utc": "2025-01-01T00:00:00+00:00",
        "last_timestamp_utc": "2025-01-01T00:45:00+00:00",
        "n_timesteps": 4,
        "cadence_seconds": 900,
        "pv_weather_field_names": ("ghi_w_per_m2",),
        "provenance": {"source_file_sha256": "abc123", "station_id": "260"},
        "first_timestamp_local": "2025-01-01T01:00:00+01:00",
        "last_timestamp_local": "2025-01-01T01:45:00+01:00",
    }

    shifted_weather = _shared_weather(
        member_id="knmi-shifted",
        timestamps_utc=tuple(item + timedelta(minutes=15) for item in quarter.timestamps_utc),
        temperature_c=[3.0, 2.5, 2.0, 1.5],
    )
    with pytest.raises(ValueError, match="not exactly aligned"):
        align_heat_pump_profile(quarter, shifted_weather)


def test_build_heat_pump_profile_from_csv_requires_supplied_weather(tmp_path: Path) -> None:
    path = tmp_path / "when2heat.csv"
    pd.DataFrame(
        {
            "utc_timestamp": [datetime(2025, 1, 1, tzinfo=UTC).isoformat().replace("+00:00", "Z")],
            "cet_cest_timestamp": ["2025-01-01T01:00:00+0100"],
            "NL_heat_profile_space_SFH": [3.0],
            "NL_COP_ASHP_radiator": [3.0],
        }
    ).to_csv(path, index=False, sep=";", decimal=",")
    weather = _shared_weather(
        member_id="weather-member-1",
        timestamps_utc=_quarter_timestamps(4),
        temperature_c=[0.0, 0.0, 0.0, 0.0],
    )

    profile = build_heat_pump_profile_from_when2heat_csv(
        path,
        weather=weather,
        components=(When2HeatComponent("NL_heat_profile_space_SFH", "NL_COP_ASHP_radiator", 1.0),),
    )

    assert np.allclose(profile.electric_kw, [1000.0] * 4)
    assert profile.weather_member_id == "weather-member-1"
    assert profile.shared_weather_driver_id == weather.shared_weather_driver_id
    assert profile.source_metadata["csv_separator"] == ";"
    assert profile.source_metadata["selected_heat_columns"] == ("NL_heat_profile_space_SFH",)


def test_cold_week_sanity_peak_coincides_with_cold_spell() -> None:
    timestamps = _quarter_timestamps(14 * 96)
    temperature = np.full(len(timestamps), 7.0)
    cold_start = 3 * 96
    cold_stop = 10 * 96
    temperature[cold_start:cold_stop] = -5.0
    electric = np.full(len(timestamps), 1.0)
    electric[cold_start:cold_stop] = 4.0
    profile = HeatPumpProfile(
        shared_weather_driver_id="knmi_synthetic:design-cold-week",
        weather_member_id="design-cold-week",
        weather_source="knmi_synthetic",
        timestamps_utc=timestamps,
        electric_kw=electric,
        thermal_demand_kw=electric * 3.0,
        cop=np.full(len(timestamps), 3.0),
        temperature_c=temperature,
        source_columns=("synthetic_heat", "synthetic_cop"),
        source_path=None,
        downscaling_method="test_15min_native",
        pv_weather_field_names=("ghi_w_per_m2",),
        weather_provenance={"acceptance_evidence": "synthetic_unit_test_only"},
    )

    sanity = cold_week_sanity_check(profile)

    assert sanity.peak_inside_cold_week is True
    assert sanity.coldest_week_start_utc == timestamps[cold_start]
    assert sanity.peak_temperature_c == -5.0
    assert sanity.max_load_inside_cold_week_kw == 4.0
    assert sanity.max_load_outside_cold_week_kw == 1.0


def test_alignment_requires_shared_weather_driver_identity() -> None:
    hourly = When2HeatHourlyProfile(
        timestamps_utc=_hourly_timestamps(1),
        thermal_demand_kw=np.array([3000.0]),
        electric_kw=np.array([1000.0]),
        cop=np.array([3.0]),
        components=(When2HeatComponent("heat", "cop", 1.0),),
    )
    quarter = downscale_hourly_to_15min(hourly)

    @dataclass(frozen=True)
    class TemperatureOnlyWeather:
        member_id: str
        source: str
        timestamps_utc: tuple[datetime, ...]
        temperature_c: np.ndarray

    weather = TemperatureOnlyWeather(
        member_id="temperature-only",
        source="knmi",
        timestamps_utc=quarter.timestamps_utc,
        temperature_c=np.zeros(4),
    )

    with pytest.raises(ValueError, match="shared_weather_driver_id"):
        align_heat_pump_profile(quarter, weather)


def test_alignment_rejects_temperature_only_shared_driver() -> None:
    hourly = When2HeatHourlyProfile(
        timestamps_utc=_hourly_timestamps(1),
        thermal_demand_kw=np.array([3000.0]),
        electric_kw=np.array([1000.0]),
        cop=np.array([3.0]),
        components=(When2HeatComponent("heat", "cop", 1.0),),
    )
    quarter = downscale_hourly_to_15min(hourly)

    @dataclass(frozen=True)
    class TemperatureOnlySharedWeather:
        member_id: str
        source: str
        shared_weather_driver_id: str
        timestamps_utc: tuple[datetime, ...]
        temperature_c: np.ndarray

    weather = TemperatureOnlySharedWeather(
        member_id="temperature-only",
        source="knmi",
        shared_weather_driver_id="knmi:temperature-only",
        timestamps_utc=quarter.timestamps_utc,
        temperature_c=np.zeros(4),
    )

    with pytest.raises(ValueError, match="PV/irradiance"):
        align_heat_pump_profile(quarter, weather)


def test_hp001_final_readiness_guard_requires_weather_and_cold_spell_approvals() -> None:
    annual_approvals = {
        "value_column": "HP-SCALING-VALUE-COLUMN",
        "denominator": "HP-SCALING-DENOMINATOR",
        "unit_conversion": "HP-SCALING-CONVERSION",
        "sfh_mfh_split": "HP-SCALING-SPLIT",
        "adoption_electrification": "HP-SCALING-ADOPTION",
    }

    assert HP001_FINAL_READINESS_REQUIRED_APPROVAL_KEYS == (
        "value_column",
        "denominator",
        "unit_conversion",
        "sfh_mfh_split",
        "adoption_electrification",
        "scenario_source_consistency",
        "d004_paired_weather_acceptance",
        "cold_spell_tolerances",
    )
    assert hp001_final_readiness_missing_approval_keys(annual_approvals) == (
        "scenario_source_consistency",
        "d004_paired_weather_acceptance",
        "cold_spell_tolerances",
    )
    with pytest.raises(ValueError, match="scenario-consistency"):
        require_hp001_final_readiness_approvals(annual_approvals)

    require_hp001_final_readiness_approvals(
        {
            **annual_approvals,
            "scenario_source_consistency": "A016-SCENARIO-CONSISTENCY-FUTURE",
            "d004_paired_weather_acceptance": "D004-PAIRED-ACCEPTANCE-FUTURE",
            "cold_spell_tolerances": "HP-COLD-SPELL-TOLERANCES-FUTURE",
        }
    )


def test_hp001_executable_value_binding_template_stays_fail_closed() -> None:
    packet = hp_scaling.build_hp001_executable_value_binding_decision_packet()

    with pytest.raises(ValueError, match="not approved for executable use"):
        hp001_local_scaling_config_from_value_binding_record(
            packet["unsigned_candidate_binding_record"]
        )

