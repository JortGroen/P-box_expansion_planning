from __future__ import annotations

from datetime import UTC, datetime, timedelta
import gzip
import inspect
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

import src.ev_model as ev_model
from src.ev_model import (
    EV_CALENDAR_MAPPING_RULE_ID,
    EV_HOME_COMPONENT,
    EV_PUBLIC_COMPONENT,
    EVProfileBootstrapSampler,
    EVProfileLibrary,
    EXPECTED_FULL_YEAR_STEPS,
    a014_node_weights_from_load_table,
    adoption_node_allocations,
    adoption_scenarios,
    allocate_charge_points_to_nodes,
    allocate_public_charge_points_by_capacity_class,
    public_set_b_capacity_allocation_readiness_artifact,
    public_set_b_capacity_class_totals,
    apply_ev_cal001_ordinal_mapping,
    build_ev_integration_readiness_artifact,
    canonical_ev_planning_calendar_2035,
    charge_point_range_by_year,
    distinct_member_count,
    ev_candidate_checksum_expectations,
    ev_candidate_member_selection_manifest,
    ev_candidate_member_selection_manifest_set,
    ev_ic1_adapter_guardrail_packet,
    ev_downstream_adequacy_criterion_packet,
    ev005_within_realization_replacement_policy_packet,
    ev_ic1_candidate_adapter_artifact,
    ev_ic1_candidate_member_reference_artifact,
    ev_library_integration_artifact_from_manifest,
    ev_member_selection_implementation_plan,
    ev_planning_calendar_mapping_expectation,
    load_adoption_scenarios_config,
    load_ev_integration_readiness_record,
    load_processed_batch_npz,
    national_outlook_projections,
    node_charge_point_ranges,
    parse_elaad_profile_response,
    proposed_a014_allocation_preview,
    proposed_local_charge_point_counts,
    save_processed_batch_npz,
    validate_adoption_scenarios_config,
    verify_ev_candidate_checksums,
    write_ev_integration_readiness_artifact,
)
from src.rng import SeedTree


def _git_blob_sha256(path: Path) -> str:
    # The committed JSON artifact is checked out with platform-dependent line endings.
    # Hash the Git blob so provenance stays stable between Windows worktrees and CI.
    blob = subprocess.check_output(["git", "show", f"HEAD:{path.as_posix()}"])
    import hashlib

    return hashlib.sha256(blob).hexdigest()


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


def test_ev_cal001_canonical_target_calendar_is_complete_2035() -> None:
    datetimes_utc, datetimes_local = canonical_ev_planning_calendar_2035()

    assert len(datetimes_utc) == EXPECTED_FULL_YEAR_STEPS
    assert len(datetimes_local) == EXPECTED_FULL_YEAR_STEPS
    assert datetimes_local[0].isoformat() == "2035-01-01T00:00:00+01:00"
    assert datetimes_utc[0].isoformat() == "2034-12-31T23:00:00+00:00"
    assert all(
        later - earlier == timedelta(minutes=15)
        for earlier, later in zip(datetimes_utc, datetimes_utc[1:])
    )


def test_ev_cal001_ordinal_mapping_preserves_members_demands_and_provenance() -> None:
    batch = parse_elaad_profile_response(_payload(n_profiles=2), batch_seed=140001, expected_n_profiles=2)

    mapped = apply_ev_cal001_ordinal_mapping(
        batch,
        component_id=EV_HOME_COMPONENT,
        library_id="A_home_vancar_cp_y2030",
        processed_path="data/processed/elaad_profiles/candidate.npz",
        processed_sha256_file="a" * 64,
    )

    assert mapped.member_ids == batch.member_ids
    assert mapped.batch_seed == batch.batch_seed
    assert mapped.n_timesteps == EXPECTED_FULL_YEAR_STEPS
    assert mapped.n_profiles == 2
    np.testing.assert_array_equal(mapped.demands_kw, batch.demands_kw)
    assert mapped.source_datetimes_utc == batch.datetimes_utc
    assert mapped.target_datetimes_local[0].year == 2035
    assert mapped.mapping_provenance["calendar_mapping_rule_id"] == EV_CALENDAR_MAPPING_RULE_ID
    assert mapped.mapping_provenance["source_timestamp_index_policy"] == (
        "target_index_i_uses_source_index_i"
    )
    assert mapped.mapping_provenance["unmapped_or_repeated_source_timestep_count"] == 0
    assert mapped.mapping_provenance["weekday_weekend_preserved"] is False
    assert mapped.mapping_provenance["annual_energy_preserved"] is True
    assert mapped.mapping_provenance["held_out_access"] is False
    assert mapped.mapping_provenance["m_sufficiency_claimed"] is False
    assert mapped.demands_kw is not batch.demands_kw


def test_ev_cal001_ordinal_mapping_rejects_non_candidate_and_incomplete_batches() -> None:
    batch = parse_elaad_profile_response(_payload(n_profiles=1), batch_seed=140001, expected_n_profiles=1)

    with pytest.raises(ValueError, match="candidate batches only"):
        apply_ev_cal001_ordinal_mapping(
            batch,
            component_id=EV_HOME_COMPONENT,
            library_id="A_home_vancar_cp_y2030",
            processed_path="data/processed/elaad_profiles/held_out.npz",
            processed_sha256_file="a" * 64,
            partition="held_out",
        )

    incomplete = ev_model.ElaadProfileBatch(
        member_ids=batch.member_ids,
        datetimes_utc=batch.datetimes_utc[:-1],
        datetimes_local=batch.datetimes_local[:-1],
        demands_kw=batch.demands_kw[:-1, :],
        batch_seed=batch.batch_seed,
        response_config={},
    )
    with pytest.raises(ValueError, match="complete 35,040-step"):
        apply_ev_cal001_ordinal_mapping(
            incomplete,
            component_id=EV_HOME_COMPONENT,
            library_id="A_home_vancar_cp_y2030",
            processed_path="data/processed/elaad_profiles/candidate.npz",
            processed_sha256_file="a" * 64,
        )


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


def _library_manifest(
    *,
    candidate_seeds: tuple[int, ...],
    held_out_seed: int = 190001,
    component_prefix: str = "A_home",
) -> dict:
    batches = [
        {
            "partition": "candidate",
            "seed": seed,
            "n_profiles": 100,
            "n_timesteps": EXPECTED_FULL_YEAR_STEPS,
            "processed_path": f"data/processed/elaad_profiles/{component_prefix}_{seed}.npz",
            "processed_sha256_file": f"{seed:064x}"[-64:],
            "manifest_path": f"data/metadata/elaad_profiles/{component_prefix}_{seed}_manifest.json",
            "distinct_member_count": 100,
            "request_sha256": f"{seed + 1:064x}"[-64:],
        }
        for seed in candidate_seeds
    ]
    batches.append(
        {
            "partition": "held_out",
            "seed": held_out_seed,
            "n_profiles": 100,
            "n_timesteps": EXPECTED_FULL_YEAR_STEPS,
            "processed_path": f"data/processed/elaad_profiles/{component_prefix}_{held_out_seed}.npz",
            "processed_sha256_file": f"{held_out_seed:064x}"[-64:],
            "manifest_path": f"data/metadata/elaad_profiles/{component_prefix}_{held_out_seed}_manifest.json",
            "distinct_member_count": 100,
            "request_sha256": f"{held_out_seed + 1:064x}"[-64:],
        }
    )
    return {
        "data_id": "D-002",
        "candidate_member_count": 100 * len(candidate_seeds),
        "held_out_member_count": 100,
        "held_out_unopened_for_adequacy": True,
        "library_adequacy_proven": False,
        "policy": {
            "decisions": ["EV-003", "EV-005"],
            "m_sufficiency_claimed": False,
        },
        "batches": batches,
    }


def test_ev_integration_library_artifact_filters_candidate_batches_without_profile_access(tmp_path: Path) -> None:
    manifest_path = tmp_path / "library_manifest.json"
    manifest_path.write_text(
        json.dumps(_library_manifest(candidate_seeds=(140001, 140101))),
        encoding="utf-8",
    )

    artifact = ev_library_integration_artifact_from_manifest(
        manifest_path,
        library_id="A_home_vancar_cp_y2030",
        component_id=EV_HOME_COMPONENT,
        expected_candidate_members=200,
    )
    record = artifact.manifest_record()

    assert artifact.candidate_seeds == (140001, 140101)
    assert record["candidate_member_count"] == 200
    assert record["held_out_member_count"] == 100
    assert record["held_out_unopened_for_adequacy"] is True
    assert record["library_adequacy_proven"] is False
    assert record["sampling_policy"]["source_profile_files_opened"] is False  # type: ignore[index]
    assert record["candidate_batches"][0]["member_id_pattern"] == "profile_140001_<returned_profile_index:03d>"  # type: ignore[index]


def test_ev_integration_library_artifact_rejects_bad_held_out_and_m_claims(tmp_path: Path) -> None:
    manifest = _library_manifest(candidate_seeds=(140001,))
    manifest["held_out_unopened_for_adequacy"] = False
    manifest_path = tmp_path / "bad_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="held-out batches"):
        ev_library_integration_artifact_from_manifest(
            manifest_path,
            library_id="A_home_vancar_cp_y2030",
            component_id=EV_HOME_COMPONENT,
            expected_candidate_members=100,
        )

    manifest = _library_manifest(candidate_seeds=(140001,))
    manifest["library_adequacy_proven"] = True
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="certify library adequacy"):
        ev_library_integration_artifact_from_manifest(
            manifest_path,
            library_id="A_home_vancar_cp_y2030",
            component_id=EV_HOME_COMPONENT,
            expected_candidate_members=100,
        )


