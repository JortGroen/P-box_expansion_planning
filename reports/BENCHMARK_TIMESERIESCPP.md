# E1.S2b TimeSeriesCPP AC Benchmark

## Verdict

The selected SimBench primary grid can be adapted to the lower-level `lightsim2grid.timeSerie.TimeSeriesCPP` path after explicitly materializing pandapower switch topology. Open line switches are represented as out-of-service lines, closed bus-bus switches are fused, and the switch table is then dropped before conversion.

For 672 repeated baseline steps, TimeSeriesCPP reports a median internal solver time of 119.995 ms total (0.1786 ms/step). The measured `compute_Vs` Python wall time is 125.407 ms total (0.1866 ms/step). This supports an AC validation budget on the order of one full-year deterministic trajectory in 6.54 s for voltage solves alone, before scenario construction and selected result extraction.

This does not change G1 or G2. It refines the compute-path evidence: the earlier high-level `pandapower.runpp` path is unsuitable for the Monte Carlo inner loop, but the lower-level C++ time-series solve can host deterministic AC validation subsets.

## Evidence

- Config: `reports/benchmark_timeseriescpp_input.json`
- Raw numeric output: `reports/benchmark_timeseriescpp_raw.json`
- Evidence manifest: `reports/benchmark_timeseriescpp_evidence.json`
- Timestamp: `2026-07-14T11:14:37.881805Z`

## Timing Summary

| Component | Median ms | Notes |
| --- | ---: | --- |
| Network conversion/setup | 5282.800 | load grid, materialize topology, pandapower baseline solve, LightSim conversion, TimeSeriesCPP construction |
| Time-series input update | 0.859 | construct repeated `gen_p`, `sgen_p`, `load_p`, `load_q`, and `vinit` arrays |
| `compute_Vs` wall time | 125.407 | TimeSeriesCPP voltage solve for 672 steps |
| Internal solver time | 119.995 | Reported by TimeSeriesCPP |
| Internal preprocessing time | 1.755 | Reported by TimeSeriesCPP |
| Voltage result extraction | 0.023 | `get_voltages()` to NumPy |
| Current-flow extraction | 4.370 | `compute_flows()` and `get_flows()` |
| Active-power-flow extraction | 3.083 | `compute_power_flows()` and `get_power_flows()` |

## High-Level `runpp` Diagnosis

The high-level pandapower benchmark accepted `lightsim2grid=True`: every measured run recorded `net._options['lightsim2grid'] == True`, converged, and emitted no fallback warnings. Its median wall time was 103.823 ms per solve, versus 85.829 ms for native pandapower on the same grid. Therefore the prior result should be interpreted as high-level pandapower orchestration plus LightSim-compatible Newton solve, not as the standalone numerical cost of the lower-level C++ time-series path.

## Adapter Scope

- Open line switches materialized: `[233, 235, 237, 239, 241, 243, 245, 247]`
- Lines disabled from those switches: `[113, 114, 115, 116, 117, 118, 119, 120]`
- Closed bus-bus switches fused: `[0, 5]`
- Bus count: 117 -> 115
- In-service lines after materialization: 113
- Input shapes: `{'gen_p': [672, 1], 'sgen_p': [672, 121], 'load_p': [672, 115], 'load_q': [672, 115], 'vinit': [115], 'voltages': [672, 115], 'branch_flows': [672, 123]}`
- Converter warnings recorded in raw output: `['There were some Nan in the pp_net.sgen["min_p_mw"], they have been replaced by 0', 'There were some Nan in the pp_net.sgen["max_p_mw"], they have been replaced by 0', 'There were some Nan in the pp_net.sgen["min_q_mvar"], they have been replaced by 0', 'There were some Nan in the pp_net.sgen["max_q_mvar"], they have been replaced by 0', 'LightSim has not found any generators tagged as "slack bus" in the pandapower network.I will attempt to add some from the ext_grid.']`

## Corrected G2 AC Budget

Use TimeSeriesCPP, not repeated high-level `runpp`, for deterministic AC validation state batches where the materialized topology is scientifically equivalent to the pandapower switch model. A conservative planning budget should count conversion/setup once per fixed grid plus array-update and extraction costs per batch. At the measured median `compute_Vs` wall rate, 35,040 deterministic voltage solves are approximately 6.54 s before profile construction and selected result extraction; using TimeSeriesCPP's internal solver clock alone gives approximately 6.26 s. The G2 validation design should still benchmark the actual near-threshold state set and extract the required transformer loading quantity, rather than assuming voltage-only timings are the final validation cost.

## Guardrails

No claim is made that AC power flow is infeasible. No G1, G2, event-definition, A-013, epsilon-grid, transformer denominator, or interface-schema decision is changed by this diagnostic.
