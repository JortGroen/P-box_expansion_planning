from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
from urllib import parse
import zipfile

import numpy as np
import pytest

import data.get_weather_pv as weather_pv
from src.contracts.net_load import validate_executable_input_gate
from src.hp_model import HeatPumpProfile
from src.pv_model import (
    PVCapacitySourcePacket,
    PVGISReference,
    PVSystemConfig,
    PVWeatherInputArtifact,
    WeatherMember,
    canonical_15min_local_axis_for_year,
    canonical_15min_utc_axis_for_local_year,
    assert_pv_weather_artifact_allows_consumer_use,
    assert_weather_member_matches_input_artifact,
    build_pv_ic1_executable_input_artifact,
    build_pv_final_acceptance_gate_packet,
    build_pv_paired_readiness_preflight_packet,
    check_profile_against_pvgis_reference,
    generate_pv_profile,
    generate_pv_profile_from_input_artifact,
    load_pv_capacity_source_packet,
    load_pv_weather_input_artifact,
    parse_pvgis_monthly_reference,
    seasonal_energy_kwh,
    summarize_pv_profile,
    validate_canonical_15min_calendar,
)
from src.weather_model import assert_same_weather_realization


def _short_weather(
    *,
    temperature_c: list[float] | None = None,
    ghi_w_per_m2: list[float] | None = None,
) -> WeatherMember:
    timestamps_utc = tuple(datetime(2025, 1, 1, tzinfo=UTC) + timedelta(minutes=15 * index) for index in range(4))
    timestamps_local = tuple(item.astimezone(canonical_15min_local_axis_for_year(2025)[0].tzinfo) for item in timestamps_utc)
    return WeatherMember(
        member_id="knmi_member_001",
        shared_weather_driver_id="d004_test_weather:knmi_member_001",
        source="knmi_historical_plus_paired_irradiance",
        timestamps_utc=timestamps_utc,
        timestamps_local=timestamps_local,
        temperature_c=temperature_c or [25.0, 35.0, 400.0, 25.0],
        pv_weather_fields={"ghi_w_per_m2": ghi_w_per_m2 or [0.0, 1000.0, 1000.0, 2000.0]},
        provenance={"fixture": "pv_model_short_weather"},
    )


def test_canonical_15min_axis_preserves_local_year_and_dst() -> None:
    timestamps_utc = canonical_15min_utc_axis_for_local_year(2025)
    timestamps_local = canonical_15min_local_axis_for_year(2025)

    assert len(timestamps_utc) == 35_040
    assert len(timestamps_local) == 35_040
    assert timestamps_utc[0].isoformat() == "2024-12-31T23:00:00+00:00"
    assert timestamps_local[0].isoformat() == "2025-01-01T00:00:00+01:00"
    assert timestamps_local[-1].isoformat() == "2025-12-31T23:45:00+01:00"
    assert {int((right - left).total_seconds()) for left, right in zip(timestamps_utc, timestamps_utc[1:])} == {
        900
    }
    assert any(item.isoformat() == "2025-03-30T03:00:00+02:00" for item in timestamps_local)
    assert not any(item.isoformat() == "2025-03-30T02:00:00+01:00" for item in timestamps_local)


def test_weather_member_retains_paired_identity_and_complete_calendar() -> None:
    timestamps_utc = canonical_15min_utc_axis_for_local_year(2025)
    timestamps_local = canonical_15min_local_axis_for_year(2025)
    member = WeatherMember(
        member_id="knmi_2025_rotterdam_001",
        shared_weather_driver_id="knmi_historical_member:knmi_2025_rotterdam_001",
        source="knmi_historical_member",
        timestamps_utc=timestamps_utc,
        timestamps_local=timestamps_local,
        temperature_c=np.full(len(timestamps_utc), 12.0),
        pv_weather_fields={"ghi_w_per_m2": np.zeros(len(timestamps_utc))},
    )

    validate_canonical_15min_calendar(member, local_year=2025)
    assert member.shared_weather_driver_id == "knmi_historical_member:knmi_2025_rotterdam_001"
    assert member.identity_record()["cadence_seconds"] == 900
    assert member.identity_record()["first_timestamp_local"] == "2025-01-01T00:00:00+01:00"
    assert len(member.identity_record()["content_sha256"]) == 64

    incomplete = WeatherMember(
        member_id="knmi_2025_rotterdam_incomplete",
        shared_weather_driver_id="knmi_historical_member:knmi_2025_rotterdam_incomplete",
        source="knmi_historical_member",
        timestamps_utc=timestamps_utc[:-1],
        timestamps_local=timestamps_local[:-1],
        temperature_c=np.full(len(timestamps_utc) - 1, 12.0),
        pv_weather_fields={"ghi_w_per_m2": np.zeros(len(timestamps_utc) - 1)},
    )
    with pytest.raises(ValueError, match="canonical 2025 UTC calendar"):
        validate_canonical_15min_calendar(incomplete, local_year=2025)


def test_weather_member_rejects_unpaired_or_invalid_weather_paths() -> None:
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
    with pytest.raises(ValueError, match="timezone-aware"):
        WeatherMember(
            member_id="bad",
            shared_weather_driver_id="driver",
            source="knmi",
            timestamps_utc=(datetime(2025, 1, 1), datetime(2025, 1, 1, 0, 15)),
            timestamps_local=timestamps_local,
            temperature_c=[1.0, 1.0],
            pv_weather_fields={"ghi_w_per_m2": [0.0, 0.0]},
        )
    with pytest.raises(ValueError, match="non-negative"):
        _short_weather(ghi_w_per_m2=[0.0, -1.0, 0.0, 0.0])


def test_generate_pv_profile_uses_explicit_weather_and_config() -> None:
    weather = _short_weather()
    config = PVSystemConfig(
        installed_capacity_kw=10.0,
        performance_ratio=0.9,
        reference_irradiance_w_per_m2=1000.0,
        temperature_coefficient_per_c=-0.004,
        reference_temperature_c=25.0,
        clip_to_capacity=True,
        config_id="test_rooftop_config",
    )

    profile = generate_pv_profile(weather, config)

    assert profile.weather_member_id == weather.member_id
    assert profile.shared_weather_driver_id == weather.shared_weather_driver_id
    assert profile.config.config_id == "test_rooftop_config"
    assert profile.weather_identity["member_id"] == weather.member_id
    assert profile.weather_identity["content_sha256"] == weather.content_sha256
    assert profile.weather_content_sha256 == weather.content_sha256
    assert profile.identity_record()["member_id"] == weather.member_id
    assert profile.identity_record()["source"] == weather.source
    assert profile.identity_record()["content_sha256"] == weather.content_sha256
    assert profile.identity_record()["shared_weather_driver_id"] == weather.shared_weather_driver_id
    np.testing.assert_allclose(profile.generation_kw, [0.0, 8.64, 0.0, 10.0])
    assert profile.annual_energy_kwh() == pytest.approx((8.64 + 10.0) * 0.25)

def test_pv_profile_rejects_mismatched_weather_identity() -> None:
    weather = _short_weather()
    config = PVSystemConfig(
        installed_capacity_kw=1.0,
        performance_ratio=1.0,
        reference_irradiance_w_per_m2=1000.0,
        temperature_coefficient_per_c=0.0,
        reference_temperature_c=25.0,
        clip_to_capacity=True,
    )
    identity = weather.identity_record()
    identity["shared_weather_driver_id"] = "different_driver"

    with pytest.raises(ValueError, match="shared_weather_driver_id"):
        weather_profile = generate_pv_profile(weather, config)
        type(weather_profile)(
            weather_member_id=weather.member_id,
            weather_source=weather.source,
            shared_weather_driver_id=weather.shared_weather_driver_id,
            timestamps_utc=weather.timestamps_utc,
            timestamps_local=weather.timestamps_local,
            generation_kw=weather_profile.generation_kw,
            config=config,
            weather_identity=identity,
        )


def test_summarize_pv_profile_exposes_weather_content_identity() -> None:
    weather = _short_weather()
    config = PVSystemConfig(
        installed_capacity_kw=1.0,
        performance_ratio=1.0,
        reference_irradiance_w_per_m2=1000.0,
        temperature_coefficient_per_c=0.0,
        reference_temperature_c=25.0,
        clip_to_capacity=True,
    )
    summary = summarize_pv_profile(generate_pv_profile(weather, config))

    assert summary["weather_content_sha256"] == weather.content_sha256
    assert summary["weather_identity_record"]["member_id"] == weather.member_id
    assert summary["weather_identity_record"]["weather_member_id"] == weather.member_id
    assert summary["weather_identity_record"]["content_sha256"] == weather.content_sha256
    assert summary["weather_identity_record"]["shared_weather_driver_id"] == weather.shared_weather_driver_id
    assert summary["weather_identity_record"]["cadence_seconds"] == 900


def test_synthetic_hp_and_pv_profiles_share_weather_identity_without_final_acceptance() -> None:
    weather = _short_weather(temperature_c=[5.0, 5.5, 6.0, 6.5], ghi_w_per_m2=[0.0, 50.0, 100.0, 150.0])
    config = PVSystemConfig(
        installed_capacity_kw=1.0,
        performance_ratio=0.9,
        reference_irradiance_w_per_m2=1000.0,
        temperature_coefficient_per_c=0.0,
        reference_temperature_c=25.0,
        clip_to_capacity=True,
    )
    pv_profile = generate_pv_profile(weather, config)
    hp_profile = HeatPumpProfile(
        shared_weather_driver_id=weather.shared_weather_driver_id,
        weather_member_id=weather.member_id,
        weather_source=weather.source,
        timestamps_utc=weather.timestamps_utc,
        timestamps_local=weather.timestamps_local,
        electric_kw=np.full(weather.n_timesteps, 0.4),
        thermal_demand_kw=np.full(weather.n_timesteps, 1.2),
        cop=np.full(weather.n_timesteps, 3.0),
        temperature_c=weather.temperature_c,
        source_columns=("synthetic_hp_kw",),
        source_path=None,
        downscaling_method="synthetic_scaffold_not_acceptance",
        pv_weather_field_names=tuple(weather.pv_weather_fields),
        weather_content_sha256=weather.content_sha256,
        weather_provenance={"scope": "synthetic common-driver scaffold only"},
    )

    assert_same_weather_realization(weather, pv_profile.identity_record())
    assert_same_weather_realization(pv_profile.identity_record(), hp_profile.weather_identity_record())

    mismatched = dict(hp_profile.weather_identity_record())
    mismatched["shared_weather_driver_id"] = "different-driver"
    with pytest.raises(ValueError, match="shared_weather_driver_id"):
        assert_same_weather_realization(pv_profile.identity_record(), mismatched)


