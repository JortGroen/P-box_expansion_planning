from __future__ import annotations

from datetime import UTC, datetime, timedelta
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

import data.get_elaad_profiles as elaad
import data.get_hp_scaling as hp_scaling
import data.get_ndw_charging_inventory as ndw
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
    expected_ids = {"D-001", "D-002", "D-003", "D-004", "D-008", "D-012", "D-013"}
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
    assert "summaries" not in payload
    assert payload["selection"]["municipality_boundary_note"].startswith(
        "The NDW OCPI file exposes city strings"
    )


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
