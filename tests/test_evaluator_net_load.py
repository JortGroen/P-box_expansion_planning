from __future__ import annotations

import numpy as np
import pytest

from src.contracts.net_load import (
    ComponentProvenance,
    NetLoadAssemblyPlan,
    NetLoadComponent,
    assemble_net_load_from_components,
    build_net_load_result,
    validate_net_load_result,
)


def _calendar() -> np.ndarray:
    return np.array(
        [
            "2035-01-01T00:00:00",
            "2035-01-01T00:15:00",
            "2035-01-01T00:30:00",
            "2035-01-01T00:45:00",
        ],
        dtype="datetime64[s]",
    )


def _component(
    component_id: str,
    kind: str,
    p_kw: list[float],
    *,
    node_id: str = "node-1",
    member_id: str | None = None,
    source_id: str | None = None,
    shared_weather_driver_id: str | None = None,
    timestamps: np.ndarray | None = None,
) -> NetLoadComponent:
    return NetLoadComponent(
        provenance=ComponentProvenance(
            component_id=component_id,
            kind=kind,
            node_id=node_id,
            member_id=member_id,
            source_id=source_id,
            shared_weather_driver_id=shared_weather_driver_id,
            metadata={"synthetic": True},
        ),
        p_kw=np.array(p_kw, dtype=float),
        q_kvar=np.zeros(4, dtype=float),
        timestamps=_calendar() if timestamps is None else timestamps,
    )


def _integration_components() -> list[NetLoadComponent]:
    return [
        _component("base-a", "baseline", [10.0, 11.0, 12.0, 13.0], node_id="node-a", member_id="simbench-a"),
        _component("ev-a", "ev", [1.0, 2.0, 3.0, 4.0], node_id="node-a", member_id="ev-7"),
        _component("hp-b", "hp", [4.0, 5.0, 6.0, 7.0], node_id="node-b", member_id="hp-3", shared_weather_driver_id="weather-1"),
        _component("pv-b", "pv", [0.0, -2.0, -3.0, 0.0], node_id="node-b", member_id="pv-3", shared_weather_driver_id="weather-1"),
        _component("adoption-a", "adoption", [0.5, 0.5, 0.5, 0.5], node_id="node-a", member_id="adoption-2035"),
        _component("flex-a", "flexibility", [-0.2, -0.2, 0.0, 0.0], node_id="node-a", member_id="rho-0.5"),
    ]


def test_same_synthetic_inputs_give_deterministic_output() -> None:
    components = [
        _component("base-a", "baseline", [10.0, 11.0, 12.0, 13.0], member_id="simbench-a"),
        _component("ev-a", "ev", [1.0, 2.0, 3.0, 4.0], member_id="ev-member-7"),
        _component("pv-a", "pv", [0.0, -5.0, -6.0, 0.0], member_id="pv-synthetic"),
    ]

    first = build_net_load_result(components, metadata={"scenario": "synthetic"})
    second = build_net_load_result(components, metadata={"scenario": "synthetic"})

    np.testing.assert_array_equal(first.p_net_kw, second.p_net_kw)
    np.testing.assert_array_equal(first.q_net_kvar, second.q_net_kvar)
    np.testing.assert_array_equal(first.timestamps, second.timestamps)
    assert first.node_ids == second.node_ids
    assert first.component_provenance == second.component_provenance
    np.testing.assert_array_equal(first.p_net_kw, np.array([[11.0, 8.0, 9.0, 17.0]]))


def test_mismatched_calendars_are_rejected() -> None:
    shifted = _calendar().copy()
    shifted[2] = np.datetime64("2035-01-01T00:31:00")

    with pytest.raises(ValueError, match="complete 15-minute calendar"):
        _component("bad-calendar", "baseline", [1.0, 1.0, 1.0, 1.0], timestamps=shifted)

    later_calendar = _calendar() + np.timedelta64(15, "m")
    with pytest.raises(ValueError, match="same 15-minute calendar"):
        build_net_load_result(
            [
                _component("base-a", "baseline", [1.0, 1.0, 1.0, 1.0]),
                _component("ev-a", "ev", [1.0, 1.0, 1.0, 1.0], timestamps=later_calendar),
            ]
        )


def test_incomplete_or_nonfinite_trajectories_are_rejected() -> None:
    with pytest.raises(ValueError, match="p_kw must not be empty"):
        NetLoadComponent(
            provenance=ComponentProvenance("empty", "baseline", "node-1"),
            p_kw=np.array([], dtype=float),
            q_kvar=np.array([], dtype=float),
            timestamps=np.array([], dtype="datetime64[s]"),
        )

    with pytest.raises(ValueError, match="p_kw must contain only finite"):
        _component("nan-load", "ev", [1.0, np.nan, 2.0, 3.0])

    result = build_net_load_result([_component("base-a", "baseline", [1.0, 1.0, 1.0, 1.0])])
    result.p_net_kw[0, 0] = np.inf
    with pytest.raises(ValueError, match="net-load arrays must contain only finite"):
        validate_net_load_result(result)