def test_pvgis_reference_check_covers_seasonal_totals_and_peak_timing() -> None:
    timestamps_utc = canonical_15min_utc_axis_for_local_year(2025)
    timestamps_local = canonical_15min_local_axis_for_year(2025)
    month_to_kw = {1: 1.0, 2: 1.0, 12: 1.0, 3: 2.0, 4: 2.0, 5: 2.0, 6: 4.0, 7: 4.0, 8: 4.0, 9: 2.5, 10: 2.5, 11: 2.5}
    ghi = np.asarray([month_to_kw[item.month] / 10.0 * 1000.0 for item in timestamps_local])
    weather = WeatherMember(
        member_id="weather_member_with_summer_peak",
        shared_weather_driver_id="synthetic_weather:weather_member_with_summer_peak",
        source="knmi_paired_irradiance",
        timestamps_utc=timestamps_utc,
        timestamps_local=timestamps_local,
        temperature_c=np.full(len(timestamps_utc), 25.0),
        pv_weather_fields={"ghi_w_per_m2": ghi},
    )
    config = PVSystemConfig(
        installed_capacity_kw=10.0,
        performance_ratio=1.0,
        reference_irradiance_w_per_m2=1000.0,
        temperature_coefficient_per_c=0.0,
        reference_temperature_c=25.0,
        clip_to_capacity=True,
        config_id="seasonal_shape",
    )
    profile = generate_pv_profile(weather, config)
    reference = PVGISReference(
        source_id="synthetic_pvgis_reference",
        seasonal_energy_kwh=seasonal_energy_kwh(profile),
        peak_month=7,
    )

    check = check_profile_against_pvgis_reference(
        profile,
        reference,
        max_relative_seasonal_error=1e-12,
        max_relative_annual_error=1e-12,
        allowed_peak_months=[6, 7, 8],
    )

    assert check.passed is True
    assert check.profile_peak_month in {6, 7, 8}
    shifted_reference = PVGISReference(
        source_id="shifted_reference",
        seasonal_energy_kwh={**seasonal_energy_kwh(profile), "JJA": seasonal_energy_kwh(profile)["JJA"] * 1.2},
        peak_month=1,
    )
    failed = check_profile_against_pvgis_reference(
        profile,
        shifted_reference,
        max_relative_seasonal_error=0.01,
    )
    assert failed.passed is False
    assert any("JJA seasonal relative error" in reason for reason in failed.failed_reasons)
    assert any("peak month" in reason for reason in failed.failed_reasons)


def test_parse_pvgis_monthly_reference_is_validation_only() -> None:
    payload = {
        "outputs": {
            "monthly": {
                "fixed": [
                    {"month": month, "E_m": float(100 + month * 10)}
                    for month in range(1, 13)
                ]
            }
        }
    }

    reference = parse_pvgis_monthly_reference(payload, source_id="pvgis_tmy_rotterdam")

    assert reference.typical_year_use == "calibration_or_validation_only"
    assert reference.peak_month == 12
    assert reference.seasonal_energy_kwh["DJF"] == pytest.approx(110.0 + 120.0 + 220.0)
    assert reference.annual_energy_kwh == pytest.approx(sum(100 + month * 10 for month in range(1, 13)))


def test_weather_pv_url_builders_are_official_and_credential_free() -> None:
    pvgis_url = weather_pv.build_pvgis_seriescalc_url(
        lat=52.0,
        lon=4.3,
        startyear=2014,
        endyear=2023,
        peakpower_kw=1.0,
        loss_percent=14.0,
        angle_degrees=35.0,
        aspect_degrees=0.0,
    )
    parsed = parse.urlparse(pvgis_url)
    query = parse.parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "re.jrc.ec.europa.eu"
    assert parsed.path == "/api/v5_3/seriescalc"
    assert query["pvcalculation"] == ["1"]
    assert query["peakpower"] == ["1.0"]
    assert query["outputformat"] == ["json"]

    tmy_url = weather_pv.build_pvgis_tmy_url(lat=52.0, lon=4.3)
    assert parse.urlparse(tmy_url).path == "/api/v5_3/tmy"

    knmi_list_url = weather_pv.build_knmi_file_list_url(max_keys=25)
    knmi_parsed = parse.urlparse(knmi_list_url)
    assert knmi_parsed.scheme == "https"
    assert knmi_parsed.netloc == "api.dataplatform.knmi.nl"
    assert (
        knmi_parsed.path
        == "/open-data/v1/datasets/10-minute-in-situ-meteorological-observations/versions/1.0/files"
    )
    assert parse.parse_qs(knmi_parsed.query)["maxKeys"] == ["25"]
    assert "Authorization" not in knmi_list_url

    temporary_url_endpoint = weather_pv.build_knmi_temporary_url_endpoint("knmi file.nc")
    assert temporary_url_endpoint.endswith("/files/knmi%20file.nc/url")


def test_weather_pv_retrieval_plan_records_no_download(tmp_path: Path) -> None:
    path = weather_pv.write_retrieval_plan(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    base_metadata = tmp_path / "d-004_weather_pv.json"

    assert path == tmp_path / "weather_pv" / "d004_weather_pv_retrieval_plan.json"
    assert base_metadata.is_file()
    assert payload["download_performed"] is False
    assert payload["raw_data_committed"] is False
    assert payload["pvgis"]["typical_year_use"] == "calibration_or_validation_only"
    assert payload["pvgis"]["realized_weather_path_use"] is False
    assert payload["knmi"]["authorization_header_stored"] is False
    assert payload["alea_001"]["hp_and_pv_same_weather_member_required"] is True


def test_weather_pv_execution_plan_is_metadata_only(tmp_path: Path) -> None:
    path = weather_pv.write_execution_plan(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert path == tmp_path / "weather_pv" / "d004_weather_pv_execution_plan.json"
    assert payload["data_id"] == "D-004"
    assert payload["download_performed"] is False
    assert payload["raw_data_committed"] is False
    assert payload["data_register_status"] == "proposed"
    assert payload["shared_weather_contract"]["question_id"] == "Q-8"
    assert payload["shared_weather_contract"]["decision_id"] == "WEATHER-001"
    assert payload["shared_weather_contract"]["neutral_paths_owned"] is True
    assert payload["official_source_verification"]["pvgis"]["expected_size_bytes"] is None
    assert payload["official_source_verification"]["knmi"]["expected_size_bytes"] is None
    assert payload["checkpoint_resume_plan"]["current_download_helper_resume_capable"] is False
    assert "LONG-RUN NOTICE" in payload["long_run_notice_text"]
    assert "<D004_SELECTION_ID>" in payload["exact_commands_after_pi_selection"]["knmi_download"]
    assert "PVGIS TMY" in " ".join(payload["acceptance_boundary"])


def test_committed_weather_pv_execution_plan_records_no_real_data_acceptance() -> None:
    payload = json.loads(Path("data/metadata/weather_pv/d004_weather_pv_execution_plan.json").read_text(encoding="utf-8"))

    assert payload["download_performed"] is False
    assert payload["raw_data_committed"] is False
    assert payload["data_register_status"] == "proposed"
    assert "PI sign-off pending" in payload["status"]
    assert "src/weather_model.py" in payload["shared_weather_contract"]["implemented_paths"]
    assert "DATA_REGISTER D-004 must be updated only after concrete file/version/checksum selections are made" in (
        " ".join(payload["acceptance_boundary"])
    )


def test_committed_d004_source_selection_packet_is_proposal_only() -> None:
    packet_path = Path("data/metadata/weather_pv/d004_source_selection_pi_packet.json")
    payload = json.loads(packet_path.read_text(encoding="utf-8"))
    selection = payload["proposed_selection"]

    assert payload["data_id"] == "D-004"
    assert payload["download_performed"] is False
    assert selection["selection_id"] == "d004_alkmaar_berkhout_2014_2023_v1"
    assert selection["status"] == "proposed_not_pi_signed"
    assert "WEATHER-001 resolved Q-8" in selection["shared_weather_status"]
    assert payload["long_run_notice_required_for_next_step"] is False
    assert "LONG-RUN NOTICE" in payload["long_run_notice_text_if_scope_expands"]


def test_committed_d004_source_selection_packet_pins_sources_and_guards_tmy() -> None:
    payload = json.loads(Path("data/metadata/weather_pv/d004_source_selection_pi_packet.json").read_text(encoding="utf-8"))
    pvgis = payload["pvgis"]
    knmi = payload["knmi"]

    assert pvgis["site"]["area_identifier"] == "GM0361"
    assert pvgis["site"]["latitude"] == pytest.approx(52.63167)
    assert pvgis["site"]["longitude"] == pytest.approx(4.74861)
    assert pvgis["radiation_database"] == "PVGIS-SARAH3"
    assert "not a realized weather path" in pvgis["use_boundary"]
    assert {request["role"] for request in pvgis["requests"]} == {
        "hourly_series_reference",
        "typical_year_reference",
    }

    assert knmi["primary_source_proposal"] == "validated_hourly_station_zips"
    assert knmi["station"]["station_id"] == 249
    assert knmi["station"]["station_name"] == "Berkhout"
    assert knmi["year_range"] == {
        "first_year": 2014,
        "last_year": 2023,
        "filter_rule": "download the two decade ZIP files, then extract/filter only complete calendar years 2014-2023 for accepted members",
    }
    assert [source["head_content_length_bytes"] for source in knmi["files"]] == [1_536_802, 838_086]
    assert all(source["target_path"].startswith("data/raw/weather_pv/knmi/") for source in knmi["files"])
    assert any(question["id"] == "D004-Q4" for question in payload["approval_questions"])


def test_record_local_weather_pv_file_records_checksum_without_register_update(tmp_path: Path) -> None:
    source = tmp_path / "knmi_sample.nc"
    source.write_bytes(b"sample weather bytes")

    manifest_path = weather_pv.record_local_file(
        file_path=source,
        source_kind="knmi",
        file_role="historical_weather_path",
        metadata_dir=tmp_path / "metadata",
        source_url="https://example.test/knmi_sample.nc",
    )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert payload["data_id"] == "D-004"
    assert payload["source_kind"] == "knmi"
    assert payload["file_role"] == "historical_weather_path"
    assert payload["sha256_file"] == hashlib.sha256(b"sample weather bytes").hexdigest()
    assert payload["raw_data_committed"] is False
    assert "PI accepts" in payload["status"]


def test_committed_d004_retrieval_manifest_records_only_approved_four_file_route() -> None:
    manifest_path = Path("data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_retrieval_manifest.json")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = payload["source_files"]

    assert payload["selection_id"] == "d004_alkmaar_berkhout_2014_2023_v1"
    assert payload["download_performed"] is True
    assert payload["d004_status"] == "proposed_pending_pi_review"
    assert payload["raw_data_committed"] is False
    assert payload["no_analysis_performed"] is True
    assert payload["q8_shared_weather_implementation"].startswith("implemented separately")
    assert len(files) == 4
    assert {item["source_kind"] for item in files} == {"pvgis", "knmi"}
    assert {item["file_role"] for item in files} == {
        "hourly_series_calibration_or_validation_reference",
        "typical_year_calibration_or_validation_only",
        "validated_hourly_station_249_zip_2011_2020",
        "validated_hourly_station_249_zip_2021_2030",
    }
    assert all(len(item["sha256_file"]) == 64 for item in files)
    assert all(item["size_bytes"] > 0 for item in files)
    assert any("not a realized sampled weather path" in item for item in payload["validation_boundary"])
    assert any("no net-load" in item for item in payload["validation_boundary"])
    assert any("WEATHER-001 shared-weather contract implemented separately" in item for item in payload["validation_boundary"])


def test_committed_d004_source_acceptance_evidence_is_readiness_only() -> None:
    evidence_path = Path(
        "data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_source_acceptance_evidence.json"
    )
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))

    assert payload["data_id"] == "D-004"
    assert payload["selection_id"] == "d004_alkmaar_berkhout_2014_2023_v1"
    assert payload["status"] == "proposed_pending_pi_review"
    assert payload["no_analysis_performed"] is True
    assert all(item["sha256_matches_manifest"] for item in payload["raw_files"])
    assert all(item["size_matches_manifest"] for item in payload["raw_files"])
    assert all(
        payload["knmi_station_249_hourly_coverage"]["years"][str(year)]["complete"]
        for year in range(2014, 2024)
    )
    assert payload["pvgis_sarah3_hourly_series_coverage"]["rows_by_year"] == {
        str(year): 8784 if year in {2016, 2020} else 8760
        for year in range(2014, 2024)
    }
    assert payload["weather_001_compatibility"]["pv_model_consumes_neutral_weather_member"] is True
    assert any("hourly-to-15-minute" in item for item in payload["remaining_before_final_d004_acceptance"])