def test_ev_integration_readiness_artifact_combines_libraries_and_allocations(tmp_path: Path) -> None:
    home_manifest = tmp_path / "home_manifest.json"
    public_manifest = tmp_path / "public_manifest.json"
    home_manifest.write_text(
        json.dumps(_library_manifest(candidate_seeds=(140001,), component_prefix="A_home")),
        encoding="utf-8",
    )
    public_manifest.write_text(
        json.dumps(_library_manifest(candidate_seeds=(152001,), component_prefix="B_public")),
        encoding="utf-8",
    )
    config_path = tmp_path / "scenarios.json"
    config_path.write_text(json.dumps(_adoption_config()), encoding="utf-8")

    artifact = build_ev_integration_readiness_artifact(
        home_manifest_path=home_manifest,
        public_manifest_path=public_manifest,
        scenario_config_path=config_path,
        expected_home_candidate_members=100,
        expected_public_candidate_members=100,
    )
    record = artifact.manifest_record()

    assert {library["component_id"] for library in record["libraries"]} == {
        EV_HOME_COMPONENT,
        EV_PUBLIC_COMPONENT,
    }
    assert record["scenario_totals"] == {
        "low": {"home": 11, "public": 5},
        "high": {"home": 17, "public": 9},
    }
    assert record["calendar_mapping"]["planning_year"] == 2035
    assert record["policy"]["held_out_access"] is False
    assert record["policy"]["integrated_analysis_performed"] is False

    out_path = tmp_path / "readiness.json"
    write_ev_integration_readiness_artifact(artifact, out_path)
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["artifact_type"] == "ev_to_ic1_integration_readiness"
    assert written["policy"]["m_sufficiency_claimed"] is False


def test_committed_ev_integration_readiness_artifact_exposes_candidate_libraries_only() -> None:
    artifact = json.loads(
        Path("data/metadata/ev_adoption/e2_s2_ev_integration_readiness.json").read_text(
            encoding="utf-8"
        )
    )

    assert artifact["artifact_type"] == "ev_to_ic1_integration_readiness"
    assert artifact["schema_version"] == 1
    assert artifact["policy"]["held_out_access"] is False
    assert artifact["policy"]["candidate_profiles_opened"] is False
    assert artifact["policy"]["integrated_analysis_performed"] is False
    assert artifact["policy"]["m_sufficiency_claimed"] is False
    assert artifact["scenario_totals"] == {
        "low": {"home": 7992, "public": 4183},
        "middle": {"home": 9386, "public": 5127},
        "high": {"home": 10343, "public": 6138},
    }

    by_component = {library["component_id"]: library for library in artifact["libraries"]}
    assert by_component[EV_HOME_COMPONENT]["candidate_member_count"] == 1000
    assert by_component[EV_PUBLIC_COMPONENT]["candidate_member_count"] == 1200
    assert by_component[EV_HOME_COMPONENT]["held_out_unopened_for_adequacy"] is True
    assert by_component[EV_PUBLIC_COMPONENT]["held_out_unopened_for_adequacy"] is True
    assert by_component[EV_HOME_COMPONENT]["library_adequacy_proven"] is False
    assert by_component[EV_PUBLIC_COMPONENT]["library_adequacy_proven"] is False
    assert {batch["seed"] for batch in by_component[EV_HOME_COMPONENT]["candidate_batches"]} == {
        140001,
        140101,
        140201,
        140301,
        140401,
        140501,
        140601,
        140701,
        140801,
        140901,
    }
    assert len(artifact["node_allocations"]) == 3
    assert all(len(item["home_by_node"]) == 115 for item in artifact["node_allocations"])
    assert all(len(item["public_by_node"]) == 115 for item in artifact["node_allocations"])


def test_ev_candidate_checksum_verification_uses_candidate_processed_files_only(
    tmp_path: Path,
) -> None:
    payload = b"synthetic candidate bytes"
    processed_path = tmp_path / "data" / "processed" / "elaad_profiles" / "candidate.npz"
    processed_path.parent.mkdir(parents=True)
    processed_path.write_bytes(payload)
    digest = ev_model._sha256_file(processed_path)
    readiness = {
        "schema_version": 1,
        "artifact_type": "ev_to_ic1_integration_readiness",
        "policy": {
            "held_out_access": False,
            "candidate_profiles_opened": False,
            "integrated_analysis_performed": False,
            "m_sufficiency_claimed": False,
        },
        "calendar_mapping": {
            "profile_generator_calendar_local_year": 2025,
            "planning_year": 2035,
            "n_timesteps": EXPECTED_FULL_YEAR_STEPS,
            "step_seconds": 900,
            "timezone": "Europe/Amsterdam",
            "planning_year_mapping_status": (
                "deterministic_calendar_mapping_required_before_ic1_results"
            ),
        },
        "libraries": [
            {
                "library_id": "synthetic_home",
                "component_id": EV_HOME_COMPONENT,
                "candidate_member_count": 100,
                "candidate_batches": [
                    {
                        "seed": 140001,
                        "processed_path": processed_path.relative_to(tmp_path).as_posix(),
                        "processed_sha256_file": digest,
                        "n_profiles": 100,
                        "n_timesteps": EXPECTED_FULL_YEAR_STEPS,
                        "capacity_class": None,
                        "cp_capacity_kw": 11,
                    }
                ],
            }
        ],
    }

    expectations = ev_candidate_checksum_expectations(readiness)
    verifications = verify_ev_candidate_checksums(readiness, base_dir=tmp_path)

    assert len(expectations) == 1
    assert verifications[0].observed_sha256 == digest
    assert verifications[0].byte_size == len(payload)
    assert verifications[0].manifest_record()["checksum_verified"] is True


def test_ev_candidate_checksum_guardrail_rejects_held_out_paths() -> None:
    readiness = {
        "libraries": [
            {
                "library_id": "synthetic_home",
                "component_id": EV_HOME_COMPONENT,
                "candidate_batches": [
                    {
                        "seed": 141201,
                        "processed_path": "data/processed/elaad_profiles/held_out_141201.npz",
                        "processed_sha256_file": "a" * 64,
                        "n_profiles": 100,
                        "n_timesteps": EXPECTED_FULL_YEAR_STEPS,
                    }
                ],
            }
        ]
    }

    with pytest.raises(ValueError, match="candidate processed files only"):
        ev_candidate_checksum_expectations(readiness)


def test_ev_planning_calendar_mapping_guardrail_requires_2035_mapping() -> None:
    readiness = {
        "calendar_mapping": {
            "profile_generator_calendar_local_year": 2025,
            "planning_year": 2035,
            "n_timesteps": EXPECTED_FULL_YEAR_STEPS,
            "step_seconds": 900,
            "timezone": "Europe/Amsterdam",
            "planning_year_mapping_status": (
                "deterministic_calendar_mapping_required_before_ic1_results"
            ),
        }
    }

    expectation = ev_planning_calendar_mapping_expectation(readiness)

    assert expectation.source_calendar_local_year == 2025
    assert expectation.target_planning_year == 2035
    assert expectation.profile_loading_allowed_before_mapping is False

    readiness["calendar_mapping"]["planning_year"] = 2033
    with pytest.raises(ValueError, match="2035 planning year"):
        ev_planning_calendar_mapping_expectation(readiness)


def test_committed_ev_readiness_guardrail_packet_blocks_ic1_result_claims() -> None:
    artifact = load_ev_integration_readiness_record(
        Path("data/metadata/ev_adoption/e2_s2_ev_integration_readiness.json")
    )

    packet = ev_ic1_adapter_guardrail_packet(artifact)
    committed_packet = json.loads(
        Path("data/metadata/ev_adoption/e2_s2_ev_ic1_adapter_guardrails.json").read_text(
            encoding="utf-8"
        )
    )

    assert committed_packet == packet
    assert packet["candidate_checksum_expectation_count"] == 22
    assert packet["candidate_checksum_expectations_by_component"] == {
        EV_HOME_COMPONENT: 10,
        EV_PUBLIC_COMPONENT: 12,
    }
    assert packet["candidate_member_count_by_component"] == {
        EV_HOME_COMPONENT: 1000,
        EV_PUBLIC_COMPONENT: 1200,
    }
    assert packet["calendar_mapping_expectation"]["target_planning_year"] == 2035
    assert packet["policy"]["held_out_access"] is False
    assert packet["policy"]["profile_arrays_opened"] is False
    assert packet["policy"]["integrated_analysis_performed"] is False
    assert packet["policy"]["m_sufficiency_claimed"] is False
    assert any("Q-5" in blocker for blocker in packet["ic1_use_blockers"])



def test_ev_downstream_adequacy_criterion_packet_is_unsigned_and_downstream() -> None:
    packet = ev_downstream_adequacy_criterion_packet()
    committed = json.loads(
        Path("data/metadata/ev_adoption/e3_s2a_ev_adequacy_criterion_packet.json").read_text(
            encoding="utf-8"
        )
    )

    assert committed == packet
    assert packet["artifact_type"] == "ev_downstream_adequacy_criterion_packet"
    assert packet["status"] == "pi_decision_required_before_held_out_use"
    assert packet["recommended_option_id"] == "A_decision_stability_plus_event_probability_band"
    assert {option["id"] for option in packet["options"]} == {
        "A_decision_stability_plus_event_probability_band",
        "B_loading_quantile_diagnostic_plus_decision_check",
        "C_component_profile_tail_only",
    }
    by_option = {option["id"]: option for option in packet["options"]}
    assert by_option["A_decision_stability_plus_event_probability_band"]["status"] == "recommended_unsigned"
    assert by_option["C_component_profile_tail_only"]["allowed_role"] == "source_quality_diagnostic_only"
    assert "ALEA-002" in packet["governing_decisions"]
    assert "EV-005 within-realization replacement policy or no-replacement rule is signed for the tested cohort sizes" in packet[
        "preconditions_before_any_held_out_opening"
    ]
    assert packet["non_claims"] == {
        "criterion_signed": False,
        "held_out_access": False,
        "profile_arrays_loaded": False,
        "integrated_analysis_performed": False,
        "event_or_p_e_analysis_performed": False,
        "m_sufficiency_claimed": False,
        "manuscript_numbers_produced": False,
    }


