# EV-005 Finite Profile-Library Uncertainty Protocol

**Status:** Approved protocol. Numerical adequacy tolerance and the
within-realization replacement rule remain pending.

**Applies to:** EV-003 direct empirical bootstrapping, EV-004 fixed residential
charge-point distribution, ALEA-002 downstream evaluation, E2.S2, E2.S6, and
E3.S2a.

## 1. Purpose

The ElaadNL API supplies reproducible random annual profiles, but it does not
expose the underlying probability law or let the project request prescribed
quantiles or quadrature nodes. A frozen profile library is therefore an
empirical approximation of an unknown generator distribution. This protocol
keeps uncertainty caused by that finite approximation separate from uncertainty
caused by running a finite number of whole-system Monte Carlo realizations.

The protocol does not claim that a chosen library size is universally
sufficient. It tests whether the library is adequate for the downstream
transformer decision in this case study and extends the library when that test
fails.

## 2. Notation

| Symbol | Meaning |
|---|---|
| `M` | Number of unique complete annual profiles in the frozen source library |
| `K_r` | Number of home charge points assigned to grid node `r` in one scenario |
| `K` | Total home charge-point count, `sum_r K_r` |
| `N` | Number of complete whole-system Monte Carlo-year realizations |
| `D` | Number of profile selections across a run, `D = K * N` |
| `H` | Profiles reserved in independent held-out API batches |

`D = K * N` is a count of selections, not a required number of unique archived
profiles. Profiles may be reused between alternative Monte Carlo years. Whether
the same member may be selected more than once inside one realization remains
pending because it must reconcile the independence approximation, the ElaadNL
same-seed warning, and the largest E2.S6 cohort.

## 3. Fixed Residential Source Distribution

Per EV-004, the primary residential library contains complete annual,
uncontrolled ElaadNL charge-point profiles with:

- `profile_type = "cp"`;
- `location_type = "home"`;
- `cp_capacity_kw = 11`;
- `simulated_year = 2030`;
- one fixed 2025 source calendar, mapped downstream per ALEA-001;
- the generator's native home charge-point car/van mixture;
- distinct top-level API seeds across generation batches.

The same source distribution is reused for the 2030, 2033, and 2035 planning
layers. Those layers differ through externally sourced charge-point counts and
nodal allocation, not through the ElaadNL prognosis-year control.

The already generated 2030 home/car `ev` probe batch remains provenance and
diagnostic evidence. It is not silently relabeled as the EV-004 primary
charge-point library.

## 4. Candidate and Held-Out Generation

Generate the primary candidate incrementally in complete API batches. The
initial candidate target is `M = 1000`, normally ten batches of 100 profiles.
This is a feasible starting design, not an acceptance result.

Every batch records:

- request body and top-level API seed;
- returned member index and stable member ID `(batch_seed, member_index)`;
- retrieval timestamp, generator documentation version, and response config;
- raw and processed checksums;
- profile count, timestamp count, units, and validation results.

Before downstream adequacy evaluation, reserve `H = 200` additional profiles as
two distinct-seed batches of 100. Freeze the evaluation code, metrics, candidate
library, and acceptance tolerance before opening these held-out results. If the
held-out test fails, the held-out profiles may be added to the next candidate,
but a new untouched held-out batch must then be generated for the next test.

Until the API's multi-profile seed semantics are verified, treat an API batch as
the resampling and leave-out unit for library-uncertainty diagnostics. Never
split a batch across development and held-out sets.

## 5. Two Separate Uncertainty Calculations

### 5.1 Conditional Monte Carlo uncertainty

Hold one library fixed and run `N` complete ALEA-001 system realizations. The
resulting confidence interval quantifies finite-`N` uncertainty conditional on
that empirical library. `N` is selected from the final transformer statistic's
precision requirement; it is not set equal to `M`, `K`, or `M * K`.

### 5.2 Finite-library uncertainty

Hold the integrated model, scenario, Monte Carlo design, and CRN schedule fixed,
then change which independent ElaadNL batches define the empirical library.
Quantify the resulting variation in the downstream transformer statistic.

Use all of the following evidence:

1. nested complete-batch candidates up to `M = 1000`;
2. disjoint equal-size batch groups;
3. leave-one-batch-group-out comparisons;
4. the untouched `H` held-out profiles;
5. supplementary batch-level bootstrap intervals, clearly labelled as unable
   to reveal behavior absent from every generated member.

Common random numbers must keep non-EV aleatory inputs and the profile-selection
schedule comparable across candidate libraries. Monte Carlo error must be small
enough, or explicitly modeled, so it is not mistaken for library variation.

## 6. Downstream Adequacy Rule

No component-level mean, p95 curve, load-duration statistic, or ElaadNL UI
percentile can accept the library. E3.S2a propagates every candidate through
baseline, EV, HP, PV, adoption, flexibility, net-load construction, and the
decision-transformer evaluator.

The manifested report must show, at minimum:

- the provisional downstream transformer p95 used for convergence diagnostics;
- the signed overload-event measure active when the test runs;
- the finite-`N` confidence interval for each candidate library;
- between-library and held-out variation;
- whether any library change reverses the reinforcement decision;
- results by planning layer and by relevant alpha endpoint.

The numerical tolerance is predeclared before E3.S2a opens the held-out results.
It must be tied to transformer-result or reinforcement-decision stability and
must not be copied from unsupported generic percentage rules. Passing the test
accepts the candidate for this case and output domain; it is not a universal
claim that `M = 1000` is sufficient for other grids or rarer quantiles.

## 7. Replacement and Efficient Aggregation

For a fixed empirical library, independent sampling with replacement can be
implemented by drawing member indices or equivalent multinomial member counts
per node. Count-based aggregation is computationally equivalent to individual
selections and preserves complete annual member trajectories.

This implementation is not yet authorized for scientific runs. E2.S6 must first
report the range of `K_r` and `K`, and E2.S2 must reconcile repeated-member use
with the generator's same-seed warning. The signed follow-up chooses one of:

- with-replacement empirical bootstrap, with duplicate-member diagnostics;
- without-replacement sampling within a realization, requiring adequate `M` and
  documenting the induced finite-population dependence;
- a validated aggregate or fitted-sampler fallback if neither rule is adequate.

Profiles may always be reused between different Monte Carlo years because those
years represent alternative realizations rather than simultaneous charge
points.

## 8. Escalation Conditions

Stop and return to the PI if:

- E2.S6 produces a cohort too large for the approved replacement rule;
- held-out batches materially change the transformer result or decision;
- the candidate library misses a profile regime visible in held-out generation;
- a p99 or p99.9 target is activated without a new tail-adequacy design;
- the live generator version changes before all required batches are frozen;
- public charging is about to inherit the residential protocol without a
  separately approved public profile class.
