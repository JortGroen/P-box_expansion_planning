from __future__ import annotations

from datetime import UTC, datetime, timedelta
import gzip
import inspect
import json
from pathlib import Path

import numpy as np
import pytest

import src.ev_model as ev_model
from src.ev_model import (
    EV_HOME_COMPONENT,
    EVProfileLibrary,
    EVProfileBootstrapSampler,
    EXPECTED_FULL_YEAR_STEPS,
    adoption_node_allocations,
    adoption_scenarios,
    allocate_charge_points_to_nodes,
    charge_point_range_by_year,
    distinct_member_count,
    load_adoption_scenarios_config,
    load_processed_batch_npz,
    national_outlook_projections,
    node_charge_point_ranges,
    parse_elaad_profile_response,
    save_processed_batch_npz,
    validate_adoption_scenarios_config,
)
from src.rng import SeedTree


def _payload(n_profiles: int = 3, timesteps: int = EXPECTED_FULL_YEAR_STEPS) -> dict:
    start = datetime(2024, 12, 31, 23, 0, tzinfo=UTC)
    datetimes = [(start + timedelta(minutes=15 * index)).isoformat() for index in range(timesteps)]
    demands = [
        [float(profile + 1 + (step % 4)) for profile in range(n_profiles)]
        for step in range(timesteps)
    ]
    return {
        "config": {"seed": 130001, "n_profiles": n_profiles},
        "statistics": None,
        "profile": {
            "cp_ids": [f"profile_{index}" for index in range(n_profiles)],
            "datetimes": datetimes,
            "demands_kw": demands,
        },
    }


def test_parse_time_major_response_and_timezone() -> None:
    batch = parse_elaad_profile_response(_payload(), batch_seed=130001, expected_n_profiles=3)

    assert batch.demands_kw.shape == (EXPECTED_FULL_YEAR_STEPS, 3)
    assert batch.datetimes_utc[0].isoformat() == "2024-12-31T23:00:00+00:00"
    assert batch.datetimes_local[0].isoformat() == "2025-01-01T00:00:00+01:00"
    assert batch.member_ids == ("profile_130001_000", "profile_130001_001", "profile_130001_002")
    assert np.all(batch.annual_energy_kwh() > 0)


def test_parse_rejects_profile_major_output() -> None:
    payload = _payload(n_profiles=2)
    payload["profile"]["demands_kw"] = [[0.0] * EXPECTED_FULL_YEAR_STEPS for _ in range(2)]

    with pytest.raises(ValueError, match="time-major"):
        parse_elaad_profile_response(payload, batch_seed=130001, expected_n_profiles=2)


def test_parse_rejects_nonfinite_values() -> None:
    payload = _payload(n_profiles=1)
    payload["profile"]["demands_kw"][0][0] = None

    with pytest.raises(ValueError, match="missing or non-finite"):
        parse_elaad_profile_response(payload, batch_seed=130001, expected_n_profiles=1)


def test_processed_roundtrip_and_sampler_reproducibility(tmp_path: Path) -> None:
    batch = parse_elaad_profile_response(_payload(n_profiles=4), batch_seed=130001, expected_n_profiles=4)
    path = tmp_path / "batch.npz"
    save_processed_batch_npz(batch, path)
    loaded = load_processed_batch_npz(path)
    sampler = EVProfileBootstrapSampler(loaded)
    stream = SeedTree(root_seed=42).component_stream(sample_index=0, component=EV_HOME_COMPONENT)
    repeated_stream = SeedTree(root_seed=42).component_stream(sample_index=0, component=EV_HOME_COMPONENT)
    different_stream = SeedTree(root_seed=43).component_stream(sample_index=0, component=EV_HOME_COMPONENT)

    # EV-005 leaves replacement unresolved, so tests and production callers
    # must state the provisional sampling rule instead of inheriting a default.
    first = sampler.sample_member_indices(3, component_stream=stream, replace=False)
    second = sampler.sample_member_indices(3, component_stream=repeated_stream, replace=False)
    different = sampler.sample_member_indices(3, component_stream=different_stream, replace=False)

    assert np.array_equal(first, second)
    assert not np.array_equal(first, different)
    assert len(set(first.tolist())) == 3
    assert np.array_equal(
        sampler.sample_aggregate_kw(3, component_stream=stream, replace=False),
        loaded.demands_kw[:, first].sum(axis=1),
    )