def test_ev005_replacement_policy_packet_records_approval_and_profile_free_boundary() -> None:
    packet = ev005_within_realization_replacement_policy_packet()
    committed = json.loads(
        Path("data/metadata/ev_adoption/e2_s2_ev005_replacement_policy_packet.json").read_text(
            encoding="utf-8"
        )
    )

    assert committed == packet
    assert packet["artifact_type"] == "ev005_within_realization_replacement_policy_packet"
    assert packet["decision_id"] == "EV-005B"
    assert packet["status"] == "approved_for_candidate_member_selection_only"
    assert packet["recommended_option_id"] == "A_charge_point_level_with_replacement"
    assert packet["feasibility_findings"]["whole_grid_no_replacement_feasible_for_home"] is False
    assert packet["feasibility_findings"]["whole_grid_no_replacement_feasible_for_public_capacity_classes"] is False
    assert packet["candidate_library_context"]["candidate_library_sufficiency_claimed"] is False
    assert packet["non_claims"] == {
        "policy_signed": True,
        "held_out_access": False,
        "profile_arrays_loaded": False,
        "integrated_analysis_performed": False,
        "event_or_p_e_analysis_performed": False,
        "m_sufficiency_claimed": False,
        "manuscript_numbers_produced": False,
    }


def test_ev005_replacement_packet_options_keep_bootstrap_and_m_separate() -> None:
    packet = ev005_within_realization_replacement_policy_packet()
    by_option = {option["id"]: option for option in packet["options"]}

    recommended = by_option["A_charge_point_level_with_replacement"]
    assert recommended["status"] == "approved_ev005b_policy"
    assert recommended["replacement"] is True
    assert "finite-library adequacy separate" in recommended["why_defensible"]
    assert "candidate member-selection implementation only" in recommended["pi_approval"]
    assert by_option["B_whole_grid_without_replacement"]["status"] == (
        "not_executable_for_approved_2035_counts"
    )
    assert by_option["C_node_local_without_replacement_with_cross_node_reuse"]["status"] == (
        "unsigned_alternative_not_recommended"
    )
    expectations = packet["implementation_expectations_after_approval"]
    assert any("RNG-001 ComponentStream" in item for item in expectations)
    assert any("held-out and quarantined partitions remain inaccessible" in item for item in expectations)
    source = inspect.getsource(ev005_within_realization_replacement_policy_packet)
    assert "load_processed_batch_npz" not in source
    assert "np.load" not in source


def _synthetic_candidate_member_reference(n_home_members: int = 3) -> dict[str, object]:
    return {
        "artifact_type": "ev_ic1_candidate_member_reference",
        "policy": {
            "candidate_libraries_only": True,
            "held_out_access": False,
            "profile_arrays_loaded": False,
            "integrated_analysis_performed": False,
            "event_or_p_e_analysis_performed": False,
            "m_sufficiency_claimed": False,
        },
        "candidate_members": [
            {
                "partition": "candidate",
                "component_id": EV_HOME_COMPONENT,
                "library_id": "A_home_vancar_cp_y2030",
                "source_member_id": f"profile_140001_{index:03d}",
                "batch_seed": 140001,
                "returned_profile_index": index,
                "capacity_class": None,
                "cp_capacity_kw": 11,
                "processed_path": "data/processed/elaad_profiles/A_home_140001.npz",
                "candidate_processed_sha256_file": "a" * 64,
                "calendar_mapping_rule_id": EV_CALENDAR_MAPPING_RULE_ID,
                "calendar_mapping_rule_version": "ordinal-v1",
                "source_calendar_id": "elaad-2025-europe-amsterdam-15min",
                "target_calendar_id": "planning-2035-europe-amsterdam-15min",
                "source_timestamp_index_policy": "target_index_i_uses_source_index_i",
                "n_timesteps": EXPECTED_FULL_YEAR_STEPS,
                "weekday_weekend_preserved": False,
                "control_mode": "uncontrolled",
            }
            for index in range(n_home_members)
        ],
    }


def _approved_ev005b_decisions_text() -> str:
    return (
        "| ID | Date | Gate/topic | Decision | Rationale | Evidence | Status | PI sign-off |\n"
        "| EV-005B | 2026-07-22 | Within-realization EV replacement policy | "
        "Approved: test fixture only. | synthetic | synthetic | approved | PI approved in test fixture |\n"
    )


def test_ev_candidate_member_selection_uses_signed_ev005b_decision() -> None:
    stream = SeedTree(root_seed=20260722).component_stream(0, EV_HOME_COMPONENT)
    decisions = Path("registers/DECISIONS.md").read_text(encoding="utf-8")

    manifest = ev_candidate_member_selection_manifest(
        _synthetic_candidate_member_reference(),
        decisions_text=decisions,
        scenario="middle",
        node_id="load_001",
        component_id=EV_HOME_COMPONENT,
        required_members=2,
        component_stream=stream,
    )

    assert manifest["decision_id"] == "EV-005B"
    assert manifest["replacement_enabled"] is True
    assert len(manifest["selections"]) == 2
    assert all(row["component_stream_id"] == stream.stream_id for row in manifest["selections"])
    assert all(row["candidate_processed_sha256_file"] == "a" * 64 for row in manifest["selections"])
    assert manifest["policy"]["held_out_access"] is False
    assert manifest["policy"]["profile_arrays_loaded"] is False
    assert manifest["policy"]["m_sufficiency_claimed"] is False


def test_ev_candidate_member_selection_rejects_unsafe_metadata_before_approval() -> None:
    stream = SeedTree(root_seed=20260722).component_stream(0, EV_HOME_COMPONENT)
    artifact = _synthetic_candidate_member_reference()
    artifact["candidate_members"][0]["partition"] = "held_out"

    with pytest.raises(ValueError, match="non-candidate partitions"):
        ev_candidate_member_selection_manifest(
            artifact,
            decisions_text=Path("registers/DECISIONS.md").read_text(encoding="utf-8"),
            scenario="middle",
            node_id="load_001",
            component_id=EV_HOME_COMPONENT,
            required_members=2,
            component_stream=stream,
        )


def test_ev_candidate_member_selection_supports_public_capacity_class_metadata() -> None:
    artifact = _synthetic_candidate_member_reference(n_home_members=1)
    public_row = dict(artifact["candidate_members"][0])
    public_row.update(
        {
            "component_id": EV_PUBLIC_COMPONENT,
            "library_id": "B_public_vancar_cp_y2030_equal_mix",
            "source_member_id": "profile_152001_000",
            "batch_seed": 152001,
            "capacity_class": "public_11kw",
            "cp_capacity_kw": 11,
            "processed_path": "data/processed/elaad_profiles/B_public_11kw_152001.npz",
            "candidate_processed_sha256_file": "b" * 64,
        }
    )
    artifact["candidate_members"] = [public_row]
    stream = SeedTree(root_seed=20260722).component_stream(7, EV_PUBLIC_COMPONENT)

    manifest = ev_candidate_member_selection_manifest(
        artifact,
        decisions_text=Path("registers/DECISIONS.md").read_text(encoding="utf-8"),
        scenario="high",
        node_id="load_014",
        component_id=EV_PUBLIC_COMPONENT,
        capacity_class="public_11kw",
        cp_capacity_kw=11,
        required_members=2,
        component_stream=stream,
    )

    assert manifest["component_id"] == EV_PUBLIC_COMPONENT
    assert manifest["capacity_class"] == "public_11kw"
    assert manifest["candidate_pool_member_count"] == 1
    assert len(manifest["selections"]) == 2
    assert {row["source_member_id"] for row in manifest["selections"]} == {"profile_152001_000"}
    assert all(row["component_stream_id"] == stream.stream_id for row in manifest["selections"])
    assert all(row["candidate_processed_sha256_file"] == "b" * 64 for row in manifest["selections"])


def test_ev_candidate_member_selection_rejects_bad_stream_and_provenance() -> None:
    artifact = _synthetic_candidate_member_reference()
    wrong_stream = SeedTree(root_seed=20260722).component_stream(0, EV_PUBLIC_COMPONENT)

    with pytest.raises(ValueError, match="matching RNG-001 component stream"):
        ev_candidate_member_selection_manifest(
            artifact,
            decisions_text=Path("registers/DECISIONS.md").read_text(encoding="utf-8"),
            scenario="middle",
            node_id="load_001",
            component_id=EV_HOME_COMPONENT,
            required_members=1,
            component_stream=wrong_stream,
        )

    bad = _synthetic_candidate_member_reference()
    bad["candidate_members"][0]["candidate_processed_sha256_file"] = "not-a-sha"
    stream = SeedTree(root_seed=20260722).component_stream(0, EV_HOME_COMPONENT)
    with pytest.raises(ValueError, match="candidate_processed_sha256_file"):
        ev_candidate_member_selection_manifest(
            bad,
            decisions_text=Path("registers/DECISIONS.md").read_text(encoding="utf-8"),
            scenario="middle",
            node_id="load_001",
            component_id=EV_HOME_COMPONENT,
            required_members=1,
            component_stream=stream,
        )

    bad = _synthetic_candidate_member_reference()
    bad["candidate_members"][0]["calendar_mapping_rule_version"] = "old"
    with pytest.raises(ValueError, match="rule-version provenance"):
        ev_candidate_member_selection_manifest(
            bad,
            decisions_text=Path("registers/DECISIONS.md").read_text(encoding="utf-8"),
            scenario="middle",
            node_id="load_001",
            component_id=EV_HOME_COMPONENT,
            required_members=1,
            component_stream=stream,
        )

def test_ev_candidate_member_selection_records_synthetic_duplicate_manifest_fields() -> None:
    stream = SeedTree(root_seed=20260722).component_stream(3, EV_HOME_COMPONENT)

    manifest = ev_candidate_member_selection_manifest(
        _synthetic_candidate_member_reference(n_home_members=1),
        decisions_text=_approved_ev005b_decisions_text(),
        scenario="middle",
        node_id="load_001",
        component_id=EV_HOME_COMPONENT,
        required_members=3,
        component_stream=stream,
    )

    assert manifest["artifact_type"] == "ev_candidate_member_selection_manifest"
    assert manifest["replacement_enabled"] is True
    assert manifest["policy"] == {
        "candidate_only": True,
        "held_out_access": False,
        "profile_arrays_loaded": False,
        "integrated_analysis_performed": False,
        "event_or_p_e_analysis_performed": False,
        "m_sufficiency_claimed": False,
    }
    assert manifest["component_stream"]["stream_id"] == stream.stream_id
    assert len(manifest["selections"]) == 3
    assert manifest["duplicate_member_groups"] == [
        {
            "source_member_id": "profile_140001_000",
            "duplicate_multiplicity": 3,
            "duplicate_selection_indices": [0, 1, 2],
        }
    ]
    for selection in manifest["selections"]:
        assert selection["duplicate_within_realization"] is True
        assert selection["duplicate_multiplicity"] == 3
        assert selection["component_stream_id"] == stream.stream_id
        assert selection["selection_pool_index"] == 0
        assert selection["library_id"] == "A_home_vancar_cp_y2030"
        assert selection["partition"] == "candidate"
        assert selection["control_mode"] == "uncontrolled"
        assert selection["candidate_processed_sha256_file"] == "a" * 64
        assert selection["calendar_mapping_rule_version"] == "ordinal-v1"
        assert selection["source_calendar_id"] == "elaad-2025-europe-amsterdam-15min"
        assert selection["target_calendar_id"] == "planning-2035-europe-amsterdam-15min"
        assert selection["n_timesteps"] == EXPECTED_FULL_YEAR_STEPS
        assert selection["weekday_weekend_preserved"] is False
    source = inspect.getsource(ev_candidate_member_selection_manifest)
    assert "load_processed_batch_npz" not in source
    assert "np.load" not in source


