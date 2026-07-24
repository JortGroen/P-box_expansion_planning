from __future__ import annotations

import numpy as np
import pytest

from src.evaluator_sum import (
    DEFAULT_THRESHOLD_PU,
    LoadingTrajectoryCapacityProvenance,
    build_tier1_loading_trajectory_scaffold,
    count_import_overload_episodes,
    evaluate_net_load_tier1,
    evaluate_tier1,
    radial_downstream_sum,
)
from src.contracts.loading_trajectory import validate_loading_trajectory_result
from src.contracts.net_load import (
    ComponentProvenance,
    NetLoadComponent,
    NetLoadLoadingInputReadiness,
    build_net_load_result,
)


def test_radial_downstream_sum_matches_hand_calculation() -> None:
    values = np.array(
        [
            [1.0, 10.0],
            [2.0, 20.0],
            [3.0, 30.0],
            [4.0, 40.0],
        ]
    )

    downstream = radial_downstream_sum(values, parent_index=[None, 0, 1, 1])

    assert downstream.tolist() == [
        [10.0, 100.0],
        [9.0, 90.0],
        [3.0, 30.0],
        [4.0, 40.0],
    ]


def test_import_loading_and_exact_four_step_event_are_hand_computed() -> None:
    nodal_p = np.array(
        [
            [0.0, 0.0, 0.0, 0.0],
            [600.0, 600.0, 600.0, 600.0],
            [300.0, 300.0, 300.0, 300.0],
            [400.0, 400.0, 400.0, 400.0],
        ]
    )
    nodal_q = np.zeros_like(nodal_p)

    result = evaluate_tier1(
        nodal_p,
        nodal_q,
        parent_index=[None, 0, 1, 1],
        decision_node=0,
        s_nom_agg_kva=1_000.0,
    )

    assert result.p_net_kw.tolist() == [1300.0, 1300.0, 1300.0, 1300.0]
    assert result.screening_loading_pu.tolist() == [1.3, 1.3, 1.3, 1.3]
    assert result.import_loading_pu.tolist() == [1.3, 1.3, 1.3, 1.3]
    assert result.export_loading_pu.tolist() == [0.0, 0.0, 0.0, 0.0]
    assert result.overload is True
    assert result.overload_episode_count == 1
    assert result.longest_import_run_steps == 4
    assert result.primary_probability_domain is True


def test_reverse_export_reports_export_loading_without_primary_event() -> None:
    nodal_p = np.array([[-1200.0, -1200.0, -1200.0, -1200.0]])
    nodal_q = np.array([[500.0, 500.0, 500.0, 500.0]])

    result = evaluate_tier1(nodal_p, nodal_q, s_nom_agg_kva=1_300.0)

    assert result.screening_loading_pu.tolist() == [1.0, 1.0, 1.0, 1.0]
    assert result.import_loading_pu.tolist() == [0.0, 0.0, 0.0, 0.0]
    assert result.export_loading_pu.tolist() == [1.0, 1.0, 1.0, 1.0]
    assert result.import_mask.tolist() == [False, False, False, False]
    assert result.export_mask.tolist() == [True, True, True, True]
    assert result.overload is False


def test_zero_crossings_belong_to_neither_direction_but_screening_remains() -> None:
    nodal_p = np.array([[1_200.0, 0.0, -1_200.0]])
    nodal_q = np.array([[0.0, 1_200.0, 0.0]])

    result = evaluate_tier1(nodal_p, nodal_q, s_nom_agg_kva=1_200.0)

    assert result.screening_loading_pu.tolist() == [1.0, 1.0, 1.0]
    assert result.import_loading_pu.tolist() == [1.0, 0.0, 0.0]
    assert result.export_loading_pu.tolist() == [0.0, 0.0, 1.0]
    assert result.zero_mask.tolist() == [False, True, False]
    assert result.overload is False


