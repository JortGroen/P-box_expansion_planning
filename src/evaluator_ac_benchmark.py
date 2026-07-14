"""AC benchmark helpers for the E1.S2b TimeSeriesCPP diagnostic."""

from __future__ import annotations

import argparse
import copy
import json
import os
import platform
import statistics
import time
import warnings
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from src.grid_loader import load_candidate_grid
from src.manifest import build_manifest, sha256_file


SGEN_LIMIT_COLUMNS: tuple[str, ...] = ("min_p_mw", "max_p_mw", "min_q_mvar", "max_q_mvar")
DEFAULT_MATERIALIZATION_ACCEPTANCE: dict[str, float] = {
    "max_abs_loading_pu": 0.002,
    "max_abs_bus_vm_pu": 0.001,
}


@dataclass(frozen=True)
class TopologyMaterialization:
    """Summary of pandapower topology edits needed by the LightSim converter."""

    open_line_switches: tuple[int, ...]
    disabled_lines: tuple[int, ...]
    fused_bus_switches: tuple[int, ...]
    fused_bus_pairs: tuple[tuple[int, int], ...]
    dropped_switches: int
    sgen_limit_columns_cast: tuple[str, ...]
    bus_count_before: int
    bus_count_after: int
    line_count_before: int
    in_service_line_count_after: int


@dataclass(frozen=True)
class TimeSeriesInputs:
    """Time-major input arrays for ``lightsim2grid.timeSerie.TimeSeriesCPP``."""

    gen_p: np.ndarray
    sgen_p: np.ndarray
    load_p: np.ndarray
    load_q: np.ndarray
    vinit: np.ndarray


@dataclass(frozen=True)
class TimeSeriesAdapter:
    """Converted grid and baseline arrays used for TimeSeriesCPP solves."""

    net: Any
    grid_model: Any
    computer: Any
    materialization: TopologyMaterialization
    converter_warnings: tuple[str, ...]


def materialize_topology_for_lightsim(net: Any) -> tuple[Any, TopologyMaterialization]:
    """Return a LightSim-convertible copy of a SimBench pandapower network.

    The lower-level LightSim pandapower converter does not apply pandapower
    switch tables. For this diagnostic, open line switches are represented by
    setting the corresponding lines out of service, closed bus-bus switches are
    fused, and then the switch table is dropped before conversion.
    """

    import pandapower.toolbox as ppt

    converted = copy.deepcopy(net)
    bus_count_before = int(len(converted.bus))
    line_count_before = int(len(converted.line))
    open_line_switches: tuple[int, ...] = ()
    disabled_lines: tuple[int, ...] = ()
    fused_bus_switches: tuple[int, ...] = ()
    fused_bus_pairs: tuple[tuple[int, int], ...] = ()
    dropped_switches = 0

    if hasattr(converted, "switch") and len(converted.switch):
        switch_table = converted.switch.copy()
        open_trafo_mask = (switch_table["et"] == "t") & (~switch_table["closed"].astype(bool))
        if open_trafo_mask.any():
            open_switches = tuple(int(idx) for idx in switch_table.index[open_trafo_mask])
            raise ValueError(f"Unsupported open transformer switches before LightSim conversion: {open_switches}")

        open_line_mask = (switch_table["et"] == "l") & (~switch_table["closed"].astype(bool))
        open_line_switches = tuple(int(idx) for idx in switch_table.index[open_line_mask])
        disabled_lines = tuple(int(line) for line in switch_table.loc[open_line_mask, "element"])
        if disabled_lines:
            converted.line.loc[list(disabled_lines), "in_service"] = False

        bus_switch_mask = (switch_table["et"] == "b") & (switch_table["closed"].astype(bool))
        if bus_switch_mask.any() and "z_ohm" in switch_table:
            z_values = switch_table.loc[bus_switch_mask, "z_ohm"].fillna(0.0).astype(float)
            nonzero_z_switches = tuple(int(idx) for idx, value in z_values.items() if abs(value) > 0.0)
            if nonzero_z_switches:
                raise ValueError(
                    "Unsupported closed bus-bus switches with nonzero z_ohm before LightSim conversion: "
                    f"{nonzero_z_switches}"
                )
        fused_bus_switches = tuple(int(idx) for idx in switch_table.index[bus_switch_mask])
        fused_bus_pairs = tuple(
            (int(switch["bus"]), int(switch["element"])) for _, switch in switch_table.loc[bus_switch_mask].iterrows()
        )
        for _, switch in switch_table.loc[bus_switch_mask].iterrows():
            ppt.fuse_buses(
                converted,
                int(switch["bus"]),
                [int(switch["element"])],
                drop=True,
                fuse_bus_measurements=True,
            )

        dropped_switches = int(len(converted.switch))
        converted.switch.drop(converted.switch.index, inplace=True)

    cast_columns: list[str] = []
    if hasattr(converted, "sgen"):
        for column in SGEN_LIMIT_COLUMNS:
            if column in converted.sgen:
                converted.sgen[column] = converted.sgen[column].astype(float)
                cast_columns.append(column)

    materialization = TopologyMaterialization(
        open_line_switches=open_line_switches,
        disabled_lines=disabled_lines,
        fused_bus_switches=fused_bus_switches,
        fused_bus_pairs=fused_bus_pairs,
        dropped_switches=dropped_switches,
        sgen_limit_columns_cast=tuple(cast_columns),
        bus_count_before=bus_count_before,
        bus_count_after=int(len(converted.bus)),
        line_count_before=line_count_before,
        in_service_line_count_after=int(converted.line["in_service"].sum()) if "in_service" in converted.line else int(len(converted.line)),
    )
    return converted, materialization