def test_ev_member_selection_implementation_plan_records_ev005b_approval_boundary() -> None:
    plan = ev_member_selection_implementation_plan()
    committed = json.loads(
        Path("data/metadata/ev_adoption/e2_s2_ev_member_selection_implementation_plan.json").read_text(
            encoding="utf-8"
        )
    )

    assert committed == plan
    assert plan["artifact_type"] == "ev_member_selection_implementation_plan"
    assert plan["status"] == "ev005b_approved_candidate_member_selection_ready"
    assert plan["approved_decision"] == "EV-005B"
    assert plan["implementation_authorization"]["candidate_member_selection_allowed"] is True
    assert plan["implementation_authorization"]["profile_array_loading_allowed"] is False
    assert "EV-005B status is approved" in plan["preimplementation_checks"][0]
    assert set(plan["blocked_actions_after_ev005b_approval"]) == {
        "profile_array_loading",
        "held_out_or_quarantined_partition_access",
        "integrated_net_load_or_event_analysis",
        "m_sufficiency_claim",
        "manuscript_number_generation",
    }
    assert plan["non_claims"] == {
        "ev005b_approved": True,
        "production_member_draws_performed_in_this_plan": False,
        "held_out_access": False,
        "profile_arrays_loaded": False,
        "integrated_analysis_performed": False,
        "event_or_p_e_analysis_performed": False,
        "m_sufficiency_claimed": False,
        "manuscript_numbers_produced": False,
    }


def test_ev_member_selection_plan_records_rng_and_duplicate_manifest_fields() -> None:
    plan = ev_member_selection_implementation_plan()

    manifest_fields = set(plan["manifest_fields"])
    assert {
        "component_stream_id",
        "component_seed",
        "source_member_id",
        "batch_seed",
        "returned_profile_index",
        "duplicate_within_realization",
        "duplicate_multiplicity",
        "replacement_policy_id",
    } <= manifest_fields
    assert plan["duplicate_member_logging"]["required"] is True
    assert "bootstrap multiplicities" in plan["duplicate_member_logging"]["interpretation"]
    assert plan["rng001_stream_usage"]["construct_streams_in_calling_context"] is True
    assert plan["rng001_stream_usage"]["do_not_accept_raw_integer_seed_in_sampler"] is True
    assert plan["rng001_stream_usage"]["home_component_stream"] == EV_HOME_COMPONENT
    assert plan["rng001_stream_usage"]["public_component_stream"] == EV_PUBLIC_COMPONENT
    source = inspect.getsource(ev_member_selection_implementation_plan)
    assert "sample_member_indices" not in source
    assert "select_members" not in source
    assert "load_processed_batch_npz" not in source
    assert "np.load" not in source

def test_ev_ic1_candidate_adapter_artifact_materializes_allocations_and_members(
    tmp_path: Path,
) -> None:
    home_manifest = tmp_path / "home_manifest.json"
    public_manifest = tmp_path / "public_manifest.json"
    home_manifest.write_text(
        json.dumps(_library_manifest(candidate_seeds=(140001,), component_prefix="A_home")),
        encoding="utf-8",
    )
    public_manifest.write_text(
        json.dumps(_library_manifest(candidate_seeds=(152001,), component_prefix="B_public")),
        encoding="utf-8",
    )
    config_path = tmp_path / "scenarios.json"
    config_path.write_text(json.dumps(_adoption_config()), encoding="utf-8")
    readiness = build_ev_integration_readiness_artifact(
        home_manifest_path=home_manifest,
        public_manifest_path=public_manifest,
        scenario_config_path=config_path,
        expected_home_candidate_members=100,
        expected_public_candidate_members=100,
    ).manifest_record()

    artifact = ev_ic1_candidate_adapter_artifact(readiness)

    assert artifact["artifact_type"] == "ev_to_ic1_candidate_adapter_artifact"
    assert artifact["scenario_totals"] == {
        "high": {"home": 17, "public": 9},
        "low": {"home": 11, "public": 5},
    }
    assert artifact["checksum_preconditions"]["verification_status"] == (
        "verification_required_before_loading"
    )
    assert artifact["checksum_preconditions"]["profile_arrays_loaded"] is False
    assert artifact["calendar_mapping_decision"]["status"] == "approved"
    assert artifact["policy"]["held_out_access"] is False
    libraries = {item["component_id"]: item for item in artifact["candidate_libraries"]}
    assert libraries[EV_HOME_COMPONENT]["candidate_batches"][0]["member_id_pattern"] == (
        "profile_140001_<returned_profile_index:03d>"
    )
    assert libraries[EV_HOME_COMPONENT]["candidate_batches"][0]["returned_profile_index_range"] == [
        0,
        99,
    ]
    assert libraries[EV_PUBLIC_COMPONENT]["candidate_batches"][0]["checksum_verification"] == {
        "checksum_verified": False,
        "verification_required_before_loading": True,
    }


def test_ev_ic1_candidate_adapter_artifact_records_complete_checksum_verification(
    tmp_path: Path,
) -> None:
    artifact = load_ev_integration_readiness_record(
        Path("data/metadata/ev_adoption/e2_s2_ev_integration_readiness.json")
    )
    expectations = ev_candidate_checksum_expectations(artifact)
    verifications = []
    for expectation in expectations:
        payload = f"{expectation.component_id}-{expectation.seed}".encode("utf-8")
        path = tmp_path / expectation.processed_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        corrected = ev_model.EVCandidateChecksumExpectation(
            component_id=expectation.component_id,
            library_id=expectation.library_id,
            seed=expectation.seed,
            processed_path=expectation.processed_path,
            expected_sha256=ev_model._sha256_file(path),
            n_profiles=expectation.n_profiles,
            n_timesteps=expectation.n_timesteps,
            capacity_class=expectation.capacity_class,
            cp_capacity_kw=expectation.cp_capacity_kw,
        )
        verifications.append(
            ev_model.EVCandidateChecksumVerification(
                expectation=corrected,
                observed_sha256=corrected.expected_sha256,
                byte_size=len(payload),
            )
        )
    adjusted = json.loads(json.dumps(artifact))
    by_key = {
        (item.expectation.component_id, item.expectation.library_id, item.expectation.seed): item
        for item in verifications
    }
    for library in adjusted["libraries"]:
        for batch in library["candidate_batches"]:
            key = (library["component_id"], library["library_id"], batch["seed"])
            batch["processed_sha256_file"] = by_key[key].expectation.expected_sha256

    candidate_artifact = ev_ic1_candidate_adapter_artifact(
        adjusted,
        checksum_verifications=tuple(verifications),
        verification_timestamp_utc="2026-07-22T08:45:00Z",
    )

    assert candidate_artifact["checksum_preconditions"]["verification_status"] == (
        "verified_in_agent_c_worktree"
    )
    assert candidate_artifact["checksum_preconditions"]["verification_timestamp_utc"] == (
        "2026-07-22T08:45:00Z"
    )
    assert candidate_artifact["checksum_preconditions"][
        "verification_required_in_consuming_worktree_before_profile_loading"
    ] is True
    assert all(
        batch["checksum_verification"]["checksum_verified"]
        for library in candidate_artifact["candidate_libraries"]
        for batch in library["candidate_batches"]
    )


def test_ev_ic1_candidate_adapter_artifact_rejects_partial_verification() -> None:
    artifact = load_ev_integration_readiness_record(
        Path("data/metadata/ev_adoption/e2_s2_ev_integration_readiness.json")
    )
    first = ev_candidate_checksum_expectations(artifact)[0]
    verification = ev_model.EVCandidateChecksumVerification(
        expectation=first,
        observed_sha256=first.expected_sha256,
        byte_size=10,
    )

    with pytest.raises(ValueError, match="cover every candidate batch"):
        ev_ic1_candidate_adapter_artifact(artifact, checksum_verifications=(verification,))


def test_committed_ev_ic1_candidate_adapter_artifact_is_candidate_only() -> None:
    artifact = json.loads(
        Path("data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_adapter_artifact.json").read_text(
            encoding="utf-8"
        )
    )

    assert artifact["artifact_type"] == "ev_to_ic1_candidate_adapter_artifact"
    assert artifact["scenario_totals"] == {
        "high": {"home": 10343, "public": 6138},
        "low": {"home": 7992, "public": 4183},
        "middle": {"home": 9386, "public": 5127},
    }
    assert artifact["checksum_preconditions"]["candidate_processed_file_count"] == 22
    assert artifact["checksum_preconditions"]["verification_status"] == (
        "verified_in_agent_c_worktree"
    )
    assert artifact["checksum_preconditions"]["profile_arrays_loaded"] is False
    assert artifact["calendar_mapping_decision"]["status"] == "approved"
    assert artifact["policy"]["held_out_access"] is False
    assert artifact["policy"]["m_sufficiency_claimed"] is False
    assert len(artifact["node_allocations"]) == 3
    assert all(item["node_count"] == 115 for item in artifact["node_allocations"])
    libraries = {item["component_id"]: item for item in artifact["candidate_libraries"]}
    assert libraries[EV_HOME_COMPONENT]["candidate_member_count"] == 1000
    assert libraries[EV_PUBLIC_COMPONENT]["candidate_member_count"] == 1200
    assert libraries[EV_HOME_COMPONENT]["candidate_batch_count"] == 10
    assert libraries[EV_PUBLIC_COMPONENT]["candidate_batch_count"] == 12
    assert all(
        batch["checksum_verification"]["checksum_verified"]
        for library in artifact["candidate_libraries"]
        for batch in library["candidate_batches"]
    )
    assert all(
        "held_out" not in batch["processed_path"]
        for library in artifact["candidate_libraries"]
        for batch in library["candidate_batches"]
    )