def test_direction_flip_resets_episode_counter() -> None:
    nodal_p = np.array([[1_200.0, 1_200.0, -1_200.0, 1_200.0, 1_200.0, 1_200.0, 1_200.0]])
    nodal_q = np.zeros_like(nodal_p)

    result = evaluate_tier1(nodal_p, nodal_q, s_nom_agg_kva=1_000.0)

    assert result.import_loading_pu.tolist() == [1.2, 1.2, 0.0, 1.2, 1.2, 1.2, 1.2]
    assert result.overload is True
    assert result.overload_episode_count == 1
    assert result.longest_import_run_steps == 4


def test_three_qualifying_steps_do_not_trigger_but_four_do() -> None:
    assert count_import_overload_episodes([1.11, 1.11, 1.11], min_consecutive_steps=4) == (0, 3)
    assert count_import_overload_episodes([1.11, 1.11, 1.11, 1.11], min_consecutive_steps=4) == (1, 4)


def test_default_g0_a3_threshold_is_strictly_greater_than_1_0() -> None:
    assert DEFAULT_THRESHOLD_PU == 1.0
    assert count_import_overload_episodes([1.0, 1.0, 1.0, 1.0]) == (0, 0)
    assert count_import_overload_episodes([1.0001, 1.0001, 1.0001, 1.0001]) == (1, 4)

def test_declared_sensitivity_thresholds_are_explicit() -> None:
    assert count_import_overload_episodes([1.05, 1.05, 1.05, 1.05], threshold_pu=1.1) == (0, 0)
    assert count_import_overload_episodes([1.1001, 1.1001, 1.1001, 1.1001], threshold_pu=1.1) == (1, 4)
    assert count_import_overload_episodes([1.15, 1.15, 1.15, 1.15], threshold_pu=1.2) == (0, 0)
    assert count_import_overload_episodes([1.2001, 1.2001, 1.2001, 1.2001], threshold_pu=1.2) == (1, 4)

def test_full_year_behavior_detects_late_import_episode() -> None:
    nodal_p = np.full((1, 35_040), 100.0)
    nodal_q = np.zeros_like(nodal_p)
    nodal_p[0, -4:] = 1_200.0

    result = evaluate_tier1(nodal_p, nodal_q, s_nom_agg_kva=1_000.0)

    assert len(result.import_loading_pu) == 35_040
    assert result.overload is True
    assert result.overload_episode_count == 1
    assert result.longest_import_run_steps == 4
    assert result.primary_probability_domain is True


def test_window_set_is_diagnostic_not_primary_probability_domain() -> None:
    nodal_p = np.array([[100.0, 1_200.0, 1_200.0, 1_200.0, 1_200.0, 100.0]])
    nodal_q = np.zeros_like(nodal_p)

    result = evaluate_tier1(
        nodal_p,
        nodal_q,
        s_nom_agg_kva=1_000.0,
        time_domain="window_set",
        window_indices=[1, 2, 3, 4],
    )

    assert result.overload is True
    assert result.primary_probability_domain is False
    assert result.time_domain == "window_set"
    assert result.threshold_pu == DEFAULT_THRESHOLD_PU


def test_preserves_unwidened_direction_masks_for_later_interval_loading() -> None:
    nodal_p = np.array([[1_100.0, -1_100.0, 0.0]])
    nodal_q = np.zeros_like(nodal_p)

    result = evaluate_tier1(nodal_p, nodal_q, s_nom_agg_kva=1_000.0)
    widened_loading = result.screening_loading_pu + 0.2

    assert widened_loading.tolist() == pytest.approx([1.3, 1.3, 0.2])
    assert np.where(result.import_mask, widened_loading, 0.0).tolist() == pytest.approx([1.3, 0.0, 0.0])
    assert result.export_mask.tolist() == [False, True, False]
    assert result.zero_mask.tolist() == [False, False, True]


def test_invalid_window_arguments_are_rejected() -> None:
    nodal_p = np.array([[1.0, 2.0]])
    nodal_q = np.zeros_like(nodal_p)

    with pytest.raises(ValueError, match="window_indices are required"):
        evaluate_tier1(nodal_p, nodal_q, s_nom_agg_kva=1.0, time_domain="window_set")

    with pytest.raises(ValueError, match="only allowed"):
        evaluate_tier1(nodal_p, nodal_q, s_nom_agg_kva=1.0, window_indices=[0])


