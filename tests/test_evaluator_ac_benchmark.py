from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.evaluator_ac_benchmark import (
    DEFAULT_MATERIALIZATION_ACCEPTANCE,
    build_timeseries_adapter,
    make_repeated_inputs,
    materialize_topology_for_lightsim,
    run_materialization_discrepancy,
    render_report,
)
from src.grid_loader import load_candidate_grid


@pytest.mark.integration
@pytest.mark.slow
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


@pytest.mark.integration
@pytest.mark.slow
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


@pytest.mark.integration
@pytest.mark.slow
def test_materialize_topology_rejects_impedance_bearing_closed_bus_switch() -> None:
    net = load_candidate_grid("simbench_semiurb")
    net.switch.loc[0, "z_ohm"] = 0.1

    with pytest.raises(ValueError, match="nonzero z_ohm"):
        materialize_topology_for_lightsim(net)


@pytest.mark.integration
@pytest.mark.slow
def test_materialization_discrepancy_reports_transformer_and_voltage_deltas() -> None:
    net = load_candidate_grid("simbench_semiurb")

    result = run_materialization_discrepancy(
        net,
        load_multipliers=(0.8, 1.0, 2.65, 2.85),
        acceptance=DEFAULT_MATERIALIZATION_ACCEPTANCE,
    )

    assert result["open_transformer_switch_check"].startswith("passed")
    assert result["closed_bus_bus_impedance_check"].startswith("passed")
    assert "one-end-open line" in result["one_end_open_line_note"]
    assert result["acceptance_passed"] is True
    assert len(result["rows"]) == 4
    assert result["transformer_indices"] == [0, 1]
    for row in result["rows"]:
        assert set(row["delta"]) == {"p_mw", "q_mvar", "s_mva", "loading_pu", "max_bus_vm_pu"}
        assert row["original"]["nameplate_mva"] == pytest.approx(80.0)
        assert row["materialized"]["nameplate_mva"] == pytest.approx(80.0)
        assert abs(row["delta"]["loading_pu"]) <= DEFAULT_MATERIALIZATION_ACCEPTANCE["max_abs_loading_pu"]
        assert row["delta"]["max_bus_vm_pu"] <= DEFAULT_MATERIALIZATION_ACCEPTANCE["max_abs_bus_vm_pu"]


@pytest.mark.integration
@pytest.mark.slow
def test_timeseriescpp_inputs_match_converter_element_counts() -> None:
    adapter = build_timeseries_adapter(load_candidate_grid("simbench_semiurb"))

    inputs = make_repeated_inputs(adapter, 3)

    assert inputs.gen_p.shape == (3, len(adapter.grid_model.get_generators()))
    assert inputs.sgen_p.shape == (3, len(adapter.grid_model.get_static_generators()))
    assert inputs.load_p.shape == (3, len(adapter.grid_model.get_loads()))
    assert inputs.load_q.shape == (3, len(adapter.grid_model.get_loads()))
    assert inputs.vinit.shape == (len(adapter.net.bus),)
    assert np.iscomplexobj(inputs.vinit)


@pytest.mark.integration
@pytest.mark.slow
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


def test_render_report_includes_timing_context_note() -> None:
    raw = {
        "timestamp_utc": "2026-07-17T00:00:00Z",
        "config_path": "experiments/example/diagnostic_config.runtime.json",
        "config": {
            "raw_output_path": "experiments/example/raw.json",
            "report_output_path": "experiments/example/report.md",
            "timing_context_note": "Descriptive E0.S3b compliance rerun only.",
        },
        "timeseriescpp": {
            "time_steps": 2,
            "internal_solver": {"median_s": 0.002},
            "compute_vs_wall": {"median_s": 0.004},
            "conversion_setup": {"median_s": 0.1},
            "input_update": {"median_s": 0.001},
            "internal_preprocessing": {"median_s": 0.001},
            "voltage_result_extraction": {"median_s": 0.001},
            "current_flow_result_extraction": {"median_s": 0.001},
            "power_flow_result_extraction": {"median_s": 0.001},
            "input_shapes": {},
        },
        "pandapower_runpp": {
            "pandapower_lightsim2grid": {"elapsed": {"median_s": 0.01}},
            "pandapower_native": {"elapsed": {"median_s": 0.02}},
        },
        "topology_materialization": {
            "open_line_switches": [],
            "disabled_lines": [],
            "fused_bus_switches": [],
            "bus_count_before": 1,
            "bus_count_after": 1,
            "in_service_line_count_after": 0,
        },
        "adapter_converter_warnings": [],
        "materialization_discrepancy": {
            "acceptance_criterion": {"max_abs_loading_pu": 0.002, "max_abs_bus_vm_pu": 0.001},
            "acceptance_passed": True,
            "rows": [
                {
                    "load_multiplier": 1.0,
                    "original": {"loading_pu": 0.1},
                    "materialized": {"loading_pu": 0.1},
                    "delta": {"p_mw": 0.0, "q_mvar": 0.0, "s_mva": 0.0, "loading_pu": 0.0, "max_bus_vm_pu": 0.0},
                }
            ],
            "open_transformer_switch_check": "passed",
            "closed_bus_bus_impedance_check": "passed",
            "one_end_open_line_note": "No one-end-open line difference.",
        },
    }

    report = render_report(raw, Path("experiments/example/custom_evidence.json"))

    assert "Timing context: Descriptive E0.S3b compliance rerun only." in report
    assert "- Standard claim-source manifest: `experiments/example/manifest.json`" in report
    assert "- Retained/custom evidence: `experiments/example/custom_evidence.json`" in report
    assert "Evidence manifest" not in report
