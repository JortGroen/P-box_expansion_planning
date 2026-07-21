from __future__ import annotations

import numpy as np
import pytest

from src.evaluator_sum import (
    DEFAULT_THRESHOLD_PU,
    count_import_overload_episodes,
    evaluate_tier1,
    radial_downstream_sum,
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

