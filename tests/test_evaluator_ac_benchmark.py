from __future__ import annotations

import numpy as np
import pytest

from src.evaluator_ac_benchmark import (
    build_timeseries_adapter,
    make_repeated_inputs,
    materialize_topology_for_lightsim,
    run_materialization_equivalence,
)
from src.grid_loader import load_candidate_grid


def test_materialize_topology_records_primary_switch_handling() -> None:
    net = load_candidate_grid("simbench_semiurb")

    converted, summary = materialize_topology_for_lightsim(net)

    assert summary.open_line_switches == (233, 235, 237, 239, 241, 243, 245, 247)
    assert summary.disabled_lines == (113, 114, 115, 116, 117, 118, 119, 120)
    assert summary.fused_bus_switches == (0, 5)
    assert summary.bus_count_before == 117
    assert summary.bus_count_after == 115
    assert len(converted.switch) == 0
    assert not converted.line.loc[list(summary.disabled_lines), "in_service"].any()


def test_materialize_topology_rejects_open_transformer_switch() -> None:
    net = load_candidate_grid("simbench_semiurb")
    switch_index = int(net.switch.index.max()) + 1
    net.switch.loc[switch_index] = {
        "bus": int(net.trafo.loc[0, "hv_bus"]),
        "element": 0,
        "et": "t",
        "type": "LBS",
        "closed": False,
        "name": "unsupported open transformer switch",
        "z_ohm": 0.0,
        "in_ka": np.nan,
    }

    with pytest.raises(ValueError, match="Unsupported open transformer switches"):
        materialize_topology_for_lightsim(net)


def test_materialization_equivalence_reports_transformer_and_voltage_deltas() -> None:
    net = load_candidate_grid("simbench_semiurb")

    result = run_materialization_equivalence(net, load_multipliers=(1.0, 1.1))

    assert result["open_transformer_switch_check"].startswith("passed")
    assert "one-end-open line" in result["one_end_open_line_note"]
    assert len(result["rows"]) == 2
    assert result["transformer_indices"] == [0, 1]
    for row in result["rows"]:
        assert set(row["delta"]) == {"p_mw", "q_mvar", "s_mva", "loading_pu", "max_bus_vm_pu"}
        assert row["original"]["nameplate_mva"] == pytest.approx(80.0)
        assert row["materialized"]["nameplate_mva"] == pytest.approx(80.0)
        assert abs(row["delta"]["loading_pu"]) < 1e-3
        assert row["delta"]["max_bus_vm_pu"] < 1e-3


def test_timeseriescpp_inputs_match_converter_element_counts() -> None:
    adapter = build_timeseries_adapter(load_candidate_grid("simbench_semiurb"))

    inputs = make_repeated_inputs(adapter, 3)

    assert inputs.gen_p.shape == (3, len(adapter.grid_model.get_generators()))
    assert inputs.sgen_p.shape == (3, len(adapter.grid_model.get_static_generators()))
    assert inputs.load_p.shape == (3, len(adapter.grid_model.get_loads()))
    assert inputs.load_q.shape == (3, len(adapter.grid_model.get_loads()))
    assert inputs.vinit.shape == (len(adapter.net.bus),)
    assert np.iscomplexobj(inputs.vinit)


def test_timeseriescpp_solves_small_batch() -> None:
    adapter = build_timeseries_adapter(load_candidate_grid("simbench_semiurb"))
    inputs = make_repeated_inputs(adapter, 2)

    solved = adapter.computer.compute_Vs(
        inputs.gen_p,
        inputs.sgen_p,
        inputs.load_p,
        inputs.load_q,
        inputs.vinit,
        20,
        1e-8,
    )

    assert solved == 1
    assert adapter.computer.nb_solved() == 2
    assert np.asarray(adapter.computer.get_voltages()).shape == (2, len(adapter.net.bus))
