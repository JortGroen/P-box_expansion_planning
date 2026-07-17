# E1.S2 Laptop Benchmark Runner Reproduction

Status: ExperimentRunner reproduction of the historical high-level
`pandapower.runpp` benchmark. Timing values are expected to differ from
the retained custom evidence because this is a fresh wall-clock run.

## Evidence

- Runner config: `experiments/e1_s2_laptop_benchmark/runner_config.json`
- Standard manifest: `manifest.json` in this experiment directory

| grid | backend | median_ms | converged_all |
| --- | --- | --- | --- |
| simbench_semiurb | pandapower_native | 54.7812 | True |
| simbench_semiurb | lightsim2grid_runpp | 52.6871 | True |
| simbench_urban | pandapower_native | 72.382 | True |
| simbench_urban | lightsim2grid_runpp | 49.5992 | True |
| cigre_mv | pandapower_native | 44.4129 | True |
| cigre_mv | lightsim2grid_runpp | 45.9133 | True |

No claim is made that AC power flow is infeasible; this remains a
high-level orchestration benchmark only.