def test_committed_d004_member_construction_rule_packet_records_approval_without_d004_signoff() -> None:
    packet_path = Path("data/metadata/weather_pv/d004_member_construction_rule_packet.json")
    payload = json.loads(packet_path.read_text(encoding="utf-8"))
    rule = payload["proposed_rule"]

    assert payload["data_id"] == "D-004"
    assert payload["decision_packet_status"] == "approved_by_decisions_register"
    assert payload["member_construction_rule_status"] == "approved"
    assert payload["d004_status_after_packet"] == "proposed_not_signed"
    assert payload["no_raw_download"] is True
    assert payload["no_integrated_analysis"] is True
    assert rule["calendar"]["calendar_year_basis"] == "UTC calendar year"
    assert rule["calendar"]["step_seconds"] == 900
    assert rule["calendar"]["timesteps_non_leap"] == 35_040
    assert rule["calendar"]["timesteps_leap"] == 35_136
    assert rule["knmi_hourly_source"]["temperature_field"]["target_field"] == "temperature_c"
    assert rule["knmi_hourly_source"]["ghi_field"]["target_field"] == "ghi_w_per_m2"
    assert rule["knmi_hourly_source"]["ghi_field"]["conversion"] == "Q * 10000 / 3600"
    assert rule["pvgis_reference_source"]["not_realized_weather_member_source"] is True
    assert rule["weather_member_identity"]["years"] == list(range(2014, 2024))
    assert "pv_weather_fields.ghi_w_per_m2" in rule["weather_member_fields"]
    assert "content_sha256" in rule["weather_member_fields"]
    assert any("Q energy" in item for item in payload["acceptance_tests_after_pi_approval"])
    assert "D-004 source acceptance/sign-off remains pending" in payload["remaining_blockers"]
    assert not any("PI approval of D004-MC-001" in item for item in payload["remaining_blockers"])


def test_committed_d004_member_construction_clarification_records_resolution() -> None:
    path = Path("data/metadata/weather_pv/d004_member_construction_pi_clarification.json")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["data_id"] == "D-004"
    assert payload["question_id"] == "Q-9"
    assert payload["member_construction_rule_id"] == "D004-MC-001"
    assert payload["clarification_status"] == "resolved_by_decisions_register"
    assert payload["implementation_allowed_before_approval"] is True
    assert payload["resolved_by"] == "D004-MC-001 approved in registers/DECISIONS.md"
    assert payload["d004_status"] == "proposed_not_signed"
    assert payload["recommended_approval_summary"]["calendar_basis"] == "UTC calendar year"
    assert payload["recommended_approval_summary"]["pvgis_use"] == "calibration_or_validation_provenance_only"
    assert any("no D-004 signoff" in item for item in payload["scope_boundaries"])
    assert any("no net-load/event/P(E)" in item for item in payload["scope_boundaries"])


def test_d004_member_readiness_diagnostics_can_validate_metadata_without_raw_files(tmp_path: Path) -> None:
    metadata_src = Path("data/metadata/weather_pv")
    metadata_dst = tmp_path / "metadata" / "weather_pv"
    metadata_dst.mkdir(parents=True)
    for name in [
        weather_pv.D004_RETRIEVAL_MANIFEST,
        weather_pv.D004_MEMBER_MANIFEST_NAME,
        *[weather_pv.D004_MEMBER_METADATA_TEMPLATE.format(year=year) for year in range(2014, 2024)],
    ]:
        (metadata_dst / name).write_text((metadata_src / name).read_text(encoding="utf-8"), encoding="utf-8")

    diagnostics = weather_pv.build_d004_member_readiness_diagnostics(
        root_dir=tmp_path,
        metadata_dir=tmp_path / "metadata",
        include_raw_diagnostics=False,
    )

    assert diagnostics["d004_final_acceptance"] is False
    assert diagnostics["no_integrated_analysis"] is True
    assert diagnostics["manifest_checks"]["years_match_2014_2023"] is True
    assert diagnostics["manifest_checks"]["all_calendar_cadence_ok"] is True
    assert diagnostics["manifest_checks"]["all_energy_preserved"] is True
    assert diagnostics["manifest_checks"]["pvgis_realized_weather_path"] is False
    assert diagnostics["hp_pv_paired_weather_readiness"]["status"] == "metadata_ready_pending_integrated_acceptance"
    assert all(not item["local_file_present"] for item in diagnostics["raw_source_checks"])
    assert diagnostics["pvgis_knmi_seasonal_peak_diagnostics"]["status"] == "not_run_raw_files_unavailable"


def test_committed_d004_member_readiness_diagnostics_records_unsigned_readiness() -> None:
    path = Path("data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_member_readiness_diagnostics.json")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["data_id"] == "D-004"
    assert payload["selection_id"] == "d004_alkmaar_berkhout_2014_2023_v1"
    assert payload["status"] == "readiness_diagnostics_pending_pi_review"
    assert payload["d004_final_acceptance"] is False
    assert payload["no_integrated_analysis"] is True
    assert payload["no_manuscript_results"] is True
    assert payload["manifest_checks"]["members_present"] == 10
    assert payload["manifest_checks"]["years"] == list(range(2014, 2024))
    assert payload["manifest_checks"]["all_calendar_cadence_ok"] is True
    assert payload["manifest_checks"]["all_energy_preserved"] is True
    assert payload["manifest_checks"]["all_temperature_finite"] is True
    assert payload["manifest_checks"]["all_ghi_nonnegative"] is True
    assert payload["manifest_checks"]["pvgis_realized_weather_path"] is False
    assert all(item["sha256_matches_manifest"] for item in payload["raw_source_checks"])
    assert all(item["size_matches_manifest"] for item in payload["raw_source_checks"])
    assert payload["hp_pv_paired_weather_readiness"]["identity_roundtrip_ok"] is True
    assert payload["hp_pv_paired_weather_readiness"]["paired_acceptance_not_run"] is True
    assert payload["pvgis_knmi_seasonal_peak_diagnostics"]["tolerance_status"] == "not_pi_signed_diagnostic_only"
    assert payload["pvgis_knmi_seasonal_peak_diagnostics"]["years"]["2020"]["knmi_peak_ghi_month_utc"] in {5, 6, 7}
    assert "net-load" in " ".join(payload["remaining_before_final_d004_acceptance"])