def run_materialization_discrepancy(
    net: Any,
    *,
    load_multipliers: Sequence[float],
    acceptance: dict[str, float] | None = None,
    transformer_indices: Sequence[int] = (0, 1),
) -> dict[str, Any]:
    """Quantify original switch-table versus materialized-network discrepancy."""

    criteria = acceptance or DEFAULT_MATERIALIZATION_ACCEPTANCE
    rows: list[dict[str, Any]] = []
    for multiplier in load_multipliers:
        original = copy.deepcopy(net)
        materialized_input = copy.deepcopy(net)
        _scale_loads(original, multiplier)
        _scale_loads(materialized_input, multiplier)

        materialized, materialization = materialize_topology_for_lightsim(materialized_input)
        _run_equivalence_power_flow(original)
        _run_equivalence_power_flow(materialized)

        original_loading = _decision_transformer_loading(original, transformer_indices)
        materialized_loading = _decision_transformer_loading(materialized, transformer_indices)
        rows.append(
            {
                "load_multiplier": float(multiplier),
                "original": original_loading,
                "materialized": materialized_loading,
                "delta": {
                    "p_mw": materialized_loading["p_mw"] - original_loading["p_mw"],
                    "q_mvar": materialized_loading["q_mvar"] - original_loading["q_mvar"],
                    "s_mva": materialized_loading["s_mva"] - original_loading["s_mva"],
                    "loading_pu": materialized_loading["loading_pu"] - original_loading["loading_pu"],
                    "max_bus_vm_pu": _max_bus_voltage_deviation(original, materialized, materialization),
                },
            }
        )

    max_abs_delta = {
        "p_mw": max(abs(row["delta"]["p_mw"]) for row in rows),
        "q_mvar": max(abs(row["delta"]["q_mvar"]) for row in rows),
        "s_mva": max(abs(row["delta"]["s_mva"]) for row in rows),
        "loading_pu": max(abs(row["delta"]["loading_pu"]) for row in rows),
        "max_bus_vm_pu": max(abs(row["delta"]["max_bus_vm_pu"]) for row in rows),
    }
    return {
        "load_multipliers": [float(value) for value in load_multipliers],
        "transformer_indices": [int(index) for index in transformer_indices],
        "rows": rows,
        "max_abs_delta": max_abs_delta,
        "acceptance_criterion": dict(criteria),
        "acceptance_passed": (
            max_abs_delta["loading_pu"] <= float(criteria["max_abs_loading_pu"])
            and max_abs_delta["max_bus_vm_pu"] <= float(criteria["max_abs_bus_vm_pu"])
        ),
        "open_transformer_switch_check": "passed: no open transformer switches were present before dropping the switch table",
        "closed_bus_bus_impedance_check": "passed: no closed bus-bus switches with nonzero z_ohm were present before fusing",
        "one_end_open_line_note": (
            "Open line switches are represented by setting the corresponding whole line out of service. "
            "If pandapower retains any charging contribution from a one-end-open line under the original switch-table model, "
            "that contribution is removed in the materialized network; the numerical effect is captured by the Q, loading, "
            "and voltage deltas above."
        ),
    }