def test_ev_ic1_candidate_member_reference_expands_synthetic_batches(tmp_path: Path) -> None:
    home_manifest = tmp_path / "home_manifest.json"
    public_manifest = tmp_path / "public_manifest.json"
    home_manifest.write_text(
        json.dumps(_library_manifest(candidate_seeds=(140001,), component_prefix="A_home")),
        encoding="utf-8",
    )
    public_manifest.write_text(
        json.dumps(_library_manifest(candidate_seeds=(152001,), component_prefix="B_public")),
        encoding="utf-8",
    )
    config_path = tmp_path / "scenarios.json"
    config_path.write_text(json.dumps(_adoption_config()), encoding="utf-8")
    readiness = build_ev_integration_readiness_artifact(
        home_manifest_path=home_manifest,
        public_manifest_path=public_manifest,
        scenario_config_path=config_path,
        expected_home_candidate_members=100,
        expected_public_candidate_members=100,
    ).manifest_record()
    adjusted = ev_ic1_candidate_adapter_artifact(readiness)
    for library in adjusted["candidate_libraries"]:
        for batch in library["candidate_batches"]:
            if library["component_id"] == EV_PUBLIC_COMPONENT:
                batch["capacity_class"] = "public_11kw"
                batch["cp_capacity_kw"] = 11
            batch["checksum_verification"] = {
                "checksum_verified": True,
                "observed_sha256": batch["processed_sha256_file"],
                "expected_sha256": batch["processed_sha256_file"],
                "byte_size": 10,
            }

    reference = ev_ic1_candidate_member_reference_artifact(adjusted)

    assert reference["artifact_type"] == "ev_ic1_candidate_member_reference"
    assert reference["candidate_member_count_by_component"] == {
        EV_HOME_COMPONENT: 100,
        EV_PUBLIC_COMPONENT: 100,
    }
    assert len(reference["candidate_members"]) == 200
    first_home = next(
        row for row in reference["candidate_members"] if row["component_id"] == EV_HOME_COMPONENT
    )
    assert first_home["source_member_id"] == "profile_140001_000"
    assert first_home["returned_profile_index"] == 0
    assert first_home["calendar_mapping_rule_id"] == "EV-CAL-001"
    assert first_home["weekday_weekend_preserved"] is False
    assert len(reference["scenario_node_requirements"]) == 6
    assert reference["selection_boundary"] == {
        "replacement_policy_id": "EV-005B",
        "replacement_rule_chosen": True,
        "replacement_policy_scope": "candidate_member_selection_only",
        "component_stream_required": True,
        "sample_rows_materialized_in_reference": False,
        "candidate_selection_manifest_set": "data/metadata/ev_adoption/e2_s2_ev005b_candidate_selection_manifests.json.gz",
        "realization_selection_performed": False,
    }
    assert reference["policy"]["profile_arrays_loaded"] is False
    assert reference["policy"]["m_sufficiency_claimed"] is False



def test_ev_candidate_member_selection_manifest_set_materializes_declared_branches() -> None:
    reference = json.loads(
        Path("data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_member_reference.json").read_text(
            encoding="utf-8"
        )
    )
    decisions = Path("registers/DECISIONS.md").read_text(encoding="utf-8")

    artifact = ev_candidate_member_selection_manifest_set(
        reference,
        decisions_text=decisions,
        root_seed=20260722,
        sample_index=0,
        materialized_timestamp_utc="2026-07-22T17:45:00Z",
        source_candidate_member_reference_sha256="0" * 64,
    )

    assert artifact["artifact_type"] == "ev_candidate_member_selection_manifest_set"
    assert artifact["decision_id"] == "EV-005B"
    assert artifact["root_seed"] == 20260722
    assert artifact["sample_index"] == 0
    assert artifact["source_candidate_member_reference_sha256"] == "0" * 64
    assert artifact["policy"] == {
        "candidate_only": True,
        "replacement_policy_id": "EV-005B",
        "replacement_enabled": True,
        "held_out_access": False,
        "quarantined_access": False,
        "profile_arrays_loaded": False,
        "integrated_analysis_performed": False,
        "event_or_p_e_analysis_performed": False,
        "capacity_screen_performed": False,
        "manuscript_numbers_produced": False,
        "m_sufficiency_claimed": False,
    }
    assert artifact["calendar_mapping"] == {
        "status": "approved",
        "rule_id": EV_CALENDAR_MAPPING_RULE_ID,
        "rule_version": "ordinal-v1",
        "source_calendar_id": "elaad-2025-europe-amsterdam-15min",
        "target_calendar_id": "planning-2035-europe-amsterdam-15min",
        "source_timestamp_index_policy": "target_index_i_uses_source_index_i",
        "n_timesteps": EXPECTED_FULL_YEAR_STEPS,
        "weekday_weekend_preserved": False,
    }
    totals = {
        item["scenario"]: {
            "home": item["home_required_members"],
            "public": item["public_required_members"],
            "public_by_capacity": item["public_required_members_by_capacity_class"],
        }
        for item in artifact["scenarios"]
    }
    assert totals == {
        "high": {
            "home": 10343,
            "public": 6138,
            "public_by_capacity": {
                "public_11kw": 1535,
                "public_13kw": 1535,
                "public_15kw": 1534,
                "public_22kw": 1534,
            },
        },
        "low": {
            "home": 7992,
            "public": 4183,
            "public_by_capacity": {
                "public_11kw": 1046,
                "public_13kw": 1046,
                "public_15kw": 1046,
                "public_22kw": 1045,
            },
        },
        "middle": {
            "home": 9386,
            "public": 5127,
            "public_by_capacity": {
                "public_11kw": 1282,
                "public_13kw": 1282,
                "public_15kw": 1282,
                "public_22kw": 1281,
            },
        },
    }
    for scenario in artifact["scenarios"]:
        node_selection_count = sum(
            len(node["selections"])
            for node in scenario["node_manifests"]
        )
        assert node_selection_count == scenario["home_required_members"] + scenario["public_required_members"]
        assert scenario["component_streams"][EV_HOME_COMPONENT]["component"] == EV_HOME_COMPONENT
        assert scenario["component_streams"][EV_PUBLIC_COMPONENT]["component"] == EV_PUBLIC_COMPONENT
        for node in scenario["node_manifests"]:
            assert len(node["selections"]) == node["home_required_members"] + node["public_required_members"]
            for selection in node["selections"]:
                assert selection["partition"] == "candidate"
                assert selection["candidate_processed_path"].startswith("data/processed/elaad_profiles/")
                assert "held_out" not in selection["candidate_processed_path"]
                assert "quarantined" not in selection["candidate_processed_path"]
    assert any(item["duplicate_source_member_count"] > 0 for item in artifact["duplicate_summary"])
    source = inspect.getsource(ev_candidate_member_selection_manifest_set)
    assert "load_processed_batch_npz" not in source
    assert "np.load" not in source



def test_committed_ev_candidate_member_selection_manifest_set_records_fast_provenance() -> None:
    reference_path = Path("data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_member_reference.json")
    selection_path = Path("data/metadata/ev_adoption/e2_s2_ev005b_candidate_selection_manifests.json.gz")
    reference_sha = _git_blob_sha256(reference_path)
    compressed = selection_path.read_bytes()
    committed = json.loads(gzip.decompress(compressed))

    assert compressed[4:8] == b"\x00\x00\x00\x00"
    assert committed["schema_version"] == 1
    assert committed["artifact_type"] == "ev_candidate_member_selection_manifest_set"
    assert committed["decision_id"] == "EV-005B"
    assert committed["source_candidate_member_reference"] == str(reference_path).replace("\\", "/")
    assert committed["source_candidate_member_reference_sha256"] == reference_sha
    assert committed["seed_tree"]["protocol_id"] == "RNG-001"
    assert committed["calendar_mapping"] == {
        "status": "approved",
        "rule_id": EV_CALENDAR_MAPPING_RULE_ID,
        "rule_version": "ordinal-v1",
        "source_calendar_id": "elaad-2025-europe-amsterdam-15min",
        "target_calendar_id": "planning-2035-europe-amsterdam-15min",
        "source_timestamp_index_policy": "target_index_i_uses_source_index_i",
        "n_timesteps": EXPECTED_FULL_YEAR_STEPS,
        "weekday_weekend_preserved": False,
    }
    assert committed["policy"] == {
        "candidate_only": True,
        "replacement_policy_id": "EV-005B",
        "replacement_enabled": True,
        "held_out_access": False,
        "quarantined_access": False,
        "profile_arrays_loaded": False,
        "integrated_analysis_performed": False,
        "event_or_p_e_analysis_performed": False,
        "capacity_screen_performed": False,
        "manuscript_numbers_produced": False,
        "m_sufficiency_claimed": False,
    }
    totals = {
        item["scenario"]: (item["home_required_members"], item["public_required_members"])
        for item in committed["scenarios"]
    }
    assert totals == {"high": (10343, 6138), "low": (7992, 4183), "middle": (9386, 5127)}
    assert committed["scenario_count"] == 3
    first_node = committed["scenarios"][0]["node_manifests"][0]
    assert first_node["scenario"] == "high"
    assert first_node["node_id"] == "load_000"
    assert first_node["home_required_members"] == 111
    assert first_node["public_required_members"] == 66
    first_selection = first_node["selections"][0]
    assert first_selection == {
        "batch_seed": 140401,
        "candidate_processed_path": "data/processed/elaad_profiles/A_home_vancar_cp_y2030_batchseed140401_n100.npz",
        "candidate_processed_sha256_file": "ec00d29fdbcec28a78620d688bfb583ec73265f23a29272883ae7036957645a1",
        "capacity_class": None,
        "component_id": EV_HOME_COMPONENT,
        "control_mode": "uncontrolled",
        "cp_capacity_kw": None,
        "duplicate_multiplicity": 15,
        "duplicate_within_realization": True,
        "library_id": "A_home_vancar_cp_y2030",
        "node_id": "load_000",
        "partition": "candidate",
        "realization_selection_index": 0,
        "returned_profile_index": 70,
        "selection_count_at_node": 111,
        "selection_index": 0,
        "selection_pool_index": 470,
        "source_member_id": "profile_140401_070",
    }
    assert committed["duplicate_summary"][0] == {
        "capacity_class": None,
        "component_id": EV_HOME_COMPONENT,
        "duplicate_source_member_count": 1000,
        "max_duplicate_multiplicity": 23,
        "scenario": "high",
        "selected_count": 10343,
        "unique_source_member_count": 1000,
    }