def test_hp_and_pv_components_share_weather_driver_when_both_present() -> None:
    build_net_load_result(
        [
            _component("hp-a", "hp", [3.0, 4.0, 5.0, 6.0], shared_weather_driver_id="weather-17"),
            _component("pv-a", "pv", [0.0, -2.0, -3.0, 0.0], shared_weather_driver_id="weather-17"),
        ]
    )

    with pytest.raises(ValueError, match="HP and PV components must share"):
        build_net_load_result(
            [
                _component("hp-a", "hp", [3.0, 4.0, 5.0, 6.0], shared_weather_driver_id="weather-17"),
                _component("pv-a", "pv", [0.0, -2.0, -3.0, 0.0], shared_weather_driver_id="weather-18"),
            ]
        )

    with pytest.raises(ValueError, match="HP and PV components must share"):
        build_net_load_result(
            [
                _component("hp-a", "hp", [3.0, 4.0, 5.0, 6.0]),
                _component("pv-a", "pv", [0.0, -2.0, -3.0, 0.0], shared_weather_driver_id="weather-17"),
            ]
        )


def test_component_member_metadata_remains_traceable() -> None:
    result = build_net_load_result(
        [
            _component(
                "ev-home-001",
                "ev",
                [1.0, 1.5, 2.0, 2.5],
                node_id="node-ev",
                member_id="elaad-member-42",
                source_id="EV-004-home-cp",
            ),
            _component(
                "flex-ev-home-001",
                "flexibility",
                [-0.2, -0.2, 0.0, 0.0],
                node_id="node-ev",
                member_id="rho-0.5",
                source_id="FLEX-001",
            ),
        ],
        metadata={"scenario": "synthetic", "year": 2035},
    )

    assert result.node_ids == ("node-ev",)
    assert result.metadata["year"] == 2035
    ev_provenance = result.component_provenance[0]
    assert ev_provenance.component_id == "ev-home-001"
    assert ev_provenance.member_id == "elaad-member-42"
    assert ev_provenance.source_id == "EV-004-home-cp"
    assert ev_provenance.metadata["synthetic"] is True
    np.testing.assert_array_equal(result.p_net_kw, np.array([[0.8, 1.3, 2.0, 2.5]]))


def test_integration_harness_assembles_all_component_families_in_plan_node_order() -> None:
    plan = NetLoadAssemblyPlan(node_ids=("node-b", "node-a"), metadata={"scenario": "synthetic-2035"})

    result = assemble_net_load_from_components(
        plan,
        _integration_components(),
        metadata={"rho": 0.5},
    )

    assert result.node_ids == ("node-b", "node-a")
    assert result.metadata["assembly"] == "synthetic_ic1_harness"
    assert result.metadata["scenario"] == "synthetic-2035"
    assert result.metadata["rho"] == 0.5
    assert result.shared_weather_driver_ids == ("weather-1",)
    np.testing.assert_array_equal(result.timestamps, _calendar())
    np.testing.assert_array_equal(
        result.p_net_kw,
        np.array(
            [
                [4.0, 3.0, 3.0, 7.0],
                [11.3, 13.3, 15.5, 17.5],
            ]
        ),
    )


def test_integration_harness_rejects_missing_required_component_family() -> None:
    plan = NetLoadAssemblyPlan(node_ids=("node-a", "node-b"))
    components = [
        component
        for component in _integration_components()
        if component.provenance.kind != "adoption"
    ]

    with pytest.raises(ValueError, match="missing required component kind\\(s\\): adoption"):
        assemble_net_load_from_components(plan, components)


def test_integration_harness_rejects_duplicate_or_unknown_nodes() -> None:
    with pytest.raises(ValueError, match="node_ids must not contain duplicates"):
        NetLoadAssemblyPlan(node_ids=("node-a", "node-a"))

    plan = NetLoadAssemblyPlan(node_ids=("node-a", "node-b"))
    components = _integration_components()
    components[0] = _component("base-z", "baseline", [1.0, 1.0, 1.0, 1.0], node_id="node-z")

    with pytest.raises(ValueError, match="component node_id must appear"):
        assemble_net_load_from_components(plan, components)


def test_integration_harness_rejects_calendar_and_weather_mismatches() -> None:
    plan = NetLoadAssemblyPlan(node_ids=("node-a", "node-b"))
    shifted = _calendar() + np.timedelta64(15, "m")
    components = _integration_components()
    components[1] = _component("ev-shifted", "ev", [1.0, 2.0, 3.0, 4.0], node_id="node-a", timestamps=shifted)

    with pytest.raises(ValueError, match="same 15-minute calendar"):
        assemble_net_load_from_components(plan, components)

    components = _integration_components()
    components[3] = _component(
        "pv-b",
        "pv",
        [0.0, -2.0, -3.0, 0.0],
        node_id="node-b",
        shared_weather_driver_id="weather-2",
    )
    with pytest.raises(ValueError, match="HP and PV components must share"):
        assemble_net_load_from_components(plan, components)