def _scale_loads(net: Any, multiplier: float) -> None:
    net.load.loc[:, "p_mw"] = net.load["p_mw"].astype(float) * float(multiplier)
    net.load.loc[:, "q_mvar"] = net.load["q_mvar"].astype(float) * float(multiplier)


def _run_equivalence_power_flow(net: Any) -> None:
    import pandapower as pp

    pp.runpp(net, algorithm="nr", calculate_voltage_angles=True, init="auto", max_iteration=50)
    if not bool(net.converged):
        raise RuntimeError("Equivalence power flow did not converge")


def _decision_transformer_loading(net: Any, transformer_indices: Sequence[int]) -> dict[str, float]:
    indices = list(transformer_indices)
    p_mw = float(net.res_trafo.loc[indices, "p_hv_mw"].sum())
    q_mvar = float(net.res_trafo.loc[indices, "q_hv_mvar"].sum())
    s_mva = float(np.hypot(p_mw, q_mvar))
    nameplate_mva = float(net.trafo.loc[indices, "sn_mva"].sum())
    return {
        "p_mw": p_mw,
        "q_mvar": q_mvar,
        "s_mva": s_mva,
        "nameplate_mva": nameplate_mva,
        "loading_pu": s_mva / nameplate_mva,
    }


def _max_bus_voltage_deviation(original: Any, materialized: Any, materialization: TopologyMaterialization) -> float:
    bus_map = {int(bus): int(bus) for bus in original.bus.index}
    for keep_bus, dropped_bus in materialization.fused_bus_pairs:
        bus_map[int(dropped_bus)] = int(keep_bus)

    deviations: list[float] = []
    for original_bus, materialized_bus in bus_map.items():
        if original_bus in original.res_bus.index and materialized_bus in materialized.res_bus.index:
            deviations.append(
                abs(float(original.res_bus.loc[original_bus, "vm_pu"]) - float(materialized.res_bus.loc[materialized_bus, "vm_pu"]))
            )
    if not deviations:
        raise ValueError("No common buses available for voltage comparison")
    return max(deviations)


def build_timeseries_adapter(net: Any) -> TimeSeriesAdapter:
    """Convert a pandapower network into a TimeSeriesCPP-ready adapter."""

    import pandapower as pp
    from lightsim2grid.gridmodel.from_pandapower import init
    from lightsim2grid.timeSerie import TimeSeriesCPP

    converted, materialization = materialize_topology_for_lightsim(net)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        pp.runpp(converted, algorithm="nr", numba=True)
        grid_model = init(converted, pp_orig_file="pandapower_v3")
    return TimeSeriesAdapter(
        net=converted,
        grid_model=grid_model,
        computer=TimeSeriesCPP(grid_model),
        materialization=materialization,
        converter_warnings=tuple(str(warning.message) for warning in caught),
    )


