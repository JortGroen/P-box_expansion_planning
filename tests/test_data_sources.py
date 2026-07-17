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
from data.get_elaad_profiles import (
    ProfileBatch,
    _shape_report,
    build_batch_request,
    build_library_plan,
    build_probe_request,
    run_set_a_library_batch,
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
    expected_ids = {"D-001", "D-002", "D-003", "D-004", "D-008"}
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


def test_data_register_has_no_e2_s1_placeholders() -> None:
    register = Path("registers/DATA_REGISTER.md").read_text(encoding="utf-8")

    for placeholder in ("TBD", "to check", "URL to verify", "DOI/URL to verify"):
        assert placeholder not in register


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