def test_ev_candidate_member_selection_manifest_set_is_deterministic_and_guarded() -> None:
    reference = json.loads(
        Path("data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_member_reference.json").read_text(
            encoding="utf-8"
        )
    )
    decisions = Path("registers/DECISIONS.md").read_text(encoding="utf-8")

    first = ev_candidate_member_selection_manifest_set(
        reference,
        decisions_text=decisions,
        root_seed=20260722,
        sample_index=1,
        scenarios=["low"],
        materialized_timestamp_utc="2026-07-22T17:45:00Z",
    )
    repeated = ev_candidate_member_selection_manifest_set(
        reference,
        decisions_text=decisions,
        root_seed=20260722,
        sample_index=1,
        scenarios=["low"],
        materialized_timestamp_utc="2026-07-22T17:45:00Z",
    )
    different_sample = ev_candidate_member_selection_manifest_set(
        reference,
        decisions_text=decisions,
        root_seed=20260722,
        sample_index=2,
        scenarios=["low"],
        materialized_timestamp_utc="2026-07-22T17:45:00Z",
    )

    assert repeated == first
    first_rows = first["scenarios"][0]["node_manifests"][0]["selections"][:10]
    different_rows = different_sample["scenarios"][0]["node_manifests"][0]["selections"][:10]
    assert [row["source_member_id"] for row in first_rows] != [row["source_member_id"] for row in different_rows]
    assert first["scenarios"][0]["component_streams"] != different_sample["scenarios"][0]["component_streams"]

    with pytest.raises(PermissionError, match="EV-005B remains unapproved"):
        ev_candidate_member_selection_manifest_set(
            reference,
            decisions_text="| EV-005B | 2026-07-22 | x | x | x | x | proposed | -- |",
            root_seed=20260722,
            sample_index=1,
            scenarios=["low"],
            materialized_timestamp_utc="2026-07-22T17:45:00Z",
        )
    unsafe = json.loads(json.dumps(reference))
    unsafe["scenario_node_requirements"][0]["public_required_members_by_capacity_class"]["public_11kw"] += 1
    with pytest.raises(ValueError, match="conserve node public total"):
        ev_candidate_member_selection_manifest_set(
            unsafe,
            decisions_text=decisions,
            root_seed=20260722,
            sample_index=1,
            scenarios=["high"],
            materialized_timestamp_utc="2026-07-22T17:45:00Z",
        )


@pytest.mark.slow
def test_committed_ev005b_candidate_selection_manifest_set_matches_builder() -> None:
    reference = json.loads(
        Path("data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_member_reference.json").read_text(
            encoding="utf-8"
        )
    )
    decisions = Path("registers/DECISIONS.md").read_text(encoding="utf-8")
    reference_sha = _git_blob_sha256(Path("data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_member_reference.json"))
    expected = ev_candidate_member_selection_manifest_set(
        reference,
        decisions_text=decisions,
        root_seed=20260722,
        sample_index=0,
        materialized_timestamp_utc="2026-07-22T17:45:00Z",
        source_candidate_member_reference_sha256=reference_sha,
    )
    committed_path = Path("data/metadata/ev_adoption/e2_s2_ev005b_candidate_selection_manifests.json.gz")
    committed = json.loads(gzip.decompress(committed_path.read_bytes()).decode("utf-8"))

    assert committed == expected
def test_committed_ev_ic1_candidate_member_reference_is_candidate_only() -> None:
    adapter = json.loads(
        Path("data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_adapter_artifact.json").read_text(
            encoding="utf-8"
        )
    )
    public_capacity = json.loads(
        Path("data/metadata/ev_adoption/e2_s2_public_set_b_capacity_allocation_readiness.json").read_text(
            encoding="utf-8"
        )
    )
    reference = ev_ic1_candidate_member_reference_artifact(
        adapter,
        public_capacity_artifact=public_capacity,
    )
    committed = json.loads(
        Path("data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_member_reference.json").read_text(
            encoding="utf-8"
        )
    )

    assert committed == reference
    assert reference["candidate_member_count_by_component"] == {
        EV_HOME_COMPONENT: 1000,
        EV_PUBLIC_COMPONENT: 1200,
    }
    assert reference["public_candidate_member_count_by_capacity_class"] == {
        "public_11kw": 300,
        "public_13kw": 300,
        "public_15kw": 300,
        "public_22kw": 300,
    }
    assert len(reference["candidate_members"]) == 2200
    assert len(reference["scenario_node_requirements"]) == 345
    assert len({
        (row["component_id"], row["library_id"], row["source_member_id"])
        for row in reference["candidate_members"]
    }) == 2200
    assert any(
        row["component_id"] == EV_HOME_COMPONENT
        and row["source_member_id"] == "profile_140001_000"
        for row in reference["candidate_members"]
    )
    assert any(
        row["component_id"] == EV_PUBLIC_COMPONENT
        and row["capacity_class"] == "public_22kw"
        and row["source_member_id"] == "profile_153101_099"
        for row in reference["candidate_members"]
    )
    assert all(row["partition"] == "candidate" for row in reference["candidate_members"])
    assert all(row["n_timesteps"] == EXPECTED_FULL_YEAR_STEPS for row in reference["candidate_members"])
    assert reference["calendar_mapping"] == {
        "status": "approved",
        "rule_id": "EV-CAL-001",
        "rule_version": "ordinal-v1",
        "source_calendar_id": "elaad-2025-europe-amsterdam-15min",
        "target_calendar_id": "planning-2035-europe-amsterdam-15min",
        "source_timestamp_index_policy": "target_index_i_uses_source_index_i",
        "n_timesteps": EXPECTED_FULL_YEAR_STEPS,
        "weekday_weekend_preserved": False,
    }
    assert reference["policy"] == {
        "candidate_libraries_only": True,
        "held_out_access": False,
        "profile_arrays_loaded": False,
        "integrated_analysis_performed": False,
        "event_or_p_e_analysis_performed": False,
        "m_sufficiency_claimed": False,
    }
    for requirement in reference["scenario_node_requirements"]:
        by_class = requirement["public_required_members_by_capacity_class"]
        assert by_class is not None
        assert sum(by_class.values()) == requirement["public_required_members"]
        assert requirement["source_type"] == "required_member_counts_not_realization_draws"


def test_ev_ic1_candidate_member_reference_rejects_unsafe_inputs() -> None:
    adapter = json.loads(
        Path("data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_adapter_artifact.json").read_text(
            encoding="utf-8"
        )
    )
    adapter["policy"]["held_out_access"] = True
    with pytest.raises(ValueError, match="held-out"):
        ev_ic1_candidate_member_reference_artifact(adapter)

    adapter = json.loads(
        Path("data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_adapter_artifact.json").read_text(
            encoding="utf-8"
        )
    )
    adapter["candidate_libraries"][0]["candidate_batches"][0]["checksum_verification"] = {
        "checksum_verified": False
    }
    with pytest.raises(ValueError, match="verified candidate checksums"):
        ev_ic1_candidate_member_reference_artifact(adapter)

    adapter = json.loads(
        Path("data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_adapter_artifact.json").read_text(
            encoding="utf-8"
        )
    )
    public_capacity = json.loads(
        Path("data/metadata/ev_adoption/e2_s2_public_set_b_capacity_allocation_readiness.json").read_text(
            encoding="utf-8"
        )
    )
    public_capacity["scenario_allocations"][0]["public_by_node_by_capacity_class"]["load_000"]["public_11kw"] += 1
    with pytest.raises(ValueError, match="conserve node public totals"):
        ev_ic1_candidate_member_reference_artifact(
            adapter,
            public_capacity_artifact=public_capacity,
        )

def test_committed_ev_calendar_mapping_decision_route_records_approved_option_a() -> None:
    route = json.loads(
        Path("data/metadata/ev_adoption/e2_s2_ev_calendar_mapping_decision_route.json").read_text(
            encoding="utf-8"
        )
    )

    assert route["artifact_type"] == "ev_calendar_mapping_decision_route"
    assert route["decision_id"] == "EV-CAL-001"
    assert route["implementation_authorized"] is True
    assert route["approved_option"] == "A"
    assert route["approved_rule"]["id"] == "EV-CAL-001"
    assert route["approved_rule"]["source_timestamp_index_policy"] == (
        "target_index_i_uses_source_index_i"
    )
    assert route["approved_rule"]["weekday_weekend_preserved"] is False
    assert route["source_calendar"] == {
        "calendar_id": "elaad-2025-europe-amsterdam-15min",
        "n_timesteps": EXPECTED_FULL_YEAR_STEPS,
        "timezone": "Europe/Amsterdam",
        "year": 2025,
    }
    assert route["target_calendar"] == {
        "calendar_id": "planning-2035-europe-amsterdam-15min",
        "n_timesteps": EXPECTED_FULL_YEAR_STEPS,
        "timezone": "Europe/Amsterdam",
        "year": 2035,
    }
    assert {option["id"] for option in route["options"]} == {"A", "B", "C", "D"}
    by_option = {option["id"]: option for option in route["options"]}
    assert by_option["A"]["pi_signed"] is True
    assert all(by_option[key]["pi_signed"] is False for key in ("B", "C", "D"))
    assert route["non_claims"] == {
        "event_or_p_e_analysis_performed": False,
        "held_out_access": False,
        "m_sufficiency_claimed": False,
        "manuscript_numbers_produced": False,
        "profile_arrays_loaded": False,
    }
    required_provenance = set(route["provenance_fields_required"])
    assert {
        "component_id",
        "library_id",
        "source_member_id",
        "batch_seed",
        "returned_profile_index",
        "candidate_processed_sha256_file",
        "component_stream_id",
        "calendar_mapping_rule_id",
        "source_calendar_id",
        "target_calendar_id",
        "dst_policy",
        "holiday_policy",
    } <= required_provenance
    assert {
        "source_calendar_validation",
        "target_calendar_validation",
        "deterministic_mapping_table_generation",
        "unsigned_mapping_rule_rejection",
        "held_out_or_quarantined_partition_rejection",
    } <= set(route["tests_required_before_implementation"])