def test_sampler_selection_records_component_stream_and_member_ids() -> None:
    batch = parse_elaad_profile_response(_payload(n_profiles=5), batch_seed=130001, expected_n_profiles=5)
    sampler = EVProfileBootstrapSampler(batch)
    stream = SeedTree(root_seed=20260720).component_stream(
        sample_index=12,
        component=EV_HOME_COMPONENT,
    )

    first = sampler.select_members(4, component_stream=stream, replace=False)
    second = sampler.select_members(4, component_stream=stream, replace=False)
    records = tuple(record.manifest_record() for record in first.component_selections())

    assert first.indices == second.indices
    assert first.member_ids == second.member_ids
    assert first.stream_id == stream.stream_id
    assert all(record["stream_id"] == stream.stream_id for record in records)
    assert [record["selection_index"] for record in records] == [0, 1, 2, 3]
    assert first.member_ids == tuple(batch.member_ids[index] for index in first.indices)


def test_sampler_component_stream_identity_changes_selection() -> None:
    batch = parse_elaad_profile_response(_payload(n_profiles=10), batch_seed=130001, expected_n_profiles=10)
    sampler = EVProfileBootstrapSampler(batch)
    base = SeedTree(root_seed=20260720).component_stream(sample_index=0, component=EV_HOME_COMPONENT)
    different_root = SeedTree(root_seed=20260721).component_stream(
        sample_index=0,
        component=EV_HOME_COMPONENT,
    )
    different_sample = SeedTree(root_seed=20260720).component_stream(
        sample_index=1,
        component=EV_HOME_COMPONENT,
    )

    base_selection = sampler.select_members(6, component_stream=base, replace=False)
    root_selection = sampler.select_members(6, component_stream=different_root, replace=False)
    sample_selection = sampler.select_members(6, component_stream=different_sample, replace=False)

    assert base.stream_id != different_root.stream_id
    assert base.stream_id != different_sample.stream_id
    assert base_selection.indices != root_selection.indices
    assert base_selection.indices != sample_selection.indices


def test_sampler_rejects_too_many_without_replacement() -> None:
    batch = parse_elaad_profile_response(_payload(n_profiles=2), batch_seed=130001, expected_n_profiles=2)
    sampler = EVProfileBootstrapSampler(batch)
    stream = SeedTree(root_seed=1).component_stream(sample_index=0, component=EV_HOME_COMPONENT)

    with pytest.raises(ValueError, match="more distinct members"):
        sampler.sample_member_indices(3, component_stream=stream, replace=False)

    replacement = sampler.sample_member_indices(3, component_stream=stream, replace=True)
    assert len(replacement) == 3
    assert set(replacement.tolist()) <= {0, 1}


def test_sampler_requires_explicit_replacement_rule() -> None:
    batch = parse_elaad_profile_response(_payload(n_profiles=2), batch_seed=130001, expected_n_profiles=2)
    sampler = EVProfileBootstrapSampler(batch)
    stream = SeedTree(root_seed=1).component_stream(sample_index=0, component=EV_HOME_COMPONENT)

    with pytest.raises(TypeError, match="replace"):
        sampler.sample_member_indices(1, component_stream=stream)


def test_sampler_rejects_non_home_ev_component_stream() -> None:
    batch = parse_elaad_profile_response(_payload(n_profiles=2), batch_seed=130001, expected_n_profiles=2)
    sampler = EVProfileBootstrapSampler(batch)
    stream = SeedTree(root_seed=1).component_stream(sample_index=0, component="ev_public")

    with pytest.raises(ValueError, match="ev_home"):
        sampler.sample_member_indices(1, component_stream=stream, replace=False)


def test_ev_sampler_contains_no_independent_local_random_generator() -> None:
    sampler_source = inspect.getsource(ev_model.EVProfileBootstrapSampler)

    assert "default_rng" not in sampler_source
    assert "np.random" not in sampler_source


def test_distinct_member_count_detects_duplicate_profiles() -> None:
    payload = _payload(n_profiles=2)
    payload["profile"]["demands_kw"] = [[1.0, 1.0] for _ in range(EXPECTED_FULL_YEAR_STEPS)]
    batch = parse_elaad_profile_response(payload, batch_seed=130001, expected_n_profiles=2)

    assert distinct_member_count(batch) == 1


