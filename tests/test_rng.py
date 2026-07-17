from __future__ import annotations

import numpy as np
import pytest

from src.rng import (
    AleatoryRealization,
    ComponentSelection,
    SeedTree,
    assert_crn_equivalent,
    component_seed,
    sample_seed,
)


def test_sample_seed_is_stable_and_sample_specific() -> None:
    assert sample_seed(20260717, 3) == sample_seed(20260717, 3)
    assert sample_seed(20260717, 3) != sample_seed(20260717, 4)

    with pytest.raises(ValueError, match="sample_index"):
        sample_seed(1, -1)


def test_crn_branch_reuses_aleatory_streams_across_alpha_endpoint_and_treatment() -> None:
    tree = SeedTree(root_seed=20260717)
    ev_stream = tree.component_stream(11, "ev_home")
    selection = ComponentSelection(
        component="ev_home",
        source_batch_id="elaad_set_a_seed140001",
        source_member_id="profile_140001_007",
        selection_index=7,
        stream_id=ev_stream.stream_id,
    )
    realization = tree.realization(
        11,
        component_names=("baseline", "hp", "pv"),
        component_selections=(selection,),
        shared_driver_ids={"weather": "knmi_paired_member_042"},
    )

    lower = realization.branch(
        alpha=0.0,
        endpoint="lower",
        treatment="no-flex",
    )
    upper = realization.branch(
        alpha=1.0,
        endpoint="upper",
        treatment="smart-flex",
    )

    assert_crn_equivalent([lower, upper])
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
    realization = tree.realization(
        2,
        component_names=("hp", "pv"),
        shared_driver_ids={"weather": "knmi_temperature_irradiance_pair_003"},
    )
    branch = realization.branch(
        alpha="0.5",
        endpoint="lower",
        treatment="baseline",
    )
    manifest = branch.manifest_record()
    streams = {record["component"]: record for record in manifest["component_streams"]}

    assert manifest["shared_driver_ids"] == {
        "weather": "knmi_temperature_irradiance_pair_003"
    }
    assert streams["hp"]["seed"] != streams["pv"]["seed"]


def test_component_selections_are_manifestable_and_sorted() -> None:
    tree = SeedTree(root_seed=123)
    realization = tree.realization(
        0,
        component_selections=(
            ComponentSelection(
                component="ev_home",
                source_batch_id="candidate_set_a",
                source_member_id="profile_140001_002",
                selection_index=2,
                stream_id=tree.component_stream(0, "ev_home").stream_id,
            ),
            ComponentSelection(
                component="baseline",
                source_member_id="simbench_profile_001",
                stream_id=tree.component_stream(0, "baseline").stream_id,
            ),
        ),
    )
    branch = realization.branch(
        alpha=0.25,
        endpoint="upper",
        treatment="no-flex",
    )

    manifest = branch.manifest_record()

    assert manifest["root_seed"] == 123
    assert manifest["sample_seed"] == tree.sample_seed(0)
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
    assert {record["component"] for record in manifest["component_streams"]} == {
        "baseline",
        "ev_home",
    }


def test_root_and_sample_seed_prevent_empty_stream_fingerprint_collision() -> None:
    first = SeedTree(root_seed=1).realization(0).branch(
        alpha=0.0, endpoint="lower", treatment="no-flex"
    )
    second = SeedTree(root_seed=2).realization(0).branch(
        alpha=0.0, endpoint="lower", treatment="no-flex"
    )

    assert first.manifest_record()["component_streams"] == []
    assert first.manifest_record()["root_seed"] == 1
    assert first.manifest_record()["sample_seed"] != second.manifest_record()["sample_seed"]
    assert first.aleatory_fingerprint() != second.aleatory_fingerprint()


def test_mismatched_member_or_driver_cannot_pass_crn_equivalence() -> None:
    tree = SeedTree(root_seed=20260717)
    first_stream = tree.component_stream(4, "ev_home")
    first = tree.realization(
        4,
        component_selections=(
            ComponentSelection(
                component="ev_home",
                source_member_id="profile_140001_001",
                stream_id=first_stream.stream_id,
            ),
        ),
        shared_driver_ids={"weather": "weather_member_001"},
    ).branch(alpha=0.0, endpoint="lower", treatment="no-flex")
    different_member = tree.realization(
        4,
        component_selections=(
            ComponentSelection(
                component="ev_home",
                source_member_id="profile_140001_002",
                stream_id=first_stream.stream_id,
            ),
        ),
        shared_driver_ids={"weather": "weather_member_001"},
    ).branch(alpha=1.0, endpoint="upper", treatment="no-flex")
    different_driver = tree.realization(
        4,
        component_selections=(
            ComponentSelection(
                component="ev_home",
                source_member_id="profile_140001_001",
                stream_id=first_stream.stream_id,
            ),
        ),
        shared_driver_ids={"weather": "weather_member_002"},
    ).branch(alpha=1.0, endpoint="upper", treatment="no-flex")

    with pytest.raises(ValueError, match="same aleatory realization"):
        assert_crn_equivalent([first, different_member])
    with pytest.raises(ValueError, match="same aleatory realization"):
        assert_crn_equivalent([first, different_driver])


def test_selection_stream_id_must_match_realization_stream() -> None:
    tree = SeedTree(root_seed=1)
    selection = ComponentSelection(
        component="ev_home",
        source_member_id="profile_140001_001",
        stream_id="sample_0:baseline",
    )

    with pytest.raises(ValueError, match="stream_id"):
        AleatoryRealization(
            tree=tree,
            sample_index=0,
            streams={"ev_home": tree.component_stream(0, "ev_home")},
            component_selections=(selection,),
        )


def test_invalid_names_are_rejected() -> None:
    tree = SeedTree(root_seed=1)

    with pytest.raises(ValueError, match="component"):
        tree.component_stream(0, "")
    with pytest.raises(ValueError, match="source_member_id"):
        ComponentSelection(component="ev_home", source_member_id="", stream_id="s")
