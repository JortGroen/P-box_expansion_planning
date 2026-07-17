# E1.S2 Laptop Benchmark Runner Reproduction

Status: ExperimentRunner reproduction of the historical high-level
`pandapower.runpp` benchmark. Timing values are expected to differ from
the retained custom evidence because this is a fresh wall-clock run.

## Evidence

- Runner config: `experiments/e1_s2_laptop_benchmark/runner_config.json`
- Standard manifest: `manifest.json` in this experiment directory

| grid | backend | median_ms | converged_all |
| --- | --- | --- | --- |
| simbench_semiurb | pandapower_native | 108.49 | True |
| simbench_semiurb | lightsim2grid_runpp | 109.709 | True |
| simbench_urban | pandapower_native | 124.814 | True |
| simbench_urban | lightsim2grid_runpp | 102.411 | True |
| cigre_mv | pandapower_native | 73.5985 | True |
| cigre_mv | lightsim2grid_runpp | 83.2476 | True |

No claim is made that AC power flow is infeasible; this remains a
high-level orchestration benchmark only.
