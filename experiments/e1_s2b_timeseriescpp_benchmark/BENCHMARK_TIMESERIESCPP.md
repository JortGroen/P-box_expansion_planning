# E1.S2b TimeSeriesCPP AC Benchmark

## Verdict

The selected SimBench primary grid can be adapted to the lower-level `lightsim2grid.timeSerie.TimeSeriesCPP` path after explicitly materializing pandapower switch topology. Open line switches are represented as out-of-service lines, closed bus-bus switches are fused, and the switch table is then dropped before conversion.

For 672 repeated baseline steps, TimeSeriesCPP reports a median internal solver time of 157.821 ms total (0.2349 ms/step). The measured `compute_Vs` Python wall time is 165.658 ms total (0.2465 ms/step). This supports an AC validation budget on the order of one full-year deterministic trajectory in 8.64 s for voltage solves alone, before scenario construction and selected result extraction.

This does not change G1 or G2. It refines the compute-path evidence: the earlier high-level `pandapower.runpp` path is unsuitable for the Monte Carlo inner loop, but the lower-level C++ time-series solve can host deterministic AC validation subsets.

## Evidence

- Config: `reports/benchmark_timeseriescpp_input.json`
- Raw numeric output: `reports/benchmark_timeseriescpp_raw.json`
- Evidence manifest: `experiments/e1_s2b_timeseriescpp_benchmark/custom_evidence.json`
- Timestamp: `2026-07-17T10:18:49.733669Z`

## Timing Summary

| Component | Median ms | Notes |
| --- | ---: | --- |
| Network conversion/setup | 5096.992 | load grid, materialize topology, pandapower baseline solve, LightSim conversion, TimeSeriesCPP construction |
| Time-series input update | 1.113 | construct repeated `gen_p`, `sgen_p`, `load_p`, `load_q`, and `vinit` arrays |
| `compute_Vs` wall time | 165.658 | TimeSeriesCPP voltage solve for 672 steps |
| Internal solver time | 157.821 | Reported by TimeSeriesCPP |
| Internal preprocessing time | 3.420 | Reported by TimeSeriesCPP |
| Voltage result extraction | 0.027 | `get_voltages()` to NumPy |
| Current-flow extraction | 5.307 | `compute_flows()` and `get_flows()` |
| Active-power-flow extraction | 4.584 | `compute_power_flows()` and `get_power_flows()` |

## High-Level `runpp` Diagnosis

The high-level pandapower benchmark accepted `lightsim2grid=True`: every measured run recorded `net._options['lightsim2grid'] == True`, converged, and emitted no fallback warnings. Its median wall time was 68.093 ms per solve, versus 51.272 ms for native pandapower on the same grid. Therefore the prior result should be interpreted as high-level pandapower orchestration plus LightSim-compatible Newton solve, not as the standalone numerical cost of the lower-level C++ time-series path.

## Adapter Scope

- Open line switches materialized: `[233, 235, 237, 239, 241, 243, 245, 247]`
- Lines disabled from those switches: `[113, 114, 115, 116, 117, 118, 119, 120]`
- Closed bus-bus switches fused: `[0, 5]`
- Bus count: 117 -> 115
- In-service lines after materialization: 113
- Input shapes: `{'gen_p': [672, 1], 'sgen_p': [672, 121], 'load_p': [672, 115], 'load_q': [672, 115], 'vinit': [115], 'voltages': [672, 115], 'branch_flows': [672, 123]}`
- Converter warnings recorded in raw output: `['There were some Nan in the pp_net.sgen["min_p_mw"], they have been replaced by 0', 'There were some Nan in the pp_net.sgen["max_p_mw"], they have been replaced by 0', 'There were some Nan in the pp_net.sgen["min_q_mvar"], they have been replaced by 0', 'There were some Nan in the pp_net.sgen["max_q_mvar"], they have been replaced by 0', 'LightSim has not found any generators tagged as "slack bus" in the pandapower network.I will attempt to add some from the ext_grid.']`