def test_gzip_payload_can_be_parsed(tmp_path: Path) -> None:
    path = tmp_path / "response.json.gz"
    raw = json.dumps(_payload(n_profiles=1)).encode("utf-8")
    with gzip.open(path, "wb") as handle:
        handle.write(raw)

    with gzip.open(path, "rb") as handle:
        batch = parse_elaad_profile_response(handle.read(), batch_seed=130001, expected_n_profiles=1)

    assert batch.n_profiles == 1


def test_profile_library_preserves_member_identity_and_isolates_held_out() -> None:
    candidate_a = parse_elaad_profile_response(_payload(n_profiles=2), batch_seed=140001, expected_n_profiles=2)
    candidate_b = parse_elaad_profile_response(_payload(n_profiles=2), batch_seed=140101, expected_n_profiles=2)
    held_out = parse_elaad_profile_response(_payload(n_profiles=1), batch_seed=141001, expected_n_profiles=1)
    library = EVProfileLibrary(
        batches=(candidate_a, candidate_b, held_out),
        partitions=("candidate", "candidate", "held_out"),
    )

    assert library.n_members == 5
    assert library.member_ids == (
        "profile_140001_000",
        "profile_140001_001",
        "profile_140101_000",
        "profile_140101_001",
        "profile_141001_000",
    )
    assert library.demands_kw.shape == (EXPECTED_FULL_YEAR_STEPS, 5)
    assert library.member_table()[2] == {
        "member_id": "profile_140101_000",
        "partition": "candidate",
        "batch_seed": 140101,
        "returned_profile_index": 0,
    }
    assert library.view("candidate").n_members == 4
    with pytest.raises(PermissionError, match="Held-out and quarantined EV profiles remain isolated"):
        library.view("held_out")


def test_profile_library_sampler_reproducibility_and_leave_one_batch_views() -> None:
    batches = tuple(
        parse_elaad_profile_response(_payload(n_profiles=2), batch_seed=seed, expected_n_profiles=2)
        for seed in (140001, 140101, 140201)
    )
    library = EVProfileLibrary(batches=batches, partitions=("candidate", "candidate", "candidate"))

    sampler = library.sampler()
    stream = SeedTree(root_seed=123).component_stream(sample_index=0, component=EV_HOME_COMPONENT)
    first = sampler.sample_member_indices(3, component_stream=stream, replace=False)
    second = sampler.sample_member_indices(3, component_stream=stream, replace=False)
    assert np.array_equal(first, second)
    assert library.nested_candidate_view(2).n_members == 4
    leave_one_out = library.leave_one_batch_out_candidate_views()
    assert len(leave_one_out) == 3
    assert all(view.n_members == 4 for view in leave_one_out)
    disjoint = library.disjoint_candidate_batch_views(1)
    assert len(disjoint) == 3
    assert all(view.n_members == 2 for view in disjoint)


def test_profile_library_rejects_mixed_sampling_and_partition_relabeling(tmp_path: Path) -> None:
    candidate = parse_elaad_profile_response(_payload(n_profiles=2), batch_seed=140001, expected_n_profiles=2)
    held_out = parse_elaad_profile_response(_payload(n_profiles=1), batch_seed=141201, expected_n_profiles=1)
    mixed = EVProfileLibrary(
        batches=(candidate, held_out),
        partitions=("candidate", "held_out"),
    )

    with pytest.raises(PermissionError, match="candidate-only"):
        mixed.sampler()
    with pytest.raises(PermissionError, match="traceable E3.S2a"):
        mixed.view("held_out")
    with pytest.raises(PermissionError, match="committed library manifest"):
        EVProfileLibrary.from_npz_paths(
            [tmp_path / "candidate.npz"],
            partitions=["candidate"],
        )