def test_ev_calendar_mapping_decision_packet_records_approved_readiness_boundary() -> None:
    packet = Path("reports/e2_s2_ev_calendar_mapping_decision_packet.md").read_text(
        encoding="utf-8"
    )

    assert "Status: Approved as EV-CAL-001 Option A" in packet
    assert "Option A: Ordinal Timestep Mapping" in packet
    assert "Option B: Weekday-Class Calendar Mapping" in packet
    assert "Option C: Source-Year Computational Calendar" in packet
    assert "Option D: Weather-Year Matched Calendar" in packet
    assert "EV-CAL-001 Option A is approved for candidate/readiness mapping code" in packet
    assert "estimate `P(E)`" in packet

def test_committed_ev_cal001_decision_and_methods_are_signed() -> None:
    decisions = Path("registers/DECISIONS.md").read_text(encoding="utf-8")
    methods = Path("paper/methods_decisions_and_assumptions.md").read_text(encoding="utf-8")

    assert "| EV-CAL-001 | 2026-07-22 | EV source-to-planning calendar mapping |" in decisions
    assert "Approved Option A: map complete 2025 ElaadNL EV source profiles" in decisions
    assert "PI approved Option A in chat, 2026-07-22" in decisions
    assert "<!-- methods-id: EV-CAL-001 -->" in methods
    assert "target timestep" in methods and "source timestep `i`" in methods
    assert "weekday_weekend_preserved = false" in methods