def _net_load_calendar() -> np.ndarray:
    return np.array(
        [
            "2035-01-01T00:00:00",
            "2035-01-01T00:15:00",
            "2035-01-01T00:30:00",
            "2035-01-01T00:45:00",
        ],
        dtype="datetime64[s]",
    )


def _net_load_component(
    component_id: str,
    kind: str,
    node_id: str,
    p_kw: list[float],
    q_kvar: list[float],
) -> NetLoadComponent:
    return NetLoadComponent(
        provenance=ComponentProvenance(
            component_id=component_id,
            kind=kind,
            node_id=node_id,
            member_id=f"{component_id}-member",
            source_id="synthetic-tier1-fixture",
            metadata={"fixture": "ic1-to-tier1"},
        ),
        p_kw=np.array(p_kw, dtype=float),
        q_kvar=np.array(q_kvar, dtype=float),
        timestamps=_net_load_calendar(),
    )


def test_net_load_result_routes_to_loading_trajectory_contract() -> None:
    net_load = build_net_load_result(
        [
            _net_load_component("baseline-a", "baseline", "node-a", [8.0, 8.0, 8.0, 8.0], [6.0, 6.0, 6.0, 6.0]),
            _net_load_component("ev-a", "ev", "node-a", [1.0, 2.0, 3.0, 4.0], [0.0, 0.0, 0.0, 0.0]),
            _net_load_component("pv-b", "pv", "node-b", [0.0, -2.0, -4.0, -6.0], [0.0, 0.0, 0.0, 0.0]),
        ],
        metadata={"scaffold": "synthetic-ic1-to-tier1"},
    )

    result = evaluate_net_load_tier1(net_load, s_nom_agg_kva=10.0)

    validate_loading_trajectory_result(result)
    np.testing.assert_allclose(result.p_net_kw, np.array([9.0, 8.0, 7.0, 6.0]))
    np.testing.assert_allclose(result.q_net_kvar, np.array([6.0, 6.0, 6.0, 6.0]))
    np.testing.assert_allclose(result.s_net_kva, np.hypot(result.p_net_kw, result.q_net_kvar))
    assert result.import_mask.tolist() == [True, True, True, True]
    assert result.export_mask.tolist() == [False, False, False, False]
    assert result.zero_mask.tolist() == [False, False, False, False]
    assert result.time_domain == "full_year"
    assert result.primary_probability_domain is True


def test_net_load_to_tier1_preserves_unwidened_direction_gates() -> None:
    net_load = build_net_load_result(
        [
            _net_load_component("baseline-a", "baseline", "node-a", [3.0, 0.0, 0.0, 4.0], [4.0, 5.0, 0.0, 3.0]),
            _net_load_component("pv-a", "pv", "node-a", [0.0, -2.0, 0.0, -8.0], [0.0, 0.0, 0.0, 0.0]),
        ]
    )

    result = evaluate_net_load_tier1(net_load, s_nom_agg_kva=5.0)

    np.testing.assert_allclose(result.p_net_kw, np.array([3.0, -2.0, 0.0, -4.0]))
    np.testing.assert_allclose(result.screening_loading_pu, np.array([1.0, np.hypot(-2.0, 5.0) / 5.0, 0.0, 1.0]))
    assert result.import_mask.tolist() == [True, False, False, False]
    assert result.export_mask.tolist() == [False, True, False, True]
    assert result.zero_mask.tolist() == [False, False, True, False]
    assert result.import_loading_pu.tolist() == pytest.approx([1.0, 0.0, 0.0, 0.0])
    assert result.export_loading_pu.tolist() == pytest.approx([0.0, np.hypot(-2.0, 5.0) / 5.0, 0.0, 1.0])


def test_net_load_to_tier1_rejects_invalid_ic1_payload_before_evaluation() -> None:
    invalid = build_net_load_result(
        [
            _net_load_component(
                "baseline-a",
                "baseline",
                "node-a",
                [1.0, 1.0, 1.0, 1.0],
                [0.0, 0.0, 0.0, 0.0],
            )
        ]
    )
    invalid.p_net_kw[0, 1] = np.nan

    with pytest.raises(ValueError, match="net-load arrays must contain only finite"):
        evaluate_net_load_tier1(invalid, s_nom_agg_kva=1.0)


