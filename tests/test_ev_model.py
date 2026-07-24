from __future__ import annotations

from datetime import UTC, datetime, timedelta
import gzip
import hashlib
import inspect
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

import data.get_ev_adequacy_preflight as ev_adequacy_preflight
import data.get_ev_component_outputs as ev_component_outputs
from data.get_ev_component_outputs import (
    EVComponentOutputVerificationError,
    build_ev_per_node_manifest_index,
    export_ev_per_node_component_outputs,
    rebuild_and_verify_ev_component_outputs,
    verify_existing_ev_component_outputs,
    write_generic_loader_manifests,
)
import src.ev_model as ev_model
from src.ev_model import (
    EV_CALENDAR_MAPPING_RULE_ID,
    EV_HOME_COMPONENT,
    EV_PUBLIC_COMPONENT,
    EVProfileBootstrapSampler,
    EVProfileLibrary,
    EXPECTED_FULL_YEAR_STEPS,
    a014_executable_adoption_artifact,
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
    e3_s2a_ev_heldout_adequacy_preflight_blockers,
    ev005_within_realization_replacement_policy_packet,
    ev_ic1_candidate_adapter_artifact,
    ev_ic1_candidate_member_reference_artifact,
    ev_ic1_component_input_scaffold_artifact,
    ev_ic1_component_output_consumption_packet,
    ev_ic1_accepted_artifact_index_preflight,
    ev_ic1_generic_component_output_loader_manifests,
    ev_candidate_profile_checksum_preflight_artifact,
    materialize_ev_ic1_candidate_component_outputs,
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
from src.contracts.loading_trajectory import LoadingTrajectoryPreRunConfig
from src.contracts.net_load import (
    AcceptedComponentAdapterArtifact,
    ExecutableInputArtifact,
    FutureLayerScreenPreflightConfig,
    NetLoadRealizationContext,
    build_accepted_artifact_loader_blocker_preflight,
    load_component_adapter_output_from_npz_artifact,
    load_component_adapter_outputs_from_npz_artifacts,
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


def _synthetic_ev_component_input_scaffold() -> dict[str, object]:
    return {
        "artifact_type": "ev_ic1_component_input_scaffold",
        "component_kind": "ev",
        "planning_year": 2035,
        "calendar_mapping": {
            "rule_id": EV_CALENDAR_MAPPING_RULE_ID,
            "n_timesteps": EXPECTED_FULL_YEAR_STEPS,
        },
        "source_artifacts": {
            "candidate_adapter_artifact": "candidate-adapter.json",
            "candidate_member_reference": "member-reference.json",
            "candidate_selection_manifest_set": "selection-manifests.json.gz",
        },
        "policy": {
            "candidate_libraries_only": True,
            "held_out_access": False,
            "quarantined_access": False,
            "profile_arrays_loaded": False,
            "integrated_analysis_performed": False,
            "event_or_p_e_analysis_performed": False,
            "capacity_screen_performed": False,
            "manuscript_numbers_produced": False,
            "m_sufficiency_claimed": False,
            "final_low_middle_high_branch_selected": False,
        },
    }


def test_ev_candidate_profile_checksum_preflight_records_verified_candidate_files(
    tmp_path: Path,
) -> None:
    payload = b"synthetic candidate bytes"
    processed_path = tmp_path / "data" / "processed" / "elaad_profiles" / "candidate.npz"
    processed_path.parent.mkdir(parents=True)
    processed_path.write_bytes(payload)
    digest = ev_model._sha256_file(processed_path)
    readiness = {
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
        ]
    }
    verifications = verify_ev_candidate_checksums(readiness, base_dir=tmp_path)

    artifact = ev_candidate_profile_checksum_preflight_artifact(
        _synthetic_ev_component_input_scaffold(),
        readiness,
        verifications,
        verification_timestamp_utc="2026-07-24T12:00:00Z",
    )

    assert artifact["artifact_type"] == "ev_ic1_candidate_profile_checksum_preflight"
    assert artifact["status"] == "candidate_processed_checksums_verified_array_loading_still_blocked"
    assert artifact["verification"]["candidate_processed_file_count"] == 1
    assert artifact["verification"]["by_component"][EV_HOME_COMPONENT] == {
        "batch_count": 1,
        "member_count": 100,
        "byte_size": len(payload),
    }
    assert artifact["verification"]["all_observed_sha256_match_expected"] is True
    assert artifact["verification"]["verified_candidate_batches"][0]["checksum_verified"] is True
    assert artifact["ic1_preconditions"]["future_consumer_must_reverify_ignored_files_before_array_loading"] is True
    assert artifact["policy"]["profile_arrays_loaded"] is False


def test_ev_candidate_profile_checksum_preflight_requires_complete_coverage(
    tmp_path: Path,
) -> None:
    payload = b"synthetic candidate bytes"
    processed_path = tmp_path / "data" / "processed" / "elaad_profiles" / "candidate.npz"
    processed_path.parent.mkdir(parents=True)
    processed_path.write_bytes(payload)
    digest = ev_model._sha256_file(processed_path)
    readiness = {
        "libraries": [
            {
                "library_id": "synthetic_home",
                "component_id": EV_HOME_COMPONENT,
                "candidate_member_count": 200,
                "candidate_batches": [
                    {
                        "seed": 140001,
                        "processed_path": processed_path.relative_to(tmp_path).as_posix(),
                        "processed_sha256_file": digest,
                        "n_profiles": 100,
                        "n_timesteps": EXPECTED_FULL_YEAR_STEPS,
                    },
                    {
                        "seed": 140101,
                        "processed_path": "data/processed/elaad_profiles/missing_candidate.npz",
                        "processed_sha256_file": "b" * 64,
                        "n_profiles": 100,
                        "n_timesteps": EXPECTED_FULL_YEAR_STEPS,
                    },
                ],
            }
        ]
    }
    partial = verify_ev_candidate_checksums(
        {"libraries": [{**readiness["libraries"][0], "candidate_batches": [readiness["libraries"][0]["candidate_batches"][0]]}]},
        base_dir=tmp_path,
    )

    with pytest.raises(ValueError, match="verification for every candidate batch"):
        ev_candidate_profile_checksum_preflight_artifact(
            _synthetic_ev_component_input_scaffold(),
            readiness,
            partial,
            verification_timestamp_utc="2026-07-24T12:00:00Z",
        )


def test_ev_candidate_profile_checksum_preflight_does_not_load_arrays() -> None:
    source = inspect.getsource(ev_candidate_profile_checksum_preflight_artifact)

    assert "load_processed_batch_npz" not in source
    assert "np.load" not in source


def _synthetic_selection_manifest_set(processed_path: str, sha256: str) -> dict[str, object]:
    return {
        "artifact_type": "ev_candidate_member_selection_manifest_set",
        "policy": {
            "candidate_only": True,
            "held_out_access": False,
            "quarantined_access": False,
            "profile_arrays_loaded": False,
            "integrated_analysis_performed": False,
            "event_or_p_e_analysis_performed": False,
            "capacity_screen_performed": False,
            "manuscript_numbers_produced": False,
            "m_sufficiency_claimed": False,
            "replacement_policy_id": "EV-005B",
            "replacement_enabled": True,
        },
        "scenarios": [
            {
                "scenario": "low",
                "planning_year": 2035,
                "component_streams": {EV_HOME_COMPONENT: {"stream_id": "stream-home"}},
                "node_manifests": [
                    {
                        "node_id": "load_000",
                        "selections": [
                            {
                                "partition": "candidate",
                                "component_id": EV_HOME_COMPONENT,
                                "candidate_processed_path": processed_path,
                                "candidate_processed_sha256_file": sha256,
                                "returned_profile_index": 0,
                                "source_member_id": "profile_140001_000",
                                "batch_seed": 140001,
                                "library_id": "synthetic_home",
                                "duplicate_within_realization": False,
                            },
                            {
                                "partition": "candidate",
                                "component_id": EV_HOME_COMPONENT,
                                "candidate_processed_path": processed_path,
                                "candidate_processed_sha256_file": sha256,
                                "returned_profile_index": 1,
                                "source_member_id": "profile_140001_001",
                                "batch_seed": 140001,
                                "library_id": "synthetic_home",
                                "duplicate_within_realization": True,
                            },
                        ],
                    }
                ],
            }
        ],
    }


def _synthetic_component_output_inputs(tmp_path: Path) -> tuple[dict[str, object], dict[str, object], dict[str, object], np.ndarray]:
    batch = parse_elaad_profile_response(_payload(n_profiles=2), batch_seed=140001, expected_n_profiles=2)
    processed_path = tmp_path / "data" / "processed" / "elaad_profiles" / "synthetic_candidate.npz"
    processed_path.parent.mkdir(parents=True, exist_ok=True)
    save_processed_batch_npz(batch, processed_path)
    digest = ev_model._sha256_file(processed_path)
    rel_path = processed_path.relative_to(tmp_path).as_posix()
    readiness = {
        "libraries": [
            {
                "library_id": "synthetic_home",
                "component_id": EV_HOME_COMPONENT,
                "candidate_member_count": 2,
                "candidate_batches": [
                    {
                        "seed": 140001,
                        "processed_path": rel_path,
                        "processed_sha256_file": digest,
                        "n_profiles": 2,
                        "n_timesteps": EXPECTED_FULL_YEAR_STEPS,
                        "capacity_class": None,
                        "cp_capacity_kw": 11,
                    }
                ],
            }
        ]
    }
    scaffold = _synthetic_ev_component_input_scaffold()
    scaffold["scenario_inputs"] = [
        {
            "scenario": "low",
            "planning_year": 2035,
            "node_inputs": [{"node_id": "load_000"}],
        }
    ]
    preflight = ev_candidate_profile_checksum_preflight_artifact(
        scaffold,
        readiness,
        verify_ev_candidate_checksums(readiness, base_dir=tmp_path),
        verification_timestamp_utc="2026-07-24T12:00:00Z",
    )
    selection_manifest = _synthetic_selection_manifest_set(rel_path, digest)
    return scaffold, preflight, selection_manifest, batch.demands_kw[:, 0] + batch.demands_kw[:, 1]


def test_materialize_ev_ic1_candidate_component_outputs_reverifies_and_sums_profiles(
    tmp_path: Path,
) -> None:
    scaffold, preflight, selection_manifest, expected_sum = _synthetic_component_output_inputs(tmp_path)

    manifest = materialize_ev_ic1_candidate_component_outputs(
        scaffold,
        preflight,
        selection_manifest,
        base_dir=tmp_path,
        output_dir=Path("data") / "processed" / "elaad_profiles" / "component_outputs",
        materialized_timestamp_utc="2026-07-24T12:30:00Z",
    )

    assert manifest["artifact_type"] == "ev_ic1_candidate_component_output_manifest"
    assert manifest["ic1_boundary"]["not_a_net_load_result"] is True
    assert manifest["policy"]["candidate_profile_arrays_loaded_for_ev_component_output_only"] is True
    assert manifest["policy"]["integrated_analysis_performed"] is False
    assert manifest["materialization"]["candidate_files_reverified_before_array_loading"] is True
    scenario = manifest["scenario_outputs"][0]
    assert scenario["selected_member_count"] == 2
    assert scenario["duplicate_selected_row_count"] == 1
    output_path = tmp_path / scenario["output_file"]["path"]
    with np.load(output_path, allow_pickle=False) as data:
        np.testing.assert_allclose(data["p_kw_by_node"][0], expected_sum)
        np.testing.assert_allclose(data["q_kvar_by_node"], 0.0)
        assert data["p_kw_by_node"].shape == (1, EXPECTED_FULL_YEAR_STEPS)
        assert data["timestamps_utc"].shape == (EXPECTED_FULL_YEAR_STEPS,)


def test_materialize_ev_ic1_candidate_component_outputs_blocks_non_candidate_partition(
    tmp_path: Path,
) -> None:
    scaffold, preflight, selection_manifest, _expected_sum = _synthetic_component_output_inputs(tmp_path)
    selection_manifest["scenarios"][0]["node_manifests"][0]["selections"][0]["partition"] = "held_out"

    with pytest.raises(PermissionError, match="candidate selections"):
        materialize_ev_ic1_candidate_component_outputs(
            scaffold,
            preflight,
            selection_manifest,
            base_dir=tmp_path,
            output_dir=tmp_path / "data" / "processed" / "elaad_profiles" / "component_outputs",
            materialized_timestamp_utc="2026-07-24T12:30:00Z",
        )


def test_materialize_ev_ic1_candidate_component_outputs_rejects_checksum_drift(
    tmp_path: Path,
) -> None:
    scaffold, preflight, selection_manifest, _expected_sum = _synthetic_component_output_inputs(tmp_path)
    processed_path = tmp_path / selection_manifest["scenarios"][0]["node_manifests"][0]["selections"][0]["candidate_processed_path"]
    processed_path.write_bytes(b"drifted")

    with pytest.raises(ValueError, match="checksum mismatch before array loading"):
        materialize_ev_ic1_candidate_component_outputs(
            scaffold,
            preflight,
            selection_manifest,
            base_dir=tmp_path,
            output_dir=tmp_path / "data" / "processed" / "elaad_profiles" / "component_outputs",
            materialized_timestamp_utc="2026-07-24T12:30:00Z",
        )


def test_ev_component_output_verifier_rebuilds_and_matches_committed_manifest(
    tmp_path: Path,
) -> None:
    scaffold, preflight, selection_manifest, _expected_sum = _synthetic_component_output_inputs(tmp_path)
    committed_manifest = materialize_ev_ic1_candidate_component_outputs(
        scaffold,
        preflight,
        selection_manifest,
        base_dir=tmp_path,
        output_dir=Path("data") / "processed" / "elaad_profiles" / "component_outputs",
        materialized_timestamp_utc="2026-07-24T12:30:00Z",
    )
    output_path = tmp_path / committed_manifest["scenario_outputs"][0]["output_file"]["path"]
    output_path.unlink()

    result = rebuild_and_verify_ev_component_outputs(
        component_input_scaffold=scaffold,
        checksum_preflight=preflight,
        selection_manifest_set=selection_manifest,
        committed_component_output_manifest=committed_manifest,
        base_dir=tmp_path,
        output_dir=Path("data") / "processed" / "elaad_profiles" / "component_outputs",
        timestamp_utc="2026-07-24T12:45:00Z",
    )

    assert result["status"] == "verified"
    assert result["mode"] == "rebuild"
    rebuilt_manifest = result["manifest"]
    assert rebuilt_manifest["scenario_outputs"][0]["output_file"]["sha256"] == (
        committed_manifest["scenario_outputs"][0]["output_file"]["sha256"]
    )


def test_ev_component_output_rebuild_rejects_duplicate_expected_scenario(
    tmp_path: Path,
) -> None:
    scaffold, preflight, selection_manifest, _expected_sum = _synthetic_component_output_inputs(tmp_path)
    committed_manifest = materialize_ev_ic1_candidate_component_outputs(
        scaffold,
        preflight,
        selection_manifest,
        base_dir=tmp_path,
        output_dir=Path("data") / "processed" / "elaad_profiles" / "component_outputs",
        materialized_timestamp_utc="2026-07-24T12:30:00Z",
    )
    committed_manifest["materialization"]["output_files"].append(
        json.loads(json.dumps(committed_manifest["materialization"]["output_files"][0]))
    )

    with pytest.raises(EVComponentOutputVerificationError, match="duplicate scenario records") as excinfo:
        rebuild_and_verify_ev_component_outputs(
            component_input_scaffold=scaffold,
            checksum_preflight=preflight,
            selection_manifest_set=selection_manifest,
            committed_component_output_manifest=committed_manifest,
            base_dir=tmp_path,
            output_dir=Path("data") / "processed" / "elaad_profiles" / "component_outputs",
            timestamp_utc="2026-07-24T12:45:00Z",
        )

    assert "expected: low" in str(excinfo.value)
    assert "observed: --" in str(excinfo.value)


def test_ev_component_output_rebuild_rejects_duplicate_observed_scenario(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scaffold, preflight, selection_manifest, _expected_sum = _synthetic_component_output_inputs(tmp_path)
    committed_manifest = materialize_ev_ic1_candidate_component_outputs(
        scaffold,
        preflight,
        selection_manifest,
        base_dir=tmp_path,
        output_dir=Path("data") / "processed" / "elaad_profiles" / "component_outputs",
        materialized_timestamp_utc="2026-07-24T12:30:00Z",
    )

    def fake_materializer(*_args: object, **_kwargs: object) -> dict[str, object]:
        observed = materialize_ev_ic1_candidate_component_outputs(
            scaffold,
            preflight,
            selection_manifest,
            base_dir=tmp_path,
            output_dir=Path("data") / "processed" / "elaad_profiles" / "component_outputs",
            materialized_timestamp_utc="2026-07-24T12:45:00Z",
        )
        observed["materialization"]["output_files"].append(
            json.loads(json.dumps(observed["materialization"]["output_files"][0]))
        )
        return observed

    monkeypatch.setattr(ev_component_outputs, "materialize_ev_ic1_candidate_component_outputs", fake_materializer)

    with pytest.raises(EVComponentOutputVerificationError, match="duplicate scenario records") as excinfo:
        rebuild_and_verify_ev_component_outputs(
            component_input_scaffold=scaffold,
            checksum_preflight=preflight,
            selection_manifest_set=selection_manifest,
            committed_component_output_manifest=committed_manifest,
            base_dir=tmp_path,
            output_dir=Path("data") / "processed" / "elaad_profiles" / "component_outputs",
            timestamp_utc="2026-07-24T12:45:00Z",
        )

    assert "expected: --" in str(excinfo.value)
    assert "observed: low" in str(excinfo.value)


def test_ev_component_output_rebuild_rejects_missing_observed_scenario(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scaffold, preflight, selection_manifest, _expected_sum = _synthetic_component_output_inputs(tmp_path)
    committed_manifest = materialize_ev_ic1_candidate_component_outputs(
        scaffold,
        preflight,
        selection_manifest,
        base_dir=tmp_path,
        output_dir=Path("data") / "processed" / "elaad_profiles" / "component_outputs",
        materialized_timestamp_utc="2026-07-24T12:30:00Z",
    )
    extra_record = json.loads(json.dumps(committed_manifest["materialization"]["output_files"][0]))
    extra_record["scenario"] = "middle"
    extra_record["path"] = extra_record["path"].replace("_low.npz", "_middle.npz")
    committed_manifest["materialization"]["output_files"].append(extra_record)

    def fake_materializer(*_args: object, **_kwargs: object) -> dict[str, object]:
        return materialize_ev_ic1_candidate_component_outputs(
            scaffold,
            preflight,
            selection_manifest,
            base_dir=tmp_path,
            output_dir=Path("data") / "processed" / "elaad_profiles" / "component_outputs",
            materialized_timestamp_utc="2026-07-24T12:45:00Z",
        )

    monkeypatch.setattr(ev_component_outputs, "materialize_ev_ic1_candidate_component_outputs", fake_materializer)

    with pytest.raises(EVComponentOutputVerificationError, match="scenario set mismatch") as excinfo:
        rebuild_and_verify_ev_component_outputs(
            component_input_scaffold=scaffold,
            checksum_preflight=preflight,
            selection_manifest_set=selection_manifest,
            committed_component_output_manifest=committed_manifest,
            base_dir=tmp_path,
            output_dir=Path("data") / "processed" / "elaad_profiles" / "component_outputs",
            timestamp_utc="2026-07-24T12:45:00Z",
        )

    assert "missing: middle" in str(excinfo.value)
    assert "extra: --" in str(excinfo.value)


def test_ev_component_output_verifier_fails_closed_when_outputs_missing(
    tmp_path: Path,
) -> None:
    scaffold, preflight, selection_manifest, _expected_sum = _synthetic_component_output_inputs(tmp_path)
    committed_manifest = materialize_ev_ic1_candidate_component_outputs(
        scaffold,
        preflight,
        selection_manifest,
        base_dir=tmp_path,
        output_dir=Path("data") / "processed" / "elaad_profiles" / "component_outputs",
        materialized_timestamp_utc="2026-07-24T12:30:00Z",
    )
    output_path = tmp_path / committed_manifest["scenario_outputs"][0]["output_file"]["path"]
    output_path.unlink()

    with pytest.raises(
        EVComponentOutputVerificationError,
        match="Missing ignored EV component-output NPZ files",
    ) as excinfo:
        verify_existing_ev_component_outputs(committed_manifest, base_dir=tmp_path)

    assert (
        "data/processed/elaad_profiles/component_outputs/ev_ic1_candidate_component_output_low.npz"
        in str(excinfo.value)
    )
    assert "Restore the ignored candidate processed-profile NPZ files" in str(excinfo.value)


def test_ev_component_output_rebuild_fails_before_loading_when_candidate_files_missing(
    tmp_path: Path,
) -> None:
    scaffold, preflight, selection_manifest, _expected_sum = _synthetic_component_output_inputs(tmp_path)
    committed_manifest = materialize_ev_ic1_candidate_component_outputs(
        scaffold,
        preflight,
        selection_manifest,
        base_dir=tmp_path,
        output_dir=Path("data") / "processed" / "elaad_profiles" / "component_outputs",
        materialized_timestamp_utc="2026-07-24T12:30:00Z",
    )
    processed_path = tmp_path / selection_manifest["scenarios"][0]["node_manifests"][0]["selections"][0]["candidate_processed_path"]
    processed_path.unlink()

    with pytest.raises(
        EVComponentOutputVerificationError,
        match="Missing candidate processed-profile NPZ files",
    ) as excinfo:
        rebuild_and_verify_ev_component_outputs(
            component_input_scaffold=scaffold,
            checksum_preflight=preflight,
            selection_manifest_set=selection_manifest,
            committed_component_output_manifest=committed_manifest,
            base_dir=tmp_path,
            output_dir=Path("data") / "processed" / "elaad_profiles" / "component_outputs",
            timestamp_utc="2026-07-24T12:45:00Z",
        )

    assert "data/processed/elaad_profiles/synthetic_candidate.npz" in str(excinfo.value)
    assert "ask the PI before regenerating ElaadNL source batches" in str(excinfo.value)


def test_ev_component_output_rebuild_checkpoints_missing_candidate_profiles_without_source_root(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source_artifacts"
    target_root = tmp_path / "clean_consumer"
    scaffold, preflight, selection_manifest, _expected_sum = _synthetic_component_output_inputs(source_root)
    source_output_dir = source_root / "outputs"
    source_output_dir.mkdir(parents=True, exist_ok=True)
    committed_manifest = materialize_ev_ic1_candidate_component_outputs(
        scaffold,
        preflight,
        selection_manifest,
        base_dir=source_root,
        output_dir=source_output_dir,
        materialized_timestamp_utc="2026-07-24T12:30:00Z",
    )
    rel_path = selection_manifest["scenarios"][0]["node_manifests"][0]["selections"][0]["candidate_processed_path"]
    checkpoint = Path("metadata") / "ev_component_output_recovery.json"

    with pytest.raises(EVComponentOutputVerificationError, match="Missing candidate processed-profile NPZ files"):
        rebuild_and_verify_ev_component_outputs(
            component_input_scaffold=scaffold,
            checksum_preflight=preflight,
            selection_manifest_set=selection_manifest,
            committed_component_output_manifest=committed_manifest,
            base_dir=target_root,
            output_dir=target_root / "outputs",
            timestamp_utc="2026-07-24T12:45:00Z",
            checkpoint_path=checkpoint,
        )

    checkpoint_payload = json.loads((target_root / checkpoint).read_text(encoding="utf-8"))
    assert checkpoint_payload["status"] == "blocked_missing_candidate_processed_profiles"
    assert checkpoint_payload["candidate_source_root"]["argument_supplied"] is False
    assert checkpoint_payload["missing_candidate_processed_profiles"][0]["processed_path"] == rel_path
    assert checkpoint_payload["checkpoint"]["complete"] is True


def test_ev_component_output_rebuild_restores_candidate_profiles_from_verified_source_root(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source_artifacts"
    target_root = tmp_path / "clean_consumer"
    scaffold, preflight, selection_manifest, _expected_sum = _synthetic_component_output_inputs(source_root)
    source_output_dir = source_root / "outputs"
    source_output_dir.mkdir(parents=True, exist_ok=True)
    committed_manifest = materialize_ev_ic1_candidate_component_outputs(
        scaffold,
        preflight,
        selection_manifest,
        base_dir=source_root,
        output_dir=source_output_dir,
        materialized_timestamp_utc="2026-07-24T12:30:00Z",
    )
    rel_path = selection_manifest["scenarios"][0]["node_manifests"][0]["selections"][0]["candidate_processed_path"]
    checkpoint = Path("metadata") / "ev_component_output_recovery.json"

    result = rebuild_and_verify_ev_component_outputs(
        component_input_scaffold=scaffold,
        checksum_preflight=preflight,
        selection_manifest_set=selection_manifest,
        committed_component_output_manifest=committed_manifest,
        base_dir=target_root,
        output_dir=target_root / "outputs",
        timestamp_utc="2026-07-24T12:45:00Z",
        candidate_source_root=source_root,
        checkpoint_path=checkpoint,
    )

    assert result["status"] == "verified"
    recovery = result["candidate_processed_profile_recovery"]
    assert recovery["status"] == "candidate_processed_profiles_ready_for_component_output_rebuild"
    assert recovery["restored_candidate_processed_profile_count"] == 1
    assert recovery["policy"]["held_out_access"] is False
    assert recovery["policy"]["profile_arrays_loaded_during_candidate_restore"] is False
    copied_path = target_root / rel_path
    assert copied_path.is_file()
    assert ev_model._sha256_file(copied_path) == recovery["restored_candidate_processed_profiles"][0]["expected_sha256"]
    checkpoint_payload = json.loads((target_root / checkpoint).read_text(encoding="utf-8"))
    assert checkpoint_payload["status"] == "component_outputs_rebuilt_and_verified"
    assert checkpoint_payload["candidate_source_root"]["absolute_path_committed"] is False
    assert len(checkpoint_payload["rebuilt_component_outputs"]) == 1
    verify_existing_ev_component_outputs(committed_manifest, base_dir=target_root)


def test_ev_component_output_rebuild_rejects_source_profile_checksum_mismatch(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source_artifacts"
    target_root = tmp_path / "clean_consumer"
    scaffold, preflight, selection_manifest, _expected_sum = _synthetic_component_output_inputs(source_root)
    source_output_dir = source_root / "outputs"
    source_output_dir.mkdir(parents=True, exist_ok=True)
    committed_manifest = materialize_ev_ic1_candidate_component_outputs(
        scaffold,
        preflight,
        selection_manifest,
        base_dir=source_root,
        output_dir=source_output_dir,
        materialized_timestamp_utc="2026-07-24T12:30:00Z",
    )
    rel_path = selection_manifest["scenarios"][0]["node_manifests"][0]["selections"][0]["candidate_processed_path"]
    (source_root / rel_path).write_bytes(b"not the committed candidate profile")
    checkpoint = Path("metadata") / "ev_component_output_recovery.json"

    with pytest.raises(EVComponentOutputVerificationError, match="recovery failed before EV array loading"):
        rebuild_and_verify_ev_component_outputs(
            component_input_scaffold=scaffold,
            checksum_preflight=preflight,
            selection_manifest_set=selection_manifest,
            committed_component_output_manifest=committed_manifest,
            base_dir=target_root,
            output_dir=target_root / "outputs",
            timestamp_utc="2026-07-24T12:45:00Z",
            candidate_source_root=source_root,
            checkpoint_path=checkpoint,
        )

    checkpoint_payload = json.loads((target_root / checkpoint).read_text(encoding="utf-8"))
    assert checkpoint_payload["status"] == "blocked_missing_or_mismatched_candidate_processed_profiles"
    assert checkpoint_payload["source_checksum_mismatches"][0]["processed_path"] == rel_path
    assert not (target_root / rel_path).exists()


def test_committed_ev_ic1_candidate_component_output_manifest_records_fast_provenance() -> None:
    manifest = json.loads(
        Path(
            "data/metadata/ev_adoption/e2_s2_ev_ic1_candidate_component_output_manifest.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["artifact_type"] == "ev_ic1_candidate_component_output_manifest"
    assert manifest["status"] == "candidate_only_ev_component_outputs_materialized_for_ic1_preflight"
    assert manifest["decision_ids"] == [
        "EV-003",
        "EV-005",
        "EV-005B",
        "EV-007A",
        "A-014",
        "EV-008A",
        "EV-CAL-001",
        "RNG-001",
    ]
    materialization = manifest["materialization"]
    assert materialization["candidate_files_reverified_before_array_loading"] is True
    assert materialization["candidate_processed_file_count"] == 22
    assert materialization["loaded_candidate_profile_batches"] == 22
    assert materialization["output_directory"] == "data/processed/elaad_profiles/component_outputs"
    assert len(materialization["output_files"]) == 3
    assert all(output["path"].startswith("data/processed/elaad_profiles/component_outputs/") for output in materialization["output_files"])
    assert all(output["array_shape"] == [115, EXPECTED_FULL_YEAR_STEPS] for output in materialization["output_files"])
    assert all(output["byte_size"] > 0 for output in materialization["output_files"])
    assert all(len(output["sha256"]) == 64 for output in materialization["output_files"])
    scenarios = {row["scenario"]: row for row in manifest["scenario_outputs"]}
    assert set(scenarios) == {"low", "middle", "high"}
    assert scenarios["low"]["selected_member_count_by_component"] == {
        EV_HOME_COMPONENT: 7992,
        EV_PUBLIC_COMPONENT: 4183,
    }
    assert scenarios["middle"]["selected_member_count_by_component"] == {
        EV_HOME_COMPONENT: 9386,
        EV_PUBLIC_COMPONENT: 5127,
    }
    assert scenarios["high"]["selected_member_count_by_component"] == {
        EV_HOME_COMPONENT: 10343,
        EV_PUBLIC_COMPONENT: 6138,
    }
    assert manifest["calendar_mapping"]["rule_id"] == EV_CALENDAR_MAPPING_RULE_ID
    assert manifest["ic1_boundary"] == {
        "component_adapter_output_ready_for_agent_a_preflight": True,
        "contains_ev_component_outputs_only": True,
        "agent_a_must_load_ignored_output_files_by_manifest_checksum": True,
        "not_a_net_load_result": True,
    }
    assert manifest["policy"] == {
        "candidate_libraries_only": True,
        "held_out_access": False,
        "quarantined_access": False,
        "candidate_profile_arrays_loaded_for_ev_component_output_only": True,
        "integrated_analysis_performed": False,
        "event_or_p_e_analysis_performed": False,
        "capacity_screen_performed": False,
        "final_low_middle_high_branch_selected": False,
        "m_sufficiency_claimed": False,
        "manuscript_numbers_produced": False,
    }


def _committed_ev_component_output_consumption_inputs() -> tuple[dict[str, object], dict[str, object], str]:
    base = Path("data/metadata/ev_adoption")
    scaffold = json.loads((base / "e2_s2_ev_ic1_component_input_scaffold.json").read_text(encoding="utf-8"))
    component_output_manifest_path = base / "e2_s2_ev_ic1_candidate_component_output_manifest.json"
    component_output_manifest = json.loads(component_output_manifest_path.read_text(encoding="utf-8"))
    return scaffold, component_output_manifest, _git_blob_sha256(component_output_manifest_path)


def test_committed_ev_ic1_component_output_consumption_packet_matches_builder() -> None:
    scaffold, component_output_manifest, manifest_sha = _committed_ev_component_output_consumption_inputs()

    expected = ev_ic1_component_output_consumption_packet(
        scaffold,
        component_output_manifest,
        component_output_manifest_sha256=manifest_sha,
    )
    committed = json.loads(
        Path(
            "data/metadata/ev_adoption/e2_s2_ev_ic1_component_output_consumption_packet.json"
        ).read_text(encoding="utf-8")
    )

    assert committed == expected
    assert committed["artifact_type"] == "ev_ic1_component_output_consumption_packet"
    assert committed["status"] == "candidate_only_component_outputs_ready_for_future_ic1_loader_preflight"
    assert committed["allowed_consumer"] == {
        "agent_a_generic_loader_may_consume_after_sha256_verification": True,
        "agent_a_must_verify_each_output_npz_sha256_before_loading": True,
        "agent_a_must_keep_scenario_branch_explicit": True,
        "ic1_preflight_or_real_artifact_assembly_only": True,
        "paper_facing_integrated_adequacy_use_allowed": False,
    }
    assert committed["source_artifacts"]["component_output_manifest_sha256"] == manifest_sha
    assert committed["node_axis"]["node_count"] == 115
    assert committed["calendar_mapping"]["rule_id"] == EV_CALENDAR_MAPPING_RULE_ID
    outputs = committed["component_output_contract"]["scenario_outputs"]
    assert {row["scenario"] for row in outputs} == {"low", "middle", "high"}
    assert all(row["output_npz_path"].endswith(f"_{row['scenario']}.npz") for row in outputs)
    assert all(row["array_shape"] == [115, EXPECTED_FULL_YEAR_STEPS] for row in outputs)
    assert committed["source_profile_libraries"][EV_HOME_COMPONENT]["candidate_member_count"] == 1000
    assert committed["source_profile_libraries"][EV_PUBLIC_COMPONENT]["candidate_member_count"] == 1200
    assert committed["policy"] == {
        "candidate_libraries_only": True,
        "held_out_access": False,
        "quarantined_access": False,
        "profile_arrays_loaded_in_this_packet": False,
        "integrated_analysis_performed": False,
        "event_or_p_e_analysis_performed": False,
        "capacity_screen_performed": False,
        "final_low_middle_high_branch_selected": False,
        "m_sufficiency_claimed": False,
        "manuscript_numbers_produced": False,
    }


def test_ev_component_output_consumption_packet_rejects_missing_scenario() -> None:
    scaffold, component_output_manifest, _manifest_sha = _committed_ev_component_output_consumption_inputs()
    broken = json.loads(json.dumps(component_output_manifest))
    broken["materialization"]["output_files"] = broken["materialization"]["output_files"][:-1]

    with pytest.raises(ValueError, match="identical scenario coverage"):
        ev_ic1_component_output_consumption_packet(scaffold, broken)


def test_ev_component_output_consumption_packet_rejects_duplicate_scenario() -> None:
    scaffold, component_output_manifest, _manifest_sha = _committed_ev_component_output_consumption_inputs()
    broken = json.loads(json.dumps(component_output_manifest))
    broken["materialization"]["output_files"].append(broken["materialization"]["output_files"][0])

    with pytest.raises(ValueError, match="duplicate output files scenarios"):
        ev_ic1_component_output_consumption_packet(scaffold, broken)


def test_ev_component_output_consumption_packet_rejects_unsafe_policy() -> None:
    scaffold, component_output_manifest, _manifest_sha = _committed_ev_component_output_consumption_inputs()
    broken = json.loads(json.dumps(component_output_manifest))
    broken["policy"]["held_out_access"] = True

    with pytest.raises(ValueError, match="held-out access"):
        ev_ic1_component_output_consumption_packet(scaffold, broken)


def _committed_ev_accepted_index_inputs() -> tuple[dict[str, object], dict[str, object], str, str]:
    base = Path("data/metadata/ev_adoption")
    consumption_path = base / "e2_s2_ev_ic1_component_output_consumption_packet.json"
    adoption_path = base / "e2_s6_a014_alkmaar_executable_adoption_artifact.json"
    return (
        json.loads(consumption_path.read_text(encoding="utf-8")),
        json.loads(adoption_path.read_text(encoding="utf-8")),
        _git_blob_sha256(consumption_path),
        _git_blob_sha256(adoption_path),
    )


def test_committed_ev_ic1_accepted_artifact_index_preflight_matches_builder() -> None:
    consumption, adoption, consumption_sha, adoption_sha = _committed_ev_accepted_index_inputs()

    expected = ev_ic1_accepted_artifact_index_preflight(
        consumption,
        adoption,
        consumption_packet_sha256=consumption_sha,
        adoption_artifact_sha256=adoption_sha,
    )
    committed = json.loads(
        Path(
            "data/metadata/ev_adoption/e2_s2_ev_ic1_accepted_artifact_index_preflight.json"
        ).read_text(encoding="utf-8")
    )

    assert committed == expected
    assert committed["artifact_type"] == "ev_ic1_accepted_artifact_index_preflight"
    assert committed["status"] == "accepted_ev_metadata_index_for_agent_a_preflight_blocked_for_integrated_results"
    assert committed["source_artifacts"]["component_output_consumption_packet_sha256"] == consumption_sha
    assert committed["source_artifacts"]["a014_executable_adoption_artifact_sha256"] == adoption_sha
    assert {row["scenario"] for row in committed["scenario_index"]} == {"low", "middle", "high"}
    assert committed["node_axis"]["node_count"] == 115
    assert committed["accepted_for_agent_a_preflight"] == {
        "metadata_index_may_be_consumed": True,
        "agent_a_must_verify_this_index_sha256": True,
        "agent_a_must_verify_source_artifact_sha256s": True,
        "agent_a_must_verify_each_output_npz_sha256_before_loading": True,
        "scenario_branch_must_be_explicit": True,
        "reject_unknown_scenario_branch": True,
        "paper_facing_integrated_use_allowed": False,
    }
    blocker_ids = {row["blocker_id"] for row in committed["remaining_blockers"]}
    assert blocker_ids == {
        "E3.S2a-EV-HELD-OUT-ADEQUACY-NOT-RUN",
        "EV-005-M-SUFFICIENCY-NOT-CERTIFIED",
        "G5-FINAL-LOW-MIDDLE-HIGH-BRANCH-NOT-SELECTED",
        "IC-1-INTEGRATED-NET-LOAD-ASSEMBLY-NOT-RUN",
        "A-016-CROSS-COMPONENT-SCENARIO-CONSISTENCY-NOT-YET-CHECKED",
    }
    assert committed["policy"] == {
        "candidate_libraries_only": True,
        "held_out_access": False,
        "quarantined_access": False,
        "profile_arrays_loaded_in_this_index": False,
        "integrated_analysis_performed": False,
        "event_or_p_e_analysis_performed": False,
        "capacity_screen_performed": False,
        "final_low_middle_high_branch_selected": False,
        "m_sufficiency_claimed": False,
        "manuscript_numbers_produced": False,
        "fail_closed_on_unresolved_blockers": True,
    }


def test_ev_ic1_accepted_artifact_index_rejects_scenario_mismatch() -> None:
    consumption, adoption, _consumption_sha, _adoption_sha = _committed_ev_accepted_index_inputs()
    broken = json.loads(json.dumps(adoption))
    broken["scenario_allocations"] = broken["scenario_allocations"][:-1]

    with pytest.raises(ValueError, match="identical low/middle/high scenario coverage"):
        ev_ic1_accepted_artifact_index_preflight(consumption, broken)


def test_ev_ic1_accepted_artifact_index_rejects_unsafe_policy() -> None:
    consumption, adoption, _consumption_sha, _adoption_sha = _committed_ev_accepted_index_inputs()
    broken = json.loads(json.dumps(consumption))
    broken["policy"]["m_sufficiency_claimed"] = True

    with pytest.raises(ValueError, match="library sufficiency"):
        ev_ic1_accepted_artifact_index_preflight(broken, adoption)


def test_ev_ic1_accepted_artifact_index_rejects_public_capacity_drift() -> None:
    consumption, adoption, _consumption_sha, _adoption_sha = _committed_ev_accepted_index_inputs()
    broken = json.loads(json.dumps(consumption))
    first_output = broken["component_output_contract"]["scenario_outputs"][0]
    first_output["public_selected_member_count_by_capacity_class"]["public_11kw"] += 1

    with pytest.raises(ValueError, match="capacity-class counts"):
        ev_ic1_accepted_artifact_index_preflight(broken, adoption)


def test_committed_ev_candidate_profile_checksum_preflight_records_fast_provenance() -> None:
    artifact = json.loads(
        Path(
            "data/metadata/ev_adoption/e2_s2_ev_candidate_profile_checksum_preflight.json"
        ).read_text(encoding="utf-8")
    )

    assert artifact["artifact_type"] == "ev_ic1_candidate_profile_checksum_preflight"
    assert artifact["status"] == "candidate_processed_checksums_verified_array_loading_still_blocked"
    assert artifact["decision_ids"] == [
        "EV-003",
        "EV-005",
        "EV-005B",
        "EV-007A",
        "A-014",
        "EV-008A",
        "EV-CAL-001",
        "RNG-001",
    ]
    verification = artifact["verification"]
    assert verification["candidate_processed_file_count"] == 22
    assert verification["candidate_batch_count"] == 22
    assert verification["candidate_member_count"] == 2200
    assert verification["by_component"][EV_HOME_COMPONENT]["member_count"] == 1000
    assert verification["by_component"][EV_PUBLIC_COMPONENT]["member_count"] == 1200
    assert verification["public_member_count_by_capacity_class"] == {
        "public_11kw": 300,
        "public_13kw": 300,
        "public_15kw": 300,
        "public_22kw": 300,
    }
    assert verification["all_observed_sha256_match_expected"] is True
    sample = verification["verified_candidate_batches"][0]
    assert sample["component_id"] == EV_HOME_COMPONENT
    assert sample["seed"] == 140001
    assert sample["observed_sha256"] == sample["expected_sha256"]
    assert artifact["calendar_mapping"]["rule_id"] == EV_CALENDAR_MAPPING_RULE_ID
    assert artifact["calendar_mapping"]["source_timestep_i_maps_to_target_timestep_i"] is True
    assert artifact["policy"] == {
        "candidate_libraries_only": True,
        "held_out_access": False,
        "quarantined_access": False,
        "profile_arrays_loaded": False,
        "integrated_analysis_performed": False,
        "event_or_p_e_analysis_performed": False,
        "capacity_screen_performed": False,
        "final_low_middle_high_branch_selected": False,
        "m_sufficiency_claimed": False,
        "manuscript_numbers_produced": False,
    }


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
    assert any("G0-A3" in blocker for blocker in packet["ic1_use_blockers"])
    assert not any("Q-5" in blocker for blocker in packet["ic1_use_blockers"])



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


def _committed_ev_heldout_preflight_inputs() -> tuple[dict[str, object], dict[str, object], str, str]:
    base = Path("data/metadata/ev_adoption")
    accepted_index_path = base / "e2_s2_ev_ic1_accepted_artifact_index_preflight.json"
    criterion_path = base / "e3_s2a_ev_adequacy_criterion_packet.json"
    return (
        json.loads(accepted_index_path.read_text(encoding="utf-8")),
        json.loads(criterion_path.read_text(encoding="utf-8")),
        _git_blob_sha256(accepted_index_path),
        _git_blob_sha256(criterion_path),
    )


def test_committed_e3_s2a_ev_heldout_adequacy_preflight_matches_builder() -> None:
    accepted_index, criterion, accepted_sha, criterion_sha = _committed_ev_heldout_preflight_inputs()

    checksum_path = Path(
        "data/metadata/ev_adoption/e3_s2a_ev_candidate_component_output_checksum_preflight.json"
    )
    checksum_verification = json.loads(checksum_path.read_text(encoding="utf-8"))
    expected = e3_s2a_ev_heldout_adequacy_preflight_blockers(
        accepted_index,
        criterion,
        accepted_artifact_index_sha256=accepted_sha,
        criterion_packet_sha256=criterion_sha,
        candidate_output_checksum_verification=checksum_verification,
        candidate_output_checksum_verification_path=checksum_path.as_posix(),
        candidate_output_checksum_verification_sha256=ev_adequacy_preflight.git_blob_or_file_sha256(checksum_path),
    )
    committed = json.loads(
        Path(
            "data/metadata/ev_adoption/e3_s2a_ev_heldout_adequacy_preflight_blockers.json"
        ).read_text(encoding="utf-8")
    )

    assert committed == expected
    assert committed["artifact_type"] == "e3_s2a_ev_heldout_adequacy_preflight_blocker_manifest"
    assert committed["status"] == "blocked_before_held_out_access"
    assert committed["blocked"] is True
    assert committed["missing_checksum_or_manifest_inputs"] == []
    assert committed["candidate_output_checksum_verification"]["status"] == "blocked_missing_ignored_component_outputs"
    assert committed["candidate_output_checksum_verification"]["all_expected_outputs_verified"] is False
    assert committed["candidate_output_checksum_verification"]["missing_output_count"] == 3
    blocker_ids = {row["blocker_id"] for row in committed["blockers"]}
    assert {
        "E3.S2A-DOWNSTREAM-AGGREGATE-ADEQUACY-CRITERION-NOT-SIGNED",
        "E3.S2-IC1-ASSEMBLY-NOT-ACCEPTED",
        "EV-HELD-OUT-ACCESS-NOT-EXPLICITLY-INVOKED",
        "A-016-SCENARIO-CONSISTENCY-NOT-RESOLVED",
        "G5-FINAL-LOW-MIDDLE-HIGH-BRANCH-NOT-SELECTED",
        "EV-CANDIDATE-OUTPUT-CHECKSUMS-NOT-VERIFIED-IN-CONSUMING-WORKTREE",
        "EV-005-M-SUFFICIENCY-NOT-CERTIFIED",
    }.issubset(blocker_ids)
    assert committed["policy"] == {
        "held_out_access": False,
        "quarantined_access": False,
        "profile_arrays_loaded": False,
        "integrated_analysis_performed": False,
        "event_or_p_e_analysis_performed": False,
        "capacity_screen_performed": False,
        "m_sufficiency_claimed": False,
        "manuscript_numbers_produced": False,
        "fail_closed_on_blockers": True,
    }


def test_e3_s2a_ev_heldout_preflight_records_missing_manifest_inputs() -> None:
    accepted_index, criterion, accepted_sha, criterion_sha = _committed_ev_heldout_preflight_inputs()
    broken = json.loads(json.dumps(accepted_index))
    broken["source_artifacts"]["component_output_manifest_sha256"] = ""

    manifest = e3_s2a_ev_heldout_adequacy_preflight_blockers(
        broken,
        criterion,
        accepted_artifact_index_sha256=accepted_sha,
        criterion_packet_sha256=criterion_sha,
    )

    assert any(row["input"] == "source_artifacts.component_output_manifest_sha256" for row in manifest["missing_checksum_or_manifest_inputs"])
    assert any(row["blocker_id"] == "E3.S2A-MISSING-CHECKSUM-OR-MANIFEST-INPUT" for row in manifest["blockers"])


def test_e3_s2a_ev_heldout_preflight_rejects_unsafe_heldout_policy() -> None:
    accepted_index, criterion, _accepted_sha, _criterion_sha = _committed_ev_heldout_preflight_inputs()
    broken = json.loads(json.dumps(accepted_index))
    broken["policy"]["held_out_access"] = True

    with pytest.raises(ValueError, match="held_out_access=False"):
        e3_s2a_ev_heldout_adequacy_preflight_blockers(broken, criterion)


def test_ev_adequacy_preflight_cli_builder_is_deterministic(tmp_path: Path) -> None:
    output_path = tmp_path / "preflight" / "blockers.json"

    first = ev_adequacy_preflight.write_preflight_manifest(output_path)
    repeated = ev_adequacy_preflight.write_preflight_manifest(output_path)
    written = json.loads(output_path.read_text(encoding="utf-8"))

    assert written == first == repeated
    assert written["blocked"] is True
    assert written["policy"]["held_out_access"] is False
    assert written["policy"]["profile_arrays_loaded"] is False


def _synthetic_ev_accepted_component_output_index(tmp_path: Path) -> tuple[dict[str, object], dict[str, bytes]]:
    payloads = {
        "low": b"candidate-low-output-bytes",
        "middle": b"candidate-middle-output-bytes",
        "high": b"candidate-high-output-bytes",
    }
    rows = []
    for scenario, payload in payloads.items():
        rows.append(
            {
                "scenario": scenario,
                "output_npz_path": f"outputs/{scenario}.npz",
                "output_sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    return {"scenario_index": rows}, payloads


def test_ev_candidate_output_checksum_preflight_verifies_files_without_loading_arrays(tmp_path: Path) -> None:
    accepted_index, payloads = _synthetic_ev_accepted_component_output_index(tmp_path)
    output_root = tmp_path / "outputs"
    output_root.mkdir(parents=True)
    for scenario, payload in payloads.items():
        (output_root / f"{scenario}.npz").write_bytes(payload)
    checkpoint = tmp_path / "metadata" / "checksum_preflight.json"

    payload = ev_adequacy_preflight.verify_candidate_component_output_checksums(
        accepted_index,
        base_dir=tmp_path,
        checkpoint_path=checkpoint,
    )

    assert checkpoint.is_file()
    assert json.loads(checkpoint.read_text(encoding="utf-8")) == payload
    assert payload["status"] == "verified_candidate_component_outputs"
    assert payload["all_expected_outputs_verified"] is True
    assert payload["missing_outputs"] == []
    assert payload["checksum_mismatches"] == []
    assert {row["status"] for row in payload["verification_records"]} == {"verified"}
    assert payload["policy"]["hash_file_bytes_only"] is True
    assert payload["policy"]["held_out_access"] is False
    assert payload["policy"]["profile_arrays_loaded"] is False
    source = inspect.getsource(ev_adequacy_preflight.verify_candidate_component_output_checksums)
    assert "np.load" not in source
    assert "load_processed_batch_npz" not in source


def test_ev_candidate_output_checksum_preflight_checkpoints_missing_outputs(tmp_path: Path) -> None:
    accepted_index, payloads = _synthetic_ev_accepted_component_output_index(tmp_path)
    output_root = tmp_path / "outputs"
    output_root.mkdir(parents=True)
    for scenario in ("low", "middle"):
        (output_root / f"{scenario}.npz").write_bytes(payloads[scenario])
    checkpoint = tmp_path / "metadata" / "checksum_preflight.json"

    payload = ev_adequacy_preflight.verify_candidate_component_output_checksums(
        accepted_index,
        base_dir=tmp_path,
        checkpoint_path=checkpoint,
    )

    assert payload["status"] == "blocked_missing_ignored_component_outputs"
    assert payload["all_expected_outputs_verified"] is False
    assert payload["checkpoint"]["complete"] is True
    assert payload["missing_outputs"] == [
        {"scenario": "high", "output_npz_path": "outputs/high.npz"}
    ]
    by_scenario = {row["scenario"]: row for row in payload["verification_records"]}
    assert by_scenario["high"]["status"] == "missing"
    assert by_scenario["high"]["observed_sha256"] is None


def test_ev_candidate_output_checksum_preflight_rejects_bad_scenario_set(tmp_path: Path) -> None:
    accepted_index, _payloads = _synthetic_ev_accepted_component_output_index(tmp_path)
    duplicate = json.loads(json.dumps(accepted_index))
    duplicate["scenario_index"][1]["scenario"] = "low"

    with pytest.raises(ValueError, match="duplicate scenarios"):
        ev_adequacy_preflight.verify_candidate_component_output_checksums(
            duplicate,
            base_dir=tmp_path,
            checkpoint_path=tmp_path / "checksum.json",
        )

    held_out = json.loads(json.dumps(accepted_index))
    held_out["scenario_index"][0]["output_npz_path"] = "data/processed/held_out/low.npz"
    with pytest.raises(ValueError, match="held-out/quarantined"):
        ev_adequacy_preflight.verify_candidate_component_output_checksums(
            held_out,
            base_dir=tmp_path,
            checkpoint_path=tmp_path / "checksum.json",
        )


def _committed_ev_generic_loader_inputs() -> tuple[dict[str, object], dict[str, object], str, str]:
    base = Path("data/metadata/ev_adoption")
    accepted_path = base / "e2_s2_ev_ic1_accepted_artifact_index_preflight.json"
    recovery_path = base / "e3_s2a_ev_component_output_recovery_preflight.json"
    return (
        json.loads(accepted_path.read_text(encoding="utf-8")),
        json.loads(recovery_path.read_text(encoding="utf-8")),
        _git_blob_sha256(accepted_path),
        _git_blob_sha256(recovery_path),
    )


def test_committed_ev_generic_loader_manifest_packet_matches_builder() -> None:
    accepted_index, recovery, accepted_sha, recovery_sha = _committed_ev_generic_loader_inputs()
    packet_path = Path("data/metadata/ev_adoption/e3_s2a_ev_ic1_generic_component_output_manifest_packet.json")
    manifest_paths = [
        Path("data/metadata/ev_adoption/generic_component_output_manifests") / f"ev_2035_{scenario}.json"
        for scenario in ("high", "low", "middle")
    ]
    sha_by_path = {path.as_posix(): ev_model._sha256_file(path) for path in manifest_paths}

    expected = ev_ic1_generic_component_output_loader_manifests(
        accepted_index,
        recovery,
        accepted_artifact_index_sha256=accepted_sha,
        recovery_preflight_sha256=recovery_sha,
        manifest_sha256_by_path=sha_by_path,
    )
    committed = json.loads(packet_path.read_text(encoding="utf-8"))

    assert committed == expected
    assert committed["status"] == "blocked_ev_generic_loader_manifests_multi_node_contract"
    assert committed["missing_generic_manifest_sha256_paths"] == []
    assert {row["scenario"] for row in committed["scenario_manifests"]} == {"low", "middle", "high"}
    assert committed["policy"] == {
        "candidate_libraries_only": True,
        "held_out_access": False,
        "quarantined_access": False,
        "profile_arrays_loaded_by_manifest_builder": False,
        "integrated_analysis_performed": False,
        "event_or_p_e_analysis_performed": False,
        "capacity_screen_performed": False,
        "final_low_middle_high_branch_selected": False,
        "m_sufficiency_claimed": False,
        "manuscript_numbers_produced": False,
        "fail_closed_on_unresolved_blockers": True,
    }


def test_ev_generic_loader_manifest_stays_fail_closed_at_agent_a_loader_boundary(tmp_path: Path) -> None:
    packet = json.loads(
        Path("data/metadata/ev_adoption/e3_s2a_ev_ic1_generic_component_output_manifest_packet.json").read_text(
            encoding="utf-8"
        )
    )
    low_record = next(row for row in packet["scenario_manifests"] if row["scenario"] == "low")
    low_manifest = packet["manifests_by_scenario"]["low"]
    manifest_path = Path(low_record["path"])
    (tmp_path / manifest_path).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / manifest_path).write_text(json.dumps(low_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_sha = ev_model._sha256_file(tmp_path / manifest_path)

    source_path = Path("data/metadata/ev_adoption/e2_s2_ev_ic1_accepted_artifact_index_preflight.json")
    (tmp_path / source_path).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / source_path).write_text("ev accepted artifact source\n", encoding="utf-8")
    source_sha = ev_model._sha256_file(tmp_path / source_path)
    artifact = ExecutableInputArtifact(
        artifact_id="e2_s2_ev_ic1_accepted_artifact_index_preflight",
        kind="ev",
        artifact_status="accepted",
        version_id="e2_s2_ev_ic1_accepted_artifact_index_preflight_v1",
        source_id="elaadnl_ev_accepted_artifact_index_preflight",
        member_id="ev005b_candidate_index_root20260722_sample0_all_declared_branches",
        calendar_id="planning-2035-europe-amsterdam-15min",
        node_ids=tuple(f"load_{index:03d}" for index in range(115)),
        signed_register_ids=("A-014", "EV-003", "EV-005", "EV-005B", "EV-007", "EV-007A", "EV-008A", "EV-CAL-001"),
        blocking_register_ids=(),
        timestep_seconds=900,
        manifest_path=source_path.as_posix(),
        provenance={"fixture": "ev generic loader schema test"},
    )

    preflight = build_accepted_artifact_loader_blocker_preflight(
        FutureLayerScreenPreflightConfig(
            config_id="ev-generic-loader-schema-test",
            scenario_ids=("low",),
            planning_years=(2035,),
            rho_values=(0.0,),
            node_ids=tuple(f"load_{index:03d}" for index in range(115)),
            metadata={"calendar_id": "planning-2035-europe-amsterdam-15min"},
        ),
        (artifact,),
        LoadingTrajectoryPreRunConfig(
            config_id="ev-generic-loader-schema-test",
            purpose="e3_s2b_future_layer_screen",
            planning_years=(2035,),
        ),
        capacity_provenance={
            "s_nom_agg_kva": 80000.0,
            "convention_status": "pending_g1_a2_e3_s2b",
            "source": "metadata fixture",
            "metadata": {"not_evaluated_here": True},
        },
        artifact_sha256_by_path={source_path.as_posix(): source_sha},
        component_output_manifest_paths_by_kind={"ev": manifest_path.as_posix()},
        component_output_manifest_sha256_by_path={manifest_path.as_posix(): manifest_sha},
        repo_root=tmp_path,
        required_component_kinds=("ev",),
        downstream_blocker_ids=(),
    )

    codes = {item["code"] for item in preflight["blocker_manifest"]["items"]}
    assert preflight["ready_for_artifact_loader_execution"] is False
    assert "component_output_manifest_required_keys_missing" not in codes
    assert "component_output_manifest_not_accepted" in codes
    assert "component_output_manifest_node_missing" in codes
    assert preflight["component_output_manifest_records"] == (
        {
            "kind": "ev",
            "artifact_id": "e2_s2_ev_ic1_accepted_artifact_index_preflight",
            "path": manifest_path.as_posix(),
            "state": "blocked",
            "sha256": manifest_sha,
            "expected_sha256": manifest_sha,
            "checksum_match": True,
        },
    )
    assert low_manifest["artifact_status"] == "blocked_multi_node_contract"
    assert low_manifest["node_id"] == "ev_multi_node_axis_115"
    assert (
        low_manifest["provenance"]["agent_a_loader_boundary"]["blocker_id"]
        == "A-LOADER-MULTI-NODE-EV-OUTPUT-CONTRACT-NOT-YET-SIGNED"
    )


def test_ev_generic_loader_manifest_builder_rejects_unverified_recovery() -> None:
    accepted_index, recovery, accepted_sha, recovery_sha = _committed_ev_generic_loader_inputs()
    broken = json.loads(json.dumps(recovery))
    broken["policy"]["held_out_access"] = True

    with pytest.raises(ValueError, match="held_out_access=False"):
        ev_ic1_generic_component_output_loader_manifests(
            accepted_index,
            broken,
            accepted_artifact_index_sha256=accepted_sha,
            recovery_preflight_sha256=recovery_sha,
        )


def test_ev_generic_loader_manifest_writer_is_deterministic(tmp_path: Path) -> None:
    accepted_index, recovery, _accepted_sha, _recovery_sha = _committed_ev_generic_loader_inputs()
    accepted_path = Path("metadata") / "accepted.json"
    recovery_path = Path("metadata") / "recovery.json"
    (tmp_path / accepted_path).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / accepted_path).write_text(json.dumps(accepted_index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (tmp_path / recovery_path).write_text(json.dumps(recovery, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    first = write_generic_loader_manifests(
        accepted_artifact_index=accepted_index,
        recovery_preflight=recovery,
        base_dir=tmp_path,
        manifest_directory=Path("metadata") / "generic",
        packet_path=Path("metadata") / "packet.json",
        accepted_artifact_index_path=accepted_path,
        recovery_preflight_path=recovery_path,
    )
    repeated = write_generic_loader_manifests(
        accepted_artifact_index=accepted_index,
        recovery_preflight=recovery,
        base_dir=tmp_path,
        manifest_directory=Path("metadata") / "generic",
        packet_path=Path("metadata") / "packet.json",
        accepted_artifact_index_path=accepted_path,
        recovery_preflight_path=recovery_path,
    )

    assert first == repeated
    assert json.loads((tmp_path / "metadata" / "packet.json").read_text(encoding="utf-8")) == first
    assert len(first["scenario_manifests"]) == 3


def _write_synthetic_multi_node_ev_npz(path: Path, *, node_ids: tuple[str, ...] = ("load_000", "load_001")) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    timestamps = np.array(
        ["2035-01-01T00:00:00", "2035-01-01T00:15:00", "2035-01-01T00:30:00", "2035-01-01T00:45:00"],
        dtype="datetime64[s]",
    )
    p_kw = np.array([[1.0, 2.0, 3.0, 4.0], [10.0, 20.0, 30.0, 40.0]], dtype=float)[: len(node_ids)]
    q_kvar = p_kw / 10.0
    ev_component_outputs._write_deterministic_npz(
        path,
        {
            "node_ids": np.asarray(node_ids),
            "p_kw_by_node": p_kw,
            "q_kvar_by_node": q_kvar,
            "timestamps_utc": timestamps,
        },
    )
    return p_kw, q_kvar, timestamps


def _synthetic_generic_packet(source_path: Path, source_sha: str, *, node_ids: tuple[str, ...] = ("load_000", "load_001")) -> dict[str, object]:
    scenarios = ("high", "low", "middle")
    scenario_manifests = []
    manifests_by_scenario = {}
    for scenario in scenarios:
        record = {
            "scenario": scenario,
            "array_path": source_path.as_posix(),
            "array_sha256": source_sha,
            "path": f"metadata/generic/ev_2035_{scenario}.json",
            "sha256": "0" * 64,
        }
        scenario_manifests.append(record)
        manifests_by_scenario[scenario] = {
            "artifact_id": f"synthetic_generic_{scenario}",
            "artifact_status": "blocked_multi_node_contract",
            "kind": "ev",
            "component_id": f"ev_component_output_2035_{scenario}",
            "node_id": "ev_multi_node_axis_115",
            "member_id": f"ev005b_root20260722_sample0_{scenario}_branch",
            "source_id": "D-002_D-010_D-012",
            "calendar_id": "planning-2035-europe-amsterdam-15min",
            "timestep_seconds": 900,
            "array_path": source_path.as_posix(),
            "array_sha256": source_sha,
            "provenance": {
                "node_axis": {"node_count": len(node_ids), "node_ids": list(node_ids)},
                "calendar_mapping": {"rule_id": "EV-CAL-001", "target_calendar_id": "planning-2035-europe-amsterdam-15min"},
                "a014_allocation_provenance": {"decision_id": "A-014"},
                "selection_manifest_provenance": {"decision_id": "EV-005B"},
                "remaining_blockers": [
                    {"blocker_id": "E3.S2a-EV-HELD-OUT-ADEQUACY-NOT-RUN", "status": "blocked"}
                ],
            },
        }
    return {
        "artifact_type": "ev_ic1_generic_component_output_manifest_packet",
        "artifact_id": "synthetic_ev_generic_packet",
        "schema_version": 1,
        "task_id": "E3.S2a",
        "status": "blocked_ev_generic_loader_manifests_multi_node_contract",
        "decision_ids": ["A-014", "EV-003", "EV-005", "EV-005B", "EV-007A", "EV-008A", "EV-CAL-001"],
        "source_ids": ["D-002", "D-010", "D-012"],
        "policy": {
            "candidate_libraries_only": True,
            "held_out_access": False,
            "quarantined_access": False,
            "elaad_api_calls": False,
            "integrated_analysis_performed": False,
            "event_or_p_e_analysis_performed": False,
            "capacity_screen_performed": False,
            "final_low_middle_high_branch_selected": False,
            "m_sufficiency_claimed": False,
            "manuscript_numbers_produced": False,
        },
        "scenario_manifests": scenario_manifests,
        "manifests_by_scenario": manifests_by_scenario,
    }


def _ev_loader_context() -> NetLoadRealizationContext:
    tree = SeedTree(20260722)
    sample_index = 0
    return NetLoadRealizationContext(
        scenario="low",
        planning_year=2035,
        time_domain="full_year",
        rho=0.0,
        root_seed=tree.root_seed,
        sample_index=sample_index,
        sample_seed=tree.sample_seed(sample_index),
        component_streams=(tree.component_stream(sample_index, "ev"),),
        shared_weather_driver_id="not_weather_dependent",
    )


def test_ev_per_node_export_splits_fixture_into_agent_a_loadable_artifact(tmp_path: Path) -> None:
    source_path = Path("data/processed/elaad_profiles/component_outputs/ev_fixture_low.npz")
    p_kw, q_kvar, timestamps = _write_synthetic_multi_node_ev_npz(tmp_path / source_path)
    source_sha = ev_model._sha256_file(tmp_path / source_path)
    packet = _synthetic_generic_packet(source_path, source_sha)

    result = export_ev_per_node_component_outputs(
        generic_packet=packet,
        base_dir=tmp_path,
        generic_packet_path=Path("metadata/generic_packet.json"),
        output_dir=Path("data/processed/elaad_profiles/component_outputs/per_node"),
        manifest_dir=Path("metadata/per_node"),
        checkpoint_path=Path("metadata/per_node_checkpoint.json"),
        timestamp_utc="2026-07-24T17:00:00Z",
        artifact_status="synthetic_fixture",
        scenario_filter=("low",),
        node_filter=("load_001",),
    )

    assert result["status"] == "per_node_exports_written_scaffold"
    assert result["completed_per_node_export_count"] == 1
    export_record = result["completed_per_node_exports"][0]
    manifest = json.loads((tmp_path / export_record["manifest_path"]).read_text(encoding="utf-8"))
    loaded = load_component_adapter_output_from_npz_artifact(
        manifest,
        _ev_loader_context(),
        repo_root=tmp_path,
        expected_calendar_id="planning-2035-europe-amsterdam-15min",
        expected_node_ids=("load_001",),
        allow_synthetic_fixture=True,
    )
    assert loaded.node_id == "load_001"
    assert loaded.kind == "ev"
    np.testing.assert_allclose(loaded.p_kw, p_kw[1])
    np.testing.assert_allclose(loaded.q_kvar, q_kvar[1])
    assert np.array_equal(loaded.timestamps, timestamps)
    assert manifest["provenance"]["source_multi_node_sha256"] == source_sha


def test_ev_per_node_export_blocks_missing_source_npz(tmp_path: Path) -> None:
    source_path = Path("data/processed/elaad_profiles/component_outputs/missing.npz")
    packet = _synthetic_generic_packet(source_path, "1" * 64)

    result = export_ev_per_node_component_outputs(
        generic_packet=packet,
        base_dir=tmp_path,
        generic_packet_path=Path("metadata/generic_packet.json"),
        checkpoint_path=Path("metadata/per_node_checkpoint.json"),
        timestamp_utc="2026-07-24T17:00:00Z",
        scenario_filter=("low",),
    )

    assert result["status"] == "blocked_missing_source_component_outputs"
    assert result["missing_source_component_outputs"][0]["path"] == source_path.as_posix()
    assert json.loads((tmp_path / "metadata/per_node_checkpoint.json").read_text(encoding="utf-8")) == result


def test_ev_per_node_export_blocks_source_checksum_mismatch(tmp_path: Path) -> None:
    source_path = Path("data/processed/elaad_profiles/component_outputs/ev_fixture_low.npz")
    _write_synthetic_multi_node_ev_npz(tmp_path / source_path)
    packet = _synthetic_generic_packet(source_path, "2" * 64)

    result = export_ev_per_node_component_outputs(
        generic_packet=packet,
        base_dir=tmp_path,
        generic_packet_path=Path("metadata/generic_packet.json"),
        checkpoint_path=Path("metadata/per_node_checkpoint.json"),
        timestamp_utc="2026-07-24T17:00:00Z",
        scenario_filter=("low",),
    )

    assert result["status"] == "blocked_source_component_output_checksum_mismatch"
    assert result["source_checksum_mismatches"][0]["failure"] == "source_checksum_mismatch"


def test_ev_per_node_export_rejects_unsafe_approval_tokens(tmp_path: Path) -> None:
    source_path = Path("data/processed/elaad_profiles/component_outputs/ev_fixture_low.npz")
    _write_synthetic_multi_node_ev_npz(tmp_path / source_path)
    packet = _synthetic_generic_packet(source_path, ev_model._sha256_file(tmp_path / source_path))
    packet["decision_ids"] = [*packet["decision_ids"], "EV-FUTURE-PLACEHOLDER"]

    with pytest.raises(EVComponentOutputVerificationError, match="Unsafe approval/source token"):
        export_ev_per_node_component_outputs(
            generic_packet=packet,
            base_dir=tmp_path,
            timestamp_utc="2026-07-24T17:00:00Z",
            scenario_filter=("low",),
        )


def test_ev_per_node_export_rejects_duplicate_and_missing_node_ids(tmp_path: Path) -> None:
    source_path = Path("data/processed/elaad_profiles/component_outputs/ev_fixture_low.npz")
    _write_synthetic_multi_node_ev_npz(tmp_path / source_path)
    packet = _synthetic_generic_packet(source_path, ev_model._sha256_file(tmp_path / source_path), node_ids=("load_000", "load_000"))
    with pytest.raises(EVComponentOutputVerificationError, match="duplicate node IDs"):
        export_ev_per_node_component_outputs(
            generic_packet=packet,
            base_dir=tmp_path,
            timestamp_utc="2026-07-24T17:00:00Z",
            scenario_filter=("low",),
        )

    packet = _synthetic_generic_packet(source_path, ev_model._sha256_file(tmp_path / source_path), node_ids=("load_000", "load_002"))
    with pytest.raises(EVComponentOutputVerificationError, match="node axis does not match"):
        export_ev_per_node_component_outputs(
            generic_packet=packet,
            base_dir=tmp_path,
            timestamp_utc="2026-07-24T17:00:00Z",
            scenario_filter=("low",),
        )


def test_ev_per_node_export_rejects_accepted_status_before_approval(tmp_path: Path) -> None:
    source_path = Path("data/processed/elaad_profiles/component_outputs/ev_fixture_low.npz")
    _write_synthetic_multi_node_ev_npz(tmp_path / source_path)
    packet = _synthetic_generic_packet(source_path, ev_model._sha256_file(tmp_path / source_path))

    with pytest.raises(EVComponentOutputVerificationError, match="future signed executable approval"):
        export_ev_per_node_component_outputs(
            generic_packet=packet,
            base_dir=tmp_path,
            timestamp_utc="2026-07-24T17:00:00Z",
            scenario_filter=("low",),
            artifact_status="accepted",
        )



def test_committed_ev_per_node_manifest_index_matches_builder() -> None:
    base = Path("data/metadata/ev_adoption")
    generic_packet_path = base / "e3_s2a_ev_ic1_generic_component_output_manifest_packet.json"
    committed_path = base / "e3_s2a_ev_per_node_manifest_index_preflight.json"
    generic_packet = json.loads(generic_packet_path.read_text(encoding="utf-8"))
    committed = json.loads(committed_path.read_text(encoding="utf-8"))

    expected = build_ev_per_node_manifest_index(
        generic_packet=generic_packet,
        base_dir=Path("."),
        generic_packet_path=generic_packet_path,
        index_path=None,
        timestamp_utc=str(committed["timestamp_utc"]),
    )

    assert committed == expected
    assert committed["status"] == "blocked_per_node_manifest_index_not_ready_for_agent_a_loader"
    assert committed["expected_per_node_unit_count"] == 345
    assert committed["missing_per_node_unit_count"] == 345
    assert committed["ready_for_agent_a_loader_execution"] is False
    assert committed["index_scope"] == {
        "filtered_scope": False,
        "full_declared_scope": True,
        "node_filter": None,
        "real_loader_ready_requires_full_declared_scope": True,
        "scenario_filter": None,
    }


def _write_synthetic_per_node_exports(
    tmp_path: Path,
    *,
    scenarios: tuple[str, ...] = ("low", "middle"),
    node_ids: tuple[str, ...] = ("load_000", "load_001"),
    artifact_status: str = "synthetic_fixture",
) -> dict[str, object]:
    source_path = Path("data/processed/elaad_profiles/component_outputs/ev_fixture_all.npz")
    _write_synthetic_multi_node_ev_npz(tmp_path / source_path, node_ids=node_ids)
    source_sha = ev_model._sha256_file(tmp_path / source_path)
    packet = _synthetic_generic_packet(source_path, source_sha, node_ids=node_ids)
    packet_path = tmp_path / "metadata/generic_packet.json"
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    export_ev_per_node_component_outputs(
        generic_packet=packet,
        base_dir=tmp_path,
        generic_packet_path=Path("metadata/generic_packet.json"),
        output_dir=Path("data/processed/elaad_profiles/component_outputs/per_node"),
        manifest_dir=Path("metadata/per_node"),
        checkpoint_path=Path("metadata/per_node_checkpoint.json"),
        timestamp_utc="2026-07-24T18:00:00Z",
        artifact_status=artifact_status,
        allow_accepted_status=artifact_status == "accepted",
        scenario_filter=scenarios,
    )
    return packet


def test_ev_per_node_manifest_index_loads_two_scenario_fixture_through_agent_a_boundary(tmp_path: Path) -> None:
    packet = _write_synthetic_per_node_exports(tmp_path)

    index = build_ev_per_node_manifest_index(
        generic_packet=packet,
        base_dir=tmp_path,
        generic_packet_path=Path("metadata/generic_packet.json"),
        output_dir=Path("data/processed/elaad_profiles/component_outputs/per_node"),
        manifest_dir=Path("metadata/per_node"),
        index_path=Path("metadata/per_node_index.json"),
        timestamp_utc="2026-07-24T18:01:00Z",
        scenario_filter=("low", "middle"),
        allow_synthetic_fixture=True,
        require_accepted_status=False,
    )

    assert index["status"] == "synthetic_per_node_manifest_index_ready_for_agent_a_loader_fixture"
    assert index["ready_for_agent_a_loader_execution"] is False
    assert index["ready_for_synthetic_agent_a_loader_fixture"] is True
    assert index["expected_per_node_unit_count"] == 4
    assert index["verified_per_node_unit_count"] == 4
    assert index["missing_per_node_units"] == []
    assert json.loads((tmp_path / "metadata/per_node_index.json").read_text(encoding="utf-8")) == index

    low = next(row for row in index["agent_a_loader_index_by_scenario"] if row["scenario"] == "low")
    manifests = [json.loads((tmp_path / path).read_text(encoding="utf-8")) for path in low["component_output_manifest_paths"]]
    outputs = load_component_adapter_outputs_from_npz_artifacts(
        manifests,
        _ev_loader_context(),
        repo_root=tmp_path,
        expected_calendar_id="planning-2035-europe-amsterdam-15min",
        expected_node_ids=("load_000", "load_001"),
        allow_synthetic_fixture=True,
    )
    assert tuple(output.node_id for output in outputs) == ("load_000", "load_001")
    assert all(output.kind == "ev" for output in outputs)


def test_ev_per_node_manifest_index_blocks_missing_per_node_outputs(tmp_path: Path) -> None:
    source_path = Path("data/processed/elaad_profiles/component_outputs/ev_fixture_all.npz")
    packet = _synthetic_generic_packet(source_path, "1" * 64)
    packet_path = tmp_path / "metadata/generic_packet.json"
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    index = build_ev_per_node_manifest_index(
        generic_packet=packet,
        base_dir=tmp_path,
        generic_packet_path=Path("metadata/generic_packet.json"),
        output_dir=Path("data/processed/elaad_profiles/component_outputs/per_node"),
        manifest_dir=Path("metadata/per_node"),
        index_path=Path("metadata/per_node_index.json"),
        timestamp_utc="2026-07-24T18:01:00Z",
        scenario_filter=("low", "middle"),
    )

    assert index["status"] == "blocked_per_node_manifest_index_not_ready_for_agent_a_loader"
    assert index["ready_for_agent_a_loader_execution"] is False
    assert index["expected_per_node_unit_count"] == 4
    assert index["missing_per_node_unit_count"] == 4
    assert index["verified_per_node_units"] == []


def test_ev_per_node_manifest_index_records_checksum_mismatch(tmp_path: Path) -> None:
    packet = _write_synthetic_per_node_exports(tmp_path)
    target = tmp_path / "data/processed/elaad_profiles/component_outputs/per_node/ev_ic1_candidate_component_output_low_load_000.npz"
    target.write_bytes(b"not the original deterministic npz")

    index = build_ev_per_node_manifest_index(
        generic_packet=packet,
        base_dir=tmp_path,
        generic_packet_path=Path("metadata/generic_packet.json"),
        output_dir=Path("data/processed/elaad_profiles/component_outputs/per_node"),
        manifest_dir=Path("metadata/per_node"),
        index_path=Path("metadata/per_node_index.json"),
        timestamp_utc="2026-07-24T18:01:00Z",
        scenario_filter=("low",),
        allow_synthetic_fixture=True,
        require_accepted_status=False,
    )

    assert index["status"] == "blocked_per_node_manifest_index_not_ready_for_agent_a_loader"
    assert index["checksum_mismatch_count"] == 1
    assert index["stale_per_node_units"][0]["blockers"] == ["array_checksum_mismatch"]


def test_ev_per_node_manifest_index_blocks_filtered_accepted_scope_for_real_loader(tmp_path: Path) -> None:
    packet = _write_synthetic_per_node_exports(tmp_path, scenarios=("low",), artifact_status="accepted")

    index = build_ev_per_node_manifest_index(
        generic_packet=packet,
        base_dir=tmp_path,
        generic_packet_path=Path("metadata/generic_packet.json"),
        output_dir=Path("data/processed/elaad_profiles/component_outputs/per_node"),
        manifest_dir=Path("metadata/per_node"),
        index_path=Path("metadata/per_node_index.json"),
        timestamp_utc="2026-07-24T18:02:00Z",
        scenario_filter=("low",),
    )

    assert index["status"] == "blocked_filtered_per_node_manifest_index_not_real_loader_ready"
    assert index["verified_per_node_unit_count"] == 2
    assert index["missing_per_node_unit_count"] == 0
    assert index["ready_for_agent_a_loader_execution"] is False
    assert index["index_scope"]["filtered_scope"] is True
    assert index["index_scope"]["full_declared_scope"] is False
    assert "E3.S2a-FILTERED-INDEX-NOT-REAL-LOADER-READY" in index["remaining_blockers"]


def test_ev_per_node_manifest_index_allows_unfiltered_complete_accepted_fixture(tmp_path: Path) -> None:
    packet = _write_synthetic_per_node_exports(
        tmp_path,
        scenarios=("high", "low", "middle"),
        artifact_status="accepted",
    )

    index = build_ev_per_node_manifest_index(
        generic_packet=packet,
        base_dir=tmp_path,
        generic_packet_path=Path("metadata/generic_packet.json"),
        output_dir=Path("data/processed/elaad_profiles/component_outputs/per_node"),
        manifest_dir=Path("metadata/per_node"),
        index_path=Path("metadata/per_node_index.json"),
        timestamp_utc="2026-07-24T18:02:00Z",
    )

    assert index["status"] == "accepted_per_node_manifest_index_ready_for_agent_a_loader"
    assert index["expected_per_node_unit_count"] == 6
    assert index["verified_per_node_unit_count"] == 6
    assert index["ready_for_agent_a_loader_execution"] is True
    assert index["ready_for_synthetic_agent_a_loader_fixture"] is False
    assert index["index_scope"]["filtered_scope"] is False
    assert index["remaining_blockers"] == []


def test_ev_per_node_manifest_index_rejects_duplicate_scenario_and_node_metadata(tmp_path: Path) -> None:
    source_path = Path("data/processed/elaad_profiles/component_outputs/ev_fixture_all.npz")
    _write_synthetic_multi_node_ev_npz(tmp_path / source_path)
    packet = _synthetic_generic_packet(source_path, ev_model._sha256_file(tmp_path / source_path))
    packet["scenario_manifests"][1]["scenario"] = "high"

    with pytest.raises(EVComponentOutputVerificationError, match="duplicate scenario"):
        build_ev_per_node_manifest_index(
            generic_packet=packet,
            base_dir=tmp_path,
            timestamp_utc="2026-07-24T18:01:00Z",
        )

    packet = _synthetic_generic_packet(source_path, ev_model._sha256_file(tmp_path / source_path), node_ids=("load_000", "load_000"))
    with pytest.raises(EVComponentOutputVerificationError, match="duplicate node IDs"):
        build_ev_per_node_manifest_index(
            generic_packet=packet,
            base_dir=tmp_path,
            timestamp_utc="2026-07-24T18:01:00Z",
        )


def test_ev_per_node_manifest_index_rejects_policy_violations_and_unsafe_tokens(tmp_path: Path) -> None:
    source_path = Path("data/processed/elaad_profiles/component_outputs/ev_fixture_all.npz")
    packet = _synthetic_generic_packet(source_path, "1" * 64)
    for key in ("final_low_middle_high_branch_selected", "held_out_access", "quarantined_access", "elaad_api_calls", "m_sufficiency_claimed"):
        broken = json.loads(json.dumps(packet))
        broken["policy"][key] = True
        with pytest.raises(EVComponentOutputVerificationError, match=f"{key}=False"):
            build_ev_per_node_manifest_index(
                generic_packet=broken,
                base_dir=tmp_path,
                timestamp_utc="2026-07-24T18:01:00Z",
            )

    broken = json.loads(json.dumps(packet))
    broken["decision_ids"] = [*broken["decision_ids"], "EV-FUTURE-PLACEHOLDER"]
    with pytest.raises(EVComponentOutputVerificationError, match="Unsafe approval/source token"):
        build_ev_per_node_manifest_index(
            generic_packet=broken,
            base_dir=tmp_path,
            timestamp_utc="2026-07-24T18:01:00Z",
        )


def test_ev_per_node_manifest_index_blocks_nonaccepted_status_before_real_loader_use(tmp_path: Path) -> None:
    packet = _write_synthetic_per_node_exports(tmp_path)

    index = build_ev_per_node_manifest_index(
        generic_packet=packet,
        base_dir=tmp_path,
        generic_packet_path=Path("metadata/generic_packet.json"),
        output_dir=Path("data/processed/elaad_profiles/component_outputs/per_node"),
        manifest_dir=Path("metadata/per_node"),
        index_path=Path("metadata/per_node_index.json"),
        timestamp_utc="2026-07-24T18:01:00Z",
        scenario_filter=("low",),
    )

    assert index["ready_for_agent_a_loader_execution"] is False
    assert index["stale_per_node_unit_count"] == 2
    assert "manifest_artifact_status_not_allowed" in index["stale_per_node_units"][0]["blockers"]


def test_ev_per_node_manifest_index_rejects_stale_generic_or_unsafe_paths(tmp_path: Path) -> None:
    packet = _write_synthetic_per_node_exports(tmp_path)
    manifest_path = tmp_path / "metadata/per_node/ev_2035_low_load_000.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["array_path"] = "data/metadata/ev_adoption/generic_component_output_manifests/ev_2035_low.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    index = build_ev_per_node_manifest_index(
        generic_packet=packet,
        base_dir=tmp_path,
        generic_packet_path=Path("metadata/generic_packet.json"),
        output_dir=Path("data/processed/elaad_profiles/component_outputs/per_node"),
        manifest_dir=Path("metadata/per_node"),
        index_path=Path("metadata/per_node_index.json"),
        timestamp_utc="2026-07-24T18:01:00Z",
        scenario_filter=("low",),
        allow_synthetic_fixture=True,
        require_accepted_status=False,
    )

    blockers = set(index["stale_per_node_units"][0]["blockers"])
    assert "manifest_array_path_mismatch" in blockers
    assert "manifest_array_path_forbidden" in blockers

    broken = json.loads(json.dumps(packet))
    broken["scenario_manifests"][0]["array_path"] = "data/raw/elaad_profiles/held_out.npz"
    with pytest.raises(EVComponentOutputVerificationError, match="held-out/quarantined/raw/generic source paths"):
        build_ev_per_node_manifest_index(
            generic_packet=broken,
            base_dir=tmp_path,
            timestamp_utc="2026-07-24T18:01:00Z",
        )


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


def test_committed_a014_executable_adoption_artifact_matches_builder() -> None:
    config_path = Path("configs/scenarios.yaml")
    preview_path = Path("data/metadata/ev_adoption/e2_s6_a014_alkmaar_allocation_preview.json")
    config = load_adoption_scenarios_config(config_path)

    expected = a014_executable_adoption_artifact(
        config,
        source_config_path=config_path.as_posix(),
        source_config_sha256=_git_blob_sha256(config_path),
        preview_artifact_path=preview_path.as_posix(),
        preview_artifact_sha256=_git_blob_sha256(preview_path),
    )
    committed = json.loads(
        Path(
            "data/metadata/ev_adoption/e2_s6_a014_alkmaar_executable_adoption_artifact.json"
        ).read_text(encoding="utf-8")
    )

    assert committed == expected
    assert committed["artifact_type"] == "a014_executable_ev_adoption_allocation_artifact"
    assert committed["status"] == "accepted_executable_per_node_ev_adoption_allocation"
    assert committed["decision_ids"] == ["EV-007", "EV-007A", "A-014"]
    assert committed["scenario_totals"] == {
        "high": {"home": 10343, "public": 6138},
        "low": {"home": 7992, "public": 4183},
        "middle": {"home": 9386, "public": 5127},
    }
    assert committed["node_axis"]["node_count"] == 115
    assert committed["scenario_selection"]["final_low_middle_high_branch_selected"] is False
    assert committed["policy"] == {
        "executable_adoption_counts": True,
        "candidate_profile_arrays_loaded": False,
        "held_out_access": False,
        "quarantined_access": False,
        "integrated_analysis_performed": False,
        "event_or_p_e_analysis_performed": False,
        "capacity_screen_performed": False,
        "final_low_middle_high_branch_selected": False,
        "m_sufficiency_claimed": False,
        "manuscript_numbers_produced": False,
    }


def test_a014_executable_adoption_artifact_conserves_all_node_totals() -> None:
    artifact = a014_executable_adoption_artifact(load_adoption_scenarios_config(Path("configs/scenarios.yaml")))

    assert len(artifact["node_axis"]["node_ids"]) == 115
    for record in artifact["scenario_allocations"]:
        node_rows = record["node_allocations"]
        assert len(node_rows) == 115
        assert sum(row["home_charge_points"] for row in node_rows) == record["home_charge_points"]
        assert sum(row["public_charge_points"] for row in node_rows) == record["public_charge_points"]
        assert all(row["home_charge_points"] >= 0 and row["public_charge_points"] >= 0 for row in node_rows)


def test_a014_executable_adoption_artifact_rejects_unapproved_statuses() -> None:
    config = load_adoption_scenarios_config(Path("configs/scenarios.yaml"))
    config["local_grid_scenarios"]["status"] = "proposed"
    config["local_grid_scenarios"]["scenarios"] = []
    with pytest.raises(ValueError, match="approved EV-007A"):
        a014_executable_adoption_artifact(config)

    config = load_adoption_scenarios_config(Path("configs/scenarios.yaml"))
    config["allocation"]["status"] = "proposed"
    with pytest.raises(ValueError, match="approved A-014"):
        a014_executable_adoption_artifact(config)


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


def _committed_ev_component_scaffold_inputs() -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object], str]:
    base = Path("data/metadata/ev_adoption")
    adapter = json.loads((base / "e2_s2_ev_ic1_candidate_adapter_artifact.json").read_text(encoding="utf-8"))
    public_capacity = json.loads((base / "e2_s2_public_set_b_capacity_allocation_readiness.json").read_text(encoding="utf-8"))
    member_reference = json.loads((base / "e2_s2_ev_ic1_candidate_member_reference.json").read_text(encoding="utf-8"))
    selection_bytes = (base / "e2_s2_ev005b_candidate_selection_manifests.json.gz").read_bytes()
    selection_manifest = json.loads(gzip.decompress(selection_bytes))
    import hashlib

    return adapter, public_capacity, member_reference, selection_manifest, hashlib.sha256(selection_bytes).hexdigest()


def test_ev_ic1_component_input_scaffold_bridges_to_ic1_accepted_artifact() -> None:
    adapter, public_capacity, member_reference, selection_manifest, selection_sha = _committed_ev_component_scaffold_inputs()

    artifact = ev_ic1_component_input_scaffold_artifact(
        adapter,
        public_capacity,
        member_reference,
        selection_manifest,
        candidate_selection_manifest_sha256=selection_sha,
    )

    assert artifact["artifact_type"] == "ev_ic1_component_input_scaffold"
    assert artifact["status"] == "accepted_metadata_only_for_ic1_component_input_scaffold"
    assert artifact["source_ids"] == ["D-002", "D-010"]
    assert artifact["policy"] == {
        "candidate_libraries_only": True,
        "held_out_access": False,
        "quarantined_access": False,
        "profile_arrays_loaded": False,
        "integrated_analysis_performed": False,
        "event_or_p_e_analysis_performed": False,
        "capacity_screen_performed": False,
        "manuscript_numbers_produced": False,
        "m_sufficiency_claimed": False,
        "final_low_middle_high_branch_selected": False,
    }
    assert artifact["calendar_mapping"]["rule_id"] == "EV-CAL-001"
    assert artifact["calendar_mapping"]["n_timesteps"] == EXPECTED_FULL_YEAR_STEPS
    assert len(artifact["ic1_accepted_component_adapter_artifact"]["node_ids"]) == 115

    bridge = AcceptedComponentAdapterArtifact(**artifact["ic1_accepted_component_adapter_artifact"])
    assert bridge.kind == "ev"
    assert bridge.calendar_id == "planning-2035-europe-amsterdam-15min"
    assert bridge.timestep_seconds == 900

    totals = {
        row["scenario"]: (row["home_charge_points"], row["public_charge_points"])
        for row in artifact["scenario_inputs"]
    }
    assert totals == {"high": (10343, 6138), "low": (7992, 4183), "middle": (9386, 5127)}
    for scenario in artifact["scenario_inputs"]:
        assert scenario["node_count"] == 115
        assert sum(row["home_charge_points"] for row in scenario["node_inputs"]) == scenario["home_charge_points"]
        assert sum(row["public_charge_points"] for row in scenario["node_inputs"]) == scenario["public_charge_points"]
        assert all(
            sum(row["public_charge_points_by_capacity_class"].values()) == row["public_charge_points"]
            for row in scenario["node_inputs"]
        )


def test_ev_ic1_component_input_scaffold_rejects_unsafe_inputs() -> None:
    adapter, public_capacity, member_reference, selection_manifest, selection_sha = _committed_ev_component_scaffold_inputs()

    unsafe_adapter = json.loads(json.dumps(adapter))
    unsafe_adapter["policy"]["held_out_access"] = True
    with pytest.raises(ValueError, match="held-out access"):
        ev_ic1_component_input_scaffold_artifact(
            unsafe_adapter,
            public_capacity,
            member_reference,
            selection_manifest,
            candidate_selection_manifest_sha256=selection_sha,
        )

    unsafe_selection = json.loads(json.dumps(selection_manifest))
    unsafe_selection["policy"]["profile_arrays_loaded"] = True
    with pytest.raises(ValueError, match="profile_arrays_loaded"):
        ev_ic1_component_input_scaffold_artifact(
            adapter,
            public_capacity,
            member_reference,
            unsafe_selection,
            candidate_selection_manifest_sha256=selection_sha,
        )

    mismatched = json.loads(json.dumps(selection_manifest))
    mismatched["scenarios"][0]["home_required_members"] += 1
    with pytest.raises(ValueError, match="selection totals"):
        ev_ic1_component_input_scaffold_artifact(
            adapter,
            public_capacity,
            member_reference,
            mismatched,
            candidate_selection_manifest_sha256=selection_sha,
        )


def test_committed_ev_ic1_component_input_scaffold_matches_builder() -> None:
    adapter, public_capacity, member_reference, selection_manifest, selection_sha = _committed_ev_component_scaffold_inputs()
    expected = ev_ic1_component_input_scaffold_artifact(
        adapter,
        public_capacity,
        member_reference,
        selection_manifest,
        candidate_selection_manifest_sha256=selection_sha,
    )
    committed = json.loads(
        Path("data/metadata/ev_adoption/e2_s2_ev_ic1_component_input_scaffold.json").read_text(
            encoding="utf-8"
        )
    )

    assert committed == expected
    assert committed["loading_preconditions"] == {
        "verify_candidate_selection_manifest_set_sha256_before_use": True,
        "verify_candidate_processed_file_checksums_before_profile_loading": True,
        "load_only_candidate_processed_profile_arrays": True,
        "apply_ev_cal001_ordinal_mapping_before_ic1_aggregation": True,
    }