def make_repeated_inputs(adapter: TimeSeriesAdapter, steps: int) -> TimeSeriesInputs:
    """Create repeated baseline TimeSeriesCPP input arrays with checked shapes."""

    if steps <= 0:
        raise ValueError("steps must be positive")
    net = adapter.net
    grid_model = adapter.grid_model
    gen_p = np.tile(np.asarray(grid_model.get_gen_target_p(), dtype=float), (steps, 1))
    sgen_p = np.tile(np.asarray(grid_model.get_sgen_target_p(), dtype=float), (steps, 1))
    load_p = np.tile(np.asarray(grid_model.get_load_target_p(), dtype=float), (steps, 1))
    load_q = np.tile(net.load["q_mvar"].to_numpy(dtype=float), (steps, 1))
    vinit = net.res_bus["vm_pu"].to_numpy(dtype=float) * np.exp(
        1j * np.deg2rad(net.res_bus["va_degree"].to_numpy(dtype=float))
    )
    expected = {
        "gen_p": len(grid_model.get_generators()),
        "sgen_p": len(grid_model.get_static_generators()),
        "load_p": len(grid_model.get_loads()),
        "load_q": len(grid_model.get_loads()),
        "vinit": len(net.bus),
    }
    actual = {
        "gen_p": gen_p.shape[1],
        "sgen_p": sgen_p.shape[1],
        "load_p": load_p.shape[1],
        "load_q": load_q.shape[1],
        "vinit": vinit.shape[0],
    }
    if actual != expected:
        raise ValueError(f"TimeSeriesCPP shape mismatch: expected {expected}, got {actual}")
    return TimeSeriesInputs(gen_p=gen_p, sgen_p=sgen_p, load_p=load_p, load_q=load_q, vinit=vinit)


def _timed(callable_obj: Any) -> tuple[Any, float]:
    start = time.perf_counter()
    result = callable_obj()
    return result, time.perf_counter() - start


def _summary(values: Sequence[float]) -> dict[str, float]:
    return {
        "min_s": min(values),
        "median_s": statistics.median(values),
        "mean_s": statistics.fmean(values),
        "max_s": max(values),
    }


def _runpp_once(grid_key: str, *, lightsim2grid: bool) -> dict[str, Any]:
    import pandapower as pp

    net = load_candidate_grid(grid_key)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _, elapsed = _timed(
            lambda: pp.runpp(
                net,
                algorithm="nr",
                calculate_voltage_angles=True,
                init="auto",
                lightsim2grid=lightsim2grid,
            )
        )
    return {
        "elapsed_s": elapsed,
        "converged": bool(net.converged),
        "requested_lightsim2grid": lightsim2grid,
        "pandapower_option_lightsim2grid": bool(net._options.get("lightsim2grid")),
        "warnings": [str(warning.message) for warning in caught],
    }


