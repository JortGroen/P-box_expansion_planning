from __future__ import annotations

import numpy as np
import pytest

from src.flex_aggregator import FlexComponent, apply_flexibility


def test_reduces_only_import_side_controllable_demand() -> None:
    result = apply_flexibility(
        [
            FlexComponent("ev", [10.0, 20.0, -5.0], controllable_fraction=0.5, is_import_controllable=True),
            FlexComponent("pv", [-7.0, -8.0, -9.0], component_type="pv"),
            FlexComponent("fixed", [3.0, 3.0, 3.0], controllable_fraction=1.0),
        ],
        rho=0.4,
    )

    ev, pv, fixed = result.component_results
    np.testing.assert_allclose(ev.reduction_p_kw, [2.0, 4.0, 0.0])
    np.testing.assert_allclose(ev.adjusted_p_kw, [8.0, 16.0, -5.0])
    np.testing.assert_allclose(pv.adjusted_p_kw, [-7.0, -8.0, -9.0])
    np.testing.assert_allclose(fixed.adjusted_p_kw, [3.0, 3.0, 3.0])
    assert ev.reason.startswith("reduced positive import demand")
    assert pv.reason == "not marked as import-side controllable demand"
    assert fixed.reason == "not marked as import-side controllable demand"
    np.testing.assert_allclose(result.aggregate_adjusted_p_kw, [4.0, 11.0, -11.0])


def test_preserves_complete_trajectory_alignment_and_metadata() -> None:
    timestamps = ("t0", "t1", "t2")
    result = apply_flexibility(
        [
            FlexComponent(
                "hp",
                [4.0, 5.0, 6.0],
                controllable_fraction=0.25,
                is_import_controllable=True,
                component_type="heat_pump",
                node_id="n1",
                timestamps=timestamps,
            ),
            FlexComponent("baseline", [1.0, 1.0, 1.0], timestamps=timestamps),
        ],
        rho=1.0,
        active_mask=np.array([True, False, True]),
    )

    hp = result.component_results[0]
    assert result.timestamps == timestamps
    assert hp.timestamps == timestamps
    assert hp.node_id == "n1"
    assert hp.component_type == "heat_pump"
    np.testing.assert_allclose(hp.reduction_p_kw, [1.0, 0.0, 1.5])
    np.testing.assert_array_equal(result.active_mask, [True, False, True])


def test_rho_endpoints_and_determinism() -> None:
    components = [FlexComponent("ev", [10.0, 20.0], controllable_fraction=0.5, is_import_controllable=True)]

    no_flex = apply_flexibility(components, rho=0.0)
    max_flex_a = apply_flexibility(components, rho=1.0)
    max_flex_b = apply_flexibility(components, rho=1.0)

    np.testing.assert_allclose(no_flex.aggregate_adjusted_p_kw, [10.0, 20.0])
    np.testing.assert_allclose(max_flex_a.aggregate_adjusted_p_kw, [5.0, 10.0])
    np.testing.assert_allclose(max_flex_a.aggregate_adjusted_p_kw, max_flex_b.aggregate_adjusted_p_kw)
    assert max_flex_a.total_reduction_kwh == max_flex_b.total_reduction_kwh


def test_shift_to_adjacent_rebound_conserves_component_energy() -> None:
    result = apply_flexibility(
        [FlexComponent("ev", [10.0, 10.0, 10.0], controllable_fraction=0.5, is_import_controllable=True)],
        rho=1.0,
        active_mask=np.array([False, True, False]),
        rebound_mode="shift_to_adjacent",
    )

    component = result.component_results[0]
    np.testing.assert_allclose(component.reduction_p_kw, [0.0, 5.0, 0.0])
    np.testing.assert_allclose(component.rebound_p_kw, [0.0, 0.0, 5.0])
    np.testing.assert_allclose(component.adjusted_p_kw, [10.0, 5.0, 15.0])
    assert component.reduction_kwh == component.rebound_kwh
    assert np.sum(component.original_p_kw) == np.sum(component.adjusted_p_kw)


def test_rejects_invalid_rho_fraction_and_rebound_mode() -> None:
    component = FlexComponent("ev", [1.0], controllable_fraction=0.5, is_import_controllable=True)

    with pytest.raises(ValueError, match="rho must be finite and in \\[0, 1\\]"):
        apply_flexibility([component], rho=1.01)

    with pytest.raises(ValueError, match="controllable_fraction"):
        apply_flexibility([FlexComponent("ev", [1.0], controllable_fraction=-0.1)], rho=0.5)

    with pytest.raises(ValueError, match="rebound_mode"):
        apply_flexibility([component], rho=0.5, rebound_mode="later")


def test_rejects_misaligned_or_malformed_trajectories() -> None:
    with pytest.raises(ValueError, match="identical length"):
        apply_flexibility([FlexComponent("a", [1.0, 2.0]), FlexComponent("b", [1.0])], rho=0.5)

    with pytest.raises(ValueError, match="timestamps"):
        apply_flexibility(
            [
                FlexComponent("a", [1.0, 2.0], timestamps=("t0", "t1")),
                FlexComponent("b", [1.0, 2.0], timestamps=("t0", "other")),
            ],
            rho=0.5,
        )

    with pytest.raises(ValueError, match="active_mask must be a boolean array"):
        apply_flexibility([FlexComponent("a", [1.0, 2.0])], rho=0.5, active_mask=np.array([1, 0]))

    with pytest.raises(ValueError, match="p_kw must contain only finite"):
        apply_flexibility([FlexComponent("a", [1.0, np.nan])], rho=0.5)


def test_shift_to_adjacent_rebound_requires_adjacent_step_when_reduction_exists() -> None:
    with pytest.raises(ValueError, match="requires at least two timesteps"):
        apply_flexibility(
            [FlexComponent("ev", [10.0], controllable_fraction=0.5, is_import_controllable=True)],
            rho=1.0,
            rebound_mode="shift_to_adjacent",
        )