def test_profile_library_loads_candidate_partitions_from_manifest(tmp_path: Path) -> None:
    candidate = parse_elaad_profile_response(_payload(n_profiles=2), batch_seed=140001, expected_n_profiles=2)
    held_out = parse_elaad_profile_response(_payload(n_profiles=1), batch_seed=141201, expected_n_profiles=1)
    candidate_path = tmp_path / "candidate.npz"
    held_out_path = tmp_path / "held_out.npz"
    save_processed_batch_npz(candidate, candidate_path)
    save_processed_batch_npz(held_out, held_out_path)

    import hashlib

    manifest_path = tmp_path / "manifest.json"
    manifest = {
        "batches": [
            {
                "partition": "candidate",
                "processed_path": candidate_path.name,
                "processed_sha256_file": hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
            },
            {
                "partition": "held_out",
                "processed_path": held_out_path.name,
                "processed_sha256_file": hashlib.sha256(held_out_path.read_bytes()).hexdigest(),
            },
        ]
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    library = EVProfileLibrary.from_library_manifest(manifest_path, base_dir=tmp_path)
    assert library.n_members == 2
    assert library.partitions == ("candidate",)

    with pytest.raises(PermissionError, match="traceable E3.S2a"):
        EVProfileLibrary.from_library_manifest(
            manifest_path,
            base_dir=tmp_path,
            include_partitions=("held_out",),
        )

    manifest["batches"][0]["processed_sha256_file"] = "bad"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum mismatch"):
        EVProfileLibrary.from_library_manifest(manifest_path, base_dir=tmp_path)


def _adoption_config() -> dict:
    return {
        "schema_version": 1,
        "task_id": "E2.S6",
        "source_ids": {
            "national_outlook_projection": "D-010",
            "local_allocation_assumption": "A-014",
        },
        "sources": {"D-010": {"url": "https://outlook.elaad.nl/scenariotool"}},
        "national_outlook_projections": [
            {
                "year": 2030,
                "scenario": "low",
                "location": "home",
                "value": 10.6,
                "rounded_count": 11,
                "provenance": {
                    "source_id": "D-010",
                    "response_sha256": "a" * 64,
                },
            }
        ],
        "allocation": {
            "status": "approved",
            "method_id": "A-014",
            "node_weights": [
                {"node_id": "load_a", "weight": 0.5},
                {"node_id": "load_b", "weight": 0.3},
                {"node_id": "load_c", "weight": 0.2},
            ],
        },
        "local_grid_scenarios": {
            "status": "approved",
            "scenarios": [
                {
                    "year": 2030,
                    "scenario": "low",
                    "home_charge_points": 11,
                    "public_charge_points": 5,
                    "provenance": {
                        "source_type": "local_grid",
                        "home_charge_points": "Q-7-approved-local-home",
                        "public_charge_points": "Q-7-approved-local-public",
                    },
                },
                {
                    "year": 2030,
                    "scenario": "high",
                    "home_charge_points": 17,
                    "public_charge_points": 9,
                    "provenance": {
                        "source_type": "local_grid",
                        "home_charge_points": "Q-7-approved-local-home",
                        "public_charge_points": "Q-7-approved-local-public",
                    },
                },
            ],
        },
    }


def test_adoption_config_validates_schema_and_provenance() -> None:
    config = _adoption_config()

    validate_adoption_scenarios_config(config)
    scenarios = adoption_scenarios(config)
    national = national_outlook_projections(config)

    assert scenarios[0].home_charge_points == 11
    assert scenarios[0].provenance["source_type"] == "local_grid"
    assert national[0].rounded_count == 11
    assert national[0].source_id == "D-010"


def test_committed_adoption_scenarios_config_validates() -> None:
    config = load_adoption_scenarios_config(Path("configs/scenarios.yaml"))
    national = national_outlook_projections(config)

    assert len(national) == 18
    assert config["local_grid_scenarios"]["status"] == "blocked"
    with pytest.raises(ValueError, match="remain blocked until Q-7"):
        adoption_scenarios(config)


def test_adoption_config_accepts_approved_status() -> None:
    config = _adoption_config()
    config["allocation"]["status"] = "approved"
    config["local_grid_scenarios"]["status"] = "approved"

    validate_adoption_scenarios_config(config)


def test_local_scenarios_reject_counts_until_status_approved() -> None:
    for status in ("blocked", "proposed"):
        config = _adoption_config()
        config["local_grid_scenarios"]["status"] = status

        with pytest.raises(ValueError, match="only after their register status is approved"):
            validate_adoption_scenarios_config(config)


def test_adoption_scenarios_rejects_unapproved_empty_local_status() -> None:
    config = _adoption_config()
    config["local_grid_scenarios"]["status"] = "proposed"
    config["local_grid_scenarios"]["scenarios"] = []

    with pytest.raises(ValueError, match="remain blocked until Q-7"):
        adoption_scenarios(config)


def test_adoption_config_rejects_invalid_allocation_status() -> None:
    config = _adoption_config()
    config["allocation"]["status"] = "signed"

    with pytest.raises(ValueError, match="status"):
        validate_adoption_scenarios_config(config)


def test_national_projections_cannot_flow_into_local_allocation() -> None:
    config = _adoption_config()
    config["local_grid_scenarios"]["scenarios"][0]["provenance"]["home_charge_points"] = "D-010"

    with pytest.raises(ValueError, match="National Outlook projections cannot be used directly"):
        validate_adoption_scenarios_config(config)


def test_blocked_committed_local_scenarios_cannot_allocate() -> None:
    config = load_adoption_scenarios_config(Path("configs/scenarios.yaml"))

    with pytest.raises(ValueError, match="blocked until Q-7"):
        adoption_node_allocations(config)


def test_unapproved_allocation_status_cannot_allocate() -> None:
    config = _adoption_config()
    config["allocation"]["status"] = "proposed"

    with pytest.raises(ValueError, match="A-014 is approved"):
        adoption_node_allocations(config)


def test_adoption_config_rejects_duplicate_scenario_keys_and_noninteger_counts() -> None:
    config = _adoption_config()
    config["local_grid_scenarios"]["scenarios"].append(
        dict(config["local_grid_scenarios"]["scenarios"][0])
    )

    with pytest.raises(ValueError, match="keys must be unique"):
        validate_adoption_scenarios_config(config)

    config = _adoption_config()
    config["local_grid_scenarios"]["scenarios"][0]["home_charge_points"] = 11.2
    with pytest.raises(ValueError, match="true integer"):
        validate_adoption_scenarios_config(config)


def test_adoption_config_rejects_bad_node_weights() -> None:
    config = _adoption_config()
    config["allocation"]["node_weights"][1]["node_id"] = "load_a"
    with pytest.raises(ValueError, match="unique"):
        validate_adoption_scenarios_config(config)

    config = _adoption_config()
    config["allocation"]["node_weights"][1]["weight"] = float("nan")
    with pytest.raises(ValueError, match="finite and non-negative"):
        validate_adoption_scenarios_config(config)


def test_allocate_charge_points_conserves_integer_counts_deterministically() -> None:
    weights = (("load_b", 1.0), ("load_a", 1.0), ("load_c", 1.0))

    first = allocate_charge_points_to_nodes(5, weights)
    second = allocate_charge_points_to_nodes(5, tuple(reversed(weights)))

    assert first == second
    assert first == {"load_a": 2, "load_b": 2, "load_c": 1}
    assert sum(first.values()) == 5
    assert all(isinstance(value, int) and value >= 0 for value in first.values())


def test_allocate_charge_points_validates_inputs_directly() -> None:
    with pytest.raises(ValueError, match="true integer"):
        allocate_charge_points_to_nodes(1.2, (("load_a", 1.0),))
    with pytest.raises(ValueError, match="non-negative integer"):
        allocate_charge_points_to_nodes(-1, (("load_a", 1.0),))
    with pytest.raises(ValueError, match="unique non-empty"):
        allocate_charge_points_to_nodes(2, (("load_a", 1.0), ("load_a", 2.0)))
    with pytest.raises(ValueError, match="finite non-negative"):
        allocate_charge_points_to_nodes(2, (("load_a", float("nan")),))
    with pytest.raises(ValueError, match="positive"):
        allocate_charge_points_to_nodes(2, (("load_a", 0.0),))


def test_adoption_node_allocations_conserve_home_and_public_counts() -> None:
    allocations = adoption_node_allocations(_adoption_config())

    assert allocations[0].total_home_charge_points == 11
    assert allocations[0].total_public_charge_points == 5
    assert allocations[0].home_by_node == {"load_a": 6, "load_b": 3, "load_c": 2}


def test_charge_point_ranges_report_totals_and_per_node_kr() -> None:
    config = _adoption_config()
    scenarios = adoption_scenarios(config)
    allocations = adoption_node_allocations(config)

    assert charge_point_range_by_year(scenarios) == {
        2030: {
            "home_min": 11,
            "home_max": 17,
            "public_min": 5,
            "public_max": 9,
        }
    }
    assert node_charge_point_ranges(allocations)["load_a"] == {
        "home_min": 6,
        "home_max": 9,
        "public_min": 3,
        "public_max": 4,
    }
