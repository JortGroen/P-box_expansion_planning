from __future__ import annotations

import numpy as np
import pytest

from src.evaluator_sum import (
    DEFAULT_THRESHOLD_PU,
    count_import_overload_episodes,
    evaluate_net_load_tier1,
    evaluate_tier1,
    radial_downstream_sum,
)
from src.contracts.loading_trajectory import validate_loading_trajectory_result
from src.contracts.net_load import (
    ComponentProvenance,
    NetLoadComponent,
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


def test_default_g0_a3_threshold_is_strictly_greater_than_1_1() -> None:
    assert count_import_overload_episodes([1.1, 1.1, 1.1, 1.1]) == (0, 0)
    assert count_import_overload_episodes([1.1001, 1.1001, 1.1001, 1.1001]) == (1, 4)


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