## Materialization Discrepancy

This is a pandapower-to-pandapower materialization discrepancy check, not a TimeSeriesCPP-to-pandapower adapter validation. The original pandapower network with its switch table was compared with the materialized LightSim-compatible pandapower network at the baseline state, perturbed load states, and states that bracket approximately 0.95 to 1.05 p.u. original total-nameplate loading. The check compares aggregate decision-transformer P, Q, apparent power, loading, and maximum bus voltage magnitude deviation after mapping fused bus-bus switch pairs back to the retained bus.

Declared acceptance criterion across every configured case: abs loading delta <= 0.002 p.u. and max abs bus-voltage delta <= 0.001 p.u. Result: passed.

| Load multiplier | Original loading p.u. | Materialized loading p.u. | Abs delta P MW | Abs delta Q Mvar | Abs delta S MVA | Abs delta loading p.u. | Max abs delta V p.u. |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.800 | 0.115053 | 0.116075 | 0.000566061 | 0.0830245 | 0.0817753 | 0.00102219 | 0.000239125 |
| 1.000 | 0.178578 | 0.17944 | 0.000733958 | 0.0826894 | 0.0688833 | 0.000861042 | 0.000238851 |
| 1.200 | 0.258409 | 0.259155 | 0.0009171 | 0.0823942 | 0.0596928 | 0.00074616 | 0.000238645 |
| 1.500 | 0.389392 | 0.390053 | 0.00122432 | 0.0820369 | 0.0528877 | 0.000661096 | 0.000238492 |
| 2.650 | 0.957904 | 0.958529 | 0.00294438 | 0.0821176 | 0.0499757 | 0.000624696 | 0.000240861 |
| 2.700 | 0.985119 | 0.985746 | 0.00304887 | 0.0822019 | 0.0501844 | 0.000627304 | 0.00024114 |
| 2.750 | 1.01259 | 1.01322 | 0.00315704 | 0.0822962 | 0.0504127 | 0.000630158 | 0.000241443 |
| 2.800 | 1.04033 | 1.04096 | 0.0032691 | 0.0824013 | 0.0506607 | 0.000633259 | 0.00024177 |
| 2.850 | 1.06834 | 1.06897 | 0.00338532 | 0.0825179 | 0.0509286 | 0.000636608 | 0.000242123 |

- Open transformer switch check: passed: no open transformer switches were present before dropping the switch table.
- Closed bus-bus impedance check: passed: no closed bus-bus switches with nonzero z_ohm were present before fusing.
- One-end-open line charging note: Open line switches are represented by setting the corresponding whole line out of service. If pandapower retains any charging contribution from a one-end-open line under the original switch-table model, that contribution is removed in the materialized network; the numerical effect is captured by the Q, loading, and voltage deltas above.
- TimeSeriesCPP adapter numerical comparison is deferred to G2, where transformer-loading extraction from TimeSeriesCPP outputs and the materialization discrepancy above must be included in the Tier-1-to-AC validation envelope.

## Corrected G2 AC Budget

Use TimeSeriesCPP, not repeated high-level `runpp`, for deterministic AC validation state batches where the materialized topology is scientifically equivalent to the pandapower switch model. A conservative planning budget should count conversion/setup once per fixed grid plus array-update and extraction costs per batch. At the measured median `compute_Vs` wall rate, 35,040 deterministic voltage solves are approximately 8.64 s before profile construction and selected result extraction; using TimeSeriesCPP's internal solver clock alone gives approximately 8.23 s. The G2 validation design should still benchmark the actual near-threshold state set and extract the required transformer loading quantity, rather than assuming voltage-only timings are the final validation cost.

## Guardrails

No claim is made that AC power flow is infeasible. No G1, G2, event-definition, A-013, epsilon-grid, transformer denominator, or interface-schema decision is changed by this diagnostic.
