from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from src.contracts.loading_trajectory import validate_loading_trajectory_result
from src.evaluator_sum import Tier1Evaluation, evaluate_tier1


def _valid_result(**overrides: object) -> Tier1Evaluation:
    p_net_kw = np.array([1000.0, -500.0, 0.0])
    q_net_kvar = np.array([0.0, 500.0, 300.0])
    s_net_kva = np.hypot(p_net_kw, q_net_kvar)
    screening_loading_pu = s_net_kva / 1000.0
    import_mask = p_net_kw > 0.0
    export_mask = p_net_kw < 0.0
    zero_mask = p_net_kw == 0.0
    result = Tier1Evaluation(
        p_net_kw=p_net_kw,
        q_net_kvar=q_net_kvar,
        s_net_kva=s_net_kva,
        screening_loading_pu=screening_loading_pu,
        import_loading_pu=np.where(import_mask, screening_loading_pu, 0.0),
        export_loading_pu=np.where(export_mask, screening_loading_pu, 0.0),
        import_mask=import_mask,
        export_mask=export_mask,
        zero_mask=zero_mask,
        overload=False,
        overload_episode_count=0,
        longest_import_run_steps=1,
        time_domain="full_year",
        primary_probability_domain=True,
        threshold_pu=1.1,
        min_consecutive_steps=4,
    )
    return replace(result, **overrides)


def test_tier1_evaluation_satisfies_loading_trajectory_contract() -> None:
    result = evaluate_tier1(
        np.array([[1000.0, -500.0, 0.0]]),
        np.array([[0.0, 500.0, 300.0]]),
        s_nom_agg_kva=1000.0,
    )

    validate_loading_trajectory_result(result)


def test_rejects_inconsistent_shapes_and_empty_vectors() -> None:
    with pytest.raises(ValueError, match="identical shapes"):
        validate_loading_trajectory_result(_valid_result(q_net_kvar=np.array([0.0, 1.0])))

    empty = np.array([], dtype=float)
    empty_mask = np.array([], dtype=bool)
    with pytest.raises(ValueError, match="must not be empty"):
        validate_loading_trajectory_result(
            _valid_result(
                p_net_kw=empty,
                q_net_kvar=empty,
                s_net_kva=empty,
                screening_loading_pu=empty,
                import_loading_pu=empty,
                export_loading_pu=empty,
                import_mask=empty_mask,
                export_mask=empty_mask,
                zero_mask=empty_mask,
            )
        )

    with pytest.raises(ValueError, match="one-dimensional"):
        validate_loading_trajectory_result(_valid_result(p_net_kw=np.array([[1.0, 2.0, 3.0]])))


def test_rejects_nonfinite_values_and_inconsistent_apparent_power() -> None:
    with pytest.raises(ValueError, match="p_net_kw must contain only finite"):
        validate_loading_trajectory_result(_valid_result(p_net_kw=np.array([np.nan, -500.0, 0.0])))

    with pytest.raises(ValueError, match="s_net_kva must equal"):
        validate_loading_trajectory_result(_valid_result(s_net_kva=np.array([1000.0, 1.0, 300.0])))


def test_rejects_negative_screening_loading() -> None:
    with pytest.raises(ValueError, match="screening_loading_pu must be nonnegative"):
        validate_loading_trajectory_result(_valid_result(screening_loading_pu=np.array([1.0, -0.1, 0.3])))


def test_rejects_malformed_direction_masks() -> None:
    with pytest.raises(ValueError, match="import_mask must match"):
        validate_loading_trajectory_result(_valid_result(import_mask=np.array([False, False, False])))

    with pytest.raises(ValueError, match="boolean array"):
        validate_loading_trajectory_result(_valid_result(export_mask=np.array([0, 1, 0])))


def test_rejects_inconsistent_import_and_export_loading_gates() -> None:
    with pytest.raises(ValueError, match="import_loading_pu must equal"):
        validate_loading_trajectory_result(_valid_result(import_loading_pu=np.array([1.0, 0.2, 0.0])))

    with pytest.raises(ValueError, match="export_loading_pu must equal"):
        validate_loading_trajectory_result(_valid_result(export_loading_pu=np.array([0.0, 0.0, 0.0])))


def test_rejects_invalid_threshold_and_persistence() -> None:
    with pytest.raises(ValueError, match="threshold_pu must be finite and nonnegative"):
        validate_loading_trajectory_result(_valid_result(threshold_pu=-0.1))

    with pytest.raises(TypeError, match="min_consecutive_steps must be an integer"):
        validate_loading_trajectory_result(_valid_result(min_consecutive_steps=True))

    with pytest.raises(ValueError, match="min_consecutive_steps must be positive"):
        validate_loading_trajectory_result(_valid_result(min_consecutive_steps=0))


def test_rejects_full_year_and_window_domain_inconsistencies() -> None:
    with pytest.raises(ValueError, match="time_domain must be"):
        validate_loading_trajectory_result(_valid_result(time_domain="critical_week"))

    with pytest.raises(ValueError, match="primary_probability_domain"):
        validate_loading_trajectory_result(
            _valid_result(time_domain="full_year", primary_probability_domain=False)
        )

    with pytest.raises(ValueError, match="primary_probability_domain"):
        validate_loading_trajectory_result(
            _valid_result(time_domain="window_set", primary_probability_domain=True)
        )