def _write_knmi_fixture_zip(path: Path, *, year: int, q_j_per_cm2: int = 360, t_tenths_c: int = 125) -> None:
    header = "# STN,YYYYMMDD,   HH,    T,    Q"
    rows = [header]
    current = datetime(year, 1, 1, tzinfo=UTC)
    end = datetime(year + 1, 1, 1, tzinfo=UTC)
    while current < end:
        for hour in range(1, 25):
            rows.append(f"  249,{current:%Y%m%d},{hour:5d},{t_tenths_c:5d},{q_j_per_cm2:5d}")
        current += timedelta(days=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(path.with_suffix(".txt").name, "\n".join(rows) + "\n")


def _write_empty_knmi_fixture_zip(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(path.with_suffix(".txt").name, "# STN,YYYYMMDD,   HH,    T,    Q\n")


def _write_d004_fixture_manifest(root: Path, metadata_dir: Path, *, year: int) -> None:
    selection = weather_pv.D004_SELECTION_ID
    knmi_one = root / "data" / "raw" / "weather_pv" / "knmi" / selection / "uurgeg_249_2011-2020.zip"
    knmi_two = root / "data" / "raw" / "weather_pv" / "knmi" / selection / "uurgeg_249_2021-2030.zip"
    pvgis_series = root / "data" / "raw" / "weather_pv" / "pvgis" / selection / "pvgis_seriescalc.json"
    pvgis_tmy = root / "data" / "raw" / "weather_pv" / "pvgis" / selection / "pvgis_tmy.json"
    _write_knmi_fixture_zip(knmi_one, year=year)
    _write_empty_knmi_fixture_zip(knmi_two)
    pvgis_series.parent.mkdir(parents=True, exist_ok=True)
    pvgis_series.write_text('{"fixture":"series"}\n', encoding="utf-8")
    pvgis_tmy.write_text('{"fixture":"tmy"}\n', encoding="utf-8")

    def item(path: Path, source_kind: str, file_role: str) -> dict[str, object]:
        return {
            "path": path.relative_to(root).as_posix(),
            "source_kind": source_kind,
            "file_role": file_role,
            "source_url": f"https://example.test/{path.name}",
            "size_bytes": path.stat().st_size,
            "sha256_file": weather_pv.sha256_file(path),
        }

    manifest = {
        "data_id": "D-004",
        "selection_id": selection,
        "d004_status": "proposed_pending_pi_review",
        "source_files": [
            item(pvgis_series, "pvgis", "hourly_series_calibration_or_validation_reference"),
            item(pvgis_tmy, "pvgis", "typical_year_calibration_or_validation_only"),
            item(knmi_one, "knmi", "validated_hourly_station_249_zip_2011_2020"),
            item(knmi_two, "knmi", "validated_hourly_station_249_zip_2021_2030"),
        ],
    }
    out_dir = metadata_dir / "weather_pv"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / weather_pv.D004_RETRIEVAL_MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

def test_committed_d004_acceptance_packet_keeps_decisions_with_pi() -> None:
    path = Path("data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_acceptance_packet.json")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["data_id"] == "D-004"
    assert payload["status"] == "pi_acceptance_packet_proposed_not_signed"
    assert any("D-004 remains proposed" in item for item in payload["scope_boundaries"])
    assert any("not a realized weather path" in item for item in payload["scope_boundaries"])
    assert payload["source_completeness_summary"]["source_checksums_match"] is True
    assert payload["source_completeness_summary"]["knmi_years_complete_2014_2023"] is True
    assert payload["member_readiness_summary"]["calendar_cadence_ok"] is True
    assert payload["member_readiness_summary"]["energy_preserved"] is True
    assert payload["member_readiness_summary"]["pvgis_realized_weather_path"] is False
    assert payload["member_readiness_summary"]["hp_pv_identity_roundtrip_ok"] is True
    assert payload["seasonal_peak_sanity_summary"]["tolerance_status"] == "not_pi_signed_diagnostic_only"
    assert payload["seasonal_peak_sanity_summary"]["diagnostic_only_not_final_acceptance"] is True
    assert {question["id"] for question in payload["pi_decision_questions"]} == {
        "D004-ACCEPT-Q1",
        "D004-ACCEPT-Q2",
        "D004-ACCEPT-Q3",
        "D004-ACCEPT-Q4",
    }
    assert "P(E)" in " ".join(payload["scope_boundaries"])


def test_d004_paired_weather_acceptance_scaffold_is_metadata_only(tmp_path: Path) -> None:
    metadata_src = Path("data/metadata/weather_pv")
    metadata_dst = tmp_path / "metadata" / "weather_pv"
    metadata_dst.mkdir(parents=True)
    for name in [
        weather_pv.D004_ACCEPTANCE_PACKET_NAME,
        weather_pv.D004_MEMBER_READINESS_DIAGNOSTICS_NAME,
        weather_pv.D004_MEMBER_MANIFEST_NAME,
    ]:
        (metadata_dst / name).write_text((metadata_src / name).read_text(encoding="utf-8"), encoding="utf-8")

    payload = weather_pv.build_d004_paired_weather_acceptance_scaffold(metadata_dir=tmp_path / "metadata")

    assert payload["status"] == "paired_weather_acceptance_scaffold_not_final"
    assert payload["d004_final_acceptance"] is False
    assert payload["paired_hp_pv_acceptance_run"] is False
    assert payload["source_member_acceptance_candidate"]["status"] == "candidate_for_pi_review_not_signed"
    assert payload["source_member_acceptance_candidate"]["all_scaffold_checks_passed"] is True
    assert len(payload["member_identity_records"]) == 10
    assert payload["paired_weather_identity_contract"]["required_equal_fields"] == [
        "member_id",
        "shared_weather_driver_id",
        "source",
        "first_timestamp_utc",
        "last_timestamp_utc",
        "n_timesteps",
        "cadence_seconds",
        "content_sha256",
    ]
    assert payload["pvgis_boundary"]["realized_weather_path"] is False
    assert any(item["gate"] == "cold-spell acceptance" for item in payload["blocked_acceptance_layers"])
    assert any("P(E)" in item["gate"] for item in payload["blocked_acceptance_layers"])


def test_committed_d004_paired_weather_acceptance_scaffold_keeps_final_gates_blocked() -> None:
    path = Path(
        "data/metadata/weather_pv/"
        "d004_alkmaar_berkhout_2014_2023_v1_paired_weather_acceptance_scaffold.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["data_id"] == "D-004"
    assert payload["status"] == "paired_weather_acceptance_scaffold_not_final"
    assert payload["d004_final_acceptance"] is False
    assert payload["paired_hp_pv_acceptance_run"] is False
    assert payload["cold_spell_acceptance_run"] is False
    assert payload["source_member_acceptance_candidate"]["all_scaffold_checks_passed"] is True
    assert len(payload["member_identity_records"]) == 10
    assert all(len(item["content_sha256"]) == 64 for item in payload["member_identity_records"])
    assert payload["pvgis_boundary"]["role"].endswith("provenance context only under D004-MC-001")
    assert payload["paired_weather_identity_contract"]["pv_record"] == "src.pv_model.PVGenerationProfile.identity_record()"
    assert "synthetic" in payload["paired_weather_identity_contract"]["synthetic_test_scope"]
    assert any(item["gate"] == "paired HP/PV validation" for item in payload["blocked_acceptance_layers"])


def test_d004_acceptance_tolerance_packet_is_metadata_only(tmp_path: Path) -> None:
    metadata_src = Path("data/metadata/weather_pv")
    metadata_dst = tmp_path / "metadata" / "weather_pv"
    metadata_dst.mkdir(parents=True)
    for name in [
        weather_pv.D004_ACCEPTANCE_PACKET_NAME,
        weather_pv.D004_PAIRED_WEATHER_ACCEPTANCE_SCAFFOLD_NAME,
        weather_pv.D004_MEMBER_READINESS_DIAGNOSTICS_NAME,
    ]:
        (metadata_dst / name).write_text((metadata_src / name).read_text(encoding="utf-8"), encoding="utf-8")

    payload = weather_pv.build_d004_acceptance_tolerance_packet(metadata_dir=tmp_path / "metadata")

    assert payload["status"] == "pi_acceptance_tolerance_packet_proposed_not_signed"
    assert payload["d004_final_acceptance"] is False
    assert payload["paired_hp_pv_acceptance_run"] is False
    assert {item["id"] for item in payload["satisfied_evidence_for_pi_review"]} == {
        "D004-EVIDENCE-SOURCE-FILES",
        "D004-EVIDENCE-KNMI-COMPLETENESS",
        "D004-EVIDENCE-WEATHER-MEMBERS",
        "D004-EVIDENCE-PVGIS-BOUNDARY",
        "D004-EVIDENCE-WEATHER-IDENTITY",
    }
    assert all(item["status"] == "satisfied_for_pi_review_not_signed" for item in payload["satisfied_evidence_for_pi_review"])
    assert {item["id"] for item in payload["unsigned_tolerance_decisions"]} == {
        "D004-TOL-SOURCE-MEMBER",
        "D004-TOL-PVGIS-SEASONAL-PEAK",
        "D004-TOL-PAIRED-HP-PV",
        "D004-TOL-COLD-SPELL",
    }
    assert any("HP annual local scaling" in item for item in payload["must_wait_for_hp_pv_validation"])
    assert any("no event detection" in item for item in payload["out_of_scope_guards"])


def test_committed_d004_acceptance_tolerance_packet_keeps_tolerances_unsigned() -> None:
    path = Path(
        "data/metadata/weather_pv/"
        "d004_alkmaar_berkhout_2014_2023_v1_acceptance_tolerance_packet.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["data_id"] == "D-004"
    assert payload["status"] == "pi_acceptance_tolerance_packet_proposed_not_signed"
    assert payload["source_member_acceptance_candidate"]["all_scaffold_checks_passed"] is True
    assert payload["d004_final_acceptance"] is False
    assert payload["cold_spell_acceptance_run"] is False
    assert payload["no_integrated_analysis"] is True
    assert payload["no_manuscript_results"] is True
    assert all(item["status"] == "satisfied_for_pi_review_not_signed" for item in payload["satisfied_evidence_for_pi_review"])
    seasonal = next(item for item in payload["unsigned_tolerance_decisions"] if item["id"] == "D004-TOL-PVGIS-SEASONAL-PEAK")
    assert seasonal["current_diagnostic_range"]["annual_ghi_to_pvgis_gi_ratio_min"] == pytest.approx(0.806128)
    assert seasonal["current_diagnostic_range"]["annual_ghi_to_pvgis_gi_ratio_max"] == pytest.approx(0.848755)
    assert "PI supplies explicit" in " ".join(seasonal["options_for_pi"])
    paired = next(item for item in payload["unsigned_tolerance_decisions"] if item["id"] == "D004-TOL-PAIRED-HP-PV")
    assert paired["strict_identity_fields"] == [
        "member_id",
        "shared_weather_driver_id",
        "source",
        "first_timestamp_utc",
        "last_timestamp_utc",
        "n_timesteps",
        "cadence_seconds",
        "content_sha256",
    ]
    assert "no net-load aggregation" in payload["out_of_scope_guards"]
    assert "no event detection or P(E)" in payload["out_of_scope_guards"]


def test_d004_pi_recommendation_packet_is_concise_and_unsigned(tmp_path: Path) -> None:
    metadata_src = Path("data/metadata/weather_pv")
    metadata_dst = tmp_path / "metadata" / "weather_pv"
    metadata_dst.mkdir(parents=True)
    for name in [
        weather_pv.D004_ACCEPTANCE_TOLERANCE_PACKET_NAME,
        weather_pv.D004_ACCEPTANCE_PACKET_NAME,
    ]:
        (metadata_dst / name).write_text((metadata_src / name).read_text(encoding="utf-8"), encoding="utf-8")

    payload = weather_pv.build_d004_pi_recommendation_packet(metadata_dir=tmp_path / "metadata")

    assert payload["status"] == "pi_recommendation_packet_proposed_not_signed"
    assert payload["d004_final_acceptance"] is False
    assert payload["paired_hp_pv_acceptance_run"] is False
    assert [item["id"] for item in payload["recommended_pi_decisions"]] == [
        "D004-REC-1-SOURCE-MEMBER",
        "D004-REC-2-PVGIS-SANITY",
        "D004-REC-3-WEATHER-IDENTITY",
        "D004-REC-4-COLD-SPELL",
    ]
    assert payload["recommended_pi_decisions"][0]["recommended_outcome"] == "approve_source_member_acceptance_only"
    assert payload["recommended_pi_decisions"][1]["numeric_tolerance_status"] == "unsigned_not_recommended_for_source_member_gate"
    assert payload["recommended_pi_decisions"][2]["recommended_outcome"] == "approve_exact_identity_calendar_prerequisite"
    assert payload["recommended_pi_decisions"][3]["recommended_outcome"] == "defer_to_hp_cold_spell_tolerance_decision"
    assert any("manifested paired HP/PV" in item for item in payload["decision_sequence_recommendation"])
    assert "no event detection or P(E)" in payload["out_of_scope_guards"]


def test_committed_d004_pi_recommendation_packet_keeps_decisions_with_pi() -> None:
    path = Path(
        "data/metadata/weather_pv/"
        "d004_alkmaar_berkhout_2014_2023_v1_pi_recommendation_packet.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["data_id"] == "D-004"
    assert payload["status"] == "pi_recommendation_packet_proposed_not_signed"
    assert payload["d004_final_acceptance"] is False
    assert payload["cold_spell_acceptance_run"] is False
    assert payload["no_integrated_analysis"] is True
    source = next(item for item in payload["recommended_pi_decisions"] if item["id"] == "D004-REC-1-SOURCE-MEMBER")
    assert source["recommended_outcome"] == "approve_source_member_acceptance_only"
    assert "D004-EVIDENCE-SOURCE-FILES" in source["basis"]
    pvgis = next(item for item in payload["recommended_pi_decisions"] if item["id"] == "D004-REC-2-PVGIS-SANITY")
    assert pvgis["basis"]["annual_ghi_to_pvgis_gi_ratio_min"] == pytest.approx(0.806128)
    assert pvgis["numeric_tolerance_status"] == "unsigned_not_recommended_for_source_member_gate"
    weather = next(item for item in payload["recommended_pi_decisions"] if item["id"] == "D004-REC-3-WEATHER-IDENTITY")
    assert weather["strict_identity_fields"][-1] == "content_sha256"
    cold = next(item for item in payload["recommended_pi_decisions"] if item["id"] == "D004-REC-4-COLD-SPELL")
    assert any("near-freezing" in item for item in cold["remaining_decisions"])
    assert "no capacity screen" in payload["out_of_scope_guards"]


def test_committed_d004_source_member_acceptance_decision_is_partial() -> None:
    metadata_path = Path(
        "data/metadata/weather_pv/"
        "d004_alkmaar_berkhout_2014_2023_v1_source_member_acceptance_decision.json"
    )
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    decisions = Path("registers/DECISIONS.md").read_text(encoding="utf-8")
    data_register = Path("registers/DATA_REGISTER.md").read_text(encoding="utf-8")

    assert payload["decision_id"] == "D004-SOURCE-MEMBER-ACCEPTANCE"
    assert payload["status"] == "approved_for_internal_first_screen_source_member_use_final_paired_acceptance_pending"
    assert payload["approved_scope"]["realized_weather_path"].startswith("KNMI station 249")
    assert payload["approved_scope"]["pvgis_role"].startswith("qualitative")
    assert payload["exact_weather_identity_fields"] == [
        "member_id",
        "shared_weather_driver_id",
        "source",
        "first_timestamp_utc",
        "last_timestamp_utc",
        "n_timesteps",
        "cadence_seconds",
        "content_sha256",
    ]
    assert "numerical HP cold-spell tolerances" in payload["deferred_decisions"]
    assert "D004-SOURCE-MEMBER-ACCEPTANCE" in decisions
    assert "approved for internal first-screen source/member use; final paired/cold-spell acceptance pending" in data_register
    assert "final paired HP/PV validation" in data_register

def test_d004_weather_input_artifact_builds_from_accepted_source_member_metadata(tmp_path: Path) -> None:
    metadata_src = Path("data/metadata/weather_pv")
    metadata_dst = tmp_path / "metadata" / "weather_pv"
    metadata_dst.mkdir(parents=True)
    for name in [
        weather_pv.D004_SOURCE_MEMBER_ACCEPTANCE_DECISION_NAME,
        weather_pv.D004_MEMBER_MANIFEST_NAME,
        weather_pv.D004_MEMBER_READINESS_DIAGNOSTICS_NAME,
    ]:
        (metadata_dst / name).write_text((metadata_src / name).read_text(encoding="utf-8"), encoding="utf-8")

    payload = weather_pv.build_d004_weather_input_artifact(metadata_dir=tmp_path / "metadata")
    first_member = payload["members"][0]

    assert payload["status"] == "accepted_for_source_member_readiness_final_paired_cold_spell_pending"
    assert payload["source_member_acceptance_id"] == "D004-SOURCE-MEMBER-ACCEPTANCE"
    assert payload["accepted_for_source_member_use"] is True
    assert payload["ready_for_source_member_component_input_gate"] is True
    assert payload["readiness_scope"] == "source_member_component_input_only_not_final_integrated"
    assert payload["ready_for_executable_input_gate_scope"].endswith("not_final_integrated")
    assert payload["realized_weather_path"].startswith("KNMI station 249")
    assert payload["pvgis_realized_weather_path"] is False
    assert payload["pvgis_role"].startswith("qualitative seasonal/peak sanity")
    assert payload["blocked_acceptance_gates"]["final_paired_hp_pv_acceptance"]["blocked"] is True
    assert payload["blocked_acceptance_gates"]["cold_spell_acceptance"]["blocked"] is True
    assert payload["blocked_acceptance_gates"]["integrated_analysis"]["blocked"] is True
    assert payload["required_identity_fields_for_hp_pv_pairing"] == [
        "member_id",
        "shared_weather_driver_id",
        "source",
        "first_timestamp_utc",
        "last_timestamp_utc",
        "n_timesteps",
        "cadence_seconds",
        "content_sha256",
    ]
    assert len(payload["members"]) == 10
    assert first_member["accepted_for_source_member_use"] is True
    assert first_member["final_paired_hp_pv_acceptance"] is False
    assert first_member["cold_spell_acceptance"] is False
    assert first_member["calendar_id"] == "d004_alkmaar_berkhout_2014_2023_v1:utc_year_15min_europe_amsterdam:2014"
    assert first_member["cadence_seconds"] == 900
    assert len(first_member["content_sha256"]) == 64
    assert first_member["shared_weather_driver_id"] == "d004_alkmaar_berkhout_2014_2023_v1:2014"
    assert first_member["weather_fields"]["temperature_c"]["conversion"] == "T / 10"
    assert first_member["weather_fields"]["pv_weather_fields.ghi_w_per_m2"]["hourly_energy_preserved"] is True


def test_committed_d004_weather_input_artifact_exposes_input_gate_but_blocks_final_acceptance() -> None:
    payload = weather_pv.load_d004_weather_input_artifact()

    assert payload["artifact_type"] == "accepted_weather_001_source_member_index_for_component_input_gate"
    assert payload["source_member_acceptance_id"] == "D004-SOURCE-MEMBER-ACCEPTANCE"
    assert payload["source_member_acceptance_status"] == (
        "approved_for_internal_first_screen_source_member_use_final_paired_acceptance_pending"
    )
    assert payload["accepted_for_source_member_use"] is True
    assert payload["ready_for_source_member_component_input_gate"] is True
    assert payload["readiness_scope"] == "source_member_component_input_only_not_final_integrated"
    assert payload["ready_for_executable_input_gate_scope"].endswith("not_final_integrated")
    assert payload["weather_contract"] == "WEATHER-001"
    assert payload["member_construction_rule_id"] == "D004-MC-001"
    assert payload["calendar_contract"]["cadence_seconds"] == 900
    assert payload["calendar_contract"]["timezone"] == "Europe/Amsterdam"
    assert payload["pvgis_realized_weather_path"] is False
    assert payload["pvgis_role"].startswith("qualitative seasonal/peak sanity")
    assert payload["blocked_acceptance_gates"]["final_paired_hp_pv_acceptance"]["blocked"] is True
    assert payload["blocked_acceptance_gates"]["cold_spell_acceptance"]["blocked"] is True
    assert payload["blocked_acceptance_gates"]["integrated_analysis"]["blocked"] is True
    assert [member["year"] for member in payload["members"]] == list(range(2014, 2024))
    assert all(member["accepted_for_source_member_use"] is True for member in payload["members"])
    assert all(member["final_paired_hp_pv_acceptance"] is False for member in payload["members"])
    assert all(member["cold_spell_acceptance"] is False for member in payload["members"])
    assert {member["shared_weather_driver_id"] for member in payload["members"]} == {
        f"d004_alkmaar_berkhout_2014_2023_v1:{year}" for year in range(2014, 2024)
    }


def test_pv_weather_input_artifact_adapter_loads_committed_source_member_gate() -> None:
    artifact = load_pv_weather_input_artifact(
        "data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_weather_input_artifact.json"
    )
    member = artifact.member_for_year(2020)

    assert artifact.source_member_acceptance_id == "D004-SOURCE-MEMBER-ACCEPTANCE"
    assert artifact.accepted_for_source_member_use is True
    assert artifact.ready_for_source_member_component_input_gate is True
    assert artifact.readiness_scope == "source_member_component_input_only_not_final_integrated"
    assert artifact.pvgis_realized_weather_path is False
    assert artifact.blocked_acceptance_gates["final_paired_hp_pv_acceptance"]["blocked"] is True
    assert artifact.blocked_acceptance_gates["cold_spell_acceptance"]["blocked"] is True
    assert member["member_id"] == "d004_alkmaar_berkhout_2020_v1"
    assert member["calendar_id"] == "d004_alkmaar_berkhout_2014_2023_v1:utc_year_15min_europe_amsterdam:2020"
    assert member["cadence_seconds"] == 900
    assert member["shared_weather_driver_id"] == "d004_alkmaar_berkhout_2014_2023_v1:2020"
    assert len(str(member["content_sha256"])) == 64


def test_pv_weather_input_artifact_rejects_pvgis_as_realized_or_unblocked_final_gate(tmp_path: Path) -> None:
    payload = json.loads(
        Path("data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_weather_input_artifact.json").read_text(
            encoding="utf-8"
        )
    )
    pvgis_path = tmp_path / "pvgis_realized.json"
    pvgis_path.write_text(json.dumps({**payload, "pvgis_realized_weather_path": True}), encoding="utf-8")
    with pytest.raises(ValueError, match="PVGIS"):
        load_pv_weather_input_artifact(pvgis_path)

    unsafe = json.loads(json.dumps(payload))
    unsafe["blocked_acceptance_gates"]["final_paired_hp_pv_acceptance"]["blocked"] = False
    unsafe_path = tmp_path / "final_gate_unblocked.json"
    unsafe_path.write_text(json.dumps(unsafe), encoding="utf-8")
    with pytest.raises(ValueError, match="final_paired_hp_pv_acceptance"):
        load_pv_weather_input_artifact(unsafe_path)


def test_pv_weather_artifact_consumer_gate_rejects_final_acceptance_use() -> None:
    artifact = load_pv_weather_input_artifact(
        "data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_weather_input_artifact.json"
    )

    assert_pv_weather_artifact_allows_consumer_use(artifact, intended_use="source_member_component_input")
    with pytest.raises(ValueError, match="final_paired_hp_pv_acceptance"):
        assert_pv_weather_artifact_allows_consumer_use(
            artifact,
            intended_use="final_paired_hp_pv_acceptance",
        )
    with pytest.raises(ValueError, match="final_paired_hp_pv_acceptance"):
        generate_pv_profile_from_input_artifact(
            _short_weather(temperature_c=[15.0, 15.0, 15.0, 15.0], ghi_w_per_m2=[0.0, 100.0, 500.0, 1000.0]),
            PVSystemConfig(
                installed_capacity_kw=1.0,
                performance_ratio=0.9,
                reference_irradiance_w_per_m2=1000.0,
                temperature_coefficient_per_c=0.0,
                reference_temperature_c=25.0,
                clip_to_capacity=True,
            ),
            artifact,
            year=2014,
            intended_use="final_paired_hp_pv_acceptance",
        )


def test_pv_system_config_fails_closed_without_parameter_signoff() -> None:
    unsigned = PVSystemConfig(
        installed_capacity_kw=1.0,
        performance_ratio=0.9,
        reference_irradiance_w_per_m2=1000.0,
        temperature_coefficient_per_c=0.0,
        reference_temperature_c=25.0,
        clip_to_capacity=True,
    )
    with pytest.raises(ValueError, match="unsigned"):
        unsigned.require_signed_parameters()

    with pytest.raises(ValueError, match="signed_parameter_decision_id"):
        PVSystemConfig(
            installed_capacity_kw=1.0,
            performance_ratio=0.9,
            reference_irradiance_w_per_m2=1000.0,
            temperature_coefficient_per_c=0.0,
            reference_temperature_c=25.0,
            clip_to_capacity=True,
            parameter_status="approved_for_executable_component_use",
        )

    signed = PVSystemConfig(
        installed_capacity_kw=1.0,
        performance_ratio=0.9,
        reference_irradiance_w_per_m2=1000.0,
        temperature_coefficient_per_c=0.0,
        reference_temperature_c=25.0,
        clip_to_capacity=True,
        parameter_status="approved_for_executable_component_use",
        signed_parameter_decision_id="PV-PARAM-001",
    )
    signed.require_signed_parameters()


def test_committed_d004_pv_parameter_decision_packet_is_unsigned_fail_closed() -> None:
    payload = json.loads(Path("data/metadata/weather_pv/d004_pv_parameter_decision_packet.json").read_text(encoding="utf-8"))

    assert payload["decision_id"] == "PV-PARAM-001"
    assert payload["status"] == "proposed_pending_pi_signoff"
    assert payload["parameter_config_status"] == "unsigned_fail_closed_scaffold"
    assert payload["blocks_signed_executable_pv_generation"] is True
    assert "PV-CAP-001" in payload["governing_inputs"]
    assert "PV-ORIENT-001" in payload["governing_inputs"]
    assert "statistical orientation/tilt" in payload["source_traceability"]["orientation_tilt_scope"]
    assert "outside PV-PARAM-001" in payload["source_traceability"]["capacity_source_status"]
    assert "CBS Alkmaar" in payload["source_traceability"]["capacity_source_status"]
    assert {item["field"] for item in payload["recommended_decisions"]} == {
        "installed_capacity_kw",
        "tilt_aspect",
        "losses_or_performance_ratio",
        "temperature_coefficient_per_c",
        "clipping",
        "ghi_vs_plane_of_array",
    }
    assert payload["scaffold_contract"]["guard_method"] == "PVSystemConfig.require_signed_parameters()"
    assert payload["scaffold_contract"]["required_signed_value"] == "PV-PARAM-001"
    proposed = payload["proposed_primary_first_pass_config_template"]
    assert proposed["config_id"] == "pv_param_001_first_pass_statistical_geometry_ghi_pr086_no_temp_clipped_v1"
    assert proposed["installed_capacity_kw"]["default"] is None
    assert proposed["installed_capacity_kw"]["value"] == "caller_supplied_per_node_or_fleet"
    assert "PV-CAP-001" in proposed["installed_capacity_kw"]["source"]
    assert "PV-CAP-001" in proposed["installed_capacity_kw"]["fail_closed_rule"]
    assert proposed["performance_ratio"]["value"] == pytest.approx(0.86)
    assert "PVGIS reference request loss_percent=14.0" in proposed["performance_ratio"]["source"]
    assert proposed["temperature_adjustment"]["temperature_coefficient_per_c"] == pytest.approx(0.0)
    assert proposed["irradiance_input_basis"]["value"] == "weather_member_ghi_w_per_m2"
    assert proposed["tilt_aspect"]["primary_first_pass_use"] == "statistical_distribution_required_before_executable_use"
    assert proposed["tilt_aspect"]["location_specific_geometry"] == "deferred_until_after_first_real_experiment"
    assert payload["proposed_formula_for_pi_review"]["formula"].startswith("pv_kw[t] = sum_bins")
    assert "no net-load/event/P(E)/threshold/capacity-screen/manuscript results" in payload["out_of_scope_guards"]


def test_pv_paired_readiness_preflight_fails_closed_without_signed_inputs() -> None:
    artifact = load_pv_weather_input_artifact(
        "data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_weather_input_artifact.json"
    )

    packet = build_pv_paired_readiness_preflight_packet(artifact)

    assert packet["source_member_acceptance_id"] == "D004-SOURCE-MEMBER-ACCEPTANCE"
    assert packet["source_member_ready"] is True
    assert packet["pvgis_realized_weather_path"] is False
    assert packet["pv_parameters_signed_for_component_use"] is False
    assert packet["hp_weather_identity_supplied"] is False
    assert packet["hp_pv_weather_identity_equal"] is False
    assert packet["cold_spell_tolerances_status"] == "pending_unsigned"
    assert packet["ready_for_final_paired_hp_pv_acceptance_run"] is False
    assert packet["final_paired_hp_pv_acceptance_signed_by_this_packet"] is False
    assert packet["blocking_register_ids"] == (
        "PV-PARAM-001",
        "FINAL-PAIRED-HP-PV-ACCEPTANCE",
        "COLD-SPELL-ACCEPTANCE",
    )


def test_pv_paired_readiness_preflight_requires_exact_weather_identity() -> None:
    artifact = load_pv_weather_input_artifact(
        "data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_weather_input_artifact.json"
    )
    hp_identity = dict(artifact.member_for_year(2020))
    hp_identity["content_sha256"] = "f" * 64
    signed_config = PVSystemConfig(
        installed_capacity_kw=1.0,
        performance_ratio=0.9,
        reference_irradiance_w_per_m2=1000.0,
        temperature_coefficient_per_c=0.0,
        reference_temperature_c=25.0,
        clip_to_capacity=True,
        parameter_status="approved_for_executable_component_use",
        signed_parameter_decision_id="PV-PARAM-001",
    )

    packet = build_pv_paired_readiness_preflight_packet(
        artifact,
        parameter_config=signed_config,
        hp_weather_identity=hp_identity,
        cold_spell_metadata={
            "numerical_tolerances_status": "approved_with_signed_tolerances",
            "signed_decision_id": "COLD-SPELL-TOLERANCE-001",
        },
    )

    assert packet["pv_parameters_signed_for_component_use"] is True
    assert packet["hp_pv_weather_identity_equal"] is False
    assert packet["ready_for_final_paired_hp_pv_acceptance_run"] is False
    assert packet["blocking_register_ids"] == ("FINAL-PAIRED-HP-PV-ACCEPTANCE",)
    assert "content_sha256" in packet["hp_pv_identity_check"]


def test_pv_paired_readiness_preflight_can_only_make_run_prerequisites_true_not_sign_acceptance() -> None:
    artifact = load_pv_weather_input_artifact(
        "data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_weather_input_artifact.json"
    )
    signed_config = PVSystemConfig(
        installed_capacity_kw=1.0,
        performance_ratio=0.9,
        reference_irradiance_w_per_m2=1000.0,
        temperature_coefficient_per_c=0.0,
        reference_temperature_c=25.0,
        clip_to_capacity=True,
        parameter_status="approved_for_executable_component_use",
        signed_parameter_decision_id="PV-PARAM-001",
    )

    packet = build_pv_paired_readiness_preflight_packet(
        artifact,
        parameter_config=signed_config,
        hp_weather_identity=artifact.member_for_year(2020),
        cold_spell_metadata={
            "numerical_tolerances_status": "approved_with_signed_tolerances",
            "signed_decision_id": "COLD-SPELL-TOLERANCE-001",
            "near_freezing_band_status": "signed_fixture_for_contract_test_only",
        },
    )

    assert packet["hp_pv_weather_identity_equal"] is True
    assert packet["ready_for_final_paired_hp_pv_acceptance_run"] is True
    assert packet["final_paired_hp_pv_acceptance_signed_by_this_packet"] is False
    assert packet["blocking_register_ids"] == ()
    json.dumps(dict(packet))


def _signed_pv_config_for_gate() -> PVSystemConfig:
    return PVSystemConfig(
        installed_capacity_kw=1.0,
        performance_ratio=0.9,
        reference_irradiance_w_per_m2=1000.0,
        temperature_coefficient_per_c=0.0,
        reference_temperature_c=25.0,
        clip_to_capacity=True,
        parameter_status="approved_for_executable_component_use",
        signed_parameter_decision_id="PV-PARAM-001",
    )


def _signed_cold_spell_metadata_for_gate() -> dict[str, object]:
    return {
        "numerical_tolerances_status": "approved_with_signed_tolerances",
        "signed_decision_id": "COLD-SPELL-TOLERANCE-001",
        "near_freezing_band_c_min": -2.0,
        "near_freezing_band_c_max": 2.0,
        "coldest_7_day_mean_temperature_tolerance_c": 1.0,
        "coldest_3_day_mean_temperature_tolerance_c": 1.0,
        "temperature_load_response_metric": "signed_metric_placeholder",
        "cop_response_metric": "signed_metric_placeholder",
        "first_real_acceptance_run_preinspection_signed": True,
    }


def test_pv_final_acceptance_gate_requires_explicit_member_subset() -> None:
    artifact = load_pv_weather_input_artifact(
        "data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_weather_input_artifact.json"
    )

    with pytest.raises(ValueError, match="member_ids"):
        build_pv_final_acceptance_gate_packet(
            artifact,
            parameter_config=_signed_pv_config_for_gate(),
            hp_weather_identities=(),
            cold_spell_metadata=_signed_cold_spell_metadata_for_gate(),
            member_ids=(),
        )


def test_pv_final_acceptance_gate_blocks_vague_cold_spell_tolerance_metadata() -> None:
    artifact = load_pv_weather_input_artifact(
        "data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_weather_input_artifact.json"
    )
    member = artifact.member_for_year(2020)

    packet = build_pv_final_acceptance_gate_packet(
        artifact,
        parameter_config=_signed_pv_config_for_gate(),
        hp_weather_identities=(member,),
        cold_spell_metadata={
            "numerical_tolerances_status": "approved_with_signed_tolerances",
            "signed_decision_id": "COLD-SPELL-TOLERANCE-001",
        },
        member_ids=(str(member["member_id"]),),
    )

    assert packet["hp_pv_weather_identity_equal"] is True
    assert packet["cold_spell_tolerances_signed"] is False
    assert "near_freezing_band_c_min" in packet["missing_cold_spell_tolerance_fields"]
    assert packet["blocking_register_ids"] == ("COLD-SPELL-ACCEPTANCE",)
    assert packet["ready_for_first_real_paired_acceptance_run"] is False


def test_pv_final_acceptance_gate_blocks_hp_weather_identity_drift() -> None:
    artifact = load_pv_weather_input_artifact(
        "data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_weather_input_artifact.json"
    )
    member = dict(artifact.member_for_year(2020))
    member["shared_weather_driver_id"] = "different-driver"

    packet = build_pv_final_acceptance_gate_packet(
        artifact,
        parameter_config=_signed_pv_config_for_gate(),
        hp_weather_identities=(member,),
        cold_spell_metadata=_signed_cold_spell_metadata_for_gate(),
        member_ids=(str(member["member_id"]),),
    )

    assert packet["hp_pv_weather_identity_equal"] is False
    assert packet["paired_identity_results"][0]["passed"] is False
    assert "shared_weather_driver_id" in packet["paired_identity_results"][0]["reason"]
    assert packet["blocking_register_ids"] == ("FINAL-PAIRED-HP-PV-ACCEPTANCE",)


def test_pv_final_acceptance_gate_can_be_structurally_ready_without_signing_final_acceptance() -> None:
    artifact = load_pv_weather_input_artifact(
        "data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_weather_input_artifact.json"
    )
    member = artifact.member_for_year(2020)

    packet = build_pv_final_acceptance_gate_packet(
        artifact,
        parameter_config=_signed_pv_config_for_gate(),
        hp_weather_identities=(member,),
        cold_spell_metadata=_signed_cold_spell_metadata_for_gate(),
        member_ids=(str(member["member_id"]),),
    )

    assert packet["ready_for_first_real_paired_acceptance_run"] is True
    assert packet["final_paired_hp_pv_acceptance_signed_by_this_packet"] is False
    assert packet["blocking_register_ids"] == ()
    assert packet["paired_identity_results"][0]["content_sha256"] == member["content_sha256"]
    json.dumps(dict(packet))


def test_committed_pv_final_acceptance_gate_packet_is_fail_closed() -> None:
    payload = json.loads(Path("data/metadata/weather_pv/d004_pv_final_acceptance_gate_packet.json").read_text(encoding="utf-8"))

    assert payload["scaffold_helper"] == "src.pv_model.build_pv_final_acceptance_gate_packet"
    assert payload["source_member_acceptance_id"] == "D004-SOURCE-MEMBER-ACCEPTANCE"
    assert payload["pv_parameter_gate"]["current_status"] == "proposed_pending_pi_signoff"
    assert payload["pv_parameter_gate"]["currently_satisfied"] is False
    assert payload["paired_weather_identity_gate"]["currently_satisfied"] is False
    assert payload["cold_spell_tolerance_gate"]["currently_satisfied"] is False
    assert "near_freezing_band_c_min" in payload["cold_spell_tolerance_gate"]["required_fields"]
    assert payload["fail_closed_result"]["ready_for_first_real_paired_acceptance_run"] is False
    assert payload["fail_closed_result"]["final_paired_hp_pv_acceptance_signed_by_this_packet"] is False
    assert payload["fail_closed_result"]["blocking_register_ids"] == [
        "PV-PARAM-001",
        "FINAL-PAIRED-HP-PV-ACCEPTANCE",
        "COLD-SPELL-ACCEPTANCE",
    ]
    assert "no event detection" in payload["out_of_scope_guards"]

def test_pv_weather_artifact_builds_ic1_source_member_input_bridge_but_blocks_execution() -> None:
    artifact = load_pv_weather_input_artifact(
        "data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_weather_input_artifact.json"
    )

    ic1_artifact = build_pv_ic1_executable_input_artifact(
        artifact,
        year=2021,
        node_ids=("pv-node-a", "pv-node-b"),
    )
    record = ic1_artifact.manifest_record()

    assert record["artifact_status"] == "unsigned"
    assert record["member_id"] == "d004_alkmaar_berkhout_2021_v1"
    assert record["source_id"] == "D-004:d004_alkmaar_berkhout_2014_2023_v1:WEATHER-001:pv"
    assert record["node_ids"] == ("pv-node-a", "pv-node-b")
    assert record["calendar_id"] == "d004_alkmaar_berkhout_2014_2023_v1:utc_year_15min_europe_amsterdam:2021"
    assert record["shared_weather_driver_id"] == "d004_alkmaar_berkhout_2014_2023_v1:2021"
    assert record["signed_register_ids"] == (
        "WEATHER-001",
        "D004-MC-001",
        "D004-SOURCE-MEMBER-ACCEPTANCE",
    )
    assert record["blocking_register_ids"] == (
        "PV-PARAM-001",
        "FINAL-PAIRED-HP-PV-ACCEPTANCE",
        "COLD-SPELL-ACCEPTANCE",
    )
    assert record["provenance"]["content_sha256"] == artifact.member_for_year(2021)["content_sha256"]
    assert record["provenance"]["pvgis_realized_weather_path"] is False
    assert record["provenance"]["readiness_scope"] == "source_member_component_input_only_not_final_integrated"
    assert record["provenance"]["pv_parameter_decision_status"].startswith("PV-PARAM-001 proposed")
    assert record["provenance"]["deferred_acceptance_gates"] == (
        "cold_spell_acceptance",
        "final_paired_hp_pv_acceptance",
        "integrated_analysis",
    )
    with pytest.raises(ValueError, match="PV-PARAM-001"):
        validate_executable_input_gate(
            (ic1_artifact,),
            required_component_kinds=("pv",),
            intended_use="pv_weather_source_member_component_input_readiness",
        )


def test_pv_weather_ic1_artifact_calendar_override_is_explicit_not_silent() -> None:
    artifact = load_pv_weather_input_artifact(
        "data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_weather_input_artifact.json"
    )

    ic1_artifact = build_pv_ic1_executable_input_artifact(
        artifact,
        year=2022,
        node_ids=("pv-node-a",),
        ic1_calendar_id="ic1-planning-calendar-2035-v1",
        manifest_path="data/metadata/weather_pv/custom_manifest.json",
    )
    manifest = ic1_artifact.manifest_record()

    assert manifest["calendar_id"] == "ic1-planning-calendar-2035-v1"
    assert manifest["provenance"]["source_calendar_id"] == (
        "d004_alkmaar_berkhout_2014_2023_v1:utc_year_15min_europe_amsterdam:2022"
    )
    assert manifest["provenance"]["ic1_calendar_id"] == "ic1-planning-calendar-2035-v1"
    assert manifest["provenance"]["calendar_mapping_status"] == "caller_supplied_not_d004_signed_by_this_helper"
    assert manifest["manifest_path"] == "data/metadata/weather_pv/custom_manifest.json"


def test_pv_weather_input_artifact_matches_identity_and_blocks_checksum_drift() -> None:
    artifact = load_pv_weather_input_artifact(
        "data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_weather_input_artifact.json"
    )
    identity = dict(artifact.member_for_year(2019))

    matched = assert_weather_member_matches_input_artifact(identity, artifact, year=2019)

    assert matched["member_id"] == "d004_alkmaar_berkhout_2019_v1"
    drifted = dict(identity)
    drifted["content_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="content_sha256"):
        assert_weather_member_matches_input_artifact(drifted, artifact, year=2019)


def test_generate_pv_profile_from_input_artifact_preserves_weather_artifact_provenance() -> None:
    weather = _short_weather(temperature_c=[15.0, 15.0, 15.0, 15.0], ghi_w_per_m2=[0.0, 100.0, 500.0, 1000.0])
    base_payload = json.loads(
        Path("data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_weather_input_artifact.json").read_text(
            encoding="utf-8"
        )
    )
    identity = weather.identity_record()
    member = dict(base_payload["members"][0])
    member.update({key: identity[key] for key in base_payload["required_identity_fields_for_hp_pv_pairing"]})
    member.update(
        {
            "year": 2025,
            "first_timestamp_local": identity["first_timestamp_local"],
            "last_timestamp_local": identity["last_timestamp_local"],
            "calendar_id": "d004_test_weather:utc_year_15min_europe_amsterdam:2025",
        }
    )
    base_payload["members"] = [member]
    base_payload["calendar_contract"] = {
        **base_payload["calendar_contract"],
        "calendar_id_pattern": "d004_test_weather:utc_year_15min_europe_amsterdam:<YEAR>",
        "years": [2025],
    }
    artifact_path = Path("data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_weather_input_artifact.json")
    artifact = load_pv_weather_input_artifact(artifact_path)
    artifact = type(artifact)(
        data_id=artifact.data_id,
        selection_id=artifact.selection_id,
        status=artifact.status,
        source_member_acceptance_id=artifact.source_member_acceptance_id,
        weather_contract=artifact.weather_contract,
        accepted_for_source_member_use=artifact.accepted_for_source_member_use,
        ready_for_executable_input_gate=artifact.ready_for_executable_input_gate,
        readiness_scope=artifact.readiness_scope,
        ready_for_source_member_component_input_gate=artifact.ready_for_source_member_component_input_gate,
        evidence_artifacts=artifact.evidence_artifacts,
        realized_weather_path=artifact.realized_weather_path,
        pvgis_role=artifact.pvgis_role,
        pvgis_realized_weather_path=artifact.pvgis_realized_weather_path,
        required_identity_fields_for_hp_pv_pairing=artifact.required_identity_fields_for_hp_pv_pairing,
        calendar_contract=base_payload["calendar_contract"],
        members=base_payload["members"],
        blocked_acceptance_gates=artifact.blocked_acceptance_gates,
    )
    config = PVSystemConfig(
        installed_capacity_kw=2.0,
        performance_ratio=0.9,
        reference_irradiance_w_per_m2=1000.0,
        temperature_coefficient_per_c=0.0,
        reference_temperature_c=25.0,
        clip_to_capacity=True,
        config_id="artifact_adapter_fixture",
    )

    profile = generate_pv_profile_from_input_artifact(weather, config, artifact, year=2025)
    record = profile.identity_record()

    assert profile.shared_weather_driver_id == weather.shared_weather_driver_id
    assert profile.weather_content_sha256 == weather.content_sha256
    assert record["source_member_acceptance_id"] == "D004-SOURCE-MEMBER-ACCEPTANCE"
    assert record["weather_input_artifact_status"] == "accepted_for_source_member_readiness_final_paired_cold_spell_pending"
    assert record["calendar_id"] == "d004_test_weather:utc_year_15min_europe_amsterdam:2025"
    assert record["pvgis_realized_weather_path"] is False
    assert record["pvgis_role"].startswith("qualitative seasonal/peak sanity")
    np.testing.assert_allclose(profile.generation_kw, [0.0, 0.18, 0.9, 1.8])
def test_d004_weather_member_builder_expands_knmi_hourly_fixture_to_utc_year(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    _write_d004_fixture_manifest(tmp_path, metadata_dir, year=2014)

    result = weather_pv.build_d004_weather_members(
        root_dir=tmp_path,
        metadata_dir=metadata_dir,
        years=(2014,),
        write_member_metadata=True,
    )
    member = result.members[0]

    assert member.member_id == "d004_alkmaar_berkhout_2014_v1"
    assert member.shared_weather_driver_id == "d004_alkmaar_berkhout_2014_2023_v1:2014"
    assert member.timestamps_utc[0].isoformat() == "2014-01-01T00:00:00+00:00"
    assert member.timestamps_utc[-1].isoformat() == "2014-12-31T23:45:00+00:00"
    assert member.timestamps_local[0].isoformat() == "2014-01-01T01:00:00+01:00"
    assert member.n_timesteps == 35_040
    np.testing.assert_allclose(member.temperature_c[:4], [12.5, 12.5, 12.5, 12.5])
    np.testing.assert_allclose(member.ghi_w_per_m2[:4], [1000.0, 1000.0, 1000.0, 1000.0])
    assert member.provenance["pvgis"]["not_realized_weather_member_source"] is True

    metadata = json.loads(result.metadata_paths[0].read_text(encoding="utf-8"))
    assert metadata["content_sha256"] == member.content_sha256
    assert metadata["calendar"]["calendar_year_basis"] == "UTC calendar year"
    assert metadata["knmi_hourly_source"]["source_hourly_rows"] == 8760
    assert metadata["knmi_hourly_source"]["energy_preservation_abs_error_j_per_cm2"] == pytest.approx(0.0)
    assert metadata["source_files"]["pvgis"][0]["file_role"] == "hourly_series_calibration_or_validation_reference"
    assert metadata["boundaries"][0].startswith("D-004 remains proposed")
    assert result.manifest_path is not None


def test_d004_builder_constructs_recorded_members_when_raw_files_available() -> None:
    required = [Path(item["path"]) for item in json.loads(Path("data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_retrieval_manifest.json").read_text(encoding="utf-8"))["source_files"]]
    if not all(path.is_file() for path in required):
        pytest.skip("ignored D-004 raw files are not available in this checkout")

    result = weather_pv.build_d004_weather_members(write_member_metadata=False)
    by_year = {int(member.metadata["year"]): member for member in result.members}

    assert set(by_year) == set(range(2014, 2024))
    assert by_year[2014].n_timesteps == 35_040
    assert by_year[2016].n_timesteps == 35_136
    assert by_year[2020].n_timesteps == 35_136
    assert by_year[2023].timestamps_utc[-1].isoformat() == "2023-12-31T23:45:00+00:00"
    assert all(member.ghi_w_per_m2.min() >= 0.0 for member in result.members)
    assert all(np.isfinite(member.temperature_c).all() for member in result.members)
    assert all(member.shared_weather_driver_id == f"d004_alkmaar_berkhout_2014_2023_v1:{year}" for year, member in by_year.items())
    assert all(member.provenance["pvgis"]["not_realized_weather_member_source"] is True for member in result.members)


def test_committed_d004_weather_member_manifest_records_constructed_members() -> None:
    manifest_path = Path("data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_weather_members_manifest.json")
    if not manifest_path.is_file():
        pytest.skip("D-004 weather-member manifest has not been generated in this checkout")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert payload["data_id"] == "D-004"
    assert payload["member_construction_rule_id"] == "D004-MC-001"
    assert payload["status"] == "constructed_from_approved_rule_pending_final_d004_source_acceptance"
    assert payload["source_use_boundary"]["pvgis_realized_weather_path"] is False
    assert payload["no_final_d004_acceptance"] is True
    assert payload["no_integrated_analysis"] is True
    assert [member["year"] for member in payload["members"]] == list(range(2014, 2024))
    assert len({member["content_sha256"] for member in payload["members"]}) == 10
    assert payload["members"][0]["first_timestamp_utc"] == "2014-01-01T00:00:00+00:00"
    assert payload["members"][-1]["last_timestamp_utc"] == "2023-12-31T23:45:00+00:00"


def test_committed_d004_weather_member_metadata_preserves_energy_and_identity() -> None:
    metadata_path = Path("data/metadata/weather_pv/d004_alkmaar_berkhout_2014_2023_v1_member_2020_metadata.json")
    if not metadata_path.is_file():
        pytest.skip("D-004 2020 weather-member metadata has not been generated in this checkout")
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert payload["member_id"] == "d004_alkmaar_berkhout_2020_v1"
    assert payload["shared_weather_driver_id"] == "d004_alkmaar_berkhout_2014_2023_v1:2020"
    assert payload["calendar"]["n_timesteps"] == 35_136
    assert payload["calendar"]["first_timestamp_utc"] == "2020-01-01T00:00:00+00:00"
    assert payload["calendar"]["last_timestamp_utc"] == "2020-12-31T23:45:00+00:00"
    assert payload["knmi_hourly_source"]["source_hourly_rows"] == 8784
    assert payload["knmi_hourly_source"]["energy_preservation_abs_error_j_per_cm2"] == pytest.approx(0.0)
    assert payload["knmi_hourly_source"]["ghi_min_w_per_m2"] >= 0.0
    assert len(payload["content_sha256"]) == 64
    assert payload["identity_record"]["shared_weather_driver_id"] == payload["shared_weather_driver_id"]
    assert payload["source_files"]["pvgis"][0]["file_role"].endswith("reference")
    assert any("No HP/PV paired acceptance" in item for item in payload["boundaries"])


def test_committed_d014_pv_capacity_source_packet_is_fail_closed() -> None:
    packet = load_pv_capacity_source_packet(
        "data/metadata/weather_pv/d014_pv_capacity_source_value_packet.json"
    )
    record = packet.identity_record()

    assert packet.packet_id == "D014-PV-CAPACITY-SOURCE-VALUE-PACKET"
    assert packet.data_id == "D-014"
    assert packet.governing_decisions["approved_route"] == "PV-CAP-001"
    assert packet.primary_cbs_anchor_source["table_id"] == "85005NED"
    assert packet.ii3050_growth_factor_source["numeric_growth_factor_approved"] is False
    assert packet.download_performed is False
    assert packet.raw_data_committed is False
    assert "ii3050_growth_factor_value" in packet.missing_approval_keys
    assert "PV-PARAM-001_or_amended_conversion_decision" in packet.missing_approval_keys
    assert "statistical_orientation_tilt_distribution_source" in packet.missing_approval_keys
    assert "statistical_orientation_tilt_distribution_weights" in packet.missing_approval_keys
    assert record["cbs_table_id"] == "85005NED"
    assert record["download_performed"] is False
    with pytest.raises(ValueError, match="D-014 PV capacity values are unsigned"):
        packet.require_executable_capacity_approval()


def test_pv_capacity_source_packet_rejects_silent_executable_values() -> None:
    payload = json.loads(Path("data/metadata/weather_pv/d014_pv_capacity_source_value_packet.json").read_text(encoding="utf-8"))
    payload["ii3050_growth_factor_source"]["numeric_growth_factor_approved"] = True

    with pytest.raises(ValueError, match="numeric II3050 growth factor"):
        PVCapacitySourcePacket(
            packet_id=payload["packet_id"],
            data_id=payload["data_id"],
            status=payload["status"],
            download_performed=payload["download_performed"],
            raw_data_committed=payload["raw_data_committed"],
            governing_decisions=payload["governing_decisions"],
            primary_cbs_anchor_source=payload["primary_cbs_anchor_source"],
            ii3050_growth_factor_source=payload["ii3050_growth_factor_source"],
            capacity_value_binding_under_review=payload["capacity_value_binding_under_review"],
            fail_closed_non_claims=payload["fail_closed_non_claims"],
        )