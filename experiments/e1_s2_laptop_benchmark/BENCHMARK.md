# E1.S2 Laptop Benchmark Runner Reproduction

Status: ExperimentRunner reproduction of the historical high-level
`pandapower.runpp` benchmark. Timing values are expected to differ from
the retained custom evidence because this is a fresh wall-clock run.

## Evidence

- Runner config: `experiments/e1_s2_laptop_benchmark/runner_config.json`
- Standard claim-source manifest: `experiments/e1_s2_laptop_benchmark/manifest.json`
- Retained/custom evidence: `experiments/e1_s2_laptop_benchmark/custom_evidence.json`

| grid | backend | median_ms | converged_all |
| --- | --- | --- | --- |
| simbench_semiurb | pandapower_native | 115.125 | True |
| simbench_semiurb | lightsim2grid_runpp | 118.595 | True |
| simbench_urban | pandapower_native | 95.9877 | True |
| simbench_urban | lightsim2grid_runpp | 112.993 | True |
| cigre_mv | pandapower_native | 88.4511 | True |
| cigre_mv | lightsim2grid_runpp | 79.7405 | True |

No claim is made that AC power flow is infeasible; this remains a
high-level orchestration benchmark only.
