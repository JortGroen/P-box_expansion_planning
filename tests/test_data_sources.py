from __future__ import annotations

from datetime import UTC, datetime, timedelta
import io
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from urllib import parse
import zipfile

import numpy as np
import pytest

import data.get_elaad_profiles as elaad
import data.get_hp_scaling as hp_scaling
import data.get_ndw_charging_inventory as ndw
import data.get_pv_capacity as pv_capacity
from data.get_elaad_profiles import (
    ProfileBatch,
    _shape_report,
    build_batch_request,
    build_library_plan,
    build_public_set_b_plan,
    build_probe_request,
    run_set_a_library_batch,
    write_public_set_b_library_manifest,
    write_public_set_b_plan,
    write_set_a_library_manifest,
    write_authorized_set_a_artifacts_from_raw,
    write_library_plan,
)
from data.sources import source_specs, write_metadata


def _case_dir(name: str) -> Path:
    root = Path("tests") / "_artifacts" / "data_sources" / name
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_e2_s1_sources_have_existing_retrieval_scripts() -> None:
    expected_ids = {"D-001", "D-002", "D-003", "D-004", "D-008", "D-012", "D-013", "D-014"}
    specs = source_specs()

    assert {spec.data_id for spec in specs} == expected_ids
    for spec in specs:
        script = Path(spec.retrieval_script)
        assert script.is_file(), spec.retrieval_script
        assert script.as_posix().startswith("data/get_")


def test_metadata_writer_records_no_download_by_default() -> None:
    metadata_dir = _case_dir("metadata")
    path = write_metadata("D-003", metadata_dir, extra={"test": True})

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["data_id"] == "D-003"
    assert payload["download_performed"] is False
    assert payload["status"] == "metadata-only; pending license/API verification and PI sign-off before data use"
    assert payload["extra"] == {"test": True}


def test_data_register_references_e2_s1_retrieval_scripts() -> None:
    register = Path("registers/DATA_REGISTER.md").read_text(encoding="utf-8")

    for spec in source_specs():
        assert spec.data_id in register
        assert f"`{spec.retrieval_script}`" in register


def test_ndw_inventory_counts_ocpi_units_and_power_bins() -> None:
    locations = [
        {
            "id": "alk-1",
            "city": "Alkmaar",
            "coordinates": {"longitude": "4.75", "latitude": "52.63"},
            "evses": [
                {
                    "uid": "evse-1",
                    "connectors": [
                        {
                            "standard": "IEC_62196_T2",
                            "power_type": "AC_3_PHASE",
                            "max_electric_power": 11000,
                        }
                    ],
                },
                {
                    "uid": "evse-2",
                    "connectors": [
                        {
                            "standard": "IEC_62196_T2",
                            "power_type": "AC_3_PHASE",
                            "max_electric_power": 22000,
                        }
                    ],
                },
            ],
        },
        {
            "id": "alk-2",
            "city": "ALKMAAR",
            "coordinates": {"longitude": "4.76", "latitude": "52.64"},
            "evses": [
                {
                    "uid": "evse-3",
                    "connectors": [
                        {
                            "standard": "IEC_62196_T2_COMBO",
                            "power_type": "DC",
                            "max_electric_power": 50000,
                        },
                        {
                            "standard": "CHADEMO",
                            "power_type": "DC",
                            "max_electric_power": None,
                        },
                    ],
                }
            ],
        },
        {
            "id": "outside",
            "city": "Heiloo",
            "coordinates": {"longitude": "4.74", "latitude": "52.61"},
            "evses": [],
        },
    ]

    city = ndw.filter_locations_by_city(locations, "Alkmaar")
    bbox = ndw.filter_locations_by_bbox(locations, ndw.ALKMAAR_BBOX)
    summary = ndw.summarize_ocpi_locations(city, selector="city == Alkmaar")

    assert [location["id"] for location in city] == ["alk-1", "alk-2"]
    assert [location["id"] for location in bbox] == ["alk-1", "alk-2", "outside"]
    assert summary.locations == 2
    assert summary.evses == 3
    assert summary.connectors == 4
    assert summary.connectors_missing_power == 1
    assert summary.power_type_counts == {"AC_3_PHASE": 2, "DC": 2}
    assert summary.bin_around_11kw_10000_12500 == 1
    assert summary.bin_around_22kw_21500_22500 == 1
    assert summary.dc_connectors_ge_30kw == 1


def test_ndw_inventory_rejects_malformed_bbox() -> None:
    with pytest.raises(ValueError, match="bbox must contain"):
        ndw.filter_locations_by_bbox([], (4.7, 52.6))

    with pytest.raises(ValueError, match="bbox min values"):
        ndw.filter_locations_by_bbox([], (4.8, 52.6, 4.7, 52.7))