def _capacity_provenance(**overrides: object) -> LoadingTrajectoryCapacityProvenance:
    values: dict[str, object] = {
        "s_nom_agg_kva": 10.0,
        "convention_status": "pending_g1_a2_e3_s2b",
        "transformer_indices": (0, 1),
        "unit_nameplate_kva": (5.0, 5.0),
        "source": "synthetic-headroom-fixture",
        "metadata": {"scaffold_only": True},
    }
    values.update(overrides)
    return LoadingTrajectoryCapacityProvenance(**values)


def _loading_input_readiness(
    net_load,
    *,
    metadata: dict[str, object] | None = None,
    registry_manifest: dict[str, object] | None = None,
    time_domain: str = "window_set",
) -> NetLoadLoadingInputReadiness:
    return NetLoadLoadingInputReadiness(
        net_load=net_load,
        registry_manifest=registry_manifest
        or {
            "registry_id": "synthetic-ic2-fixture",
            "readiness": {"ready_for_real_arrays": True},
        },
        realization_context_manifest={
            "scenario": "synthetic",
            "planning_year": 2035,
            "time_domain": time_domain,
            "aleatory_identity": {"root_seed": 7, "sample_index": 0},
        },
        time_domain=time_domain,
        metadata=metadata or {"scaffold_only": True},
    )


def test_loading_input_readiness_routes_to_trajectory_scaffold_without_events() -> None:
    net_load = build_net_load_result(
        [
            _net_load_component("baseline-a", "baseline", "node-a", [8.0, 8.0, 8.0, 8.0], [6.0, 6.0, 6.0, 6.0]),
            _net_load_component("ev-a", "ev", "node-a", [1.0, 2.0, 3.0, 4.0], [0.0, 0.0, 0.0, 0.0]),
            _net_load_component("pv-b", "pv", "node-b", [0.0, -2.0, -4.0, -6.0], [0.0, 0.0, 0.0, 0.0]),
        ],
        metadata={"scaffold": "synthetic-loading-input"},
    )

    result = build_tier1_loading_trajectory_scaffold(
        _loading_input_readiness(net_load),
        capacity=_capacity_provenance(),
        metadata={"route": "synthetic-ic1-to-ic2"},
    )

    validate_loading_trajectory_result(result)
    np.testing.assert_allclose(result.p_net_kw, np.array([9.0, 8.0, 7.0, 6.0]))
    np.testing.assert_allclose(result.q_net_kvar, np.array([6.0, 6.0, 6.0, 6.0]))
    np.testing.assert_allclose(result.screening_loading_pu, np.hypot(result.p_net_kw, result.q_net_kvar) / 10.0)
    assert result.import_mask.tolist() == [True, True, True, True]
    assert result.export_mask.tolist() == [False, False, False, False]
    assert result.zero_mask.tolist() == [False, False, False, False]
    assert not hasattr(result, "overload")
    manifest = result.manifest_metadata()
    assert manifest["governed_event_metadata"] == {
        "basis": "G0-A3",
        "primary_threshold_pu": 1.0,
        "strict_import_loading_gt_threshold": True,
        "sensitivity_thresholds_pu": (1.1, 1.2),
        "min_consecutive_15_minute_steps": 4,
        "not_evaluated_here": True,
    }
    assert manifest["capacity"]["convention_status"] == "pending_g1_a2_e3_s2b"
    assert manifest["no_event_detection"] is True
    assert manifest["no_probability_estimate"] is True
    assert manifest["no_capacity_screen_result"] is True
    assert "overload" not in manifest
    assert "event_count" not in manifest
    assert "p_event" not in manifest


def test_loading_trajectory_scaffold_rejects_missing_capacity_provenance() -> None:
    with pytest.raises(ValueError, match="transformer_indices"):
        _capacity_provenance(transformer_indices=())

    with pytest.raises(ValueError, match="source"):
        _capacity_provenance(source="")

    with pytest.raises(TypeError, match="exact nonnegative integers"):
        _capacity_provenance(transformer_indices=("1",))