def test_committed_candidate_adapter_artifact_references_approved_ev_cal001() -> None:
    artifact = json.loads(
        Path("data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_adapter_artifact.json").read_text(
            encoding="utf-8"
        )
    )

    decision = artifact["calendar_mapping_decision"]
    assert decision["status"] == "approved"
    assert decision["approved_rule_id"] == "EV-CAL-001"
    assert decision["approved_rule_version"] == "ordinal-v1"
    assert decision["approved_option"] == "A_ordinal_timestep_mapping"
    assert decision["expectation"]["mapping_status"] == (
        "approved_ordinal_timestep_mapping_before_ic1_results"
    )

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
        "local_count_workflow": {
            "status": "proposed_not_pi_signed",
            "option": "EV-007 Option A",
            "selected_cluster": {
                "area_type": "municipalities",
                "area_identifier": "GM0361",
                "selection_status": "proposed_not_pi_signed",
            },
            "metadata": {
                "path": "data/metadata/ev_adoption/example.json",
                "sha256": "b" * 64,
            },
            "neighborhood_filter_attempt": {
                "query": "/filters/municipalities/neighborhoods/GM0361",
                "result": "failed_http_500",
            },
            "proposed_2035_counts": [
                {
                    "year": 2035,
                    "scenario": scenario,
                    "location": location,
                    "value": float(value),
                    "rounded_count": value,
                    "status": "proposed_not_pi_signed",
                    "provenance": {
                        "source_id": "D-010",
                        "source_type": "local_outlook_cluster",
                        "area_type": "municipalities",
                        "area_identifier": "GM0361",
                        "query": (
                            "/charging_infrastructure?area_type=municipalities"
                            f"&area_identifier=GM0361&scenario={scenario}&location={location}"
                        ),
                        "response_sha256": "c" * 64,
                    },
                }
                for scenario, home_value, public_value in (
                    ("low", 8, 1),
                    ("middle", 9, 2),
                    ("high", 10, 3),
                )
                for location, value in (("home", home_value), ("public", public_value))
            ],
        },
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
                        "home_charge_points": "EV-007-local-home",
                        "public_charge_points": "EV-007-local-public",
                    },
                },
                {
                    "year": 2030,
                    "scenario": "high",
                    "home_charge_points": 17,
                    "public_charge_points": 9,
                    "provenance": {
                        "source_type": "local_grid",
                        "home_charge_points": "EV-007-local-home",
                        "public_charge_points": "EV-007-local-public",
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



def test_d010_minimal_evidence_matches_approved_local_counts() -> None:
    evidence = json.loads(
        Path("data/metadata/ev_adoption/d010_elaad_outlook_minimal_evidence.json").read_text(
            encoding="utf-8"
        )
    )
    source_metadata = json.loads(
        Path("data/metadata/ev_adoption/e2_s6_local_adoption_counts_metadata.json").read_text(
            encoding="utf-8"
        )
    )

    assert evidence["data_id"] == "D-010"
    assert evidence["artifact_type"] == "d010_elaad_outlook_minimal_evidence"
    assert evidence["status"] == "source-approved-for-ev007a-local-counts"
    assert evidence["approved_scope"] == {
        "decision_id": "EV-007A",
        "area_type": "municipalities",
        "area_identifier": "GM0361",
        "area_name": "Alkmaar",
        "planning_year": 2035,
        "selected_month": 12,
        "scenarios": ["low", "middle", "high"],
        "locations": ["home", "public"],
        "rounding_rule": source_metadata["rounding_rule"],
        "national_totals_policy": "National D-010 Outlook projections remain context/provenance only and must not be used directly as SimBench physical counts.",
    }
    assert evidence["schema_evidence"]["selected_row_fields"] == [
        "year",
        "month",
        "scenario",
        "location",
        "variant",
        "number",
    ]
    assert evidence["schema_evidence"]["raw_payload_identity"].startswith("Each approved query")
    assert evidence["non_actions"] == [
        "No new API request was made for this evidence freeze.",
        "No raw API response was committed.",
        "No EV profile generation, held-out access, net-load integration, event analysis, P(E), capacity screen, or manuscript number was produced.",
    ]
    expected_counts = {
        f"{row['scenario']}_{row['location']}": row
        for row in source_metadata["local_2035_charge_point_counts"]
    }
    assert set(evidence["approved_local_counts"]) == set(expected_counts)
    for key, row in expected_counts.items():
        frozen = evidence["approved_local_counts"][key]
        assert frozen["query"] == row["query"]
        assert frozen["retrieved_utc"] == row["retrieved_utc"]
        assert frozen["response_sha256"] == row["response_sha256"]
        assert frozen["row_count"] == 26
        assert frozen["selected_row_filter"] == {
            "year": 2035,
            "month": 12,
            "scenario": row["scenario"],
            "location": row["location"],
            "variant": row["variant"],
        }
        assert frozen["api_number"] == row["value"]
        assert frozen["rounded_count"] == row["rounded_count"]


def test_committed_adoption_scenarios_config_validates() -> None:
    config = load_adoption_scenarios_config(Path("configs/scenarios.yaml"))
    national = national_outlook_projections(config)
    proposed_local = proposed_local_charge_point_counts(config)
    scenarios = adoption_scenarios(config)
    import hashlib

    metadata = config["local_count_workflow"]["metadata"]
    metadata_path = Path(metadata["path"])
    metadata_text = metadata_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    metadata_sha256 = hashlib.sha256(metadata_text.encode("utf-8")).hexdigest()

    assert len(national) == 18
    assert len(proposed_local) == 6
    assert metadata_sha256 == metadata["sha256"]
    assert {item.location for item in proposed_local} == {"home", "public"}
    assert {item.status for item in proposed_local} == {"proposed_not_pi_signed"}
    assert all(item.area_identifier == "GM0361" for item in proposed_local)
    assert any(item.scenario == "middle" and item.location == "home" and item.rounded_count == 9386 for item in proposed_local)
    assert config["local_grid_scenarios"]["status"] == "approved"
    assert config["allocation"]["status"] == "approved"
    assert len(config["allocation"]["node_weights"]) == 115
    assert [(item.scenario, item.home_charge_points, item.public_charge_points) for item in scenarios] == [
        ("low", 7992, 4183),
        ("middle", 9386, 5127),
        ("high", 10343, 6138),
    ]
    assert charge_point_range_by_year(scenarios)[2035] == {
        "home_min": 7992,
        "home_max": 10343,
        "public_min": 4183,
        "public_max": 6138,
    }


def test_adoption_config_accepts_approved_status() -> None:
    config = _adoption_config()
    config["allocation"]["status"] = "approved"
    config["local_grid_scenarios"]["status"] = "approved"

    validate_adoption_scenarios_config(config)


def test_local_scenarios_reject_counts_until_status_approved() -> None:
    for status in ("blocked", "proposed", "pending_local_cluster_selection"):
        config = _adoption_config()
        config["local_grid_scenarios"]["status"] = status

        with pytest.raises(ValueError, match="only after local totals are approved"):
            validate_adoption_scenarios_config(config)


def test_adoption_scenarios_rejects_unapproved_empty_local_status() -> None:
    config = _adoption_config()
    config["local_grid_scenarios"]["status"] = "pending_local_cluster_selection"
    config["local_grid_scenarios"]["scenarios"] = []

    with pytest.raises(ValueError, match="require EV-007 local totals"):
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


def test_proposed_local_counts_are_not_executable_adoption_scenarios() -> None:
    config = _adoption_config()
    config["local_grid_scenarios"]["status"] = "blocked"
    config["local_grid_scenarios"]["scenarios"] = []

    proposed = proposed_local_charge_point_counts(config)

    assert [item.rounded_count for item in proposed if item.location == "home"] == [8, 9, 10]
    with pytest.raises(ValueError, match="require EV-007 local totals"):
        adoption_scenarios(config)


def test_proposed_local_count_workflow_rejects_country_queries_and_bad_status() -> None:
    config = _adoption_config()
    config["local_count_workflow"]["proposed_2035_counts"][0]["provenance"]["query"] = (
        "/charging_infrastructure?area_type=country&scenario=low&location=home"
    )
    with pytest.raises(ValueError, match="National Outlook projections cannot be used"):
        validate_adoption_scenarios_config(config)

    config = _adoption_config()
    config["local_count_workflow"]["status"] = "approved"
    with pytest.raises(ValueError, match="proposed_not_pi_signed"):
        validate_adoption_scenarios_config(config)


def test_committed_local_scenarios_materialize_a014_node_weights() -> None:
    config = load_adoption_scenarios_config(Path("configs/scenarios.yaml"))
    allocations = adoption_node_allocations(config)

    assert len(adoption_scenarios(config)) == 3
    assert len(allocations) == 3
    assert [item.scenario for item in allocations] == ["low", "middle", "high"]
    assert all(len(item.home_by_node) == 115 for item in allocations)
    assert all(len(item.public_by_node) == 115 for item in allocations)
    assert {
        item.scenario: (item.total_home_charge_points, item.total_public_charge_points)
        for item in allocations
    } == {
        "low": (7992, 4183),
        "middle": (9386, 5127),
        "high": (10343, 6138),
    }


def test_unapproved_allocation_status_cannot_allocate() -> None:
    config = _adoption_config()
    config["allocation"]["status"] = "proposed"

    with pytest.raises(ValueError, match="approved A-014 allocation"):
        adoption_node_allocations(config)


def test_approved_allocation_requires_materialized_node_weights() -> None:
    config = _adoption_config()
    config["allocation"]["status"] = "approved"
    del config["allocation"]["node_weights"]
    config["allocation"]["node_weight_source"] = {"method_id": "A-014"}

    with pytest.raises(ValueError, match="requires explicit node_weights"):
        validate_adoption_scenarios_config(config)


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


def test_public_set_b_capacity_class_totals_use_ev008a_largest_remainder() -> None:
    assert public_set_b_capacity_class_totals(5) == {
        "public_11kw": 2,
        "public_13kw": 1,
        "public_15kw": 1,
        "public_22kw": 1,
    }
    assert public_set_b_capacity_class_totals(8) == {
        "public_11kw": 2,
        "public_13kw": 2,
        "public_15kw": 2,
        "public_22kw": 2,
    }


def test_public_set_b_capacity_allocation_conserves_node_and_class_totals() -> None:
    public_by_node = {"load_b": 3, "load_a": 5}

    allocation = allocate_public_charge_points_by_capacity_class(public_by_node)

    assert list(allocation) == ["load_a", "load_b"]
    assert {node_id: sum(row.values()) for node_id, row in allocation.items()} == {
        "load_a": 5,
        "load_b": 3,
    }
    assert {
        capacity_class: sum(row[capacity_class] for row in allocation.values())
        for capacity_class in ("public_11kw", "public_13kw", "public_15kw", "public_22kw")
    } == public_set_b_capacity_class_totals(8)
    assert allocate_public_charge_points_by_capacity_class(public_by_node) == allocation


def test_public_set_b_capacity_allocation_validates_inputs_directly() -> None:
    with pytest.raises(ValueError, match="true integer"):
        allocate_public_charge_points_by_capacity_class({"load_a": 1.2})
    with pytest.raises(ValueError, match="non-negative"):
        allocate_public_charge_points_by_capacity_class({"load_a": -1})
    with pytest.raises(ValueError, match="non-empty"):
        allocate_public_charge_points_by_capacity_class({})
    with pytest.raises(ValueError, match="unique"):
        allocate_public_charge_points_by_capacity_class(
            {"load_a": 1},
            capacity_mix=(("public_11kw", 11, 0.5), ("public_11kw", 13, 0.5)),
        )


def test_public_set_b_readiness_artifact_from_committed_candidate_adapter() -> None:
    adapter = json.loads(
        Path("data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_adapter_artifact.json").read_text(
            encoding="utf-8"
        )
    )
    artifact = public_set_b_capacity_allocation_readiness_artifact(adapter)
    committed = json.loads(
        Path("data/metadata/ev_adoption/e2_s2_public_set_b_capacity_allocation_readiness.json").read_text(
            encoding="utf-8"
        )
    )

    assert committed == artifact
    assert artifact["artifact_type"] == "ev_public_set_b_capacity_allocation_readiness"
    assert artifact["decision_id"] == "EV-008A"
    assert artifact["library_id"] == "B_public_vancar_cp_y2030_equal_mix"
    assert artifact["policy"] == {
        "candidate_libraries_only": True,
        "held_out_access": False,
        "profile_arrays_loaded": False,
        "integrated_analysis_performed": False,
        "event_or_p_e_analysis_performed": False,
        "m_sufficiency_claimed": False,
        "public_smart_profiles_included": False,
        "dc_or_fast_charging_included": False,
    }
    assert set(artifact["scenario_totals"]) == {"low", "middle", "high"}
    expected_public = {"low": 4183, "middle": 5127, "high": 6138}
    for scenario_record in artifact["scenario_allocations"]:
        scenario = scenario_record["scenario"]
        by_node = scenario_record["public_by_node"]
        by_class = scenario_record["public_by_node_by_capacity_class"]
        class_totals = scenario_record["capacity_class_totals"]

        assert scenario_record["node_count"] == 115
        assert scenario_record["public_charge_points"] == expected_public[scenario]
        assert sum(by_node.values()) == expected_public[scenario]
        assert sum(class_totals.values()) == expected_public[scenario]
        assert class_totals == public_set_b_capacity_class_totals(expected_public[scenario])
        assert set(by_node) == set(by_class)
        for node_id, node_total in by_node.items():
            assert sum(by_class[node_id].values()) == node_total
    classes = artifact["candidate_library"]["capacity_classes"]
    assert {record["cp_capacity_kw"] for record in classes.values()} == {11, 13, 15, 22}
    assert {record["candidate_member_count"] for record in classes.values()} == {300}


def test_public_set_b_readiness_rejects_held_out_or_wrong_library() -> None:
    adapter = json.loads(
        Path("data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_adapter_artifact.json").read_text(
            encoding="utf-8"
        )
    )
    adapter["policy"]["held_out_access"] = True
    with pytest.raises(ValueError, match="held-out"):
        public_set_b_capacity_allocation_readiness_artifact(adapter)

    adapter = json.loads(
        Path("data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_adapter_artifact.json").read_text(
            encoding="utf-8"
        )
    )
    for library in adapter["candidate_libraries"]:
        if library["component_id"] == EV_PUBLIC_COMPONENT:
            library["library_id"] = "wrong"
    with pytest.raises(ValueError, match="EV-008A Set B"):
        public_set_b_capacity_allocation_readiness_artifact(adapter)

def test_adoption_node_allocations_conserve_home_and_public_counts() -> None:
    allocations = adoption_node_allocations(_adoption_config())

    assert allocations[0].total_home_charge_points == 11
    assert allocations[0].total_public_charge_points == 5
    assert allocations[0].home_by_node == {"load_a": 6, "load_b": 3, "load_c": 2}


def test_a014_node_weights_from_load_table_filters_and_validates() -> None:
    import pandas as pd

    load_table = pd.DataFrame(
        {
            "p_mw": [1.0, 0.5, 99.0],
            "in_service": [True, True, False],
        },
        index=[0, 2, 3],
    )

    assert a014_node_weights_from_load_table(load_table) == (
        ("load_000", 1.0),
        ("load_002", 0.5),
    )

    bad = load_table.copy()
    bad.loc[2, "p_mw"] = float("nan")
    with pytest.raises(ValueError, match="finite and non-negative"):
        a014_node_weights_from_load_table(bad)


def test_proposed_a014_preview_remains_available_for_historical_workflow() -> None:
    config = load_adoption_scenarios_config(Path("configs/scenarios.yaml"))
    config["allocation"]["status"] = "approved_after_local_totals"
    weights = (("load_a", 2.0), ("load_b", 1.0))

    preview = proposed_a014_allocation_preview(config, weights)

    assert [item.scenario for item in preview] == ["high", "low", "middle"]
    totals = {
        item.scenario: (item.total_home_charge_points, item.total_public_charge_points)
        for item in preview
    }
    assert totals == {
        "low": (7992, 4183),
        "middle": (9386, 5127),
        "high": (10343, 6138),
    }
    assert preview[1].home_by_node == {"load_a": 5328, "load_b": 2664}
    with pytest.raises(ValueError, match="approved A-014 allocation"):
        adoption_node_allocations(config)


def test_committed_a014_alkmaar_preview_preserves_totals_and_status() -> None:
    config = load_adoption_scenarios_config(Path("configs/scenarios.yaml"))
    artifact = json.loads(
        Path("data/metadata/ev_adoption/e2_s6_a014_alkmaar_allocation_preview.json").read_text(
            encoding="utf-8"
        )
    )

    assert artifact["status"] == "proposed_not_pi_signed"
    assert artifact["selected_cluster"]["area_identifier"] == "GM0361"
    assert artifact["node_weight_summary"]["node_count"] == 115
    assert artifact["node_weight_summary"]["unique_node_ids"] is True
    assert artifact["node_weight_summary"]["nonnegative_finite"] is True
    assert artifact["total_conservation_verified"] is True
    assert artifact["scenario_totals"] == artifact["expected_source_totals"]
    assert artifact["scenario_totals"] == {
        "low": {"home": 7992, "public": 4183},
        "middle": {"home": 9386, "public": 5127},
        "high": {"home": 10343, "public": 6138},
    }
    assert len(artifact["allocations_by_node"]) == 115
    assert {
        row["node_id"]
        for row in artifact["allocations_by_node"]
    } == set(artifact["per_node_ranges"])
    for scenario in ("low", "middle", "high"):
        assert sum(row[f"home_{scenario}"] for row in artifact["allocations_by_node"]) == artifact[
            "scenario_totals"
        ][scenario]["home"]
        assert sum(row[f"public_{scenario}"] for row in artifact["allocations_by_node"]) == artifact[
            "scenario_totals"
        ][scenario]["public"]
    config_allocations = adoption_node_allocations(config)
    assert node_charge_point_ranges(config_allocations) == artifact["per_node_ranges"]


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
