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
from src.pv_model import (
    PVGISReference,
    PVSystemConfig,
    WeatherMember,
    canonical_15min_local_axis_for_year,
    canonical_15min_utc_axis_for_local_year,
    check_profile_against_pvgis_reference,
    generate_pv_profile,
    parse_pvgis_monthly_reference,
    seasonal_energy_kwh,
    summarize_pv_profile,
    validate_canonical_15min_calendar,
)


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
    assert summary["weather_identity_record"]["weather_member_id"] == weather.member_id
    assert summary["weather_identity_record"]["shared_weather_driver_id"] == weather.shared_weather_driver_id
    assert summary["weather_identity_record"]["cadence_seconds"] == 900

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



