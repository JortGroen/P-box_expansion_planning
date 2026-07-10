# E1.S2 Laptop Micro-Benchmark

Status: complete for E1.S2 review.

## Scope

E1.S2 covers only:

- timing native pandapower AC `runpp` solves on the E1.S1 candidate grids
- timing pandapower `runpp(..., lightsim2grid=True)` on the same grids
- probing whether the installed `lightsim2grid` TimeSerie API is directly usable
- deriving a feasible AC-validation budget table for G1

No E1.S3 profile extraction, E1.S4 evaluator work, E3 harness work, or Monte
Carlo simulation was run.

## Evidence

Run input and evidence:

- `reports/benchmark_input.json` records the candidate grids, backends, warmups,
  repeats, and command description.
- `reports/benchmark_raw.json` records every timing replicate and convergence
  flag.
- `reports/benchmark_evidence.json` records the git commit, package versions,
  timestamp, benchmark input hash, and output checksums for this report and the
  raw benchmark output.

Environment:

| package | version |
| --- | --- |
| Python | 3.12.7 |
| pandapower | 3.5.3 |
| simbench | 1.6.2 |
| lightsim2grid | 0.13.1 |
| numpy | 2.3.5 |
| pandas | 2.3.3 |
| numba | 0.66.0 |

Protocol:

- 2 warmup solves per grid/backend
- 10 measured solves per grid/backend
- `pandapower.runpp(algorithm="nr", calculate_voltage_angles=True, init="auto")`
- backend switch only: `lightsim2grid=False` versus `lightsim2grid=True`
- all warmup and measured solves converged

## Timing Results

Times are milliseconds per deterministic AC solve through the pandapower
`runpp` API. These timings include pandapower-side overhead and should not be
read as raw C++ solver timings.

| grid | buses | backend | median ms | mean ms | min ms | max ms | converged |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| `simbench_semiurb` | 117 | pandapower native | 104.938 | 108.491 | 90.166 | 128.933 | yes |
| `simbench_semiurb` | 117 | lightsim2grid via `runpp` | 108.295 | 128.798 | 98.154 | 244.782 | yes |
| `simbench_urban` | 144 | pandapower native | 123.129 | 127.624 | 107.641 | 152.246 | yes |
| `simbench_urban` | 144 | lightsim2grid via `runpp` | 114.591 | 117.872 | 71.366 | 194.772 | yes |
| `cigre_mv` | 15 | pandapower native | 86.955 | 85.462 | 63.698 | 98.758 | yes |
| `cigre_mv` | 15 | lightsim2grid via `runpp` | 91.032 | 90.565 | 78.044 | 103.669 | yes |

Primary-grid median comparison:

| primary grid | native median ms | lightsim2grid `runpp` median ms | ratio |
| --- | ---: | ---: | ---: |
| `simbench_semiurb` | 104.938 | 108.295 | 1.032 |

For the primary grid, the pandapower `runpp` lightsim2grid backend was not
faster in this micro-benchmark. The likely practical point is overhead: the
installed high-level path still enters through pandapower for each solve.

## TimeSerie Probe

The installed `lightsim2grid.timeSerie` module imports and exposes
`TimeSeriesCPP`, but it does not expose the documented high-level `TimeSerie`
helper in this environment.

Observed public symbols:

```text
Computers, GRID2OP_INSTALLED, SolverType, TimeSeriesCPP, np, warnings
```

No direct TimeSerie benchmark was run in E1.S2, because using the raw C++ class
would require additional adapter work outside this story. This should be
revisited only if G1 requires a lower-level AC validation path.

## Budget Table For G1

The table below uses the primary-grid median timings:

- native pandapower: 104.938 ms/solve
- lightsim2grid via `runpp`: 108.295 ms/solve

The G0 primary analysis has `N=1e4`, five alpha levels, and two endpoints, so a
full-AC solve count would be `N * T * 5 * 2`. The G0 `1e-3` sensitivity has
`N=1e5`, three alpha levels, and two endpoints, so a full-AC solve count would
be `N * T * 3 * 2`. E1.S3 still has to determine the actual critical-window
length `T`; the rows below are routing examples only.

| case | AC solves | native wall time | lightsim2grid `runpp` wall time |
| --- | ---: | ---: | ---: |
| 1,000 validation solves | 1,000 | 1.75 min | 1.80 min |
| 10,000 validation solves | 10,000 | 17.49 min | 18.05 min |
| 100,000 validation solves | 100,000 | 2.91 h | 3.01 h |
| Primary full AC, `T=96` | 9,600,000 | 279.83 h | 288.79 h |
| Primary full AC, `T=672` | 67,200,000 | 1958.84 h | 2021.51 h |
| `1e-3` sensitivity full AC, `T=96` | 57,600,000 | 1679.00 h | 1732.73 h |

## G1 Recommendation

Full AC power flow inside the Monte Carlo loop is not laptop-feasible through
the current pandapower `runpp` interface. For G1, Agent A recommends preserving
the two-tier design:

- use Tier-1 summation as the MC inner loop once E1.S4/E3 provide it
- use AC power flow for deterministic checks and a bounded validation subset
- treat 10,000 to 100,000 AC validation solves as the practical laptop range
  unless a lower-level TimeSerie adapter is implemented and benchmarked

This is a compute recommendation only. It does not change G0's overload event,
P_crit handling, grid choice, or any scientific parameter.
