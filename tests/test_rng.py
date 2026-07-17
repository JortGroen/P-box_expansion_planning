from __future__ import annotations

import numpy as np
import pytest

from src.rng import ComponentSelection, SeedTree, component_seed, sample_seed


def test_sample_seed_is_stable_and_sample_specific() -> None:
    assert sample_seed(20260717, 3) == sample_seed(20260717, 3)
    assert sample_seed(20260717, 3) != sample_seed(20260717, 4)

    with pytest.raises(ValueError, match="sample_index"):
        sample_seed(1, -1)


def test_crn_branch_reuses_aleatory_streams_across_alpha_endpoint_and_treatment() -> None:
    tree = SeedTree(root_seed=20260717)
    realization = tree.realization(11, component_names=("baseline", "ev_home", "hp", "pv"))
    ev_stream = realization.stream("ev_home")
    selection = ComponentSelection(
        component="ev_home",
        source_batch_id="elaad_set_a_seed140001",
        source_member_id="profile_140001_007",
        selection_index=7,
        stream_id=ev_stream.stream_id,
    )

    lower = realization.branch(
        alpha=0.0,
        endpoint="lower",
        treatment="no-flex",
        component_selections=(selection,),
        shared_driver_ids={"weather": "knmi_paired_member_042"},
    )
    upper = realization.branch(
        alpha=1.0,
        endpoint="upper",
        treatment="smart-flex",
        component_selections=(selection,),
        shared_driver_ids={"weather": "knmi_paired_member_042"},
    )

    assert lower.aleatory_fingerprint() == upper.aleatory_fingerprint()
    assert lower.manifest_record()["branch"] != upper.manifest_record()["branch"]
    np.testing.assert_array_equal(
        realization.stream("ev_home").rng().integers(0, 10_000, size=8),
        realization.stream("ev_home").rng().integers(0, 10_000, size=8),
    )


def test_component_streams_are_separated_within_one_realization() -> None:
    tree = SeedTree(root_seed=42)
    realization = tree.realization(5, component_names=("baseline", "ev_home", "hp", "pv"))

    seeds = {component: realization.stream(component).seed for component in realization.streams}

    assert len(set(seeds.values())) == len(seeds)
    assert seeds["ev_home"] == component_seed(tree.root_seed, 5, "ev_home")
    assert not np.array_equal(
        realization.stream("ev_home").rng().integers(0, 2**31, size=12),
        realization.stream("baseline").rng().integers(0, 2**31, size=12),
    )


def test_physical_shared_driver_is_manifested_without_merging_streams() -> None:
    tree = SeedTree(root_seed=99)
    realization = tree.realization(2, component_names=("hp", "pv"))
    branch = realization.branch(
        alpha="0.5",
        endpoint="lower",
        treatment="baseline",
        shared_driver_ids={"weather": "knmi_temperature_irradiance_pair_003"},
    )
    manifest = branch.manifest_record()
    streams = {record["component"]: record for record in manifest["component_streams"]}

    assert manifest["shared_driver_ids"] == {
        "weather": "knmi_temperature_irradiance_pair_003"
    }
    assert streams["hp"]["seed"] != streams["pv"]["seed"]


def test_component_selections_are_manifestable_and_sorted() -> None:
    tree = SeedTree(root_seed=123)
    realization = tree.realization(0, component_names=("ev_home", "baseline"))
    branch = realization.branch(
        alpha=0.25,
        endpoint="upper",
        treatment="no-flex",
        component_selections=(
            ComponentSelection(
                component="ev_home",
                source_batch_id="candidate_set_a",
                source_member_id="profile_140001_002",
                selection_index=2,
                stream_id=realization.stream("ev_home").stream_id,
            ),
            ComponentSelection(
                component="baseline",
                source_member_id="simbench_profile_001",
                stream_id=realization.stream("baseline").stream_id,
            ),
        ),
    )

    manifest = branch.manifest_record()

    assert manifest["component_selections"] == [
        {
            "component": "baseline",
            "source_member_id": "simbench_profile_001",
            "stream_id": "sample_0:baseline",
        },
        {
            "component": "ev_home",
            "selection_index": 2,
            "source_batch_id": "candidate_set_a",
            "source_member_id": "profile_140001_002",
            "stream_id": "sample_0:ev_home",
        },
    ]


def test_invalid_names_are_rejected() -> None:
    tree = SeedTree(root_seed=1)

    with pytest.raises(ValueError, match="component"):
        tree.component_stream(0, "")
    with pytest.raises(ValueError, match="source_member_id"):
        ComponentSelection(component="ev_home", source_member_id="", stream_id="s")