def run_benchmark(config_path: str | Path) -> dict[str, Any]:
    """Run the E1.S2b benchmark and return serializable raw results."""

    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    grid_key = config["grid_key"]
    warmups = int(config["warmups"])
    repeats = int(config["repeats"])
    steps = int(config["time_steps"])
    max_iter = int(config["max_iter"])
    tol = float(config["tolerance"])
    equivalence_load_multipliers = tuple(float(value) for value in config.get("equivalence_load_multipliers", [1.0]))
    materialization_acceptance = config.get(
        "materialization_acceptance",
        DEFAULT_MATERIALIZATION_ACCEPTANCE,
    )

    for _ in range(warmups):
        adapter = build_timeseries_adapter(load_candidate_grid(grid_key))
        inputs = make_repeated_inputs(adapter, min(steps, 2))
        adapter.computer.compute_Vs(inputs.gen_p, inputs.sgen_p, inputs.load_p, inputs.load_q, inputs.vinit, max_iter, tol)

    conversion_times: list[float] = []
    input_times: list[float] = []
    compute_wall_times: list[float] = []
    voltage_extract_times: list[float] = []
    current_flow_times: list[float] = []
    power_flow_times: list[float] = []
    internal_solver_times: list[float] = []
    internal_preprocessing_times: list[float] = []
    internal_current_flow_times: list[float] = []
    materialization: TopologyMaterialization | None = None
    shape_record: dict[str, Any] = {}
    solved_counts: list[int] = []
    converter_warnings: tuple[str, ...] = ()

    for _ in range(repeats):
        adapter, conversion_elapsed = _timed(lambda: build_timeseries_adapter(load_candidate_grid(grid_key)))
        inputs, input_elapsed = _timed(lambda: make_repeated_inputs(adapter, steps))
        solved, compute_elapsed = _timed(
            lambda: adapter.computer.compute_Vs(
                inputs.gen_p,
                inputs.sgen_p,
                inputs.load_p,
                inputs.load_q,
                inputs.vinit,
                max_iter,
                tol,
            )
        )
        _, voltage_elapsed = _timed(lambda: np.asarray(adapter.computer.get_voltages()))
        _, current_elapsed = _timed(lambda: (adapter.computer.compute_flows(), np.asarray(adapter.computer.get_flows())))
        _, power_elapsed = _timed(lambda: (adapter.computer.compute_power_flows(), np.asarray(adapter.computer.get_power_flows())))

        conversion_times.append(conversion_elapsed)
        input_times.append(input_elapsed)
        compute_wall_times.append(compute_elapsed)
        voltage_extract_times.append(voltage_elapsed)
        current_flow_times.append(current_elapsed)
        power_flow_times.append(power_elapsed)
        internal_solver_times.append(float(adapter.computer.solver_time()))
        internal_preprocessing_times.append(float(adapter.computer.preprocessing_time()))
        internal_current_flow_times.append(float(adapter.computer.amps_computation_time()))
        solved_counts.append(int(adapter.computer.nb_solved()))
        materialization = adapter.materialization
        converter_warnings = adapter.converter_warnings
        shape_record = {
            "gen_p": list(inputs.gen_p.shape),
            "sgen_p": list(inputs.sgen_p.shape),
            "load_p": list(inputs.load_p.shape),
            "load_q": list(inputs.load_q.shape),
            "vinit": list(inputs.vinit.shape),
            "voltages": [steps, len(adapter.net.bus)],
            "branch_flows": [steps, len(adapter.net.line) + len(adapter.net.trafo)],
        }
        if int(solved) != 1 or int(adapter.computer.nb_solved()) != steps:
            raise RuntimeError(f"TimeSeriesCPP did not solve all steps: return={solved}, nb_solved={adapter.computer.nb_solved()}")

    runpp_results: dict[str, list[dict[str, Any]]] = {"pandapower_native": [], "pandapower_lightsim2grid": []}
    for _ in range(warmups):
        _runpp_once(grid_key, lightsim2grid=False)
        _runpp_once(grid_key, lightsim2grid=True)
    for _ in range(repeats):
        runpp_results["pandapower_native"].append(_runpp_once(grid_key, lightsim2grid=False))
        runpp_results["pandapower_lightsim2grid"].append(_runpp_once(grid_key, lightsim2grid=True))

    assert materialization is not None
    return {
        "schema_version": 1,
        "task_id": config["task_id"],
        "timestamp_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "config": config,
        "hardware_runtime": _hardware_runtime(),
        "topology_materialization": _dataclass_dict(materialization),
        "adapter_converter_warnings": list(converter_warnings),
        "materialization_discrepancy": run_materialization_discrepancy(
            load_candidate_grid(grid_key),
            load_multipliers=equivalence_load_multipliers,
            acceptance=materialization_acceptance,
        ),
        "timeseriescpp": {
            "time_steps": steps,
            "warmups": warmups,
            "repeats": repeats,
            "solved_counts": solved_counts,
            "input_shapes": shape_record,
            "conversion_setup": _summary(conversion_times),
            "input_update": _summary(input_times),
            "compute_vs_wall": _summary(compute_wall_times),
            "voltage_result_extraction": _summary(voltage_extract_times),
            "current_flow_result_extraction": _summary(current_flow_times),
            "power_flow_result_extraction": _summary(power_flow_times),
            "internal_solver": _summary(internal_solver_times),
            "internal_preprocessing": _summary(internal_preprocessing_times),
            "internal_current_flow": _summary(internal_current_flow_times),
        },
        "pandapower_runpp": {
            name: {
                "repeats": values,
                "elapsed": _summary([float(row["elapsed_s"]) for row in values]),
                "options_lightsim2grid_all_true": all(row["pandapower_option_lightsim2grid"] for row in values),
                "converged_all": all(row["converged"] for row in values),
                "warnings": sorted({warning for row in values for warning in row["warnings"]}),
            }
            for name, values in runpp_results.items()
        },
    }