def test_ndw_metadata_default_is_metadata_only(tmp_path: Path) -> None:
    path = ndw.write_metadata(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["data_id"] == "D-012"
    assert payload["download_performed_by_script"] is False
    assert payload["status"] == "proposed_not_pi_signed"
    assert payload["use_boundary"] == {
        "contextual_only": True,
        "promoted_to_executable_source": False,
        "not_adoption_count_source": True,
        "not_profile_library": True,
        "not_congestion_input": True,
        "promotion_requirement": "A later PI decision must explicitly promote D-012 before executable inventory-to-grid use.",
    }
    assert "summaries" not in payload
    assert payload["selection"]["municipality_boundary_note"].startswith(
        "The NDW OCPI file exposes city strings"
    )



def test_committed_ndw_metadata_remains_contextual_only() -> None:
    payload = json.loads(
        Path("data/metadata/ev_adoption/ndw_alkmaar_public_charging_inventory_metadata.json").read_text(
            encoding="utf-8"
        )
    )

    assert payload["data_id"] == "D-012"
    assert payload["status"] == "proposed_not_pi_signed"
    assert payload["use_boundary"] == {
        "contextual_only": True,
        "promoted_to_executable_source": False,
        "not_adoption_count_source": True,
        "not_profile_library": True,
        "not_congestion_input": True,
        "promotion_requirement": "A later PI decision must explicitly promote D-012 before executable inventory-to-grid use.",
    }
    assert "No integrated net-load" in payload["non_actions"][2]
def test_data_register_has_no_e2_s1_placeholders() -> None:
    register = Path("registers/DATA_REGISTER.md").read_text(encoding="utf-8")

    for placeholder in ("TBD", "to check", "URL to verify", "DOI/URL to verify"):
        assert placeholder not in register


def test_hp_scaling_route_is_public_source_only_and_value_unsigned() -> None:
    plan = hp_scaling.build_hp_scaling_retrieval_plan()

    assert plan["data_id"] == "D-013"
    assert plan["geography"]["municipality_code"] == "GM0361"
    assert plan["public_source_policy"]["public_sources_only"] is True
    assert plan["download_performed"] is False
    assert "thesis" in plan["public_source_policy"]["private_thesis_policy"]
    assert all("thesis" not in source["source"].lower() for source in plan["sources"])
    assert all(source["planned_raw_path"].startswith("data/raw/hp_scaling/") for source in plan["sources"])
    assert "local_heat_demand" in plan["value_route"]
    assert "suitability_pathway" in plan["value_route"]
    assert "unsigned_2035_adoption" in plan["value_route"]
    assert any("No executable annual TWh values" in item for item in plan["blocked_or_out_of_scope"])


def test_hp_scaling_route_keeps_hp001_components_traceable() -> None:
    components = hp_scaling.build_hp_scaling_retrieval_plan()["hp001_component_traceability"]
    by_id = {component["component_id"]: component for component in components}

    assert set(by_id) == {"sfh_space", "mfh_space", "sfh_dhw", "mfh_dhw"}
    assert by_id["sfh_space"]["when2heat_cop_column"] == "NL_COP_ASHP_radiator"
    assert by_id["mfh_space"]["when2heat_cop_column"] == "NL_COP_ASHP_radiator"
    assert by_id["sfh_dhw"]["when2heat_cop_column"] == "NL_COP_ASHP_water"
    assert by_id["mfh_dhw"]["when2heat_cop_column"] == "NL_COP_ASHP_water"
    assert {component["end_use"] for component in components} == {"space", "water"}
    assert {component["building_class"] for component in components} == {"SFH", "MFH"}
    assert all(
        component["annual_twh_source_status"] == "unsigned_local_value_pending"
        for component in components
    )


def test_hp001_scaling_formula_packet_records_remaining_unsigned_decisions(tmp_path: Path) -> None:
    packet = hp_scaling.build_hp001_scaling_formula_config_decision_packet()

    assert packet["decision_packet_id"] == "E2-S3-HP001-SCALING-FORMULA-CONFIG"
    assert packet["already_approved"]["indicator_mapping"]["approval_ids"] == (
        "D013-PBL-MAPPING",
        "A-015",
    )
    assert {item["key"] for item in packet["remaining_decisions"]} == {
        "value_column",
        "denominator",
        "unit_conversion",
        "sfh_mfh_split",
        "adoption_electrification",
    }
    assert packet["fail_closed_config_contract"]["required_approval_keys"] == [
        "value_column",
        "denominator",
        "unit_conversion",
        "sfh_mfh_split",
        "adoption_electrification",
    ]
    assert packet["formula_under_review"]["space_indicator"] == "H23_Vraag_RV_w"
    assert "No annual HP TWh values are executable." in packet["non_claims"]

    path = hp_scaling.write_hp001_scaling_formula_config_decision_packet(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["status"].endswith("annual HP TWh values not executable")


def test_hp001_value_binding_packet_preserves_unsigned_component_values(tmp_path: Path) -> None:
    packet = hp_scaling.build_hp001_value_binding_readiness_packet()

    assert packet["decision_packet_id"] == "E2-S3-HP001-VALUE-BINDING-READINESS"
    assert packet["approval_state"]["executable_binding_allowed"] is False
    assert packet["approval_state"]["missing_approval_keys"] == [
        "value_column",
        "denominator",
        "unit_conversion",
        "sfh_mfh_split",
        "adoption_electrification",
    ]
    assert packet["source_inputs_under_review"]["gj_to_twh_divisor"] == 3_600_000.0
    components = packet["component_value_drafts_unsigned_before_2035_adoption"]
    assert {component["component_id"] for component in components} == {
        "sfh_space",
        "mfh_space",
        "sfh_water",
        "mfh_water",
    }
    assert {component["annual_twh_status"] for component in components} == {
        "unsigned_local_heat_demand_before_2035_adoption"
    }
    assert {component["cop_column"] for component in components if component["end_use"] == "space"} == {
        "NL_COP_ASHP_radiator"
    }
    assert {component["cop_column"] for component in components if component["end_use"] == "water"} == {
        "NL_COP_ASHP_water"
    }
    assert "No annual HP TWh values are executable." in packet["non_claims"]

    path = hp_scaling.write_hp001_value_binding_readiness_packet(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["status"].startswith("proposed value-binding draft")


def test_elaad_source_uses_profile_generator_route() -> None:
    d002 = next(spec for spec in source_specs() if spec.data_id == "D-002")

    assert "Laadprofielengenerator" in d002.source
    assert d002.retrieval_script == "data/get_elaad_profiles.py"
    assert "elaad_profile_generation_spec.md" in d002.doi_url


def test_elaad_one_profile_probe_request_is_narrow() -> None:
    request = build_probe_request()

    assert request["simulated_year"] == 2033
    assert request["n_profiles"] == 1
    assert request["profile_type"] == "ev"
    assert request["location_type"] == "home"
    assert request["vehicle_types"] == "car"
    assert request["step_size_s"] == 900
    assert request["seed"] == 133001


def test_elaad_library_plan_uses_fixed_home_cp_distribution_and_held_out_batches() -> None:
    plan = build_library_plan()
    seeds = [batch.seed for batch in plan]

    assert len(seeds) == len(set(seeds))
    assert len(plan) == 14
    assert sum(batch.partition == "candidate" for batch in plan) == 10
    assert sum(batch.partition == "quarantined_precriterion_diagnostic" for batch in plan) == 2
    assert sum(batch.partition == "held_out" for batch in plan) == 2
    assert all(batch.set_id == "A" for batch in plan)
    assert all(batch.simulated_year == 2030 for batch in plan)
    assert all(batch.location_type == "home" for batch in plan)
    assert all(batch.profile_type == "cp" for batch in plan)
    assert all(batch.vehicle_types == ["van", "car"] for batch in plan)
    assert all(batch.cp_capacity_kw == 11 for batch in plan)
    assert all(batch.n_profiles == 100 for batch in plan)
    assert [batch.seed for batch in plan if batch.partition == "held_out"] == [141201, 141301]
    assert [batch.seed for batch in plan if batch.partition == "quarantined_precriterion_diagnostic"] == [141001, 141101]


def test_elaad_library_plan_metadata_is_non_redistribution_boundary() -> None:
    metadata_dir = _case_dir("library_plan")
    path = write_library_plan(metadata_dir)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["bulk_generation_performed"] is False
    assert payload["policy"]["decision"] == "EV-002"
    assert payload["policy"]["scientific_decisions"] == ["EV-004", "EV-005"]
    assert payload["policy"]["commit_generated_profiles"] is False
    assert payload["policy"]["redistribute_generated_profiles"] is False
    pairing = payload["seed_semantics"]["smart_counterfactual_pairing"]
    assert pairing["decision"] == "EV-006"
    assert pairing["reuse_uncontrolled_batch_seed_and_member_index"] is True
    assert pairing["may_be_aggregated_as_independent_members"] is False
    assert pairing["smart_control_role_and_parameters_approved"] is False
    assert sum(batch["partition"] == "candidate" for batch in payload["batches"]) == 10
    assert sum(batch["partition"] == "quarantined_precriterion_diagnostic" for batch in payload["batches"]) == 2
    assert sum(batch["partition"] == "held_out" for batch in payload["batches"]) == 2
    assert all(batch["processed_path"].endswith(".npz") for batch in payload["batches"])
    assert all(
        batch["raw_response_path"].startswith("data/raw/elaad_profiles/")
        for batch in payload["batches"]
    )


def test_public_set_b_plan_matches_ev008a_equal_mix_decision() -> None:
    plan = build_public_set_b_plan()
    seeds = [batch.seed for batch in plan]

    assert len(plan) == 16
    assert len(seeds) == len(set(seeds))
    assert all(batch.set_id == "B" for batch in plan)
    assert all(batch.profile_type == "cp" for batch in plan)
    assert all(batch.location_type == "public" for batch in plan)
    assert all(batch.vehicle_types == ["van", "car"] for batch in plan)
    assert all(batch.simulated_year == 2030 for batch in plan)
    assert all(batch.n_profiles == 100 for batch in plan)
    assert [batch.seed for batch in plan if batch.partition == "candidate"] == [
        152001,
        152101,
        152201,
        152301,
        152401,
        152501,
        152601,
        152701,
        152801,
        152901,
        153001,
        153101,
    ]
    assert [batch.seed for batch in plan if batch.partition == "held_out"] == [
        153201,
        153301,
        153401,
        153501,
    ]
    per_capacity = {
        capacity: sum(
            batch.n_profiles
            for batch in plan
            if batch.partition == "candidate" and batch.cp_capacity_kw == capacity
        )
        for capacity in {11, 13, 15, 22}
    }
    assert per_capacity == {11: 300, 13: 300, 15: 300, 22: 300}


def test_public_set_b_plan_metadata_records_non_actions(tmp_path: Path) -> None:
    path = write_public_set_b_plan(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["status"] == "ev008a-approved-request-metadata-only"
    assert payload["bulk_generation_performed"] is False
    assert payload["policy"]["decision"] == "EV-008A"
    assert payload["policy"]["candidate_M"] == 1200
    assert payload["policy"]["held_out_H"] == 400
    assert payload["policy"]["public_smart_charging"] is False
    assert payload["policy"]["dc_or_fast_charging"] is False
    assert payload["policy"]["m_sufficiency_claimed"] is False
    assert {batch["capacity_class"] for batch in payload["batches"]} == {
        "public_11kw",
        "public_13kw",
        "public_15kw",
        "public_22kw",
    }
    assert all(batch["request_sha256"] for batch in payload["batches"])


def test_elaad_shape_report_records_runtime_sizes_and_adequacy_boundary() -> None:
    metadata = {
        "api_runtime_s": 12.3456,
        "api_runtime_note": "Measured around the HTTPS POST only.",
        "observed_failed_command_wall_time_s": None,
        "request_json": {
            "simulated_year": 2030,
            "seed": 140001,
            "n_profiles": 100,
        },
        "response_shape_summary": {
            "n_timesteps": 35040,
            "n_profiles": 100,
            "distinct_member_count": 100,
            "first_timestamp_utc": "2024-12-31T23:00:00+00:00",
            "first_timestamp_local": "2025-01-01T00:00:00+01:00",
            "last_timestamp_local": "2025-12-31T23:45:00+01:00",
            "missing_or_nonfinite_values": 0,
            "negative_values": 0,
            "annual_energy_kwh": {
                "min": 1.0,
                "median": 2.0,
                "mean": 3.0,
                "p95": 4.0,
                "max": 5.0,
            },
            "peak_kw": {
                "min": 1.0,
                "median": 2.0,
                "mean": 3.0,
                "p95": 4.0,
                "max": 5.0,
            },
        },
        "seed_semantics_observed": {
            "returned_indices_available_for_planned_pairing": True,
            "smart_pair_order_verified": False,
        },
        "source_level_probe_verdict": {
            "supports_remaining_candidate_and_held_out_generation": True,
        },
        "raw_response": {
            "sha256_gzip_file": "raw-sha",
            "size_bytes": 123,
        },
        "processed_profiles": {
            "sha256_file": "npz-sha",
            "size_bytes": 456,
        },
    }

    report = _shape_report(metadata, Path("data/metadata/elaad_profiles/example_manifest.json"))

    assert "API runtime seconds: 12.346" in report
    assert "API runtime note: Measured around the HTTPS POST only." in report
    assert "Observed failed command wall time seconds: not recorded" in report
    assert "Supports proceeding to remaining candidate and held-out generation: True" in report
    assert "Library adequacy proven: False" in report
    assert "123 bytes gzip" in report
    assert "456 bytes npz" in report
    assert "no smart-control API call was made" in report
    assert "Smart pair order verified: False" in report


def test_elaad_raw_recovery_writes_manifest_without_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_urlopen(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("raw recovery must not make a network request")

    monkeypatch.setattr(elaad.request, "urlopen", fail_urlopen)
    monkeypatch.setattr(
        elaad,
        "build_library_plan",
        lambda: (
            ProfileBatch(
                set_id="A",
                purpose="test_home_van_car_cp_library",
                partition="candidate",
                simulated_year=2030,
                profile_type="cp",
                n_profiles=2,
                vehicle_types=["van", "car"],
                location_type="home",
                cp_capacity_kw=11,
                seed=140001,
                storage_stem="A_home_vancar_cp_y2030_batchseed140001_n2",
            ),
        ),
    )

    start = datetime(2024, 12, 31, 23, 0, tzinfo=UTC)
    datetimes = [
        (start + timedelta(minutes=15 * index)).isoformat()
        for index in range(35_040)
    ]
    demands = [
        [float(1 + (index % 4)), float(2 + (index % 5))]
        for index in range(35_040)
    ]
    payload = {
        "config": {
            **build_batch_request(elaad.build_library_plan()[0]),
            "step_size_s": "PT15M",
            "cp_capacity_kw": 11.0,
            "n_profiles": 2,
        },
        "statistics": None,
        "profile": {
            "cp_ids": ["cp_0", "cp_1"],
            "datetimes": datetimes,
            "demands_kw": demands,
        },
    }
    raw_json = json.dumps(payload).encode("utf-8")
    raw_path = tmp_path / "raw" / "A_home_vancar_cp_y2030_batchseed140001_n2.json.gz"
    raw_path.parent.mkdir(parents=True)
    with gzip.open(raw_path, "wb") as handle:
        handle.write(raw_json)
    raw_gzip_before = raw_path.read_bytes()
    raw_mtime_ns_before = raw_path.stat().st_mtime_ns

    metadata_dir = tmp_path / "metadata"
    processed_dir = tmp_path / "processed"
    reports_dir = tmp_path / "reports"
    manifest_path = write_authorized_set_a_artifacts_from_raw(
        raw_path=raw_path,
        metadata_dir=metadata_dir,
        processed_dir=processed_dir,
        reports_dir=reports_dir,
        command_wall_time_s=1.25,
    )

    assert raw_path.read_bytes() == raw_gzip_before
    assert raw_path.stat().st_mtime_ns == raw_mtime_ns_before

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    processed_path = processed_dir / "A_home_vancar_cp_y2030_batchseed140001_n2.npz"
    report_path = reports_dir / "elaad_e2_s2_ev004_home_cp_batchseed140001_shape_report.md"

    assert manifest_path == metadata_dir / "A_home_vancar_cp_y2030_batchseed140001_n2_manifest.json"
    assert processed_path.is_file()
    assert report_path.is_file()
    assert manifest["reconstructed_from_saved_raw_response"] is True
    assert manifest["response_status_code"] == 200
    assert "Inferred from successful urlopen" in manifest["response_status_code_source"]
    assert manifest["api_runtime_s"] is None
    assert manifest["observed_failed_command_wall_time_s"] == 1.25
    assert manifest["seed_semantics_observed"]["distinct_returned_members"] == 2
    assert manifest["seed_semantics_observed"]["returned_indices_available_for_planned_pairing"] is True
    assert manifest["seed_semantics_observed"]["smart_pair_order_verified"] is False
    assert manifest["source_level_probe_verdict"]["library_adequacy_proven"] is False
    assert manifest["raw_response"]["sha256_uncompressed_json"] == hashlib.sha256(raw_json).hexdigest()
    assert manifest["raw_response"]["sha256_gzip_file"] == hashlib.sha256(raw_path.read_bytes()).hexdigest()
    assert manifest["processed_profiles"]["sha256_file"] == hashlib.sha256(processed_path.read_bytes()).hexdigest()

    with np.load(processed_path, allow_pickle=False) as processed:
        assert processed["demands_kw"].shape == (35_040, 2)
        assert processed["member_ids"].tolist() == ["profile_140001_000", "profile_140001_001"]

    report = report_path.read_text(encoding="utf-8")
    assert "Smart pair order verified: False" in report
    assert "no smart-control API call was made" in report


def test_elaad_batch_checkpoint_skip_requires_matching_request_and_checksums(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    batch = ProfileBatch(
        set_id="A",
        purpose="test_home_van_car_cp_library",
        partition="candidate",
        simulated_year=2030,
        profile_type="cp",
        n_profiles=2,
        vehicle_types=["van", "car"],
        location_type="home",
        cp_capacity_kw=11,
        seed=140101,
        storage_stem="A_home_vancar_cp_y2030_batchseed140101_n2",
    )
    monkeypatch.setattr(elaad, "build_library_plan", lambda: (batch,))
    start = datetime(2024, 12, 31, 23, 0, tzinfo=UTC)
    payload = {
        "config": {
            **build_batch_request(batch),
            "step_size_s": "PT15M",
            "cp_capacity_kw": 11.0,
        },
        "statistics": None,
        "profile": {
            "cp_ids": ["cp_0", "cp_1"],
            "datetimes": [
                (start + timedelta(minutes=15 * index)).isoformat()
                for index in range(35_040)
            ],
            "demands_kw": [[float(1 + index % 3), float(2 + index % 4)] for index in range(35_040)],
        },
    }
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    raw_path = raw_dir / f"{batch.storage_stem}.json.gz"
    with gzip.open(raw_path, "wb") as handle:
        handle.write(json.dumps(payload).encode("utf-8"))
    metadata_dir = tmp_path / "metadata"
    processed_dir = tmp_path / "processed"
    reports_dir = tmp_path / "reports"
    first_manifest = write_authorized_set_a_artifacts_from_raw(
        batch=batch,
        raw_path=raw_path,
        metadata_dir=metadata_dir,
        processed_dir=processed_dir,
        reports_dir=reports_dir,
    )

    def fail_urlopen(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("verified checkpoints must not make a network request")

    monkeypatch.setattr(elaad.request, "urlopen", fail_urlopen)
    second_manifest = run_set_a_library_batch(
        batch,
        metadata_dir=metadata_dir,
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        reports_dir=reports_dir,
        timeout_s=1,
    )

    assert second_manifest == first_manifest
    manifest = json.loads(second_manifest.read_text(encoding="utf-8"))
    assert manifest["request_json"]["seed"] == 140101
    assert manifest["raw_response"]["sha256_gzip_file"] == hashlib.sha256(raw_path.read_bytes()).hexdigest()

    manifest["request_json"]["seed"] = 999999
    second_manifest.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="Checkpoint request mismatch"):
        run_set_a_library_batch(
            batch,
            metadata_dir=metadata_dir,
            raw_dir=raw_dir,
            processed_dir=processed_dir,
            reports_dir=reports_dir,
            timeout_s=1,
        )


def test_elaad_raw_recovery_rejects_wrong_response_config(tmp_path: Path) -> None:
    batch = ProfileBatch(
        set_id="A",
        purpose="test_home_van_car_cp_library",
        partition="candidate",
        simulated_year=2030,
        profile_type="cp",
        n_profiles=2,
        vehicle_types=["van", "car"],
        location_type="home",
        cp_capacity_kw=11,
        seed=140101,
        storage_stem="A_home_vancar_cp_y2030_batchseed140101_n2",
    )
    start = datetime(2024, 12, 31, 23, 0, tzinfo=UTC)
    payload = {
        "config": {
            **build_batch_request(batch),
            "step_size_s": "PT15M",
            "cp_capacity_kw": 11.0,
            "seed": 999999,
        },
        "statistics": None,
        "profile": {
            "cp_ids": ["cp_0", "cp_1"],
            "datetimes": [
                (start + timedelta(minutes=15 * index)).isoformat()
                for index in range(35_040)
            ],
            "demands_kw": [[1.0, 2.0] for _ in range(35_040)],
        },
    }
    raw_path = tmp_path / "raw.json.gz"
    with gzip.open(raw_path, "wb") as handle:
        handle.write(json.dumps(payload).encode("utf-8"))

    with pytest.raises(ValueError, match="response config mismatch for seed"):
        write_authorized_set_a_artifacts_from_raw(
            batch=batch,
            raw_path=raw_path,
            metadata_dir=tmp_path / "metadata",
            processed_dir=tmp_path / "processed",
            reports_dir=tmp_path / "reports",
        )


def test_elaad_library_manifest_records_held_out_isolation(tmp_path: Path) -> None:
    def manifest(seed: int, partition: str) -> Path:
        path = tmp_path / "metadata" / f"batch{seed}_manifest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "library_partition": partition,
            "request_json": {"seed": seed},
            "raw_response": {
                "path": f"data/raw/elaad_profiles/batch{seed}.json.gz",
                "sha256_gzip_file": f"raw-{seed}",
                "sha256_uncompressed_json": f"json-{seed}",
            },
            "processed_profiles": {
                "path": f"data/processed/elaad_profiles/batch{seed}.npz",
                "sha256_file": f"processed-{seed}",
            },
            "response_shape_summary": {
                "n_timesteps": 35040,
                "n_profiles": 100,
                "distinct_member_count": 100,
            },
            "seed_semantics_observed": {"smart_pair_order_verified": False},
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    library_manifest = write_set_a_library_manifest(
        metadata_dir=tmp_path / "metadata",
        reports_dir=tmp_path / "reports",
        command_wall_time_s=2.0,
        batch_manifest_paths=[
            manifest(140001, "candidate"),
            manifest(141001, "quarantined_precriterion_diagnostic"),
            manifest(141201, "held_out"),
        ],
    )

    payload = json.loads(library_manifest.read_text(encoding="utf-8"))
    assert payload["candidate_member_count"] == 100
    assert payload["quarantined_diagnostic_member_count"] == 100
    assert payload["held_out_member_count"] == 100
    assert payload["held_out_unopened_for_adequacy"] is True
    assert payload["library_adequacy_proven"] is False
    assert payload["policy"]["public_profiles_generated"] is False
    assert payload["policy"]["smart_profiles_generated"] is False
    report = (tmp_path / "reports" / "elaad_e2_s2_home_cp_library_report.md").read_text(encoding="utf-8")
    assert "quarantined precriterion diagnostics" in report
    assert "They were not opened for adequacy analysis" in report


def test_public_set_b_library_manifest_records_equal_mix_and_blocks_adequacy(
    tmp_path: Path,
) -> None:
    def manifest(batch: ProfileBatch) -> Path:
        path = tmp_path / "metadata" / f"{batch.storage_stem}_manifest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "set_id": "B",
            "purpose": batch.purpose,
            "library_partition": batch.partition,
            "capacity_class": batch.purpose.split("_equal_mix")[0],
            "request_json": build_batch_request(batch),
            "request_sha256": "a" * 64,
            "raw_response": {
                "path": f"data/raw/elaad_profiles/{batch.storage_stem}.json.gz",
                "sha256_gzip_file": f"raw-{batch.seed}",
                "sha256_uncompressed_json": f"json-{batch.seed}",
            },
            "processed_profiles": {
                "path": f"data/processed/elaad_profiles/{batch.storage_stem}.npz",
                "sha256_file": f"processed-{batch.seed}",
            },
            "response_shape_summary": {
                "n_timesteps": 35040,
                "n_profiles": 100,
                "distinct_member_count": 100,
                "missing_or_nonfinite_values": 0,
                "negative_values": 0,
            },
            "seed_semantics_observed": {"smart_pair_order_verified": False},
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    paths = [manifest(batch) for batch in build_public_set_b_plan()]

    library_manifest = write_public_set_b_library_manifest(
        metadata_dir=tmp_path / "metadata",
        reports_dir=tmp_path / "reports",
        command_wall_time_s=3.5,
        batch_manifest_paths=paths,
    )

    payload = json.loads(library_manifest.read_text(encoding="utf-8"))
    assert payload["candidate_member_count"] == 1200
    assert payload["held_out_member_count"] == 400
    assert payload["candidate_members_per_class"] == {
        "public_11kw": 300,
        "public_13kw": 300,
        "public_15kw": 300,
        "public_22kw": 300,
    }
    assert payload["held_out_members_per_class"] == {
        "public_11kw": 100,
        "public_13kw": 100,
        "public_15kw": 100,
        "public_22kw": 100,
    }
    assert payload["policy"]["public_profiles_generated"] is True
    assert payload["policy"]["public_smart_profiles_generated"] is False
    assert payload["policy"]["dc_or_fast_profiles_generated"] is False
    assert payload["policy"]["integrated_analysis_performed"] is False
    assert payload["policy"]["m_sufficiency_claimed"] is False
    assert payload["held_out_unopened_for_adequacy"] is True
    report = (tmp_path / "reports" / "elaad_e2_s2_public_set_b_library_report.md").read_text(
        encoding="utf-8"
    )
    assert "EV-008A source generation only" in report
    assert "does not inspect held-out adequacy" in report
    assert "M sufficiency claimed: False" in report


def test_data_entrypoints_run_directly() -> None:
    scripts = {spec.retrieval_script for spec in source_specs()}
    scripts.add("data/get_elaadnl.py")

    for script in sorted(scripts):
        metadata_dir = _case_dir("entrypoints") / Path(script).stem
        result = subprocess.run(
            [sys.executable, script, "--metadata-dir", str(metadata_dir)],
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr
        assert Path(result.stdout.strip()).is_file()

def _fake_hp_scaling_zip_bytes() -> bytes:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("Alkmaar/test.csv", "bu_code;heat_demand;pathway\nBU0001;1,2;S1\n")
    return payload.getvalue()


def _fake_hp_scaling_cbs_json(url: str, *, timeout_s: float) -> dict[str, object]:
    del timeout_s
    if "/TableInfos" in url:
        identifier = "85035NED" if "85035NED" in url else "85523NED"
        return {"value": [{"Identifier": identifier, "Title": f"title {identifier}", "Modified": "2026-01-01T00:00:00"}]}
    if "/DataProperties" in url:
        return {"value": []}
    if "/RegioS" in url:
        return {"value": [{"Key": "GM0361", "Title": "Alkmaar"}]}
    if "/Woningtype" in url:
        return {"value": [{"Key": "ZW10290", "Title": "Eengezinswoningen totaal"}, {"Key": "ZW10340", "Title": "Meergezinswoningen totaal"}]}
    if "/Woningkenmerk" in url:
        return {"value": [{"Key": "T001727", "Title": "Totaal woningen"}]}
    if "/Warmtepompen" in url:
        return {"value": [{"Key": "T001364 ", "Title": "Totaal warmtepompen"}]}
    if "/Sector" in url:
        return {"value": [{"Key": "E007041 ", "Title": "Woningen"}]}
    if "/Perioden" in url:
        return {"value": [{"Key": "2026JJ00", "Title": "2026"}]}
    if "/TypedDataSet" in url and "85035NED" in url:
        return {"value": [{"ID": 1, "RegioS": "GM0361", "Woningtype": "ZW10290", "Woningkenmerk": "T001727", "Perioden": "2026JJ00", "BeginstandWoningvoorraad_1": 10}]}
    if "/TypedDataSet" in url and "85523NED" in url:
        return {"value": [{"ID": 1, "Warmtepompen": "T001364 ", "Sector": "E007041 ", "Perioden": "2025JJ00", "OpgesteldeWarmtepompenEindeVanJaar_3": 10}]}
    raise AssertionError(url)


def test_hp_scaling_download_writes_manifest_and_keeps_values_unsigned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hp_scaling, "_read_json_url", _fake_hp_scaling_cbs_json)
    monkeypatch.setattr(hp_scaling, "_read_url_bytes", lambda url, *, timeout_s: _fake_hp_scaling_zip_bytes())

    manifest_path = hp_scaling.retrieve_hp_scaling_sources(
        raw_dir=tmp_path / "raw",
        metadata_dir=tmp_path / "metadata",
        resume=False,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["data_id"] == "D-013"
    assert manifest["download_performed"] is True
    assert manifest["raw_files_ignored"] is True
    assert len(manifest["sources"]) == 3
    assert all(source["sha256_file"] for source in manifest["sources"])
    assert "No annual HP TWh values" in " ".join(manifest["non_claims"])
    assert {component["end_use"] for component in manifest["hp001_component_traceability"]} == {"space", "water"}

    metadata_payloads = [json.loads(Path(path).read_text(encoding="utf-8")) for path in manifest["metadata_paths"]]
    assert all(payload["status"].endswith("HP scaling values remain unsigned") for payload in metadata_payloads)
    pbl_metadata = next(payload for payload in metadata_payloads if payload["source_key"] == "pbl_startanalyse_2025_alkmaar")
    csv_summary = pbl_metadata["schema_summary"]["csv_summaries"][0]
    assert csv_summary["columns"] == ["bu_code", "heat_demand", "pathway"]
    assert csv_summary["full_file_rows_inspected"] == 1
    assert csv_summary["column_classification"]["heat_or_energy_candidate_columns"] == ["heat_demand"]


def test_hp_scaling_inspect_existing_refreshes_pbl_indicator_units(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hp_scaling, "_read_json_url", _fake_hp_scaling_cbs_json)
    raw_dir = tmp_path / "raw"
    metadata_dir = tmp_path / "metadata"
    raw_dir.mkdir()
    for spec in hp_scaling.HP_SCALING_SOURCES:
        raw_path = raw_dir / Path(spec.planned_raw_path).name
        if spec.key == "pbl_startanalyse_2025_alkmaar":
            payload = io.BytesIO()
            with zipfile.ZipFile(payload, "w") as archive:
                archive.writestr(
                    "Alkmaar_strategie.csv",
                    "I01_buurtcode;Code_Indicator;Eenheid;Referentie_2030;Strategie_1;Variant_s1a_B_LuchtWP\n"
                    "BU0001;Warmtevraag woningen;GJ per yr;1,0;2,0;3,0\n"
                    "BU0002;Aantal woningen;Aansluiting;4;5;6\n",
                )
                archive.writestr(
                    "Alkmaar_totaalbebouwing.csv",
                    "I01_buurtcode;I09_aantal_woningen;Vrijstaande_woning;Rijwoning_tussen;Meersgezinswoning_hoog\n"
                    "BU0001;10;1;7;2\n",
                )
            raw_path.write_bytes(payload.getvalue())
        else:
            spec_payload = hp_scaling._cbs_table_payload(spec)
            raw_path.write_text(json.dumps(spec_payload), encoding="utf-8")

    packet_path = hp_scaling.inspect_existing_hp_scaling_sources(raw_dir=raw_dir, metadata_dir=metadata_dir)

    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    assert packet["network_performed"] is False
    assert packet["status"].endswith("values unsigned")
    pbl_metadata_path = next(path for path in packet["metadata_paths"] if "pbl_startanalyse" in path)
    pbl_metadata = json.loads(Path(pbl_metadata_path).read_text(encoding="utf-8"))
    summaries = {item["filename"]: item for item in pbl_metadata["schema_summary"]["csv_summaries"]}
    strategie = summaries["Alkmaar_strategie.csv"]
    assert strategie["indicator_unit_summary"]["available"] is True
    assert strategie["indicator_unit_summary"]["heat_or_energy_pairs"] == [
        {"code_indicator": "Warmtevraag woningen", "unit": "GJ per yr"}
    ]
    assert strategie["column_classification"]["strategy_or_pathway_columns"] == [
        "Referentie_2030",
        "Strategie_1",
        "Variant_s1a_B_LuchtWP",
    ]
    bebouwing = summaries["Alkmaar_totaalbebouwing.csv"]
    assert bebouwing["column_classification"]["sfh_candidate_columns"] == [
        "Vrijstaande_woning",
        "Rijwoning_tussen",
    ]
    assert bebouwing["column_classification"]["mfh_candidate_columns"] == ["Meersgezinswoning_hoog"]


def test_hp_scaling_resume_skips_verified_sources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hp_scaling, "_read_json_url", _fake_hp_scaling_cbs_json)
    monkeypatch.setattr(hp_scaling, "_read_url_bytes", lambda url, *, timeout_s: _fake_hp_scaling_zip_bytes())
    first = hp_scaling.retrieve_hp_scaling_sources(
        raw_dir=tmp_path / "raw",
        metadata_dir=tmp_path / "metadata",
        resume=False,
    )

    def fail_fetch(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("resume should skip verified sources")

    monkeypatch.setattr(hp_scaling, "_read_json_url", fail_fetch)
    monkeypatch.setattr(hp_scaling, "_read_url_bytes", fail_fetch)
    second = hp_scaling.retrieve_hp_scaling_sources(
        raw_dir=tmp_path / "raw",
        metadata_dir=tmp_path / "metadata",
        resume=True,
    )

    assert second == first


def test_hp001_readiness_approval_checklist_records_remaining_blockers(tmp_path: Path) -> None:
    packet = hp_scaling.build_hp001_readiness_approval_checklist_packet()

    assert packet["decision_packet_id"] == "E2-S3-HP001-READINESS-APPROVAL-CHECKLIST"
    assert packet["data_ids"] == ["D-003", "D-004", "D-013"]
    assert packet["approval_groups"]["annual_value_binding"] == [
        "value_column",
        "denominator",
        "unit_conversion",
        "sfh_mfh_split",
        "adoption_electrification",
    ]
    assert packet["approval_groups"]["scenario_consistency"] == [
        "scenario_source_consistency",
    ]
    assert packet["approval_groups"]["weather_acceptance"] == [
        "d004_paired_weather_acceptance",
        "cold_spell_tolerances",
    ]
    assert {item["key"] for item in packet["required_approvals"]} == set(
        packet["fail_closed_handoff"]["required_final_approval_keys"]
    )
    assert packet["approved_foundation"]["d004_source_member_use"].endswith(
        "internal first-screen work only."
    )
    assert "No annual HP TWh values are executable." in packet["non_claims"]
    assert "No D-004 paired-weather or cold-spell acceptance is signed." in packet["non_claims"]

    path = hp_scaling.write_hp001_readiness_approval_checklist_packet(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == "hp001_alkmaar_gm0361_readiness_approval_checklist.json"
    assert payload["status"].startswith("proposed approval checklist only")


def test_hp001_executable_value_binding_packet_is_approval_template_only(tmp_path: Path) -> None:
    packet = hp_scaling.build_hp001_executable_value_binding_decision_packet()

    assert packet["decision_packet_id"] == "E2-S3-HP001-EXECUTABLE-VALUE-BINDING-PACKET"
    assert packet["data_ids"] == ["D-003", "D-004", "D-013"]
    assert {item["key"] for item in packet["pi_approval_request"]} == {
        "value_column",
        "denominator",
        "unit_conversion",
        "sfh_mfh_split",
        "adoption_electrification",
        "scenario_source_consistency",
        "d004_paired_weather_acceptance",
        "cold_spell_tolerances",
    }
    candidate = packet["unsigned_candidate_binding_record"]
    assert candidate["status"] == "proposed_template_not_approved_for_executable_use"
    assert candidate["approval_state"]["approval_ids"] == {}
    assert candidate["approval_state"]["executable_binding_allowed"] is False
    assert packet["final_readiness_dependency"]["all_required_before_integrated_hp_use"] == [
        "value_column",
        "denominator",
        "unit_conversion",
        "sfh_mfh_split",
        "adoption_electrification",
        "scenario_source_consistency",
        "d004_paired_weather_acceptance",
        "cold_spell_tolerances",
    ]
    handoff = packet["future_executable_handoff_if_pi_signs"]
    assert handoff["required_approval_state"] == {
        "executable_binding_allowed": True,
        "missing_approval_keys": [],
        "required_before_executable_binding": [
            "value_column",
            "denominator",
            "unit_conversion",
            "sfh_mfh_split",
            "adoption_electrification",
        ],
        "approved_indicator_mapping_ids_must_include": ["D013-PBL-MAPPING", "A-015"],
        "component_annual_twh_status": "approved_for_executable_value_binding",
    }
    assert "No annual HP TWh values are executable." in packet["non_claims"]

    path = hp_scaling.write_hp001_executable_value_binding_decision_packet(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == "hp001_alkmaar_gm0361_executable_value_binding_decision_packet.json"
    assert payload["status"].endswith("approval template only")



def test_d014_pv_capacity_source_packet_is_metadata_only(tmp_path: Path) -> None:
    packet = pv_capacity.build_d014_pv_capacity_source_value_packet()

    assert packet["packet_id"] == "D014-PV-CAPACITY-SOURCE-VALUE-PACKET"
    assert packet["data_id"] == "D-014"
    assert packet["download_performed"] is False
    assert packet["raw_data_committed"] is False
    assert packet["governing_decisions"]["approved_route"] == "PV-CAP-001"
    assert "PV-PARAM-001 remains proposed" in packet["governing_decisions"]["conversion_parameters"]
    cbs = packet["primary_cbs_anchor_source"]
    assert cbs["table_id"] == "85005NED"
    assert cbs["planned_raw_path"].startswith("data/raw/pv_capacity/")
    assert cbs["schema_probe_urls"]["data_properties"].endswith("/DataProperties")
    assert "GM0361" in cbs["alkmaar_row_filter_template"]
    assert "TypedDataSet" in cbs["alkmaar_row_query_template"]
    assert packet["ii3050_growth_factor_source"]["numeric_growth_factor_approved"] is False
    assert packet["optional_geometry_allocation_workflow"]["primary_status"] == "deferred_until_after_first_real_experiment"
    assert "statistical orientation/tilt distribution packet" in packet["optional_geometry_allocation_workflow"]["recommended_next_packet"]
    assert "statistical_orientation_tilt_distribution_source" in packet["capacity_value_binding_under_review"]["approval_keys_required_before_executable_use"]
    assert "No numeric PV installed capacity is approved." in packet["fail_closed_non_claims"]

    path = pv_capacity.write_d014_pv_capacity_source_value_packet(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == "d014_pv_capacity_source_value_packet.json"
    assert payload["status"].startswith("proposed_source_value_packet")


def test_d014_cbs_odata_url_builder_is_official_and_encoded() -> None:
    url = pv_capacity.build_cbs_odata_url(
        "TypedDataSet",
        {"$filter": "RegioS eq 'GM0361' and Perioden eq '<PERIOD_KEY>'"},
    )
    parsed = parse.urlparse(url)
    query = parse.parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "opendata.cbs.nl"
    assert parsed.path == "/ODataApi/OData/85005NED/TypedDataSet"
    assert query["$filter"] == ["RegioS eq 'GM0361' and Perioden eq '<PERIOD_KEY>'"]

    with pytest.raises(ValueError, match="entity"):
        pv_capacity.build_cbs_odata_url("TypedDataSet?$filter=bad")

def test_hp001_cold_spell_acceptance_decision_packet_is_proposal_only(tmp_path: Path) -> None:
    packet = hp_scaling.build_hp001_cold_spell_acceptance_decision_packet()

    assert packet["decision_packet_id"] == "E2-S3-HP001-COLD-SPELL-ACCEPTANCE-READINESS"
    assert packet["design_id"] == "E2-S3-COLD-SPELL-ACCEPTANCE-DESIGN"
    assert packet["status"].endswith("no real paired acceptance run")
    assert [item["gate"] for item in packet["gate_separation"]] == [
        "source/member identity",
        "paired HP/PV weather equality",
        "cold-spell numerical tolerances",
    ]
    assert packet["fail_closed_runner"]["runner"] == "src.hp_model.evaluate_hp001_cold_spell_acceptance"
    assert packet["fail_closed_runner"]["identity_check"] == "src.weather_model.assert_same_weather_realization"
    assert any("near-freezing" in item for item in packet["diagnostics_to_report_before_final_acceptance"]["near_freezing_defrost_risk"])
    assert any(item["option"] == "B" for item in packet["pi_approval_options"])
    assert "No D-004 paired-weather or cold-spell acceptance is signed or run." in packet["non_claims"]

    path = hp_scaling.write_hp001_cold_spell_acceptance_decision_packet(tmp_path)
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["decision_packet_id"] == packet["decision_packet_id"]

def test_d014_cbs_anchor_query_urls_are_narrow_and_official() -> None:
    urls = pv_capacity.build_d014_cbs_anchor_query_urls()

    assert set(urls) == {
        "table_infos",
        "data_properties",
        "periods",
        "sector_and_capacity_class_codes",
        "alkmaar_region",
        "alkmaar_rows",
    }
    assert all(parse.urlparse(url).netloc == "opendata.cbs.nl" for url in urls.values())
    assert "85005NED" in urls["alkmaar_rows"]
    assert "%24filter=RegioS+eq+%27GM0361%27" in urls["alkmaar_rows"]
    assert "%24filter=Key+eq+%27GM0361%27" in urls["alkmaar_region"]


def test_committed_d014_cbs_anchor_evidence_metadata_records_unsigned_rows() -> None:
    payload = json.loads(
        Path("data/metadata/weather_pv/d014_cbs_85005ned_alkmaar_gm0361_anchor_evidence.json").read_text(
            encoding="utf-8"
        )
    )
    choices = payload["candidate_value_choices_for_pi_review"]
    fields = {item["key"]: item for item in payload["schema"]["topic_fields"]}

    assert payload["packet_id"] == "D014-CBS-PV-CAPACITY-ANCHOR-EVIDENCE"
    assert payload["download_performed"] is True
    assert payload["raw_data_committed"] is False
    assert payload["source"]["table_id"] == "85005NED"
    assert payload["source"]["modified"] == "2026-06-12T02:00:00"
    assert payload["raw_bundle"]["path"].startswith("data/raw/pv_capacity/")
    assert len(payload["raw_bundle"]["sha256"]) == 64
    assert payload["raw_bundle"]["size_bytes"] > 0
    assert payload["schema"]["alkmaar_row_count"] == 63
    assert fields["OpgesteldVermogenVanZonnepanelen_2"]["unit"] == "kWp"
    assert fields["OpgesteldVermogenOmvormers_3"]["unit"] == "kW"
    latest = next(
        item
        for item in choices["exact_row_candidates"]
        if item["choice_role"] == "latest_definitive_all_activity_and_homes_candidate"
    )
    assert latest["period_key"] == "2023JJ00"
    assert latest["period_status"] == "Definitief"
    assert latest["sector_key"] == "E007161"
    assert latest["panel_capacity_kwp"] > 0
    assert latest["inverter_capacity_kw"] > 0
    assert latest["executable_status"] == "candidate_only_unsigned"
    assert "ii3050_growth_factor_value" in payload["pi_approval_keys_before_executable_use"]
    assert any("No executable PV installed-capacity value" in item for item in payload["non_claims"])


def test_d014_ii3050_query_urls_are_public_and_pdf_pinned() -> None:
    urls = pv_capacity.build_d014_ii3050_query_urls()

    assert set(urls) == {
        "appendices_publication_page",
        "appendices_pdf",
        "main_report_publication_page",
    }
    assert parse.urlparse(urls["appendices_publication_page"]).netloc == "www.netbeheernederland.nl"
    parsed_pdf = parse.urlparse(urls["appendices_pdf"])
    assert parsed_pdf.netloc == "www.netbeheernederland.nl"
    assert parsed_pdf.path.endswith("/Bijlagen_II3050_eindrapport__285.pdf")


def test_committed_d014_ii3050_growth_evidence_metadata_records_unsigned_candidates() -> None:
    payload = json.loads(
        Path("data/metadata/weather_pv/d014_ii3050_pv_growth_evidence.json").read_text(
            encoding="utf-8"
        )
    )
    candidates = payload["table_evidence"]["planning_year_2035_candidates"]

    assert payload["packet_id"] == "D014-II3050-PV-GROWTH-EVIDENCE"
    assert payload["download_performed"] is True
    assert payload["raw_data_committed"] is False
    assert payload["approved_route_decision"] == "PV-CAP-001"
    assert payload["cbs_anchor_evidence_id"] == "D014-CBS-PV-CAPACITY-ANCHOR-EVIDENCE"
    assert payload["source"]["owner"] == "Netbeheer Nederland"
    assert payload["raw_bundle"]["path"].startswith("data/raw/pv_capacity/")
    assert len(payload["raw_bundle"]["sha256"]) == 64
    assert payload["raw_bundle"]["size_bytes"] > 1_000_000
    assert payload["table_evidence"]["table_label"] == "Tabel A.1"
    assert payload["table_evidence"]["row_label"] == "Zon PV*"
    assert payload["table_evidence"]["unit"] == "GW"
    assert {item["scenario"] for item in candidates} == {"KA", "ND", "IA"}
    assert {item["year"] for item in candidates} == {2035}
    assert all(item["executable_status"] == "candidate_only_unsigned" for item in candidates)
    assert "ii3050_growth_factor_value" in payload["pi_approval_keys_before_executable_use"]
    assert any("No II3050 growth denominator" in item for item in payload["non_claims"])


def test_d014_capacity_value_choice_packet_combines_evidence_without_executable_value(tmp_path: Path) -> None:
    packet = pv_capacity.build_d014_pv_capacity_value_choice_packet()

    assert packet["packet_id"] == "D014-PV-CAPACITY-VALUE-CHOICE-PACKET"
    assert packet["data_id"] == "D-014"
    assert packet["status"] == "proposed_value_choice_packet_no_executable_values"
    assert packet["download_performed"] is False
    assert packet["raw_data_committed"] is False
    assert packet["source_evidence_inputs"]["cbs_anchor_packet_id"] == "D014-CBS-PV-CAPACITY-ANCHOR-EVIDENCE"
    assert packet["source_evidence_inputs"]["ii3050_growth_packet_id"] == "D014-II3050-PV-GROWTH-EVIDENCE"
    operands = packet["candidate_operands_for_pi_review"]
    assert any(
        item["operand_role"] == "source_year_matched_ii3050_reference_all_activity_and_homes"
        for item in operands["cbs_alkmaar_capacity_operands"]
    )
    assert {item["scenario"] for item in operands["ii3050_2035_scenario_operands"]} == {"KA", "ND", "IA"}
    equations = {item["equation_id"]: item for item in packet["candidate_equations_for_local_2035_capacity"]}
    assert equations["dc_kwp_source_year_matched_ii3050_ratio"]["recommended_for_pi_review"] is True
    assert equations["dc_kwp_source_year_matched_ii3050_ratio"]["executable_status"] == "proposed_recommendation_unsigned"
    assert packet["scenario_consistency_issue"]["decision_id"] == "A-016"
    assert packet["scenario_consistency_issue"]["executable_status"] == "blocked_until_A016_consistency_mapping_signed"
    assert packet["capacity_convention_recommendation"]["not_approved_by_this_packet"] is True
    assert "ii3050_growth_factor_value" in packet["pi_approval_keys_before_executable_use"]
    assert any("No final PV capacity value" in item for item in packet["non_claims"])

    path = pv_capacity.write_d014_pv_capacity_value_choice_packet(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == "d014_pv_capacity_value_choice_packet.json"
    assert payload["pi_recommendation"]["recommendation_status"] == "proposed_unsigned_not_executable"


def test_committed_d014_capacity_value_choice_packet_records_recommendation_as_unsigned() -> None:
    payload = json.loads(
        Path("data/metadata/weather_pv/d014_pv_capacity_value_choice_packet.json").read_text(
            encoding="utf-8"
        )
    )

    assert payload["packet_id"] == "D014-PV-CAPACITY-VALUE-CHOICE-PACKET"
    assert payload["source_evidence_inputs"]["cbs_anchor_packet_id"] == "D014-CBS-PV-CAPACITY-ANCHOR-EVIDENCE"
    assert payload["source_evidence_inputs"]["ii3050_growth_packet_id"] == "D014-II3050-PV-GROWTH-EVIDENCE"
    assert len(payload["source_evidence_inputs"]["cbs_raw_sha256"]) == 64
    assert len(payload["source_evidence_inputs"]["ii3050_raw_sha256"]) == 64
    assert payload["pi_recommendation"]["primary_equation_id"] == "dc_kwp_source_year_matched_ii3050_ratio"
    assert payload["pi_recommendation"]["recommendation_status"] == "proposed_unsigned_not_executable"
    assert "A-016" in payload["governing_decisions"]["scenario_consistency"]
    assert "PV-PARAM-001 remains proposed" in payload["governing_decisions"]["conversion_parameters"]
    assert "no roof/building/3DBAG/PV-map" in payload["governing_decisions"]["orientation_scope"]
    assert "scenario_source_consistency_with_ev_hp_inputs" in payload["pi_approval_keys_before_executable_use"]
    assert any("No PV generation" in item for item in payload["non_claims"])


def test_d014_statistical_orientation_tilt_packet_is_lightweight_and_metadata_only(tmp_path: Path) -> None:
    packet = pv_capacity.build_d014_pv_statistical_orientation_tilt_packet()

    assert packet["packet_id"] == "D014-PV-STATISTICAL-ORIENTATION-TILT-PACKET"
    assert packet["data_id"] == "D-014"
    assert packet["download_performed"] is False
    assert packet["raw_data_committed"] is False
    assert packet["first_experiment_scope"]["statistical_orientation_tilt_classes_only"] is True
    assert packet["first_experiment_scope"]["building_or_roof_level_extraction_in_scope"] is False
    assert packet["first_experiment_scope"]["specific_3dbag_per_roof_workflow_in_first_experiment"] is False
    assert "PV-CAP-001 remains separate" in packet["governing_boundaries"]["capacity_route"]
    assert "PR=0.86/direct-GHI is not approved" in packet["governing_boundaries"]["conversion_parameters"]
    route_ids = {source["source_id"] for source in packet["source_route_comparison"]}
    assert "3dbag_deferred_roof_geometry" in route_ids
    assert "statistical_orientation_tilt_source" in packet["pi_approval_keys_before_executable_use"]
    assert "class_weight_values" in packet["pi_approval_keys_before_executable_use"]
    assert "No statistical class bins or weights are approved." in packet["non_claims"]

    path = pv_capacity.write_d014_pv_statistical_orientation_tilt_packet(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == "d014_pv_statistical_orientation_tilt_packet.json"
    assert payload["status"].startswith("proposed_statistical_orientation_tilt_packet")


def test_d014_orientation_tilt_source_choice_packet_lists_candidates_without_values(tmp_path: Path) -> None:
    packet = pv_capacity.build_d014_pv_orientation_tilt_source_choice_packet()

    assert packet["packet_id"] == "D014-PV-ORIENTATION-TILT-SOURCE-CHOICE-PACKET"
    assert packet["data_id"] == "D-014"
    assert packet["download_performed"] is False
    assert packet["raw_data_committed"] is False
    assert packet["approved_scope_decision"] == "PV-ORIENT-001"
    assert packet["first_experiment_scope"]["statistical_orientation_tilt_classes_only"] is True
    assert packet["first_experiment_scope"]["specific_3dbag_per_roof_workflow_allowed_now"] is False
    candidate_ids = {candidate["source_id"] for candidate in packet["source_candidates"]}
    assert {
        "killinger_2018_pv_system_characteristics",
        "utrecht_rooftop_pv_observed_systems",
        "ramadhani_2023_rooftop_uncertainty_method",
        "pvgis_reference",
        "pvlib_conversion_candidate",
        "jrc_dbsm_or_3dbag_deferred_building_level_work",
    }.issubset(candidate_ids)
    assert packet["recommended_source_order_for_pi_review"][0]["source_id"] == (
        "killinger_2018_pv_system_characteristics"
    )
    assert packet["proposed_class_artifact_requirements"]["executable_allowed_now"] is False
    assert "class_weight_values" in packet["pi_approval_keys_before_executable_use"]
    assert "pv_conversion_treatment_for_classes" in packet["pi_approval_keys_before_executable_use"]
    assert any("No orientation or tilt class bins" in item for item in packet["non_claims"])

    path = pv_capacity.write_d014_pv_orientation_tilt_source_choice_packet(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == "d014_pv_orientation_tilt_source_choice_packet.json"
    assert payload["status"].startswith("proposed_source_choice_packet")



def test_d014_pv_param_conversion_source_choice_packet_is_fail_closed(tmp_path: Path) -> None:
    packet = pv_capacity.build_d014_pv_param_conversion_source_choice_packet()

    assert packet["packet_id"] == "D014-PV-PARAM-CONVERSION-SOURCE-CHOICE-PACKET"
    assert packet["data_id"] == "D-014"
    assert packet["download_performed"] is False
    assert packet["raw_data_committed"] is False
    assert "PV-PARAM-001 remains proposed" in packet["governing_decisions"]["pv_param_decision_status"]
    assert "PV-ORIENT-001 statistical" in packet["governing_decisions"]["orientation_scope"]
    assert "PVGIS remains qualitative" in packet["governing_decisions"]["weather_basis"]
    candidates = {candidate["candidate_id"]: candidate for candidate in packet["conversion_source_candidates"]}
    assert "pvlib_statistical_orientation_tilt_poa_candidate" in candidates
    assert "pvgis_reference_calibration_sanity_candidate" in candidates
    assert candidates["direct_ghi_pr_scalar_candidate"]["candidate_status"] == (
        "disputed_simple_candidate_unsigned_not_executable"
    )
    assert packet["executable_gate"]["executable_allowed_now"] is False
    assert "PV-PARAM-001_or_signed_amendment" in packet["executable_gate"]["blocking_register_ids"]
    assert "orientation_tilt_value_packet_id" in packet["pi_approval_keys_before_executable_use"]
    assert any("No PV conversion formula" in item for item in packet["non_claims"])
    assert any("No PR=0.86" in item and "signed" in item for item in packet["non_claims"])

    path = pv_capacity.write_d014_pv_param_conversion_source_choice_packet(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == "d014_pv_param_conversion_source_choice_packet.json"
    assert payload["status"].startswith("proposed_conversion_source_choice")


def test_d014_first_experiment_approval_packet_is_metadata_only_and_fail_closed(tmp_path: Path) -> None:
    packet = pv_capacity.build_d014_pv_first_experiment_approval_packet()

    assert packet["packet_id"] == "D014-PV-FIRST-EXPERIMENT-APPROVAL-PACKET"
    assert packet["data_id"] == "D-014"
    assert packet["download_performed"] is False
    assert packet["raw_data_committed"] is False
    assert packet["first_experiment_scope"]["orientation_tilt_route"] == "typical/statistical distribution only"
    assert packet["first_experiment_scope"]["building_roof_location_level_geometry_allowed"] is False
    assert packet["first_experiment_scope"]["specific_3dbag_or_pv_map_workflow_allowed"] is False
    assert packet["input_metadata"]["capacity_approval_template"]["packet_id"] == "D014-PV-CAPACITY-APPROVAL-TEMPLATE"
    assert packet["input_metadata"]["orientation_tilt_value_choice"]["packet_id"] == "D014-PV-ORIENTATION-TILT-VALUE-CHOICE-PACKET"
    assert packet["input_metadata"]["pv_param_conversion_source_choice"]["packet_id"] == "D014-PV-PARAM-CONVERSION-SOURCE-CHOICE-PACKET"
    assert packet["input_metadata"]["executable_preflight_guard"]["packet_id"] == "D014-PV-EXECUTABLE-PREFLIGHT-GUARD"
    assert set(packet["separated_decision_layers"]) == {
        "installed_capacity_route",
        "orientation_tilt_distribution",
        "irradiance_to_power_conversion",
        "node_allocation",
    }
    assert packet["executable_gate"]["executable_pv_generation_authorized"] is False
    assert "PV-PARAM-001_or_signed_amendment" in packet["executable_gate"]["blocking_register_ids"]
    assert "signed_node_allocation_rule" in packet["pi_approval_keys_before_executable_use"]
    assert any("No PV capacity value" in item and "orientation/tilt" in item for item in packet["non_claims"])
    assert any("No building, roof" in item for item in packet["non_claims"])

    path = pv_capacity.write_d014_pv_first_experiment_approval_packet(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == "d014_pv_first_experiment_approval_packet.json"
    assert payload["status"].startswith("proposed_first_experiment_pv_approval_packet")


def test_d014_first_experiment_value_decision_packet_narrows_options_without_values(tmp_path: Path) -> None:
    packet = pv_capacity.build_d014_pv_first_experiment_value_decision_packet()

    assert packet["packet_id"] == "D014-PV-FIRST-EXPERIMENT-VALUE-DECISION-PACKET"
    assert packet["data_id"] == "D-014"
    assert packet["download_performed"] is False
    assert packet["raw_data_committed"] is False
    assert packet["input_metadata"]["first_experiment_approval_packet"]["packet_id"] == "D014-PV-FIRST-EXPERIMENT-APPROVAL-PACKET"
    assert packet["input_metadata"]["capacity_value_choice_packet"]["packet_id"] == "D014-PV-CAPACITY-VALUE-CHOICE-PACKET"
    assert packet["input_metadata"]["orientation_tilt_value_choice_packet"]["packet_id"] == "D014-PV-ORIENTATION-TILT-VALUE-CHOICE-PACKET"
    assert packet["input_metadata"]["pv_param_conversion_source_choice_packet"]["packet_id"] == "D014-PV-PARAM-CONVERSION-SOURCE-CHOICE-PACKET"
    assert packet["scope_guardrails"]["roof_building_location_specific_geometry_allowed"] is False
    assert packet["scope_guardrails"]["three_dbag_pv_map_or_per_roof_workflow_allowed"] is False
    assert "PVGIS remains qualitative" in packet["scope_guardrails"]["weather_realization_boundary"]
    assert set(packet["decision_options_for_pi"]) == {
        "statistical_orientation_tilt_distribution",
        "irradiance_to_power_conversion",
        "performance_loss_treatment",
        "temperature_and_clipping_treatment",
        "capacity_convention",
        "node_allocation",
        "scenario_consistency",
    }
    assert packet["recommended_first_experiment_route_for_review"]["route_status"] == (
        "recommendation_only_unsigned_not_executable"
    )
    assert packet["executable_gate"]["executable_pv_generation_authorized"] is False
    assert packet["executable_gate"]["result_if_invoked"] == "abort_until_value_decisions_signed"
    assert "PV-PARAM-001_or_signed_amendment" in packet["executable_gate"]["blocking_register_ids"]
    assert "signed_node_allocation_rule_and_normalization_denominator" in packet["pi_approval_keys_before_executable_use"]
    assert any("No PV capacity value" in item and "orientation/tilt" in item for item in packet["non_claims"])
    assert any("No building, roof" in item and "PV-map" in item for item in packet["non_claims"])

    path = pv_capacity.write_d014_pv_first_experiment_value_decision_packet(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == "d014_pv_first_experiment_value_decision_packet.json"
    assert payload["status"].startswith("proposed_first_experiment_pv_value_decision_support")

def test_d014_orientation_tilt_value_choice_packet_lists_unsigned_candidate_values(tmp_path: Path) -> None:
    packet = pv_capacity.build_d014_pv_orientation_tilt_value_choice_packet()

    assert packet["packet_id"] == "D014-PV-ORIENTATION-TILT-VALUE-CHOICE-PACKET"
    assert packet["data_id"] == "D-014"
    assert packet["download_performed"] is False
    assert packet["raw_data_committed"] is False
    assert packet["approved_scope_decision"] == "PV-ORIENT-001"
    assert packet["source_choice_packet_id"] == "D014-PV-ORIENTATION-TILT-SOURCE-CHOICE-PACKET"
    assert "PV-CAP-001/D-014 capacity remains separate" in packet["capacity_route_boundary"]
    assert "PV-PARAM-001 remains proposed" in packet["pv_param_boundary"]
    assert packet["first_experiment_scope"]["roof_or_location_level_extraction_allowed_now"] is False
    class_sets = {item["class_set_id"]: item for item in packet["candidate_class_sets"]}
    assert "killinger_empirical_extraction_pending_v1" in class_sets
    prior = class_sets["pi_prior_5_class_symmetric_rooftop_candidate_v1"]
    assert prior["value_status"] == "assumption_only_unsigned_not_executable"
    assert prior["weight_basis"] == "capacity_weight_fraction_candidate"
    assert sum(row["capacity_weight_fraction"] for row in prior["class_table"]) == pytest.approx(1.0)
    assert all("assumption-only" in row["source_value_trace"] for row in prior["class_table"])
    assert "class_weight_values" in packet["pi_approval_keys_before_executable_use"]
    assert any("Numeric class weights" in item and "unsigned" in item for item in packet["non_claims"])

    path = pv_capacity.write_d014_pv_orientation_tilt_value_choice_packet(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == "d014_pv_orientation_tilt_value_choice_packet.json"
    assert payload["status"].startswith("proposed_value_choice_packet")


def test_hp001_profile_artifact_consumption_template_is_fail_closed(tmp_path: Path) -> None:
    packet = hp_scaling.build_hp001_profile_artifact_consumption_manifest_template()

    assert packet["manifest_id"] == "E2-S3-HP001-PROFILE-ARTIFACT-CONSUMPTION-MANIFEST"
    assert packet["status"] == "proposed_template_not_approved_for_integrated_consumption"
    assert packet["future_required_status"] == "approved_for_integrated_hp_profile_consumption"
    assert packet["profile_artifact"]["cadence_seconds"] == 900
    assert packet["weather_identity"]["identity_rule"].startswith("Must match the PV profile")
    assert {component["end_use"] for component in packet["component_traceability"]} == {"space", "water"}
    assert set(packet["missing_approval_keys"]) == {
        "value_column",
        "denominator",
        "unit_conversion",
        "sfh_mfh_split",
        "adoption_electrification",
        "scenario_source_consistency",
        "d004_paired_weather_acceptance",
        "cold_spell_tolerances",
    }
    assert "No annual HP TWh values are executable." in packet["non_claims"]

    path = hp_scaling.write_hp001_profile_artifact_consumption_manifest_template(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == "hp001_profile_artifact_consumption_manifest_template.json"
    assert payload["validator"] == "src.hp_model.require_hp001_profile_artifact_consumption_manifest"


def test_hp001_profile_rebuild_preflight_template_is_fail_closed(tmp_path: Path) -> None:
    packet = hp_scaling.build_hp001_profile_rebuild_preflight_template()

    assert packet["packet_id"] == "E2-S3-HP001-PROFILE-REBUILD-PREFLIGHT"
    assert packet["status"] == "proposed_rebuild_preflight_template_not_executable"
    assert packet["future_required_manifest_status"] == "approved_for_hp001_profile_rebuild_preflight"
    assert packet["validator"] == "src.hp_model.require_hp001_profile_rebuild_preflight_manifest"
    assert "value_column" in packet["required_approval_keys_before_rebuild"]
    assert "cold_spell_tolerances" in packet["required_approval_keys_before_rebuild"]
    assert packet["preflight_manifest_template"]["output_plan"]["component_count"] == 4
    assert packet["preflight_manifest_template"]["source_artifacts"]["when2heat_source"]["data_id"] == "D-003"
    assert any("No HP profile artifact" in item for item in packet["non_claims"])

    path = hp_scaling.write_hp001_profile_rebuild_preflight_template(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == "hp001_profile_artifact_rebuild_preflight_template.json"
    assert payload["validator"] == "src.hp_model.require_hp001_profile_rebuild_preflight_manifest"


def _signed_hp001_profile_rebuild_runner_manifest() -> dict[str, object]:
    weather_identity = {
        "shared_weather_driver_id": "d004_alkmaar_berkhout_2014_2023_v1",
        "member_id": "weather-member-001",
        "source": "D-004 WEATHER-001 signed synthetic fixture",
        "content_sha256": "a" * 64,
        "n_timesteps": 35040,
        "cadence_seconds": 900,
    }
    return {
        "status": "approved_for_hp001_profile_rebuild_preflight",
        "approval_ids": {
            "value_column": "PI-HP001-VALUE-COLUMN-20260724",
            "denominator": "PI-HP001-DENOMINATOR-20260724",
            "unit_conversion": "PI-HP001-UNIT-CONVERSION-20260724",
            "sfh_mfh_split": "PI-HP001-SFH-MFH-SPLIT-20260724",
            "adoption_electrification": "PI-HP001-ADOPTION-ELECTRIFICATION-20260724",
            "scenario_source_consistency": "PI-A016-SCENARIO-CONSISTENCY-20260724",
            "d004_paired_weather_acceptance": "PI-D004-PAIRED-WEATHER-20260724",
            "cold_spell_tolerances": "PI-HP001-COLD-SPELL-TOLERANCES-20260724",
        },
        "source_artifacts": {
            "when2heat_source": {
                "data_id": "D-003",
                "path": "data/raw/when2heat/signed_fixture.csv",
                "sha256": "b" * 64,
                "provenance": "signed synthetic test fixture",
            },
            "weather_member": {
                "data_id": "D-004",
                "path": "data/processed/weather_pv/signed_fixture.parquet",
                "sha256": "c" * 64,
                "provenance": "signed synthetic test fixture",
            },
            "value_binding_record": {
                "data_id": "D-013",
                "path": "data/metadata/hp_scaling/signed_fixture.json",
                "sha256": "d" * 64,
                "provenance": "signed synthetic test fixture",
            },
        },
        "weather_identity": dict(weather_identity),
        "paired_pv_weather_identity": dict(weather_identity),
        "output_plan": {
            "profile_artifact_path": "data/processed/hp_profiles/signed_fixture.npz",
            "profile_manifest_path": "data/metadata/hp_scaling/signed_fixture_manifest.json",
            "checksum_manifest_path": "data/metadata/hp_scaling/signed_fixture_checksums.json",
            "n_timesteps": 35040,
            "cadence_seconds": 900,
            "component_count": 4,
            "electric_power_unit": "kW",
        },
        "unresolved_blocker_ids": [],
    }


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_hp001_profile_rebuild_runner_blocks_committed_template_packet(tmp_path: Path) -> None:
    preflight_path = hp_scaling.write_hp001_profile_rebuild_preflight_template(tmp_path)
    output_path = tmp_path / "runner_blocker.json"

    result_path = hp_scaling.write_hp001_profile_rebuild_runner_manifest(
        preflight_path,
        output_path,
        request_id="test-template-packet",
        repository_root=Path("."),
    )
    payload = json.loads(result_path.read_text(encoding="utf-8"))

    assert payload["packet_id"] == "E2-S3-HP001-PROFILE-REBUILD-RUNNER-SCAFFOLD"
    assert payload["status"] == "blocked_fail_closed_no_profile_rebuild"
    assert payload["accepted_for_profile_rebuild_handoff"] is False
    assert payload["profile_generation_performed"] is False
    assert payload["input_manifest"]["kind"] == "template_packet_preflight_manifest_template"
    assert payload["input_manifest"]["sha256"] == hashlib.sha256(preflight_path.read_bytes()).hexdigest()
    assert "stale_or_placeholder_approval:value_column" in payload["blocker_ids"]
    assert "source_artifacts:when2heat_source_sha256_missing_or_invalid" in payload["blocker_ids"]
    assert payload["intended_handoff_shape"] is None


def test_hp001_profile_rebuild_runner_rejects_placeholder_approval_ids(tmp_path: Path) -> None:
    manifest = _signed_hp001_profile_rebuild_runner_manifest()
    manifest["approval_ids"]["value_column"] = "<future signed value_column approval id>"
    preflight_path = _write_json(tmp_path / "preflight.json", manifest)

    payload = hp_scaling.build_hp001_profile_rebuild_runner_manifest(
        preflight_path,
        request_id="test-placeholder-approval",
        repository_root=Path("."),
    )

    assert payload["accepted_for_profile_rebuild_handoff"] is False
    assert "stale_or_placeholder_approval:value_column" in payload["blocker_ids"]
    assert payload["profile_generation_performed"] is False


def test_hp001_profile_rebuild_runner_rejects_missing_source_checksum(tmp_path: Path) -> None:
    manifest = _signed_hp001_profile_rebuild_runner_manifest()
    manifest["source_artifacts"]["when2heat_source"]["sha256"] = ""
    preflight_path = _write_json(tmp_path / "preflight.json", manifest)

    payload = hp_scaling.build_hp001_profile_rebuild_runner_manifest(
        preflight_path,
        request_id="test-missing-checksum",
        repository_root=Path("."),
    )

    assert payload["accepted_for_profile_rebuild_handoff"] is False
    assert "source_artifacts:when2heat_source_sha256_missing" in payload["blocker_ids"]


def test_hp001_profile_rebuild_runner_rejects_hp_pv_weather_mismatch(tmp_path: Path) -> None:
    manifest = _signed_hp001_profile_rebuild_runner_manifest()
    manifest["paired_pv_weather_identity"]["member_id"] = "different-member"
    preflight_path = _write_json(tmp_path / "preflight.json", manifest)

    payload = hp_scaling.build_hp001_profile_rebuild_runner_manifest(
        preflight_path,
        request_id="test-weather-mismatch",
        repository_root=Path("."),
    )

    assert payload["accepted_for_profile_rebuild_handoff"] is False
    assert "paired_weather_identity_mismatch:member_id" in payload["blocker_ids"]


def test_hp001_profile_rebuild_runner_accepts_signed_synthetic_fixture_without_generation(tmp_path: Path) -> None:
    manifest = _signed_hp001_profile_rebuild_runner_manifest()
    preflight_path = _write_json(tmp_path / "preflight.json", manifest)
    output_path = tmp_path / "runner_output.json"

    result_path = hp_scaling.write_hp001_profile_rebuild_runner_manifest(
        preflight_path,
        output_path,
        request_id="test-signed-synthetic",
        repository_root=Path("."),
    )
    payload = json.loads(result_path.read_text(encoding="utf-8"))

    assert payload["status"] == "accepted_preflight_handoff_no_profile_generation"
    assert payload["accepted_for_profile_rebuild_handoff"] is True
    assert payload["profile_generation_performed"] is False
    assert payload["blocker_ids"] == []
    assert payload["intended_handoff_shape"]["output_plan"]["component_count"] == 4
    assert payload["intended_handoff_shape"]["next_runner_boundary"].startswith(
        "future signed HP profile artifact builder"
    )
    assert payload["code_identity"]["git_head"]
    assert set(payload["code_identity"]["tracked_file_sha256"]) == {
        "data/get_hp_scaling.py",
        "src/hp_model.py",
    }

def test_d014_capacity_approval_template_is_value_free_and_fail_closed() -> None:
    packet = pv_capacity.build_d014_pv_capacity_approval_template_packet()

    assert packet["packet_id"] == "D014-PV-CAPACITY-APPROVAL-TEMPLATE"
    assert packet["data_id"] == "D-014"
    assert packet["status"] == "proposed_signed_capacity_artifact_template_no_values"
    assert packet["download_performed"] is False
    assert packet["raw_data_committed"] is False
    assert packet["upstream_value_choice_packet"]["packet_id"] == "D014-PV-CAPACITY-VALUE-CHOICE-PACKET"
    assert len(packet["upstream_value_choice_packet"]["metadata_sha256"]) == 64
    assert packet["approved_route_boundary"]["capacity_route_decision"] == "PV-CAP-001"
    assert packet["approved_route_boundary"]["scenario_consistency_decision"] == "A-016"
    assert packet["approved_route_boundary"]["orientation_scope_decision"] == "PV-ORIENT-001"
    assert packet["executable_gate"]["accepted_for_executable_pv_capacity_input"] is False
    assert packet["executable_gate"]["signed_capacity_value_approved"] is False
    assert "installed_capacity_value" in packet["required_signed_artifact_fields"]["capacity_value"]
    assert "ii3050_growth_factor_value" in packet["executable_gate"]["blocking_approval_keys"]
    assert any("No PV generation" in item for item in packet["non_claims"])


def test_committed_d014_capacity_approval_template_records_unsigned_contract() -> None:
    payload = json.loads(
        Path("data/metadata/weather_pv/d014_pv_capacity_approval_template.json").read_text(
            encoding="utf-8"
        )
    )

    assert payload["packet_id"] == "D014-PV-CAPACITY-APPROVAL-TEMPLATE"
    assert payload["upstream_value_choice_packet"]["recommended_equation_id"] == "dc_kwp_source_year_matched_ii3050_ratio"
    assert payload["recommended_pi_path"]["not_approved_by_this_template"] is True
    assert payload["executable_gate"]["requires_pi_signed_decision"] is True
    assert "PV-PARAM-001_or_amended_conversion_decision" in payload["executable_gate"]["blocking_approval_keys"]


def test_hp001_component_output_readiness_blocker_packet_is_not_executable(tmp_path: Path) -> None:
    packet = hp_scaling.build_hp001_component_output_readiness_blocker_packet()

    assert packet["packet_id"] == "E2-S3-HP001-COMPONENT-OUTPUT-READINESS-BLOCKER"
    assert packet["status"] == "proposed_blocker_packet_not_executable"
    assert packet["future_required_manifest_status"] == "approved_for_ic1_component_output_consumption"
    assert "value_column" in packet["required_approval_keys_before_ic1_consumption"]
    assert "d004_paired_weather_acceptance" in packet["required_approval_keys_before_ic1_consumption"]
    assert packet["preflight_manifest_template"]["unresolved_blocker_ids"] == []
    assert {item["end_use"] for item in packet["preflight_manifest_template"]["component_traceability"]} == {"space", "water"}
    assert any("no real HP component-output artifact" in item for item in packet["current_blockers"])
    assert "No executable annual HP values are created." in packet["non_claims"]

    path = hp_scaling.write_hp001_component_output_readiness_blocker_packet(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == "hp001_component_output_readiness_blocker_packet.json"
    assert payload["validator"] == "src.hp_model.require_hp001_component_output_readiness_manifest"


def test_d014_pv_executable_readiness_blockers_keep_generation_blocked() -> None:
    packet = pv_capacity.build_d014_pv_executable_readiness_blockers_packet()

    assert packet["packet_id"] == "D014-PV-EXECUTABLE-READINESS-BLOCKERS"
    assert packet["status"] == "proposed_fail_closed_executable_pv_readiness_blockers"
    assert packet["input_metadata"]["capacity_approval_template"]["packet_id"] == "D014-PV-CAPACITY-APPROVAL-TEMPLATE"
    assert packet["input_metadata"]["orientation_tilt_value_choice"]["packet_id"] == "D014-PV-ORIENTATION-TILT-VALUE-CHOICE-PACKET"
    assert packet["readiness_layers"]["weather_source_member"]["component_source_member_ready"] is True
    assert packet["readiness_layers"]["capacity_value"]["ready"] is False
    assert packet["readiness_layers"]["scenario_consistency"]["decision_id"] == "A-016"
    assert packet["executable_gate"]["executable_pv_generation_authorized"] is False
    assert "PV-PARAM-001" in packet["executable_gate"]["blocking_register_ids"]
    assert any("No PV generation" in item for item in packet["non_claims"])


def test_committed_d014_pv_executable_readiness_blockers_record_inputs() -> None:
    payload = json.loads(
        Path("data/metadata/weather_pv/d014_pv_executable_readiness_blockers.json").read_text(
            encoding="utf-8"
        )
    )

    assert payload["packet_id"] == "D014-PV-EXECUTABLE-READINESS-BLOCKERS"
    assert payload["executable_gate"]["component_source_member_artifact_available"] is True
    assert payload["executable_gate"]["executable_pv_generation_authorized"] is False
    assert len(payload["input_metadata"]["weather_input_artifact"]["sha256"]) == 64
    assert len(payload["input_metadata"]["pv_parameter_packet"]["sha256"]) == 64


def test_d014_pv_executable_preflight_guard_aborts_without_generation() -> None:
    packet = pv_capacity.build_d014_pv_executable_preflight_guard_packet()

    assert packet["packet_id"] == "D014-PV-EXECUTABLE-PREFLIGHT-GUARD"
    assert packet["status"] == "proposed_fail_closed_preflight_no_generation"
    assert packet["input_blocker_manifest"]["packet_id"] == "D014-PV-EXECUTABLE-READINESS-BLOCKERS"
    assert len(packet["input_blocker_manifest"]["metadata_sha256"]) == 64
    assert packet["preflight_checks"]["component_source_member_artifact_available"] is True
    assert packet["preflight_checks"]["executable_pv_generation_authorized"] is False
    assert packet["preflight_checks"]["all_required_blockers_present"] is True
    assert packet["executable_gate"]["preflight_ready_for_executable_pv_generation"] is False
    assert packet["executable_gate"]["result_if_invoked"] == "abort_with_blocker_manifest"
    assert "placeholder" in packet["token_policy"]["unsafe_tokens_for_executable_outputs"]
    assert "proposed" in packet["token_policy"]["allowlisted_non_executable_metadata_tokens"]
    assert any("No executable PV preflight passes" in item for item in packet["non_claims"])


def test_committed_d014_pv_executable_preflight_guard_records_blockers() -> None:
    payload = json.loads(
        Path("data/metadata/weather_pv/d014_pv_executable_preflight_guard.json").read_text(
            encoding="utf-8"
        )
    )

    assert payload["packet_id"] == "D014-PV-EXECUTABLE-PREFLIGHT-GUARD"
    assert payload["executable_gate"]["preflight_ready_for_executable_pv_generation"] is False
    assert payload["executable_gate"]["result_if_invoked"] == "abort_with_blocker_manifest"
    assert "D014-PV-CAPACITY-APPROVAL-TEMPLATE" in payload["executable_gate"]["blocking_register_ids"]
    assert "PV-PARAM-001" in payload["executable_gate"]["blocking_register_ids"]
