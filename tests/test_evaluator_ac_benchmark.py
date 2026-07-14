from __future__ import annotations

import numpy as np

from src.evaluator_ac_benchmark import (
    build_timeseries_adapter,
    make_repeated_inputs,
    materialize_topology_for_lightsim,
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