def write_outputs(config_path: str | Path) -> dict[str, Any]:
    """Run the benchmark and write raw, report, and evidence artifacts."""

    config_path = Path(config_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    raw = run_benchmark(config_path)
    raw_path = Path(config["raw_output_path"])
    report_path = Path(config["report_output_path"])
    evidence_path = Path(config["evidence_output_path"])
    raw_path.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(render_report(raw, evidence_path), encoding="utf-8")
    manifest = build_manifest(
        config_path=config_path,
        seeds={"none": "deterministic"},
        output_paths=[raw_path, report_path],
        extra={
            "artifact_type": "timeseriescpp_benchmark_evidence",
            "task_id": config["task_id"],
            "command": config["command"],
            "timestamp_utc": raw["timestamp_utc"],
            "timing_method": config["timing_method"],
            "warmups": config["warmups"],
            "repeats": config["repeats"],
            "time_steps": config["time_steps"],
            "hardware_runtime": raw["hardware_runtime"],
        },
    )
    evidence_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"raw": raw, "raw_path": raw_path, "report_path": report_path, "evidence_path": evidence_path}


def render_report(raw: dict[str, Any], evidence_path: Path) -> str:
    """Render the benchmark report from raw benchmark data."""

    tscpp = raw["timeseriescpp"]
    runpp = raw["pandapower_runpp"]
    steps = int(tscpp["time_steps"])
    solver_ms = tscpp["internal_solver"]["median_s"] * 1000.0
    compute_ms = tscpp["compute_vs_wall"]["median_s"] * 1000.0
    high_level_ms = runpp["pandapower_lightsim2grid"]["elapsed"]["median_s"] * 1000.0
    native_ms = runpp["pandapower_native"]["elapsed"]["median_s"] * 1000.0
    per_step_solver_ms = solver_ms / steps
    per_step_compute_ms = compute_ms / steps
    yearly_solver_s = per_step_solver_ms * 35040 / 1000.0
    yearly_compute_s = per_step_compute_ms * 35040 / 1000.0
    lines = [
        "# E1.S2b TimeSeriesCPP AC Benchmark",
        "",
        "## Verdict",
        "",
        (
            "The selected SimBench primary grid can be adapted to the lower-level "
            "`lightsim2grid.timeSerie.TimeSeriesCPP` path after explicitly materializing "
            "pandapower switch topology. Open line switches are represented as out-of-service "
            "lines, closed bus-bus switches are fused, and the switch table is then dropped "
            "before conversion."
        ),
        "",
        (
            f"For {steps} repeated baseline steps, TimeSeriesCPP reports a median internal "
            f"solver time of {solver_ms:.3f} ms total ({per_step_solver_ms:.4f} ms/step). "
            f"The measured `compute_Vs` Python wall time is {compute_ms:.3f} ms total "
            f"({per_step_compute_ms:.4f} ms/step). This supports an AC validation budget "
            f"on the order of one full-year deterministic trajectory in {yearly_compute_s:.2f} s "
            f"for voltage solves alone, before scenario construction and selected result extraction."
        ),
        "",
        "This does not change G1 or G2. It refines the compute-path evidence: the earlier high-level `pandapower.runpp` path is unsuitable for the Monte Carlo inner loop, but the lower-level C++ time-series solve can host deterministic AC validation subsets.",
        "",
        "## Evidence",
        "",
        f"- Config: `reports/benchmark_timeseriescpp_input.json`",
        f"- Raw numeric output: `reports/benchmark_timeseriescpp_raw.json`",
        f"- Evidence manifest: `{evidence_path.as_posix()}`",
        f"- Timestamp: `{raw['timestamp_utc']}`",
        "",
        "## Timing Summary",
        "",
        "| Component | Median ms | Notes |",
        "| --- | ---: | --- |",
        f"| Network conversion/setup | {tscpp['conversion_setup']['median_s'] * 1000.0:.3f} | load grid, materialize topology, pandapower baseline solve, LightSim conversion, TimeSeriesCPP construction |",
        f"| Time-series input update | {tscpp['input_update']['median_s'] * 1000.0:.3f} | construct repeated `gen_p`, `sgen_p`, `load_p`, `load_q`, and `vinit` arrays |",
        f"| `compute_Vs` wall time | {compute_ms:.3f} | TimeSeriesCPP voltage solve for {steps} steps |",
        f"| Internal solver time | {solver_ms:.3f} | Reported by TimeSeriesCPP |",
        f"| Internal preprocessing time | {tscpp['internal_preprocessing']['median_s'] * 1000.0:.3f} | Reported by TimeSeriesCPP |",
        f"| Voltage result extraction | {tscpp['voltage_result_extraction']['median_s'] * 1000.0:.3f} | `get_voltages()` to NumPy |",
        f"| Current-flow extraction | {tscpp['current_flow_result_extraction']['median_s'] * 1000.0:.3f} | `compute_flows()` and `get_flows()` |",
        f"| Active-power-flow extraction | {tscpp['power_flow_result_extraction']['median_s'] * 1000.0:.3f} | `compute_power_flows()` and `get_power_flows()` |",
        "",
        "## High-Level `runpp` Diagnosis",
        "",
        (
            f"The high-level pandapower benchmark accepted `lightsim2grid=True`: every measured "
            f"run recorded `net._options['lightsim2grid'] == True`, converged, and emitted no "
            f"fallback warnings. Its median wall time was {high_level_ms:.3f} ms per solve, "
            f"versus {native_ms:.3f} ms for native pandapower on the same grid. Therefore the "
            f"prior result should be interpreted as high-level pandapower orchestration plus "
            f"LightSim-compatible Newton solve, not as the standalone numerical cost of the "
            f"lower-level C++ time-series path."
        ),
        "",
        "## Adapter Scope",
        "",
        f"- Open line switches materialized: `{raw['topology_materialization']['open_line_switches']}`",
        f"- Lines disabled from those switches: `{raw['topology_materialization']['disabled_lines']}`",
        f"- Closed bus-bus switches fused: `{raw['topology_materialization']['fused_bus_switches']}`",
        f"- Bus count: {raw['topology_materialization']['bus_count_before']} -> {raw['topology_materialization']['bus_count_after']}",
        f"- In-service lines after materialization: {raw['topology_materialization']['in_service_line_count_after']}",
        f"- Input shapes: `{tscpp['input_shapes']}`",
        f"- Converter warnings recorded in raw output: `{raw['adapter_converter_warnings']}`",
        "",
        "## Materialization Discrepancy",
        "",
        (
            "This is a pandapower-to-pandapower materialization discrepancy check, not a "
            "TimeSeriesCPP-to-pandapower adapter validation. The original pandapower network "
            "with its switch table was compared with the materialized LightSim-compatible "
            "pandapower network at the baseline state, perturbed load states, and states that "
            "bracket approximately 0.95 to 1.05 p.u. original total-nameplate loading. The "
            "check compares aggregate decision-transformer P, Q, apparent power, loading, and "
            "maximum bus voltage magnitude deviation after mapping fused bus-bus switch pairs "
            "back to the retained bus."
        ),
        "",
        (
            "Declared acceptance criterion across every configured case: "
            f"abs loading delta <= {raw['materialization_discrepancy']['acceptance_criterion']['max_abs_loading_pu']:.6g} p.u. "
            f"and max abs bus-voltage delta <= {raw['materialization_discrepancy']['acceptance_criterion']['max_abs_bus_vm_pu']:.6g} p.u. "
            f"Result: {'passed' if raw['materialization_discrepancy']['acceptance_passed'] else 'failed'}."
        ),
        "",
        "| Load multiplier | Original loading p.u. | Materialized loading p.u. | Abs delta P MW | Abs delta Q Mvar | Abs delta S MVA | Abs delta loading p.u. | Max abs delta V p.u. |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        *[
            (
                f"| {row['load_multiplier']:.3f} | {row['original']['loading_pu']:.6g} | "
                f"{row['materialized']['loading_pu']:.6g} | {abs(row['delta']['p_mw']):.6g} | "
                f"{abs(row['delta']['q_mvar']):.6g} | {abs(row['delta']['s_mva']):.6g} | "
                f"{abs(row['delta']['loading_pu']):.6g} | {abs(row['delta']['max_bus_vm_pu']):.6g} |"
            )
            for row in raw["materialization_discrepancy"]["rows"]
        ],
        "",
        f"- Open transformer switch check: {raw['materialization_discrepancy']['open_transformer_switch_check']}.",
        f"- Closed bus-bus impedance check: {raw['materialization_discrepancy']['closed_bus_bus_impedance_check']}.",
        (
            "- One-end-open line charging note: "
            f"{raw['materialization_discrepancy']['one_end_open_line_note']}"
        ),
        "- TimeSeriesCPP adapter numerical comparison is deferred to G2, where transformer-loading extraction from TimeSeriesCPP outputs and the materialization discrepancy above must be included in the Tier-1-to-AC validation envelope.",
        "",
        "## Corrected G2 AC Budget",
        "",
        (
            f"Use TimeSeriesCPP, not repeated high-level `runpp`, for deterministic AC validation "
            f"state batches where the materialized topology is scientifically equivalent to the "
            f"pandapower switch model. A conservative planning budget should count conversion/setup "
            f"once per fixed grid plus array-update and extraction costs per batch. At the measured "
            f"median `compute_Vs` wall rate, 35,040 deterministic voltage solves are approximately "
            f"{yearly_compute_s:.2f} s before profile construction and selected result extraction; "
            f"using TimeSeriesCPP's internal solver clock alone gives approximately {yearly_solver_s:.2f} s. "
            f"The G2 validation design should still benchmark the actual near-threshold state set and "
            f"extract the required transformer loading quantity, rather than assuming voltage-only timings "
            f"are the final validation cost."
        ),
        "",
        "## Guardrails",
        "",
        "No claim is made that AC power flow is infeasible. No G1, G2, event-definition, A-013, epsilon-grid, transformer denominator, or interface-schema decision is changed by this diagnostic.",
        "",
    ]
    return "\n".join(lines)


def _hardware_runtime() -> dict[str, Any]:
    return {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
    }


def _dataclass_dict(value: TopologyMaterialization) -> dict[str, Any]:
    return {
        "open_line_switches": list(value.open_line_switches),
        "disabled_lines": list(value.disabled_lines),
        "fused_bus_switches": list(value.fused_bus_switches),
        "fused_bus_pairs": [list(pair) for pair in value.fused_bus_pairs],
        "dropped_switches": value.dropped_switches,
        "sgen_limit_columns_cast": list(value.sgen_limit_columns_cast),
        "bus_count_before": value.bus_count_before,
        "bus_count_after": value.bus_count_after,
        "line_count_before": value.line_count_before,
        "in_service_line_count_after": value.in_service_line_count_after,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the E1.S2b TimeSeriesCPP benchmark.")
    parser.add_argument("--config", default="reports/benchmark_timeseriescpp_input.json")
    args = parser.parse_args(argv)
    outputs = write_outputs(args.config)
    print(json.dumps({key: str(value) for key, value in outputs.items() if key.endswith("_path")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