def test_loading_trajectory_scaffold_rejects_cadence_or_calendar_drift() -> None:
    bad_cadence = np.array(
        [
            "2035-01-01T00:00:00",
            "2035-01-01T00:10:00",
            "2035-01-01T00:20:00",
            "2035-01-01T00:30:00",
        ],
        dtype="datetime64[s]",
    )
    with pytest.raises(ValueError, match="15-minute calendar"):
        NetLoadComponent(
            provenance=ComponentProvenance(
                component_id="baseline-a",
                kind="baseline",
                node_id="node-a",
                member_id="baseline-member",
                source_id="synthetic-tier1-fixture",
            ),
            p_kw=np.ones(4),
            q_kvar=np.zeros(4),
            timestamps=bad_cadence,
        )

    wrong_year = np.array(
        [
            "2034-01-01T00:00:00",
            "2034-01-01T00:15:00",
            "2034-01-01T00:30:00",
            "2034-01-01T00:45:00",
        ],
        dtype="datetime64[s]",
    )
    net_load = build_net_load_result(
        [
            NetLoadComponent(
                provenance=ComponentProvenance(
                    component_id="baseline-a",
                    kind="baseline",
                    node_id="node-a",
                    member_id="baseline-member",
                    source_id="synthetic-tier1-fixture",
                ),
                p_kw=np.ones(4),
                q_kvar=np.zeros(4),
                timestamps=wrong_year,
            )
        ]
    )
    with pytest.raises(ValueError, match="planning year"):
        _loading_input_readiness(net_load)


def test_loading_trajectory_scaffold_rejects_legacy_overload_metadata() -> None:
    net_load = build_net_load_result(
        [_net_load_component("baseline-a", "baseline", "node-a", [1.0, 1.0, 1.0, 1.0], [0.0, 0.0, 0.0, 0.0])],
        metadata={"overload": False},
    )

    with pytest.raises(ValueError, match="legacy event result metadata"):
        build_tier1_loading_trajectory_scaffold(
            _loading_input_readiness(net_load),
            capacity=_capacity_provenance(),
        )

    clean_net_load = build_net_load_result(
        [_net_load_component("baseline-a", "baseline", "node-a", [1.0, 1.0, 1.0, 1.0], [0.0, 0.0, 0.0, 0.0])]
    )
    with pytest.raises(ValueError, match="event/probability results"):
        build_tier1_loading_trajectory_scaffold(
            _loading_input_readiness(clean_net_load, metadata={"probability": 0.0}),
            capacity=_capacity_provenance(),
        )


def test_loading_trajectory_scaffold_rejects_unsigned_real_project_readiness() -> None:
    net_load = build_net_load_result(
        [_net_load_component("baseline-a", "baseline", "node-a", [1.0, 1.0, 1.0, 1.0], [0.0, 0.0, 0.0, 0.0])]
    )
    readiness = _loading_input_readiness(
        net_load,
        registry_manifest={
            "registry_id": "current-real-project-readiness",
            "readiness": {
                "ready_for_real_arrays": False,
                "blocking_items_by_kind": {
                    "hp": ("E2-S3-HP001-EXECUTABLE-VALUE-BINDING-PACKET",),
                    "pv": ("PV-PARAM-001",),
                },
            },
        },
    )

    with pytest.raises(ValueError, match="accepted or synthetic fixture input readiness"):
        build_tier1_loading_trajectory_scaffold(readiness, capacity=_capacity_provenance())


def test_loading_trajectory_scaffold_validator_rejects_malformed_direction_masks() -> None:
    net_load = build_net_load_result(
        [_net_load_component("baseline-a", "baseline", "node-a", [1.0, -1.0, 0.0, 1.0], [0.0, 0.0, 1.0, 0.0])]
    )
    result = build_tier1_loading_trajectory_scaffold(
        _loading_input_readiness(net_load),
        capacity=_capacity_provenance(),
    )

    result.import_mask[0] = False
    with pytest.raises(ValueError, match="import_mask must match"):
        validate_loading_trajectory_result(result)
